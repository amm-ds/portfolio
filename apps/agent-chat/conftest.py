"""Collection guard for foreign pytest runs.

This package is a standalone uv project with its own venv (see the empty
``[tool.uv.workspace]`` in pyproject.toml); the repo-root suite drives pytest
with the root config and venv, where ``agent_chat`` is not importable. When
the rootdir is not this directory, skip everything below so the root suite
never tries to collect these tests. Running pytest from this directory is
unaffected (rootdir == this directory).
"""

from pathlib import Path

import pytest

_PACKAGE_ROOT = Path(__file__).resolve().parent


def pytest_ignore_collect(collection_path: pytest.Dir, config: pytest.Config) -> bool:
    """Skip this tree when a foreign suite (rootdir elsewhere) collects it."""
    return Path(str(config.rootpath)) != _PACKAGE_ROOT
