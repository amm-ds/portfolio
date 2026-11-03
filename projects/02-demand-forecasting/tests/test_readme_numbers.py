"""README/story drift guards for the full-panel M5 headline (protocol m5_full_v1).

Every headline number quoted in README.md and story.yaml is pinned against the
committed ``reports_m5_full`` artifacts (``metrics.json`` +
``evaluation_metadata.json``). If the pipeline is re-run and a headline moves
without the narrative following, this fails loudly. The subset-era
(``reports_m5/``) and UCI-era guards were removed together with the surfaces
they guarded; those artifacts stay on disk for the test-suite and regenerate
via their own stages.
"""

import json
import re
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]

NAIVE = "seasonal_naive"
MINUS = "\u2212"  # unicode minus, written escaped to keep ruff RUF001 quiet
MULT = "\u00d7"  # multiplication sign, written escaped to keep ruff RUF001 quiet


def _load(path: Path) -> dict:
    # The reports_m5_full JSONs are committed drift-guard anchors, so CI runs
    # against the tracked files; the skip stays as a safety net for a pruned
    # worktree.
    if not path.exists():
        pytest.skip(f"{path} missing — run the full-panel stage locally first")
    return json.loads(path.read_text())


def _metrics() -> dict:
    return _load(PROJECT / "reports_m5_full" / "metrics.json")


def _meta() -> dict:
    return _load(PROJECT / "reports_m5_full" / "evaluation_metadata.json")


def _num(value: str) -> float:
    """README/story number -> float (handles unicode minus, %, thousands, bold)."""
    cleaned = value.replace("**", "").replace("%", "").replace(",", "").replace(MINUS, "-")
    return float(cleaned.strip())


def _pct1(part: float, whole: float) -> float:
    """Relative cut in percent, rounded the way the narrative prints it."""
    return round(100.0 * (part / whole - 1.0), 1)


def _headline_table(section: str) -> dict[str, list[str]]:
    """Parse the candidate headline table (WRMSSE | vs floor | WAPE | bias | stability)."""
    rows: dict[str, list[str]] = {}
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if rows:
                break  # table ended
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != 6 or cells[0] == "candidate" or set(cells[0]) <= {"-", ":"}:
            continue
        name = cells[0].replace("**", "")
        for suffix in (" (champion)", " (best single)", " (floor)"):
            name = name.replace(suffix, "")
        rows[name] = cells[1:]
    return rows


def _check_headline_table(
    table: dict[str, list[str]], where: str, required: set[str] | None = None
) -> None:
    metrics = _metrics()
    test = metrics["test"]
    sel = metrics["selection"]
    naive = test[NAIVE]["official_wrmsse"]
    if required is None:
        assert set(table) == set(metrics["candidates"]), f"{where} candidates mismatch the run"
    else:
        # the story table was trimmed to the decisive rows; every quoted
        # row must still match the committed metrics exactly
        assert required <= set(table), f"{where} headline table lost a decisive row"
        assert set(table) <= set(metrics["candidates"]), (
            f"{where} headline table quotes an unknown candidate"
        )
    for cand, (wrmsse, vs_floor, wape, bias, stability) in table.items():
        row = test[cand]
        assert _num(wrmsse) == pytest.approx(row["official_wrmsse"], abs=5e-5), (
            f"{where}: {cand} WRMSSE drifted"
        )
        if cand == NAIVE:
            assert vs_floor == "—", f"{where}: floor row must not quote a gap"
        else:
            expected = _pct1(row["official_wrmsse"], naive)
            assert _num(vs_floor) == pytest.approx(expected, abs=0.05), (
                f"{where}: {cand} vs-floor quote drifted"
            )
        assert _num(wape) == pytest.approx(row["bottom_wape"], abs=5e-5), (
            f"{where}: {cand} bottom WAPE drifted"
        )
        assert _num(bias) == pytest.approx(row["bias"], abs=5e-5), f"{where}: {cand} bias drifted"
        assert _num(stability) == pytest.approx(sel[cand]["stability"], abs=5e-5), (
            f"{where}: {cand} stability drifted"
        )


