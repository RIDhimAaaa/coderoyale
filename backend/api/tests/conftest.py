"""Integration-test harness.

Uses a throwaway `coderoyale_test` Postgres database and Redis db 15 — both
expected to be reachable on localhost (``docker compose up postgres redis``).
The whole suite shares one event loop (see pytest.ini) so the async engine and
the Redis connection pool stay bound to a single loop.
"""
import os
import socket
from urllib.parse import urlsplit

import pytest
import pytest_asyncio

# Honour DATABASE_URL / REDIS_URL from the environment (docker compose sets them to
# the `postgres` / `redis` service hosts); fall back to localhost for bare `pytest`.
_pg_host = urlsplit(os.environ.get("DATABASE_URL", "")).hostname or "localhost"
_redis_host = urlsplit(os.environ.get("REDIS_URL", "")).hostname or "localhost"

BASE_PG = f"postgresql://coderoyale:coderoyale@{_pg_host}:5432"
TEST_DB = "coderoyale_test"

os.environ["DATABASE_URL"] = f"{BASE_PG.replace('postgresql://', 'postgresql+asyncpg://')}/{TEST_DB}"
os.environ["REDIS_URL"] = f"redis://{_redis_host}:6379/15"
os.environ.setdefault("JWT_SECRET", "test-secret")


def _infra_up() -> bool:
    for host, port in ((_pg_host, 5432), (_redis_host, 6379)):
        try:
            socket.create_connection((host, port), timeout=1).close()
        except OSError:
            return False
    return True


collect_ignore_glob = [] if _infra_up() else ["test_matchmaking.py", "test_engine.py"]


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _database():
    if not _infra_up():
        yield
        return

    import asyncpg

    sys_conn = await asyncpg.connect(f"{BASE_PG}/coderoyale")
    await sys_conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
    await sys_conn.execute(f'CREATE DATABASE "{TEST_DB}"')
    await sys_conn.close()

    from app import models  # noqa: F401
    from app.db import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_redis():
    if not _infra_up():
        yield
        return
    from app.redis_client import get_redis

    r = get_redis()
    await r.flushdb()
    yield


@pytest_asyncio.fixture
async def session():
    from app.db import SessionLocal

    async with SessionLocal() as s:
        yield s
        await s.rollback()
