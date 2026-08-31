import redis.asyncio as redis

from app.config import settings

# Single shared connection pool for the process. redis-py is safe to share across tasks.
_pool = redis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)
