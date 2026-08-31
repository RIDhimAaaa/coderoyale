"""Drive a full match end to end against a running stack.

    python -m scripts.e2e_smoke           # needs api on :8000 + a seeded db

Signs in two demo players, queues them, waits for the match, has one submit a
correct solution and the other a wrong one, and asserts the winner, the rating
change and that the live leaderboard push arrived on both sockets.
"""
import asyncio
import json

import httpx
import websockets

API = "http://localhost:8000"
WS = "ws://localhost:8000/ws"

CORRECT = """\
import sys
data = sys.stdin.read().split()
n = int(data[0]); ts = list(map(int, data[1:]))
acc, out = [], []
for t in ts:
    while acc and acc[0] <= t - 60:
        acc.pop(0)
    if len(acc) < n:
        acc.append(t); out.append("ALLOW")
    else:
        out.append("REJECT")
print(" ".join(out))
"""
WRONG = "print('nope')"


async def _login(client, username):
    r = await client.post(f"{API}/auth/login", json={"username": username, "password": "password"})
    r.raise_for_status()
    return r.json()


async def _recv(ws, want, timeout=20):
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout))
        if msg.get("type") == want:
            return msg


async def _play(name, token, source, out):
    async with websockets.connect(f"{WS}?token={token}") as ws:
        await _recv(ws, "connected")
        await ws.send(json.dumps({"type": "queue.join", "topic": "dsa"}))
        found = await _recv(ws, "match.found")
        match_id = found["data"]["match_id"]
        await ws.send(json.dumps({"type": "match.watch", "match_id": match_id}))
        await _recv(ws, "match.watching")

        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{API}/matches/{match_id}/submit",
                headers={"Authorization": f"Bearer {token}"},
                json={"source": source},
            )
            r.raise_for_status()

        over = await _recv(ws, "match.over", timeout=40)
        lb = await _recv(ws, "leaderboard.update", timeout=10)
        out[name] = {"match_id": match_id, "over": over["data"], "leaderboard": lb["data"]["top"][:3]}


async def main():
    async with httpx.AsyncClient() as c:
        alice = await _login(c, "alice")
        bob = await _login(c, "bob")

    out: dict = {}
    await asyncio.gather(
        _play("alice", alice["access_token"], CORRECT, out),
        _play("bob", bob["access_token"], WRONG, out),
    )

    winner = out["alice"]["over"]["winner_id"]
    assert winner == alice["user_id"], "alice should have won"
    ratings = out["alice"]["over"]["ratings"]
    assert ratings[alice["user_id"]]["new"] > ratings[alice["user_id"]]["old"]
    assert ratings[bob["user_id"]]["new"] < ratings[bob["user_id"]]["old"]
    assert out["bob"]["leaderboard"], "bob's socket should have received the leaderboard push"

    print(json.dumps(out, indent=2))
    print("\nOK — full match verified end to end.")


if __name__ == "__main__":
    asyncio.run(main())
