"""README drift guard: every headline number quoted in the README must exist
in the regenerated committed metrics (like the demo-payload drift guard, but
for the narrative).

Parses the two headline tables (synthetic CI path + real UCI track) and the
cross-track rank claim straight out of README.md and compares them against
``reports/metrics.json`` / ``reports_uci/metrics.json``. If the pipeline is
re-run and a headline moves without the README following, this fails loudly.
"""

import json
import re
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]


def _load_metrics(path: Path) -> dict:
    # reports_uci/*.json are committed drift-guard anchors, so CI runs these
    # assertions against the tracked files. The skip stays as a safety net for
    # a genuinely absent file (e.g. a pruned worktree); the local full run
    # (after `cli all --data-source uci`) keeps the guard live against
    # regenerated files too.
    if not path.exists():
        pytest.skip(f"{path} missing — run the evaluate stage locally first")
    return json.loads(path.read_text())


def _readme_tables() -> dict[str, dict[str, list[str]]]:
    """Extract the per-run headline tables from the README by section heading."""
    text = (PROJECT / "README.md").read_text()
    tables: dict[str, dict[str, list[str]]] = {}
    markers = {
        "synthetic": "## Synthetic track",
        "uci": "## Headline results",
    }
    for key, heading in markers.items():
        section = text.split(heading, 1)[1]
        rows: dict[str, list[str]] = {}
        for line in section.splitlines():
            if not line.startswith("|"):
                if rows:
                    break  # table ended
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 5 or cells[0] in ("model", "run") or set(cells[0]) <= {"-", ":"}:
                continue
            run = cells[0].replace("**", "").split(" ")[0].replace("←", "")
            run = run.replace("best", "").strip()
            run = {"ETS": "ets"}.get(run, run)  # README display name -> metrics key
            rows[run] = cells[1:5]  # MAE, RMSE, MAPE, MASE
        tables[key] = rows
    return tables


def _quoted(value: str) -> float:
    return float(value.replace("**", "").replace("%", "").replace(",", ""))


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def test_uci_headline_table_matches_committed_metrics() -> None:
    metrics = _load_metrics(PROJECT / "reports_uci" / "metrics.json")
    table = _readme_tables()["uci"]
    assert table, "UCI headline table not found in README"
    for run, (mae, rmse, mape, mase) in table.items():
        assert run in metrics, f"README quotes unknown run {run!r}"
        block = metrics[run]
        assert _quoted(mae) == pytest.approx(block["mae"], abs=5e-4)
        assert _quoted(rmse) == pytest.approx(block["rmse"], abs=5e-4)
        assert _quoted(mape) == pytest.approx(block["mape_pct"], abs=5e-2)
        assert _quoted(mase) == pytest.approx(block["mase"], abs=5e-4)
    # the bolded "best" row in the README must be the protocol-recorded champion
    text = (PROJECT / "README.md").read_text()
    bold = re.findall(r"\*\*(\w+)[^*]*← best\*\*", text)
    assert bold and bold[0] == metrics["_meta"]["best_model"]


def test_synthetic_table_matches_committed_metrics() -> None:
    metrics = _load_metrics(PROJECT / "reports" / "metrics.json")
    table = _readme_tables()["synthetic"]
    assert table, "synthetic headline table not found in README"
    for run, (mae, rmse, mape, mase) in table.items():
        assert run in metrics, f"README quotes unknown run {run!r}"
        block = metrics[run]
        assert _quoted(mae) == pytest.approx(block["mae"], abs=5e-4)
        assert _quoted(rmse) == pytest.approx(block["rmse"], abs=5e-4)
        assert _quoted(mape) == pytest.approx(block["mape_pct"], abs=5e-2)
        assert _quoted(mase) == pytest.approx(block["mase"], abs=5e-4)


def test_cross_track_rank_claim_matches_metrics() -> None:
    """The README's 'synthetic overall champion ranks Nth on real data' must be live."""
    text = (PROJECT / "README.md").read_text()
    match = re.search(r"synthetic overall champion `(\w+)`\s+ranks\s+(\d+)(?:st|nd|rd|th)", text)
    assert match, "cross-track rank claim not found in README"
    claimed_model, claimed = match.group(1), int(match.group(2))
    uci = _load_metrics(PROJECT / "reports_uci" / "metrics.json")
    synth = _load_metrics(PROJECT / "reports" / "metrics.json")
    synth_champion = synth["_meta"]["best_model"]
    assert claimed_model == synth_champion, (
        f"README names {claimed_model}; metrics select {synth_champion}"
    )
    ranked = sorted(
        (k for k, v in uci.items() if isinstance(v, dict) and "mae" in v),
        key=lambda k: uci[k]["mae"],
    )
    actual = ranked.index(synth_champion) + 1
    assert actual == claimed, (
        f"README claims {synth_champion} ranks {claimed} on UCI; metrics say {_ordinal(actual)}"
    )
