import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db import SessionLocal, engine
from app.game import leaderboard
from app.matchmaking import matchmaker
from app.redis_client import get_redis
from app.routers import auth, matches, puzzles
from app.routers import leaderboard as leaderboard_router
from app.ws import hub
from app.ws.gateway import router as ws_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = asyncio.Event()

    async with SessionLocal() as session:
        count = await leaderboard.sync_from_db(session)
    logging.getLogger("api").info("leaderboard warmed with %d players", count)

    tasks = [
        asyncio.create_task(hub.run_subscriber(stop)),
        asyncio.create_task(matchmaker.run(stop)),
    ]
    try:
        yield
    finally:
        stop.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        await engine.dispose()


app = FastAPI(title="Code Royale API", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(puzzles.router)
app.include_router(leaderboard_router.router)
app.include_router(matches.router)
app.include_router(ws_router)


@app.get("/health")
async def health() -> dict:
    checks = {"api": "ok"}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:  # pragma: no cover
        checks["postgres"] = f"error: {exc}"
    try:
        await get_redis().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # pragma: no cover
        checks["redis"] = f"error: {exc}"

    checks["status"] = "ok" if all(v == "ok" for k, v in checks.items() if k != "status") else "degraded"
    return checks
