"""Small helpers to build rows for integration tests."""
import uuid

from app.models import Match, MatchStatus, Puzzle, PuzzleTestcase, Topic, User


def make_user(username: str | None = None, rating: int = 1200) -> User:
    return User(
        username=username or f"u_{uuid.uuid4().hex[:8]}",
        password_hash="x",
        rating=rating,
    )


def make_puzzle(topic: Topic = Topic.dsa) -> Puzzle:
    p = Puzzle(topic=topic, title=f"P {uuid.uuid4().hex[:6]}", prompt_md="do it", difficulty=1)
    p.testcases.append(PuzzleTestcase(stdin="2 3\n", expected_stdout="5", is_sample=True, ord=0))
    p.testcases.append(PuzzleTestcase(stdin="10 20\n", expected_stdout="30", is_sample=False, ord=1))
    return p


def make_match(puzzle: Puzzle, a: User, b: User, topic: Topic = Topic.dsa) -> Match:
    from datetime import datetime, timezone

    return Match(
        topic=topic,
        puzzle_id=puzzle.id,
        player_a=a.id,
        player_b=b.id,
        status=MatchStatus.active,
        started_at=datetime.now(timezone.utc),
    )
