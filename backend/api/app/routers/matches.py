import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.deps import current_user
from app.game import engine
from app.models import Match, Puzzle, Submission, User
from app.routers.puzzles import _to_out
from app.schemas import MatchOut, SubmissionOut, SubmitIn

router = APIRouter(prefix="/matches", tags=["matches"])

_WITH_PUZZLE = selectinload(Match.puzzle).selectinload(Puzzle.testcases)


async def _match_or_404(session: AsyncSession, match_id: uuid.UUID) -> Match:
    match = await session.scalar(
        select(Match).where(Match.id == match_id).options(_WITH_PUZZLE)
    )
    if match is None:
        raise HTTPException(404, "match not found")
    return match


def _to_match_out(match: Match) -> MatchOut:
    return MatchOut(
        id=match.id,
        topic=match.topic,
        status=match.status,
        player_a=match.player_a,
        player_b=match.player_b,
        winner_id=match.winner_id,
        puzzle=_to_out(match.puzzle),
        started_at=match.started_at,
        finished_at=match.finished_at,
    )


@router.get("/mine", response_model=list[MatchOut])
async def my_matches(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    matches = (
        await session.scalars(
            select(Match)
            .where(or_(Match.player_a == user.id, Match.player_b == user.id))
            .order_by(Match.created_at.desc())
            .limit(20)
            .options(_WITH_PUZZLE)
        )
    ).all()
    return [_to_match_out(m) for m in matches]


@router.get("/{match_id}", response_model=MatchOut)
async def get_match(
    match_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    match = await _match_or_404(session, match_id)
    if user.id not in (match.player_a, match.player_b):
        raise HTTPException(403, "not a participant")
    return _to_match_out(match)


@router.get("/{match_id}/submissions", response_model=list[SubmissionOut])
async def match_submissions(
    match_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    match = await _match_or_404(session, match_id)
    if user.id not in (match.player_a, match.player_b):
        raise HTTPException(403, "not a participant")
    rows = (
        await session.scalars(
            select(Submission)
            .where(Submission.match_id == match_id)
            .order_by(Submission.created_at.asc())
        )
    ).all()
    return list(rows)


@router.post("/{match_id}/submit", response_model=SubmissionOut)
async def submit(
    match_id: uuid.UUID,
    body: SubmitIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        submission = await engine.submit(
            session, match_id, user.id, body.source, body.language
        )
    except engine.MatchError as exc:
        raise HTTPException(409, str(exc))
    return submission
