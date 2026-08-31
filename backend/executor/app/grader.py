"""Turn sandbox run outcomes into per-testcase verdicts and an aggregate."""
from __future__ import annotations

import asyncio

from app.config import settings
from app.models import ExecuteRequest, ExecuteResponse, TestResult, Verdict
from app.sandbox import RunOutcome, run_once

_STATUS_TO_VERDICT = {
    "tle": Verdict.TLE,
    "mle": Verdict.MLE,
    "ce": Verdict.CE,
    "re": Verdict.RE,
    "internal": Verdict.INTERNAL,
}

# Bound how many sandboxes run concurrently on this host.
_semaphore = asyncio.Semaphore(settings.max_concurrency)


def _normalize(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def _verdict_for(outcome: RunOutcome, expected: str) -> Verdict:
    if outcome.status == "ok":
        return Verdict.PASS if _normalize(outcome.stdout) == _normalize(expected) else Verdict.FAIL
    return _STATUS_TO_VERDICT.get(outcome.status, Verdict.INTERNAL)


async def grade(req: ExecuteRequest) -> ExecuteResponse:
    wall = req.wall_timeout_seconds or settings.sandbox_wall_timeout_seconds
    results: list[TestResult] = []
    max_runtime = 0

    # Fail fast: the first non-PASS testcase ends the run. Lower p99 latency for a
    # live match, and hidden-case details are never computed once the verdict is set.
    for i, tc in enumerate(req.testcases):
        async with _semaphore:
            outcome = await asyncio.to_thread(
                run_once, req.language.value, req.source, tc.stdin, wall
            )
        verdict = _verdict_for(outcome, tc.expected)
        max_runtime = max(max_runtime, outcome.duration_ms)
        results.append(
            TestResult(
                index=i,
                verdict=verdict,
                runtime_ms=outcome.duration_ms,
                stdout=outcome.stdout[:4000],
                stderr=outcome.stderr[:4000],
            )
        )
        if verdict is not Verdict.PASS:
            break

    passed = sum(1 for r in results if r.verdict is Verdict.PASS)
    total = len(req.testcases)
    aggregate = Verdict.PASS if passed == total else results[-1].verdict
    return ExecuteResponse(
        verdict=aggregate,
        tests_passed=passed,
        tests_total=total,
        runtime_ms=max_runtime,
        results=results,
    )
