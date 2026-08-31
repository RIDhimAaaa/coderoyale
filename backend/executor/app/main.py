import logging
from contextlib import asynccontextmanager
from pathlib import Path

import docker
from fastapi import FastAPI

from app.grader import grade
from app.models import ExecuteRequest, ExecuteResponse
from app.sandbox import ensure_runner_images

log = logging.getLogger("executor")
_RUNNER_CONTEXT = str(Path(__file__).resolve().parent.parent / "runners")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_runner_images(_RUNNER_CONTEXT)
        log.info("runner images ready")
    except Exception as exc:  # pragma: no cover - infra path
        log.warning("could not pre-build runner images: %s", exc)
    yield


app = FastAPI(title="Code Royale Executor", version="0.2.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    checks = {"executor": "ok"}
    try:
        docker.from_env().ping()
        checks["docker"] = "ok"
    except Exception as exc:  # pragma: no cover
        checks["docker"] = f"error: {exc}"
    checks["status"] = "ok" if checks.get("docker") == "ok" else "degraded"
    return checks


@app.post("/execute", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest) -> ExecuteResponse:
    return await grade(req)
