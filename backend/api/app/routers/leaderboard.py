from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.game import leaderboard as lb
from app.models import User
from app.schemas import LeaderboardEntry

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("", response_model=list[LeaderboardEntry])
async def leaderboard(limit: int = 20, session: AsyncSession = Depends(get_session)):
    """Top players by rating.

    Served from the Redis sorted set (the same data pushed live over WebSocket).
    Falls back to Postgres, the source of truth, if the cache is cold.
    """
    rows = await lb.top(limit)
    if rows:
        return [LeaderboardEntry(**row) for row in rows]

    users = (
        await session.scalars(select(User).order_by(User.rating.desc()).limit(limit))
    ).all()
    return [
        LeaderboardEntry(rank=i + 1, user_id=u.id, username=u.username, rating=u.rating)
        for i, u in enumerate(users)
    ]
