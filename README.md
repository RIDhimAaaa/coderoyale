# Code Royale

Real-time 1v1 competitive coding. Queue on a topic, get matched against another
player on the same **situational** puzzle (real-world scenarios, not Leetcode
trivia), and race to pass every hidden test. First correct submission wins,
Elo ratings move, and the leaderboard updates live.

> Backend: **Python · FastAPI · PostgreSQL · Redis · Docker** · Next.js frontend

---

## Quickstart

```bash
cp .env.example .env
docker compose up --build                 # postgres, redis, api, executor

# the Next.js client — either in Docker (needs npm-registry access at build):
docker compose --profile web up --build    # -> http://localhost:3000
# ...or straight from the source:
cd frontend && npm install && npm run dev   # -> http://localhost:3000
```

`api` runs migrations and seeds demo data on start. Then:

- API docs: http://localhost:8000/docs
- Web (with the `web` profile): http://localhost:3000
- Health: http://localhost:8000/health · http://localhost:8001/health

Demo players (password `password`): `alice`, `bob`, `carol`, `dave`, `erin`.
Open two browser tabs as two different players to start a match.

## Tests

```bash
docker compose exec api pytest          # 16 — Elo, matchmaking, game engine, puzzle data
docker compose exec executor pytest     # 9  — sandbox: TLE / MLE / no-network / fork-bomb / read-only fs / CE
```

## Verify end to end

1. Two tabs → sign in as `alice` and `bob` → both **Queue: DSA**.
2. Both land in the same match. `alice` submits a correct solution, `bob` a wrong one.
3. `alice` wins; both tabs get `match.over` with the rating change; the leaderboard
   page updates live.
4. Adversarial check — from `http://localhost:8000/docs` or curl, `POST /matches/{id}/submit`
   an infinite loop (→ TLE), a 1 GiB allocation (→ MLE), a `socket.connect` (blocked),
   a fork bomb (contained), a write to `/etc` (read-only fs). None touch the host.

---

## How the resume claims map to the code

| Claim | Where |
|---|---|
| Real-time 1v1 over WebSockets + Redis pub/sub, live leaderboard synced to Next.js | `backend/api/app/ws/`, `backend/api/app/game/leaderboard.py`, `frontend/lib/ws.ts` |
| Secure RCE microservice in Python/FastAPI, ephemeral Docker sandboxes | `backend/executor/` (`app/sandbox.py`, `runners/python/`) |
| Scalable PostgreSQL schema for contest metadata + rankings, indexed for load | `backend/api/app/models.py`, `backend/api/alembic/versions/` |

## Layout

```
backend/api/        FastAPI: auth, matchmaking, game engine, Elo, WS gateway, leaderboard
backend/executor/   FastAPI: the RCE sandbox — one throwaway container per submission
frontend/           Next.js: lobby, match view, live leaderboard
docs/               ARCHITECTURE.md (diagrams, security model, scaling) · INTERVIEW.md
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full picture.
