import pathlib
import sys

import pytest


def pytest_ignore_collect(
    collection_path: pathlib.Path, config: pytest.Config
) -> bool | None:
    del collection_path, config
    return not sys.platform.startswith("win")
