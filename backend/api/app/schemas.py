import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import MatchStatus, Topic


# --- auth ---
class RegisterIn(BaseModel):
    username: str
    password: str
    email: str | None = None


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID
    username: str
    rating: int


# --- puzzles ---
class TestcaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    stdin: str
    expected_stdout: str
    ord: int


class PuzzleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    topic: Topic
    title: str
    prompt_md: str
    difficulty: int
    starter_code: str
    time_limit_s: int
    sample_testcases: list[TestcaseOut] = []


# --- matches ---
class SubmitIn(BaseModel):
    source: str
    language: str = "python"


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    verdict: str
    tests_passed: int
    tests_total: int
    runtime_ms: int
    created_at: datetime


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    topic: Topic
    status: MatchStatus
    player_a: uuid.UUID
    player_b: uuid.UUID
    winner_id: uuid.UUID | None
    puzzle: PuzzleOut
    started_at: datetime | None
    finished_at: datetime | None


# --- leaderboard ---
class LeaderboardEntry(BaseModel):
    rank: int
    user_id: uuid.UUID
    username: str
    rating: int
