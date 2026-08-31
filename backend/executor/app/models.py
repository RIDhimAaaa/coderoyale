from enum import Enum

from pydantic import BaseModel, Field


class Language(str, Enum):
    python = "python"


class Verdict(str, Enum):
    PASS = "PASS"          # output matched expected
    FAIL = "FAIL"          # ran fine, wrong output
    TLE = "TLE"            # wall-clock timeout
    MLE = "MLE"            # OOM-killed by the cgroup memory limit
    RE = "RE"              # non-zero exit / crash
    CE = "CE"              # compile / import-time error (syntax etc.)
    INTERNAL = "INTERNAL"  # sandbox itself failed


class TestCase(BaseModel):
    stdin: str = ""
    expected: str = ""


class ExecuteRequest(BaseModel):
    language: Language = Language.python
    source: str
    testcases: list[TestCase] = Field(default_factory=list)
    wall_timeout_seconds: int | None = None  # optional per-puzzle override


class TestResult(BaseModel):
    index: int
    verdict: Verdict
    runtime_ms: int
    stdout: str = ""
    stderr: str = ""


class ExecuteResponse(BaseModel):
    verdict: Verdict            # aggregate: PASS iff every testcase passed
    tests_passed: int
    tests_total: int
    runtime_ms: int             # max across testcases
    results: list[TestResult]
