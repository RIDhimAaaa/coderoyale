"""Live leaderboard backed by a Redis sorted set.

Postgres (`users.rating` + `rating_history`) stays the source of truth; this is
the hot read path and the thing pushed over WebSocket after every match.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.redis_client import get_redis
from app.ws.hub import publish

ZSET = "leaderboard:global"
NAMES = "leaderboard:names"


async def sync_from_db(session: AsyncSession) -> int:
    """Rebuild the sorted set from Postgres. Run on startup / reconcile."""
    redis = get_redis()
    users = (await session.scalars(select(User))).all()
    if not users:
        return 0
    async with redis.pipeline(transaction=True) as pipe:
        pipe.delete(ZSET, NAMES)
        pipe.zadd(ZSET, {str(u.id): u.rating for u in users})
        pipe.hset(NAMES, mapping={str(u.id): u.username for u in users})
        await pipe.execute()
    return len(users)


async def apply_rating(user_id: str, username: str, rating: int) -> None:
    redis = get_redis()
    async with redis.pipeline(transaction=True) as pipe:
        pipe.zadd(ZSET, {str(user_id): rating})
        pipe.hset(NAMES, str(user_id), username)
        await pipe.execute()


async def top(limit: int = 20) -> list[dict]:
    redis = get_redis()
    rows = await redis.zrevrange(ZSET, 0, limit - 1, withscores=True)
    if not rows:
        return []
    names = await redis.hmget(NAMES, [uid for uid, _ in rows])
    return [
        {"rank": i + 1, "user_id": uid, "username": name or uid, "rating": int(score)}
        for i, ((uid, score), name) in enumerate(zip(rows, names))
    ]


async def broadcast_update() -> None:
    await publish("leaderboard", "global", "leaderboard.update", {"top": await top()})
