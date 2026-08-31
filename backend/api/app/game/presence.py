"""Reconnect grace tracking.

When a player's WebSocket drops mid-match we don't forfeit immediately — a flaky
connection shouldn't cost the match. We record when they went "gone"; the
matchmaker reaper forfeits only if they are still gone after the grace period.
"""
from __future__ import annotations

import time

from app.redis_client import get_redis

GRACE_SECONDS = 30


def _key(match_id: str, user_id: str) -> str:
    return f"presence:gone:{match_id}:{user_id}"


async def mark_gone(match_id: str, user_id: str) -> None:
    # value = epoch seconds of disconnect; TTL well past any match length.
    await get_redis().set(_key(match_id, user_id), str(int(time.time())), ex=3600)


async def mark_back(match_id: str, user_id: str) -> None:
    await get_redis().delete(_key(match_id, user_id))


async def gone_past_grace(match_id: str, user_ids: list[str]) -> str | None:
    """Return a user_id that has been disconnected longer than the grace period."""
    redis = get_redis()
    now = int(time.time())
    for uid, raw in zip(user_ids, await redis.mget([_key(match_id, u) for u in user_ids])):
        if raw is not None and now - int(raw) >= GRACE_SECONDS:
            return uid
    return None
