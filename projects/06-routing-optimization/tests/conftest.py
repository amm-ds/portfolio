"""Shared fixtures and per-project pytest wiring (no network)."""

import importlib.util
from pathlib import Path

import pytest
from routing_optimization.parser import parse_solomon
from routing_optimization.schemas import Problem

_spec = importlib.util.spec_from_file_location(
    "routing_tiny_instance", Path(__file__).parent / "tiny_instance.py"
)
assert _spec is not None and _spec.loader is not None
_tiny_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tiny_module)
TINY_INSTANCE = _tiny_module.TINY_INSTANCE


@pytest.fixture
def tiny_text() -> str:
    """Raw Solomon-format text for the 5-customer TINY instance."""
    return TINY_INSTANCE


@pytest.fixture
def tiny_problem() -> Problem:
    """Parsed TINY problem (5 customers, capacity 60, depot horizon 500)."""
    return parse_solomon(TINY_INSTANCE, name="TINY")


def pytest_configure(config: pytest.Config) -> None:
    """Relax the monorepo-wide ``libs`` coverage gate for solo project runs.

    Root ``pyproject.toml`` measures ``--cov=libs`` with ``fail_under = 80``,
    which only full-suite runs (``make test``) can satisfy. When pytest is
    invoked with args covering exclusively this project — e.g. the per-project
    quality gate ``uv run pytest projects/06-routing-optimization -q`` — the
    libs gate is disabled; full-suite runs keep it.
    """
    args = [str(a) for a in config.args]
    if not args or not all("06-routing-optimization" in a for a in args):
        return
    cov = config.pluginmanager.get_plugin("_cov")
    if cov is not None:
        cov.options.cov_fail_under = 0
