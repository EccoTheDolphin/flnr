import re
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_path() -> Path:
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def test_files(repo_path: Path) -> Path:
    return repo_path / "tests"


@pytest.fixture(scope="session")
def sync_path(repo_path: Path) -> Path:
    return repo_path / "build" / "pytest"


@pytest.fixture(scope="session")
def worker_idx(worker_id: str) -> int:
    """Return index of current worker in pytest.

    This is a bit fragile, since it relies on specific pytest-xdist worker
    naming.
    """
    if worker_id == "master":
        return 0
    res = re.search(r"\d+$", worker_id)
    assert res is not None
    return int(res.group())