def _readme_m5_section() -> str:
    text = (PROJECT / "README.md").read_text()
    assert "## M5 headline" in text, "M5 section missing from README"
    return text.split("## M5 headline", 1)[1].split("### Related work", 1)[0]


def _story() -> str:
    return (PROJECT / "story.yaml").read_text()


def _story_conclusions() -> str:
    story = _story()
    assert "## Results summary" in story, "conclusions tables missing from story"
    return story.split("## Results summary", 1)[1]


def test_readme_headline_table_matches_committed_metrics() -> None:
    table = _headline_table(_readme_m5_section())
    assert table, "M5 headline table not found in README"
    _check_headline_table(table, "README")


def test_story_headline_table_matches_committed_metrics() -> None:
    conclusions = _story_conclusions()
    table = _headline_table(conclusions)
    assert table, "headline table not found in story conclusions"
    _check_headline_table(
        table,
        "story",
        required={"convex_ensemble", "lgbm_pool_store", "seasonal_naive"},
    )


def test_story_per_level_quotes_match_committed_metrics() -> None:
    """The 12-level table was trimmed as a verbose secondary table; the per-level
    prose quotes that remain in the story stay pinned to the committed metrics."""
    metrics = _metrics()
    test = metrics["test"]
    story = " ".join(_story().split())
    total_ens = test["convex_ensemble"]["per_level_wrmsse"]["total"]
    total_floor = test[NAIVE]["per_level_wrmsse"]["total"]
    assert total_ens == pytest.approx(0.3501, abs=5e-5)
    assert total_floor == pytest.approx(0.5600, abs=5e-5)
    assert f"{total_ens:.3f}" in story, "story lost the per-level ensemble quote"
    assert f"{total_floor:.3f}" in story, "story lost the per-level floor quote"


def test_honest_comparison_quotes_match_committed_metrics() -> None:
    """The competition-axis comparison: ensemble/floor absolutes, the headline
    cut, and the cited winner constant — live in both README and story."""
    metrics = _metrics()
    test = metrics["test"]
    naive = test[NAIVE]["official_wrmsse"]
    ens = test["convex_ensemble"]["official_wrmsse"]
    rel = _pct1(ens, naive)
    assert rel == pytest.approx(-31.0, abs=0.05)  # the headline cut itself
    readme = _readme_m5_section()
    story = _story()
    for where, text in (("README", readme), ("story", story)):
        assert f"{ens:.4f}" in text, f"{where}: ensemble absolute missing"
        assert f"{naive:.4f}" in text, f"{where}: floor absolute missing"
        m = re.search(r"\*\*" + MINUS + r"([\d.]+)%\*\*", text)
        assert m, f"{where}: bold relative-cut quote missing"
        assert float(m.group(1)) == pytest.approx(-rel, abs=0.05)
        assert MINUS + "22.4%" in text, f"{where}: competition winner constant missing"
        assert "doi.org/10.1016/j.ijforecast.2021.11.013" in text, f"{where}: citation missing"


def test_ensemble_composition_quotes_match_committed_metrics() -> None:
    """Members and weights quoted in both surfaces, and the screen rule."""
    metrics = _metrics()
    ens = metrics["ensemble"]
    members, weights = ens["members"], ens["weights"]
    assert members == ["lgbm_pool_storecat", "lgbm_pool_store", "lgbm_pool_dept"]
    assert [round(w, 2) for w in weights] == [0.60, 0.10, 0.30]
    quote = (
        f"{members[0]} {MULT} {weights[0]:.2f} + {members[1]} {MULT} {weights[1]:.2f} "
        f"+ {members[2]} {MULT} {weights[2]:.2f}"
    )
    assert quote in " ".join(_story().split())
    assert quote in " ".join(_readme_m5_section().split())
    # the screen rule itself is pinned: mean + 1.0 x population std over the
    # 2 selection origins
    screen = metrics["ensemble"]["selection_screen"]
    for block in screen.values():
        assert block["score"] == pytest.approx(block["mean"] + 1.0 * block["std"], abs=1e-12)


