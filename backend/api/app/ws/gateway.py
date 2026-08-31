"""The single client WebSocket.

Auth is via `?token=<jwt>` because browsers cannot set headers on a WebSocket
handshake. Once connected, a socket is auto-subscribed to its own `user:<id>`
channel and to the live `leaderboard`; it subscribes to a `match:<id>` channel
when it sends `match.watch`.

Client -> server messages:
    {"type": "queue.join", "topic": "dsa"}
    {"type": "queue.leave"}
    {"type": "match.watch", "match_id": "<uuid>"}
    {"type": "ping"}
"""
from __future__ import annotations

import uuid

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db import SessionLocal
from app.game import engine, presence
from app.matchmaking import queue
from app.models import Match, Topic, User
from app.security import decode_token
from app.ws.hub import manager

router = APIRouter()


async def _authenticate(ws: WebSocket) -> User | None:
    token = ws.query_params.get("token")
    if not token:
        return None
    try:
        user_id = uuid.UUID(decode_token(token))
    except (jwt.PyJWTError, ValueError, KeyError):
        return None
    async with SessionLocal() as session:
        return await session.get(User, user_id)


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    user = await _authenticate(ws)
    if user is None:
        await ws.close(code=4401)  # unauthorized
        return

    await ws.accept()
    await manager.add(ws, f"user:{user.id}")
    await manager.add(ws, "leaderboard:global")
    await ws.send_json({"scope": "user", "id": str(user.id), "type": "connected", "data": {}})

    active_topic: Topic | None = None
    watched_match: uuid.UUID | None = None
    try:
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type")

            if kind == "ping":
                await ws.send_json({"type": "pong", "data": {}})

            elif kind == "queue.join":
                active_topic = Topic(msg["topic"])
                joined = await queue.join(active_topic, str(user.id))
                await ws.send_json(
                    {"type": "queue.joined", "data": {"topic": active_topic.value, "new": joined}}
                )

            elif kind == "queue.leave":
                await queue.leave_all(str(user.id))
                active_topic = None
                await ws.send_json({"type": "queue.left", "data": {}})

            elif kind == "match.watch":
                match_id = uuid.UUID(msg["match_id"])
                async with SessionLocal() as session:
                    match = await session.get(Match, match_id)
                    if match is None or user.id not in (match.player_a, match.player_b):
                        await ws.send_json({"type": "error", "data": {"detail": "not your match"}})
                        continue
                watched_match = match_id
                await manager.add(ws, f"match:{match_id}")
                await presence.mark_back(str(match_id), str(user.id))
                await ws.send_json({"type": "match.watching", "data": {"match_id": str(match_id)}})

    except WebSocketDisconnect:
        pass
    finally:
        await manager.remove(ws)
        if active_topic is not None:
            await queue.leave_all(str(user.id))
        if watched_match is not None:
            # Start the reconnect grace clock; the reaper forfeits if it runs out.
            await presence.mark_gone(str(watched_match), str(user.id))
