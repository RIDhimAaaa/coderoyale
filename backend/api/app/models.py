import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Topic(str, enum.Enum):
    dsa = "dsa"
    backend = "backend"
    frontend = "frontend"
    aiml = "aiml"
    cyber = "cyber"


class MatchStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    finished = "finished"
    abandoned = "abandoned"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    rating: Mapped[int] = mapped_column(Integer, default=1200, server_default="1200")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_users_rating_desc", rating.desc()),)


class Puzzle(Base):
    __tablename__ = "puzzles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    topic: Mapped[Topic] = mapped_column(Enum(Topic, name="topic"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    prompt_md: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)  # 1..3
    starter_code: Mapped[str] = mapped_column(Text, default="")
    time_limit_s: Mapped[int] = mapped_column(Integer, default=300)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    testcases: Mapped[list["PuzzleTestcase"]] = relationship(
        back_populates="puzzle", cascade="all, delete-orphan", order_by="PuzzleTestcase.ord"
    )


class PuzzleTestcase(Base):
    __tablename__ = "puzzle_testcases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    puzzle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("puzzles.id", ondelete="CASCADE"), index=True
    )
    stdin: Mapped[str] = mapped_column(Text, default="")
    expected_stdout: Mapped[str] = mapped_column(Text, default="")
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)  # shown to players
    ord: Mapped[int] = mapped_column(Integer, default=0)

    puzzle: Mapped[Puzzle] = relationship(back_populates="testcases")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    topic: Mapped[Topic] = mapped_column(Enum(Topic, name="topic"))
    puzzle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("puzzles.id"))
    player_a: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    player_b: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    winner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, name="match_status"), default=MatchStatus.pending, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    puzzle: Mapped[Puzzle] = relationship()


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    language: Mapped[str] = mapped_column(String(16), default="python")
    source: Mapped[str] = mapped_column(Text)
    verdict: Mapped[str] = mapped_column(String(16))
    tests_passed: Mapped[int] = mapped_column(Integer, default=0)
    tests_total: Mapped[int] = mapped_column(Integer, default=0)
    runtime_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RatingHistory(Base):
    __tablename__ = "rating_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    old_rating: Mapped[int] = mapped_column(Integer)
    new_rating: Mapped[int] = mapped_column(Integer)
    delta: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