def test_panel_and_class_quotes_match_committed_artifacts() -> None:
    metrics = _metrics()
    meta = _meta()
    panel = meta["dataset"]["observed_panel"]
    assert panel["n_series"] == 30490 and panel["n_days"] == 1969
    assert panel["n_rows"] == 47649940
    counts = metrics["classes"]["counts"]
    assert counts == {"dense": 2754, "intermittent": 27736}
    assert metrics["hierarchy"]["n_nodes_total"] == 42840
    assert len(metrics["candidates"]) == 8
    assert len(metrics["origins"]["dates"]) == 3
    assert len(metrics["origins"]["selection"]) == 2 and len(metrics["origins"]["test"]) == 1
    assert meta["runtime_seconds"] == pytest.approx(46509, abs=1)
    readme = _readme_m5_section()
    for token in ("30,490", "1,969", "47,649,940", "59.5%", "42,840", "2,754 dense + 27,736"):
        assert token in readme, f"README lost the panel/class quote {token!r}"
    story_norm = " ".join(_story().split())
    for token in ("30,490", "42,840", "27,736", "2,754"):
        assert token in story_norm, f"story lost the panel/class quote {token!r}"


def test_zero_day_quotes_match_committed_metrics() -> None:
    """Quiet-day claims in both surfaces are live against the test block."""
    test = _metrics()["test"]
    expected = {
        "floor": 100.0 * test[NAIVE]["zero_day_accuracy"],
        "floor_intermittent": 100.0 * test[NAIVE]["zero_day_accuracy_intermittent"],
        "ensemble": 100.0 * test["convex_ensemble"]["zero_day_accuracy"],
        "ensemble_intermittent": 100.0 * test["convex_ensemble"]["zero_day_accuracy_intermittent"],
        "auto_ets": 100.0 * test["auto_ets"]["zero_day_accuracy"],
    }
    assert expected["floor"] == pytest.approx(66.6, abs=0.05)
    assert expected["ensemble"] == pytest.approx(57.3, abs=0.05)
    assert expected["auto_ets"] == pytest.approx(60.9, abs=0.05)
    for where, text in (("README", _readme_m5_section()), ("story", " ".join(_story().split()))):
        assert "66.6%" in text and "57.3%" in text, f"{where}: zero-day quote missing"
    assert "60.9%" in _readme_m5_section()
    assert "67.8%" in _readme_m5_section() and "58.9%" in _readme_m5_section()


def test_pooled_beats_global_claim_is_live() -> None:
    """The key-lesson claim: all three pooled arms beat the global model on
    the official WRMSSE (and the item-level cluster claim stays true)."""
    metrics = _metrics()
    test = metrics["test"]
    pooled = ["lgbm_pool_store", "lgbm_pool_storecat", "lgbm_pool_dept"]
    for cand in pooled:
        assert test[cand]["official_wrmsse"] < test["lgbm"]["official_wrmsse"]
    assert "inverse of the subset-era finding" in " ".join(_readme_m5_section().split())
    learned = [c for c in metrics["candidates"] if c != NAIVE]
    bottom = ["item", "state_item", "item_store"]
    for lvl in bottom:
        for cand in learned:
            assert 1.04 <= round(test[cand]["per_level_wrmsse"][lvl], 2) <= 1.15
        floor_lvl = test[NAIVE]["per_level_wrmsse"][lvl]
        assert 1.37 <= floor_lvl <= 1.40
    assert test[NAIVE]["per_level_wrmsse"]["item"] >= 1.39


def test_subset_and_uci_era_claims_are_gone_from_presented_surfaces() -> None:
    """The presented README/story must not resurrect removed-era headlines."""
    readme = (PROJECT / "README.md").read_text()
    story = _story()
    for dead in (
        "945 of 1,069",
        "0.4913",
        "0.4140",
        "77.7%",
        "two demand regimes",
        "89%-zero",
        "m5_direct_v1",
        "ensemble_l2",
    ):
        assert dead not in readme, f"README resurrected {dead!r}"
        assert dead not in story, f"story resurrected {dead!r}"
