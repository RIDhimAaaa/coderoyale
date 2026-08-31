"""Security-boundary tests: untrusted code must not be able to run long, eat the
host's memory, reach the network, fork-bomb, or write outside its tmpfs.

These spawn real containers, so they are slower and require a Docker daemon
(skipped automatically otherwise, see conftest.py).
"""
import pytest

from app.grader import grade
from app.models import ExecuteRequest, TestCase, Verdict
from app.sandbox import run_once


def _run(source: str, stdin: str = "", timeout: int = 5):
    return run_once("python", source, stdin, timeout)


def test_correct_program_passes():
    out = _run("print(sum(int(x) for x in input().split()))", stdin="2 3 4\n")
    assert out.status == "ok"
    assert out.stdout.strip() == "9"


def test_infinite_loop_is_killed_as_tle():
    out = _run("while True: pass", timeout=2)
    assert out.status == "tle"
    assert out.duration_ms < 6000  # killed, not hung forever


def test_memory_hog_is_oom_killed():
    out = _run("bytearray(1024 * 1024 * 1024)")  # 1 GiB > 256 MiB limit
    assert out.status == "mle"


def test_network_is_unreachable():
    out = _run(
        "import socket; socket.create_connection(('1.1.1.1', 53), timeout=3)"
    )
    assert out.status == "re"
    assert "unreachable" in out.stderr.lower() or "errno" in out.stderr.lower()


def test_fork_bomb_is_contained():
    # pids_limit stops the host from being starved; wall clock cleans it up.
    out = _run(
        "import os\nwhile True:\n    try: os.fork()\n    except OSError: pass",
        timeout=3,
    )
    assert out.status in {"tle", "re"}


def test_root_filesystem_is_read_only():
    out = _run("open('/etc/pwned', 'w').write('x')")
    assert out.status == "re"
    assert "read-only" in out.stderr.lower()


def test_box_tmpfs_is_writable():
    out = _run("open('/box/scratch', 'w').write('ok'); print('wrote')")
    assert out.status == "ok"
    assert out.stdout.strip() == "wrote"


def test_syntax_error_is_compile_error():
    out = _run("def broken(:\n    pass")
    assert out.status == "ce"


@pytest.mark.asyncio
async def test_grade_stops_at_first_failure():
    req = ExecuteRequest(
        source="print('always wrong')",
        testcases=[
            TestCase(stdin="", expected="always wrong"),   # PASS
            TestCase(stdin="", expected="something else"),  # FAIL -> stop
            TestCase(stdin="", expected="never checked"),
        ],
    )
    resp = await grade(req)
    assert resp.verdict is Verdict.FAIL
    assert resp.tests_passed == 1
    assert len(resp.results) == 2  # third case never ran
