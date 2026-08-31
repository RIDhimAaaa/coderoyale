"""Thin client for the RCE executor microservice.

The api never runs untrusted code itself — it POSTs the submission here and the
executor is the only component that talks to the Docker daemon.
"""
import httpx

from app.config import settings


class ExecutionResult:
    def __init__(self, payload: dict):
        self.verdict: str = payload["verdict"]
        self.tests_passed: int = payload["tests_passed"]
        self.tests_total: int = payload["tests_total"]
        self.runtime_ms: int = payload["runtime_ms"]
        self.results: list[dict] = payload.get("results", [])


async def execute_submission(
    source: str,
    testcases: list[dict],
    language: str = "python",
    wall_timeout_seconds: int | None = None,
) -> ExecutionResult:
    body = {
        "language": language,
        "source": source,
        "testcases": [
            {"stdin": tc["stdin"], "expected": tc["expected"]} for tc in testcases
        ],
        "wall_timeout_seconds": wall_timeout_seconds,
    }
    async with httpx.AsyncClient(base_url=settings.executor_url, timeout=120) as client:
        resp = await client.post("/execute", json=body)
        resp.raise_for_status()
        return ExecutionResult(resp.json())
