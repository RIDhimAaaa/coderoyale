"""Realtime fan-out.

Design: every api process keeps ONE Redis pub/sub subscriber on a single channel
(`royale`). Domain code (matchmaker, game engine) never touches WebSockets — it
just PUBLISHes an envelope. Each process's subscriber receives every envelope and
delivers it to whichever local sockets are interested. No sticky sessions, no
per-connection Redis subscriptions; add api replicas freely.

Envelope shape:
    {"scope": "user" | "match" | "leaderboard", "id": "<uuid or 'global'>",
     "type": "match.found", "data": {...}}
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict

from fastapi import WebSocket

from app.redis_client import get_redis

log = logging.getLogger("hub")
CHANNEL = "royale"


def envelope(scope: str, id: str, type: str, data: dict) -> dict:
    return {"scope": scope, "id": str(id), "type": type, "data": data}


async def publish(scope: str, id: str, type: str, data: dict) -> None:
    await get_redis().publish(CHANNEL, json.dumps(envelope(scope, id, type, data)))


class ConnectionManager:
    """Local (per-process) registry of live WebSockets and their interests."""

    def __init__(self) -> None:
        # subscription key -> set of sockets. Keys: "user:<id>", "match:<id>",
        # "leaderboard:global".
        self._subs: dict[str, set[WebSocket]] = defaultdict(set)
        self._keys: dict[WebSocket, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def add(self, ws: WebSocket, key: str) -> None:
        async with self._lock:
            self._subs[key].add(ws)
            self._keys[ws].add(key)

    async def remove(self, ws: WebSocket) -> None:
        async with self._lock:
            for key in self._keys.pop(ws, set()):
                self._subs[key].discard(ws)
                if not self._subs[key]:
                    self._subs.pop(key, None)

    async def deliver(self, key: str, payload: dict) -> None:
        for ws in list(self._subs.get(key, ())):
            try:
                await ws.send_json(payload)
            except Exception:  # pragma: no cover - client vanished mid-send
                await self.remove(ws)


manager = ConnectionManager()


async def run_subscriber(stop: asyncio.Event) -> None:
    """Background task: pump the Redis channel into local sockets until stopped."""
    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL)
    log.info("hub subscriber attached to %r", CHANNEL)
    try:
        while not stop.is_set():
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg is None:
                continue
            env = json.loads(msg["data"])
            await manager.deliver(f"{env['scope']}:{env['id']}", env)
    finally:
        await pubsub.unsubscribe(CHANNEL)
        await pubsub.aclose()
