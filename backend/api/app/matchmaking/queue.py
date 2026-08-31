"""Per-topic FIFO matchmaking queue, stored in Redis so any api replica can serve
a `queue.join` and any replica's matchmaker loop can pair players.
"""
from __future__ import annotations

from app.models import Topic
from app.redis_client import get_redis


def _key(topic: Topic) -> str:
    return f"mm:queue:{topic.value}"


def _members_key(topic: Topic) -> str:
    return f"mm:queued:{topic.value}"


async def join(topic: Topic, user_id: str) -> bool:
    """Return False if the user is already queued for this topic."""
    redis = get_redis()
    added = await redis.sadd(_members_key(topic), user_id)
    if not added:
        return False
    await redis.rpush(_key(topic), user_id)
    return True


async def leave(topic: Topic, user_id: str) -> None:
    redis = get_redis()
    await redis.srem(_members_key(topic), user_id)
    await redis.lrem(_key(topic), 0, user_id)


async def leave_all(user_id: str) -> None:
    for topic in Topic:
        await leave(topic, user_id)


async def pop_pair(topic: Topic) -> tuple[str, str] | None:
    """Atomically remove and return the two players at the head of the queue."""
    redis = get_redis()
    popped = await redis.lpop(_key(topic), 2)
    if not popped or len(popped) < 2:
        if popped:  # only one waiting — put them back at the head
            await redis.lpush(_key(topic), popped[0])
        return None
    a, b = popped[0], popped[1]
    if a == b:  # stale duplicate; drop it
        return None
    await redis.srem(_members_key(topic), a, b)
    return a, b
