import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Puzzle, Topic
from app.schemas import PuzzleOut, TestcaseOut

router = APIRouter(prefix="/puzzles", tags=["puzzles"])


def _to_out(puzzle: Puzzle) -> PuzzleOut:
    return PuzzleOut(
        id=puzzle.id,
        topic=puzzle.topic,
        title=puzzle.title,
        prompt_md=puzzle.prompt_md,
        difficulty=puzzle.difficulty,
        starter_code=puzzle.starter_code,
        time_limit_s=puzzle.time_limit_s,
        # Only sample testcases are ever exposed; the hidden ones decide the match.
        sample_testcases=[
            TestcaseOut.model_validate(tc) for tc in puzzle.testcases if tc.is_sample
        ],
    )


@router.get("", response_model=list[PuzzleOut])
async def list_puzzles(
    topic: Topic | None = None, session: AsyncSession = Depends(get_session)
):
    stmt = select(Puzzle).options(selectinload(Puzzle.testcases))
    if topic is not None:
        stmt = stmt.where(Puzzle.topic == topic)
    puzzles = (await session.scalars(stmt)).all()
    return [_to_out(p) for p in puzzles]


@router.get("/{puzzle_id}", response_model=PuzzleOut)
async def get_puzzle(puzzle_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    puzzle = await session.scalar(
        select(Puzzle).where(Puzzle.id == puzzle_id).options(selectinload(Puzzle.testcases))
    )
    if puzzle is None:
        raise HTTPException(404, "puzzle not found")
    return _to_out(puzzle)
