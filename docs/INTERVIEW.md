# Code Royale — Talking Points & Likely Questions

A crib sheet for walking an interviewer through the project. Pair it with
`ARCHITECTURE.md` (diagrams) and be ready to open the file named in each answer.

---

## 60-second pitch

> Code Royale is a real-time 1v1 competitive coding platform. Two players queue on
> a topic, get matched, and race on the same situational puzzle — not Leetcode-style
> trivia, more "here's a rate limiter, decide which requests it drops". The backend
> is three services: a FastAPI **api** that owns matchmaking, the game engine and a
> WebSocket gateway; a separate FastAPI **executor** that's the only thing allowed
> to run untrusted code, one throwaway Docker container per submission; and Redis
> for pub/sub fan-out, the matchmaking queue and a live leaderboard sorted set,
> with Postgres as the source of truth. First correct submission wins, Elo ratings
> move, and the leaderboard updates live over the same socket.

---

## Design decisions I can defend

### Why split `api` and `executor`?
Running arbitrary user code is the riskiest thing here. A separate service means
the Docker-socket privilege lives in one small place, a grading spike can't stall
the matchmaking/WebSocket path, and the two scale on different signals
(connections vs submission rate). — `docker-compose.yml`, `backend/executor/`

### How does the sandbox stop untrusted code?
One throwaway container per run, never reused. `network=none`, memory+swap capped
(OOM ⇒ MLE), `pids_limit` (fork bombs), CPU cap, read-only rootfs with a small
size-capped tmpfs for `/box` only, `cap_drop=ALL`, `no-new-privileges`, non-root
uid, `fsize`/`nofile` ulimits, host-side wall-clock timeout that kills the
container (⇒ TLE), output truncation, and an `asyncio.Semaphore` capping how many
sandboxes run at once. Code goes in as an **env var** (never a shell string),
stdin over an attached socket. — `backend/executor/app/sandbox.py`, proven in
`tests/test_sandbox.py`

### What's still weak about it, and what would you do?
Shared host kernel. Next step is gVisor / Kata / Firecracker microVMs, a seccomp
profile, and a dedicated executor host pool. I'd also move `/execute` behind a
queue so a submission spike can't overwhelm the daemon.

### How does the leaderboard stay consistent across clients?
Redis sorted set `leaderboard:global` is the hot read path and the thing pushed
over WebSocket. Postgres (`users.rating` + `rating_history`) is the source of
truth; the rating write for a match is one transaction, and Redis is updated
right after. `rating_history` alone can rebuild both caches. — `backend/api/app/game/leaderboard.py`, `engine.settle()`

### Why Redis pub/sub and not Kafka / a message broker?
The requirement is ephemeral fan-out to connected sockets — "tell everyone
watching match X". No durability or replay needed. Pub/sub is one line and
already in the stack. If we needed an event log (analytics, replays, audit)
that's a different tool and I'd add it alongside, not replace.

### How does matchmaking work with multiple api replicas?
Every replica runs the matchmaker loop. Pairing is an atomic Redis `LPOP key 2`,
so at most one replica pops any given pair — no leader election. — `backend/api/app/matchmaking/`

### WebSocket auth?
Browsers can't set headers on the WS handshake, so the JWT comes in as
`?token=`. The gateway validates it, loads the user, and the socket is
auto-subscribed to its `user:<id>` channel and the leaderboard. — `backend/api/app/ws/gateway.py`

### What happens if a player disconnects mid-match?
Not an instant forfeit — a flaky connection shouldn't cost the game. We record a
"gone" timestamp in Redis; the matchmaker reaper forfeits only if they're still
gone after a 30 s grace period. Reconnect (`match.watch`) clears it. — `backend/api/app/game/presence.py`

### Index choices?
`users(rating DESC)` for the leaderboard, `submissions(match_id)` for rendering a
match, `matches(status)` for the reaper's active-match scan, `matches(player_a/b)`
for history, `puzzles(topic)` for the random pick. Each maps to a real query — see
the table in `ARCHITECTURE.md §4`.

### How do you avoid N+1 on the match/puzzle load?
`selectinload(Match.puzzle).selectinload(Puzzle.testcases)` — one extra query for
the collection instead of one per row. — `backend/api/app/routers/matches.py`

### Puzzle correctness?
Every seed puzzle has a reference solver in `tests/test_puzzles_data.py` that must
reproduce every expected output, samples and hidden. Add a puzzle without a
solver and the suite fails.

---

## Questions to expect + short answers

| Question | Answer |
|---|---|
| "Race: both submit a correct solution near-simultaneously?" | `settle()` early-returns if `match.status != active`, and the status flip + winner write is in the settling transaction. The second one is a no-op. Truly concurrent settlements would need `SELECT … FOR UPDATE` on the match row — noted. |
| "Executor host runs out of memory/disk?" | Per-container caps + the concurrency semaphore bound total load. `--log max-size` bounds disk. Beyond that: queue + horizontal executor pool. |
| "What if Redis dies?" | Matchmaking and live pushes stop; REST + Postgres still serve. Leaderboard endpoint falls back to a Postgres query. On restart the sorted set is rebuilt from Postgres. |
| "Cheating — reading the hidden tests / the opponent's code?" | Only `is_sample` testcases are ever serialized to the client. `submission.result` events carry counts and verdict, never source. |
| "Why FastAPI?" | Async fits the workload (lots of concurrent WS + outbound calls to the executor), Pydantic gives typed request/response for free, and the ASGI WebSocket support is first-class. |
| "How would you test the realtime path in CI?" | The engine/matchmaking integration tests already run against real Redis+Postgres containers. A full ws test would drive two `websockets` clients through a match — done manually during the build (`README` §verify). |
| "Scale to a 5000-person university contest?" | `api` replicas behind an LB (stateless, no affinity needed), executor worker pool behind a queue, Redis for the hot paths, Postgres with PgBouncer + read replicas for history. The FIFO queue becomes rating-banded. |

---

## If asked "what would you build next"

1. Stronger sandbox isolation (gVisor / microVMs) + executor queue.
2. More languages — each is just another runner image against the same sandbox.
3. Rating-banded matchmaking with a widening band over wait time.
4. Spectate + match replay (needs the event log Kafka would give).
5. `SELECT … FOR UPDATE` on the match row to harden the concurrent-settle path.
