"""Idempotent seed: demo users + the situational puzzle bank.

Run inside the api container:
    docker compose exec api python -m scripts.seed
"""
import asyncio

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Puzzle, PuzzleTestcase, Topic, User
from app.security import hash_password
from scripts.puzzles_data import ALL_PUZZLES

DEMO_USERS = [
    ("alice", 1200),
    ("bob", 1200),
    ("carol", 1350),
    ("dave", 1100),
    ("erin", 1500),
]
DEMO_PASSWORD = "password"


async def seed_users(session) -> None:
    for username, rating in DEMO_USERS:
        exists = await session.scalar(select(User).where(User.username == username))
        if exists:
            continue
        session.add(
            User(
                username=username,
                email=f"{username}@coderoyale.dev",
                password_hash=hash_password(DEMO_PASSWORD),
                rating=rating,
            )
        )
    print(f"users: ensured {len(DEMO_USERS)} demo accounts (password '{DEMO_PASSWORD}')")


async def seed_puzzles(session) -> None:
    created = 0
    for spec in ALL_PUZZLES:
        exists = await session.scalar(select(Puzzle).where(Puzzle.title == spec["title"]))
        if exists:
            continue
        puzzle = Puzzle(
            topic=Topic(spec["topic"]),
            title=spec["title"],
            prompt_md=spec["prompt_md"],
            difficulty=spec["difficulty"],
            starter_code=spec["starter_code"],
            time_limit_s=spec["time_limit_s"],
        )
        for i, tc in enumerate(spec["testcases"]):
            puzzle.testcases.append(
                PuzzleTestcase(
                    stdin=tc["stdin"],
                    expected_stdout=tc["expected"],
                    is_sample=tc["is_sample"],
                    ord=i,
                )
            )
        session.add(puzzle)
        created += 1
    print(f"puzzles: created {created} new (of {len(ALL_PUZZLES)} in bank)")


async def main() -> None:
    async with SessionLocal() as session:
        await seed_users(session)
        await seed_puzzles(session)
        await session.commit()
    print("seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
