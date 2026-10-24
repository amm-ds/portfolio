"""README drift guard: every headline number quoted in the README must exist
in the regenerated committed metrics (like the demo-payload drift guard, but
for the narrative).

Parses the two headline tables (synthetic CI path + real UCI track) and the
cross-track rank claim straight out of README.md and compares them against
``reports/metrics.json`` / ``reports_uci/metrics.json``. If the pipeline is
re-run and a headline moves without the README following, this fails loudly.
The multi-step section (protocol ``direct_multihorizon_v1``) is guarded the
same way: the class scoreboard, the horizon-growth tables and the routing /
coverage / decision numbers are pinned against the committed ``_multistep``
block — stale claims fail here.
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
        "uci": "## Nowcast track",
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


# ---------------------------------------------------------------------------
# Multi-step track (protocol direct_multihorizon_v1) drift guards
# ---------------------------------------------------------------------------


def _multistep() -> dict:
    return _load_metrics(PROJECT / "reports_uci" / "metrics.json")["_multistep"]


def _multistep_section() -> str:
    text = (PROJECT / "README.md").read_text()
    assert "## Multi-step headline" in text, "multi-step section missing from README"
    return text.split("## Multi-step headline", 1)[1].split("## Synthetic track", 1)[0]


def _num(value: str) -> float:
    """README number -> float (handles unicode minus, %, thousands, bold)."""
    return float(
        value.replace("**", "").replace("%", "").replace(",", "").replace("\u2212", "-").strip()
    )


def _h_row(section: str, row_label: str) -> dict[str, float]:
    """Parse a '| h | 1 | 2 | ... |' keyed table row into {h: value}."""
    for line in section.splitlines():
        stripped = line.lstrip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip().strip("|").split("|")]
        if cells[0].replace("**", "") != row_label:
            continue
        hs = _header_horizons(section)
        return {h: _num(v) for h, v in zip(hs, cells[1:], strict=True)}
    raise AssertionError(f"row {row_label!r} not found in the h-keyed table")


def _header_horizons(section: str) -> list[str]:
    for line in section.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("| h |"):
            return [c.strip() for c in stripped.strip().strip("|").split("|")][1:]
    raise AssertionError("h-keyed table header not found")


def test_multistep_class_scoreboard_matches_committed_metrics() -> None:
    """The champion-vs-floor table per class at h=7/h=14 must be live."""
    ms = _multistep()
    section = _multistep_section()
    scoreboard = {}
    for line in section.splitlines():
        if not line.startswith("|") or "champ MAE" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 8 or cells[0] in ("class",) or set(cells[0]) <= {"-", ":"}:
            continue
        cls = cells[0].replace("**", "")
        if cls not in ms["headline_per_class"]:
            continue
        scoreboard[cls] = cells
    assert set(scoreboard) == set(ms["headline_per_class"]), "scoreboard classes mismatch"
    for cls, cells in scoreboard.items():
        entry = ms["headline_per_class"][cls]
        assert _num(cells[1]) == entry["n_series"]
        for h_key, champ_col, floor_col, ci_col in (
            ("h7", 2, 3, 4),
            ("h14", 5, 6, 7),
        ):
            if h_key not in entry:
                continue
            head = entry[h_key]
            assert _num(cells[champ_col]) == pytest.approx(head["champion_mae"], abs=5e-4)
            assert _num(cells[floor_col]) == pytest.approx(head["floor_mae"], abs=5e-4)
            m = re.match(r"\[([^,]+),\s*([^\]]+)\]", cells[ci_col].replace("**", ""))
            assert m, f"gap CI not parseable in {cells[ci_col]!r}"
            lo, hi = _num(m.group(1)), _num(m.group(2))
            assert lo == pytest.approx(head["champion_vs_floor"]["ci95"][0], abs=5e-4)
            assert hi == pytest.approx(head["champion_vs_floor"]["ci95"][1], abs=5e-4)


def test_multistep_growth_and_coverage_tables_match_committed_metrics() -> None:
    ms = _multistep()
    prob = _load_metrics(PROJECT / "reports_uci" / "probabilistic.json")["multistep"]
    section = _multistep_section()
    horizons = ms["horizons"]
    # error-growth table
    champion = _h_row(section, "champion")
    floor = _h_row(section, "floor (sn)")
    zero = _h_row(section, "zero")
    for h in horizons:
        key = str(h)
        assert champion[key] == pytest.approx(
            ms["horizon_growth"]["pooled"]["routed"][key], abs=5e-4
        )
        assert floor[key] == pytest.approx(
            ms["horizon_growth"]["pooled"]["seasonal_naive"][key], abs=5e-4
        )
        assert zero[key] == pytest.approx(ms["horizon_growth"]["pooled"]["zero"][key], abs=5e-4)
    # band table: coverage + avg width per h, and the verdict row matches per h
    coverage = _h_row(section, "coverage")
    width = _h_row(section, "avg width (units)")
    for h in horizons:
        key = str(h)
        assert coverage[key] == pytest.approx(prob["per_horizon"][key]["coverage"], abs=5e-4)
        assert width[key] == pytest.approx(prob["per_horizon"][key]["avg_width"], abs=5e-4)
    verdict_row = None
    for line in section.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("| verdict |"):
            verdict_row = [c.strip() for c in stripped.strip().strip("|").split("|")][1:]
    assert verdict_row is not None, "verdict row not found"
    for h, cell in zip(horizons, verdict_row, strict=True):
        assert cell == prob["per_horizon"][str(h)]["calibration_verdict"]
    pooled = prob["pooled_coverage"]
    assert f"{pooled:.3f}" in section


def test_multistep_routing_and_decision_numbers_match_committed_metrics() -> None:
    ms = _multistep()
    section = _multistep_section()
    classes = ms["demand_classes"]
    total = classes["n_series"]
    sparse = classes["counts"]["intermittent"] + classes["counts"]["lumpy"]
    # sparse share quoted as "N of M series (P%)"
    m = re.search(r"(\d[\d,]*) of (\d[\d,]*) series \((\d+(?:\.\d+)?)%\)", section)
    assert m, "sparse-share claim not found"
    assert int(m.group(1).replace(",", "")) == sparse
    assert int(m.group(2).replace(",", "")) == total
    assert float(m.group(3)) == pytest.approx(100.0 * sparse / total, abs=0.05)
    # routing gain quoted as "X MAE (CI [a, b])"
    lumpy_routing = ms["routing"]["per_class"]["lumpy"]
    m = re.search(r"by \*\*([\d.]+) MAE\*\* \(CI \[(-?[\d.]+),\s*(-?[\d.]+)\]\)", section)
    assert m, "routing gain claim not found"
    assert float(m.group(1)) == pytest.approx(lumpy_routing["diff"], abs=5e-4)
    assert float(m.group(2)) == pytest.approx(lumpy_routing["ci95"][0], abs=5e-4)
    assert float(m.group(3)) == pytest.approx(lumpy_routing["ci95"][1], abs=5e-4)
    # method-choice counts quoted ("zero forecast for 1,027 series, SBA 30, ...")
    from collections import Counter

    counts = Counter(ms["routing"]["method_choices"].values())
    m = re.search(r"zero\s+forecast for ([\d,]+) series", section)
    assert m and int(m.group(1).replace(",", "")) == counts.get("zero", 0)
    # decision metric per-unit costs at tau=0.90
    tau90 = {cls: e["tau_0.90"] for cls, e in ms["decision_metric"]["per_class"].items()}
    m = re.search(r"erratic \*\*([\d.]+) champion vs\s+([\d.]+) floor\*\*", section)
    assert m, "erratic decision-metric quote not found"
    assert float(m.group(1)) == pytest.approx(
        tau90["erratic"]["champion_per_unit_demand"], abs=5e-4
    )
    assert float(m.group(2)) == pytest.approx(tau90["erratic"]["floor_per_unit_demand"], abs=5e-4)
    m = re.search(r"lumpy ([\d.]+) vs ([\d.]+)\s*\(", section)
    assert m, "lumpy decision-metric quote not found"
    assert float(m.group(1)) == pytest.approx(tau90["lumpy"]["champion_per_unit_demand"], abs=5e-4)
    assert float(m.group(2)) == pytest.approx(tau90["lumpy"]["floor_per_unit_demand"], abs=5e-4)
