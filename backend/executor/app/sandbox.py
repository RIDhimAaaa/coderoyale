"""The security boundary of Code Royale.

Every untrusted submission runs in its own throwaway container built from the
prebuilt runner image. Nothing is reused between runs. The hardening applied to
each container:

  network_mode=none        no egress, no lateral movement
  mem_limit + memswap      hard memory ceiling, swap disabled -> OOM => MLE
  pids_limit               fork-bomb containment
  nano_cpus                CPU share cap
  read_only rootfs         + a small tmpfs for /box and /tmp only
  cap_drop=ALL             no capabilities
  no-new-privileges        setuid binaries cannot escalate
  non-root user (uid 1000) baked into the image
  ulimit fsize/nofile      output-file and fd ceilings
  wall-clock timeout       enforced host-side, container killed => TLE
  log max-size             bounds disk from a runaway printer

Source is delivered via an env var (never parsed by a shell) and written to the
tmpfs by the image entrypoint; stdin is streamed over an attached socket.
"""
from __future__ import annotations

import socket as _socket
import tarfile  # noqa: F401  (kept for reference; archive delivery not used)
import threading
import time
from dataclasses import dataclass

import docker
from docker.types import LogConfig

from app.config import settings

RUNNER_IMAGES = {"python": settings.runner_image_python}


@dataclass
class RunOutcome:
    status: str  # ok | tle | mle | re | ce | internal
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int


def _client() -> docker.DockerClient:
    return docker.from_env()


def ensure_runner_images(build_context: str) -> None:
    """Build any missing runner image. Called once on startup."""
    client = _client()
    for lang, tag in RUNNER_IMAGES.items():
        try:
            client.images.get(tag)
        except docker.errors.ImageNotFound:
            client.images.build(
                path=f"{build_context}/{lang}", tag=tag, rm=True, forcerm=True
            )


def _truncate(raw: bytes) -> str:
    limit = settings.sandbox_output_limit_bytes
    clipped = raw[:limit]
    text = clipped.decode("utf-8", errors="replace")
    if len(raw) > limit:
        text += "\n...[output truncated]"
    return text


def _classify(exit_code: int, oom_killed: bool, stderr: str) -> str:
    if oom_killed:
        return "mle"
    if exit_code == 0:
        return "ok"
    # Python reports syntax/indentation problems before running a single line.
    if "SyntaxError" in stderr or "IndentationError" in stderr or "TabError" in stderr:
        return "ce"
    return "re"


def run_once(language: str, source: str, stdin: str, wall_timeout_s: int) -> RunOutcome:
    """Run one submission against one input. Blocking; call from a worker thread."""
    if language not in RUNNER_IMAGES:
        return RunOutcome("internal", None, "", f"unsupported language: {language}", 0)

    client = _client()
    mem = f"{settings.sandbox_memory_mb}m"
    container = client.containers.create(
        image=RUNNER_IMAGES[language],
        environment={"CODEROYALE_SOURCE": source},
        stdin_open=True,
        network_mode="none",
        mem_limit=mem,
        memswap_limit=mem,  # == mem_limit disables swap
        nano_cpus=int(settings.sandbox_cpus * 1_000_000_000),
        pids_limit=settings.sandbox_pids_limit,
        read_only=True,
        tmpfs={
            "/box": f"rw,size={settings.sandbox_tmpfs_mb}m,mode=1777",
            "/tmp": f"rw,size={settings.sandbox_tmpfs_mb}m,mode=1777",
        },
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        ulimits=[
            docker.types.Ulimit(name="fsize", soft=8_000_000, hard=8_000_000),
            docker.types.Ulimit(name="nofile", soft=256, hard=256),
        ],
        log_config=LogConfig(type="json-file", config={"max-size": "1m"}),
    )

    started = time.monotonic()
    oom_killed = False
    exit_code: int | None = None
    status = "internal"
    try:
        # Attach a stdin socket before start so nothing is missed.
        sock = container.attach_socket(params={"stdin": 1, "stream": 1})
        raw_sock: _socket.socket = getattr(sock, "_sock", sock)
        container.start()
        try:
            raw_sock.sendall(stdin.encode("utf-8"))
            raw_sock.shutdown(_socket.SHUT_WR)
        except OSError:
            pass  # program may have exited without reading stdin
        finally:
            raw_sock.close()

        result_box: dict = {}

        def _wait() -> None:
            try:
                result_box["res"] = container.wait()
            except Exception as exc:  # pragma: no cover
                result_box["err"] = exc

        waiter = threading.Thread(target=_wait, daemon=True)
        waiter.start()
        waiter.join(timeout=wall_timeout_s)

        if waiter.is_alive():
            status = "tle"
            try:
                container.kill()
            except docker.errors.APIError:
                pass
            waiter.join(timeout=5)
        else:
            res = result_box.get("res") or {}
            exit_code = res.get("StatusCode")
            try:
                state = client.api.inspect_container(container.id)["State"]
                oom_killed = bool(state.get("OOMKilled"))
            except docker.errors.APIError:  # pragma: no cover
                pass

        stdout = _truncate(container.logs(stdout=True, stderr=False))
        stderr = _truncate(container.logs(stdout=False, stderr=True))

        if status != "tle":
            status = _classify(exit_code or 0, oom_killed, stderr)

        return RunOutcome(
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    finally:
        try:
            container.remove(force=True)
        except docker.errors.APIError:  # pragma: no cover
            pass
