"""Match lifecycle: submissions, win detection, settlement.

A match ends when either player's submission passes every testcase, or when the
clock runs out (settled by tests passed, then earliest submission; a tie is a
draw). Rating changes and their audit rows are written in one transaction.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.executor_client import execute_submission
from app.game.elo import updated_ratings
from app.game.leaderboard import apply_rating, broadcast_update
from app.models import Match, MatchStatus, Puzzle, RatingHistory, Submission, User
from app.ws.hub import publish


class MatchError(Exception):
    pass


async def _load_match(session: AsyncSession, match_id: uuid.UUID) -> Match:
    match = await session.get(Match, match_id)
    if match is None:
        raise MatchError("match not found")
    return match


async def submit(
    session: AsyncSession,
    match_id: uuid.UUID,
    user_id: uuid.UUID,
    source: str,
    language: str = "python",
) -> Submission:
    match = await _load_match(session, match_id)
    if user_id not in (match.player_a, match.player_b):
        raise MatchError("not a participant")
    if match.status != MatchStatus.active:
        raise MatchError(f"match is {match.status.value}")

    puzzle = await session.scalar(
        select(Puzzle).where(Puzzle.id == match.puzzle_id).options(selectinload(Puzzle.testcases))
    )
    testcases = [
        {"stdin": tc.stdin, "expected": tc.expected_stdout} for tc in puzzle.testcases
    ]

    result = await execute_submission(
        source, testcases, language=language, wall_timeout_seconds=None
    )

    submission = Submission(
        match_id=match_id,
        user_id=user_id,
        language=language,
        source=source,
        verdict=result.verdict,
        tests_passed=result.tests_passed,
        tests_total=result.tests_total,
        runtime_ms=result.runtime_ms,
    )
    session.add(submission)
    await session.flush()

    # Opponents see progress, never each other's code.
    await publish(
        "match",
        match_id,
        "submission.result",
        {
            "submission_id": str(submission.id),
            "user_id": str(user_id),
            "verdict": result.verdict,
            "tests_passed": result.tests_passed,
            "tests_total": result.tests_total,
            "runtime_ms": result.runtime_ms,
        },
    )

    if result.verdict == "PASS":
        await settle(session, match, winner_id=user_id)

    return submission


async def _best_submission(session: AsyncSession, match_id: uuid.UUID, user_id: uuid.UUID):
    return await session.scalar(
        select(Submission)
        .where(Submission.match_id == match_id, Submission.user_id == user_id)
        .order_by(Submission.tests_passed.desc(), Submission.created_at.asc())
        .limit(1)
    )


async def settle_on_timeout(session: AsyncSession, match_id: uuid.UUID) -> None:
    match = await _load_match(session, match_id)
    if match.status != MatchStatus.active:
        return
    a = await _best_submission(session, match_id, match.player_a)
    b = await _best_submission(session, match_id, match.player_b)

    def score(s: Submission | None) -> tuple:
        return (s.tests_passed if s else -1, -(s.created_at.timestamp() if s else 0))

    winner_id: uuid.UUID | None
    if score(a) > score(b):
        winner_id = match.player_a
    elif score(b) > score(a):
        winner_id = match.player_b
    else:
        winner_id = None  # draw
    await settle(session, match, winner_id=winner_id, reason="timeout")


async def abandon(session: AsyncSession, match_id: uuid.UUID, quitter_id: uuid.UUID) -> None:
    """A player disconnected and did not come back — the other player wins."""
    match = await _load_match(session, match_id)
    if match.status != MatchStatus.active:
        return
    other = match.player_b if quitter_id == match.player_a else match.player_a
    await settle(session, match, winner_id=other, reason="abandoned")


async def settle(
    session: AsyncSession,
    match: Match,
    winner_id: uuid.UUID | None,
    reason: str = "solved",
) -> None:
    if match.status != MatchStatus.active:
        return

    player_a = await session.get(User, match.player_a)
    player_b = await session.get(User, match.player_b)
    old_a, old_b = player_a.rating, player_b.rating

    score_a = 0.5 if winner_id is None else (1.0 if winner_id == match.player_a else 0.0)
    new_a, new_b = updated_ratings(old_a, old_b, score_a, k=settings.elo_k_factor)

    for user, old, new in ((player_a, old_a, new_a), (player_b, old_b, new_b)):
        session.add(
            RatingHistory(
                user_id=user.id,
                match_id=match.id,
                old_rating=old,
                new_rating=new,
                delta=new - old,
            )
        )
        user.rating = new

    match.status = MatchStatus.abandoned if reason == "abandoned" else MatchStatus.finished
    match.winner_id = winner_id
    match.finished_at = datetime.now(timezone.utc)
    await session.flush()

    # Redis leaderboard + push, after the DB transaction is durable-ish (flush).
    await apply_rating(str(player_a.id), player_a.username, new_a)
    await apply_rating(str(player_b.id), player_b.username, new_b)
    await publish(
        "match",
        match.id,
        "match.over",
        {
            "winner_id": str(winner_id) if winner_id else None,
            "reason": reason,
            "ratings": {
                str(player_a.id): {"old": old_a, "new": new_a},
                str(player_b.id): {"old": old_b, "new": new_b},
            },
        },
    )
    await broadcast_update()
