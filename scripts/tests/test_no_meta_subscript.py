"""Guard: project src never subscripts ``["_meta"]`` — that key is the stamper's.

``scripts/stamp_metrics_meta.py`` replaces the whole ``_meta`` object on every
stamp, so analysis stored under ``_meta`` is destroyed on restamp (07's
``p90_coverage`` and 10's ``cost_model`` were lost that way). Run-level
analysis lives under the top-level ``analysis`` key instead; ``_meta`` is
written only by the stamper (which lives in scripts/, not projects/). Lineage
reads via ``.get("_meta")`` do not match this pattern and stay allowed.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Any ["_meta"] / ['_meta'] subscript, tolerant of whitespace inside the brackets.
_META_SUBSCRIPT = re.compile(r"""\[\s*["']_meta["']\s*\]""")


def test_no_meta_subscript_in_project_src() -> None:
    offenders: list[str] = []
    for path in sorted(ROOT.glob("projects/*/src/**/*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _META_SUBSCRIPT.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()}")
    assert not offenders, (
        '["_meta"] subscripts under projects/*/src (use the top-level "analysis" '
        "key for run-level analysis; _meta belongs to scripts/stamp_metrics_meta.py):\n"
        + "\n".join(offenders)
    )
