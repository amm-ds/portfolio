"""Generate the expanded fixture PDFs and the expanded references file.

Writes the seven new PDFs under ``fixtures/expanded/`` and builds
``evaluations/references-expanded-2026-11-19.json``: the committed cases
(copied verbatim, never edited in place) plus the seven expanded cases, under
a new dataset revision. The committed ``evaluations/references.json`` and the
original fixture files are untouched.

    uv run python scripts/generate_expanded_fixtures.py
"""

from __future__ import annotations

import json
from pathlib import Path

from document_intelligence.fixtures_expanded import EXPANDED_CASES, write_expanded_fixture_set

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = ROOT / "evaluations" / "references.json"
EXPANDED_REFERENCE_PATH = ROOT / "evaluations" / "references-expanded-2026-11-19.json"


def main() -> None:
    write_expanded_fixture_set(ROOT / "fixtures")
    committed = json.loads(REFERENCE_PATH.read_text())
    expanded = {
        **{k: v for k, v in committed.items() if k not in ("dataset_revision", "cases")},
        "dataset_revision": "2026-11-19.1-expanded",
        "description": (
            committed["description"]
            + " Expanded 2026-11-19 with seven additional synthetic documents "
            "(invoice, minutes, spec-sheet, manifest, protocol, memo, incident) "
            "in a new revision; the original seven cases are unchanged."
        ),
        "cases": [*committed["cases"], *EXPANDED_CASES],
    }
    EXPANDED_REFERENCE_PATH.write_text(json.dumps(expanded, indent=2) + "\n")
    print(f"wrote {len(EXPANDED_CASES)} expanded PDFs and {EXPANDED_REFERENCE_PATH.name}")


if __name__ == "__main__":
    main()
