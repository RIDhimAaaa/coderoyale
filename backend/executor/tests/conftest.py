import pytest

docker = pytest.importorskip("docker")


def _docker_available() -> bool:
    try:
        docker.from_env().ping()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def _require_docker():
    if not _docker_available():
        pytest.skip("docker daemon not reachable", allow_module_level=True)


@pytest.fixture(scope="session", autouse=True)
def _runner_image(_require_docker):
    """Build the python runner image once for the whole test session."""
    from pathlib import Path

    from app.sandbox import ensure_runner_images

    ensure_runner_images(str(Path(__file__).resolve().parent.parent / "runners"))
