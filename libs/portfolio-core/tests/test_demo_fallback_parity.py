"""Fallback-manifest parity: the TS fallback manifests must mirror demo.yaml.

Each demo view ships a hand-maintained ``FALLBACK_MANIFEST`` it renders when
the manifest endpoint is unreachable. These tests parse the real
``projects/*/demo.yaml`` through the portfolio_core loaders and assert the
fallback constant in the demo's TSX carries the same id, title, hook, hero,
scenarios, live endpoints and payload contract — so a manifest edit cannot
silently drift from what the demo shows while offline.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest
from portfolio_core.demo import load_demo, load_demo_index

REPO = Path(__file__).resolve().parents[3]
PROJECTS = REPO / "projects"

# Every demo with a workbench frontend — a new demo manifest must add its
# pair here, or the index assertion below fails loudly.
FALLBACK_PAIRS = [
    (
        "02-demand-forecasting",
        REPO / "apps/showcase-web/src/demos/forecast-workbench/ForecastWorkbench.tsx",
    ),
    (
        "05-ml-pipeline-churn",
        REPO / "apps/showcase-web/src/demos/churn-sandbox/ChurnSandbox.tsx",
    ),
]

_KEY_RE = re.compile(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:")
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")
_DECL_RE = re.compile(r"const FALLBACK_MANIFEST: DemoManifest = ")


def _extract_fallback(tsx_path: Path) -> dict[str, Any]:
    """Pull the FALLBACK_MANIFEST object literal out of a demo TSX and parse
    it as JSON (the literal is written JSON-compatibly: double-quoted
    strings, unquoted keys, trailing commas)."""
    text = tsx_path.read_text(encoding="utf-8")
    m = _DECL_RE.search(text)
    assert m is not None, f"no FALLBACK_MANIFEST literal in {tsx_path}"
    start = text.index("{", m.end())
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                literal = text[start : i + 1]
                break
    else:  # pragma: no cover - unbalanced braces would fail the TS build
        raise AssertionError(f"unbalanced FALLBACK_MANIFEST literal in {tsx_path}")
    as_json = _TRAILING_COMMA_RE.sub(r"\1", _KEY_RE.sub(r'\1"\2":', literal))
    parsed: dict[str, Any] = json.loads(as_json)
    return parsed


@pytest.mark.parametrize(("project", "tsx_path"), FALLBACK_PAIRS)
def test_fallback_manifest_mirrors_demo_yaml(project: str, tsx_path: Path) -> None:
    manifest = load_demo(PROJECTS / project)
    assert manifest is not None, f"{project}/demo.yaml not found"
    fallback = _extract_fallback(tsx_path)

    assert fallback["id"] == manifest.id
    assert fallback["title"] == manifest.title
    assert fallback["hook"] == manifest.hook
    assert fallback["project"] == manifest.project
    assert fallback["group"] == manifest.group
    assert fallback["skills"] == manifest.skills
    assert fallback["modes"] == manifest.modes

    hero = manifest.hero.model_dump() if manifest.hero is not None else None
    assert fallback["hero"] == hero

    assert fallback["scenarios"] == [
        {"name": s.name, "controls": s.controls} for s in manifest.scenarios
    ]
    assert fallback["live_endpoints"] == [e.model_dump() for e in manifest.live_endpoints]
    assert fallback["payload"] == (
        manifest.payload.model_dump() if manifest.payload is not None else None
    )


def test_every_demo_has_a_fallback_pair() -> None:
    """A new demo manifest without a frontend fallback pair must fail here."""
    served = {m.id for m in load_demo_index(PROJECTS)}
    paired = {load_demo(PROJECTS / p).id for p, _ in FALLBACK_PAIRS}  # type: ignore[union-attr]
    assert served == paired, (
        f"demos without a fallback parity pair: {served - paired}; "
        f"pairs without a manifest: {paired - served}"
    )
