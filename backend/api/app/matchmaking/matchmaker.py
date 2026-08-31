"""Background loop (one per api process, coordinated through Redis):

  * pair queued players into matches
  * finish matches whose clock has expired

Pairing pops happen atomically in Redis (see queue.pop_pair), so running the loop
on several replicas is safe — at most one replica pops any given pair.
"""
from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.game import engine, presence
from app.matchmaking import queue
from app.models import Match, MatchStatus, Puzzle, Topic
from app.ws.hub import publish

log = logging.getLogger("matchmaker")


async def _random_puzzle(session, topic: Topic) -> Puzzle | None:
    ids = (await session.scalars(select(Puzzle.id).where(Puzzle.topic == topic))).all()
    if not ids:
        return None
    return await session.get(Puzzle, random.choice(ids))


async def _create_match(session, topic: Topic, a: str, b: str) -> Match | None:
    puzzle = await _random_puzzle(session, topic)
    if puzzle is None:
        log.warning("no puzzle for topic %s; re-queueing players", topic.value)
        await queue.join(topic, a)
        await queue.join(topic, b)
        return None
    match = Match(
        topic=topic,
        puzzle_id=puzzle.id,
        player_a=a,
        player_b=b,
        status=MatchStatus.active,
        started_at=datetime.now(timezone.utc),
    )
    session.add(match)
    await session.flush()
    return match


async def _pair_once() -> None:
    for topic in Topic:
        while True:
            pair = await queue.pop_pair(topic)
            if pair is None:
                break
            a, b = pair
            async with SessionLocal() as session:
                match = await _create_match(session, topic, a, b)
                await session.commit()
            if match is None:
                break  # no puzzle for this topic; players were re-queued, try next tick
            payload = {
                "match_id": str(match.id),
                "topic": topic.value,
                "opponent": {a: b, b: a},
                "duration_seconds": settings.match_duration_seconds,
            }
            for uid in (a, b):
                await publish("user", uid, "match.found", {**payload, "you": uid})
            log.info("match %s: %s vs %s (%s)", match.id, a, b, topic.value)


async def _reap_expired() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.match_duration_seconds)
    async with SessionLocal() as session:
        active = (
            await session.scalars(select(Match).where(Match.status == MatchStatus.active))
        ).all()
        for match in active:
            if match.started_at and match.started_at < cutoff:
                await engine.settle_on_timeout(session, match.id)
                continue
            gone = await presence.gone_past_grace(
                str(match.id), [str(match.player_a), str(match.player_b)]
            )
            if gone is not None:
                await engine.abandon(session, match.id, uuid.UUID(gone))
        await session.commit()


async def run(stop: asyncio.Event) -> None:
    log.info("matchmaker loop started")
    while not stop.is_set():
        try:
            await _pair_once()
            await _reap_expired()
        except Exception:  # pragma: no cover - keep the loop alive
            log.exception("matchmaker iteration failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.matchmaker_poll_seconds)
        except asyncio.TimeoutError:
            pass
