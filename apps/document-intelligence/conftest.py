"""Collection guard for foreign pytest runs.

This standalone uv project has its own environment and gates. The repository
root suite must not collect its tests with unrelated dependencies; running
pytest from this directory remains unaffected.
"""

from pathlib import Path

import pytest

_PACKAGE_ROOT = Path(__file__).resolve().parent


def pytest_ignore_collect(collection_path: pytest.Dir, config: pytest.Config) -> bool:
    """Skip this tree when a foreign suite (rootdir elsewhere) collects it."""
    return Path(str(config.rootpath)) != _PACKAGE_ROOT
