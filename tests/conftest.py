from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def test_resources() -> Path:
    """Return path to the resources directory."""
    return Path(__file__).parent / "resources"
