import pytest
from sqlalchemy import select

from app.matchmaking import matchmaker, queue
from app.models import Match, MatchStatus, Topic
from tests.factories import make_puzzle, make_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_pop_pair_needs_two_players():
    await queue.join(Topic.backend, "solo")
    assert await queue.pop_pair(Topic.backend) is None
    # the lone player is still queued
    assert await queue.pop_pair(Topic.backend) is None
    await queue.join(Topic.backend, "second")
    assert await queue.pop_pair(Topic.backend) == ("solo", "second")


async def test_join_is_idempotent_per_user():
    assert await queue.join(Topic.dsa, "dupe") is True
    assert await queue.join(Topic.dsa, "dupe") is False


async def test_matchmaker_pairs_and_creates_active_match(session):
    puzzle = make_puzzle(Topic.dsa)
    a, b = make_user("mm_a"), make_user("mm_b")
    session.add_all([puzzle, a, b])
    await session.commit()

    await queue.join(Topic.dsa, str(a.id))
    await queue.join(Topic.dsa, str(b.id))

    await matchmaker._pair_once()

    match = await session.scalar(select(Match).where(Match.player_a.in_([a.id, b.id])))
    assert match is not None
    assert match.status == MatchStatus.active
    assert {match.player_a, match.player_b} == {a.id, b.id}
    assert match.puzzle_id == puzzle.id
