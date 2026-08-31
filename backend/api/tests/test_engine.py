import pytest
from sqlalchemy import select

from app.executor_client import ExecutionResult
from app.game import engine
from app.models import MatchStatus, RatingHistory
from tests.factories import make_match, make_puzzle, make_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _result(verdict: str, passed: int, total: int = 2) -> ExecutionResult:
    return ExecutionResult(
        {"verdict": verdict, "tests_passed": passed, "tests_total": total, "runtime_ms": 12, "results": []}
    )


def _stub_executor(monkeypatch, *outcomes: ExecutionResult):
    """Make engine.execute_submission return the given outcomes in order."""
    it = iter(outcomes)

    async def fake(*_args, **_kwargs):
        return next(it)

    monkeypatch.setattr(engine, "execute_submission", fake)


async def _setup(session, rating_a=1200, rating_b=1200):
    puzzle = make_puzzle()
    a, b = make_user("eng_a", rating_a), make_user("eng_b", rating_b)
    session.add_all([puzzle, a, b])
    await session.flush()
    match = make_match(puzzle, a, b)
    session.add(match)
    await session.flush()
    return match, a, b


async def test_passing_submission_wins_and_moves_rating_zero_sum(session, monkeypatch):
    match, a, b = await _setup(session)
    _stub_executor(monkeypatch, _result("PASS", 2, 2))

    await engine.submit(session, match.id, a.id, "print('x')")
    await session.flush()
    for obj in (match, a, b):
        await session.refresh(obj)

    assert match.status == MatchStatus.finished
    assert match.winner_id == a.id
    assert a.rating > 1200 > b.rating
    assert a.rating - 1200 == 1200 - b.rating

    history = (
        await session.scalars(select(RatingHistory).where(RatingHistory.match_id == match.id))
    ).all()
    assert {h.user_id for h in history} == {a.id, b.id}


async def test_failing_submission_keeps_match_active(session, monkeypatch):
    match, a, _ = await _setup(session)
    _stub_executor(monkeypatch, _result("FAIL", 1, 2))

    await engine.submit(session, match.id, a.id, "print('nope')")
    await session.refresh(match)
    assert match.status == MatchStatus.active
    assert match.winner_id is None


async def test_timeout_awards_win_to_more_tests_passed(session, monkeypatch):
    match, a, b = await _setup(session)
    _stub_executor(monkeypatch, _result("FAIL", 1, 2), _result("FAIL", 0, 2))

    await engine.submit(session, match.id, a.id, "a")
    await engine.submit(session, match.id, b.id, "b")
    await session.flush()

    await engine.settle_on_timeout(session, match.id)
    await session.refresh(match)
    assert match.status == MatchStatus.finished
    assert match.winner_id == a.id


async def test_non_participant_cannot_submit(session, monkeypatch):
    match, _, _ = await _setup(session)
    outsider = make_user("outsider")
    session.add(outsider)
    await session.flush()
    _stub_executor(monkeypatch, _result("PASS", 2, 2))

    with pytest.raises(engine.MatchError):
        await engine.submit(session, match.id, outsider.id, "print('x')")
