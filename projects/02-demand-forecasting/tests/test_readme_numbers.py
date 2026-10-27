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


# ---------------------------------------------------------------------------
# Wave-20 peak-capable candidates: peak-capture + candidate-comparison guards
# ---------------------------------------------------------------------------


def test_multistep_peak_capture_table_matches_committed_metrics() -> None:
    """The peak-capture table (peak_mae / peak_recall per candidate per class)."""
    ms = _multistep()
    section = _multistep_section()
    peak = ms["peak_capture"]["per_class"]
    rows: dict[str, list[str]] = {}
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != 5 or cells[0] in ("candidate",) or set(cells[0]) <= {"-", ":"}:
            continue
        rows[cells[0].replace("**", "")] = cells[1:]
    assert set(rows) == set(ms["peak_capture"]["candidates"]), "peak-capture table mismatch"
    for cand, cells in rows.items():
        for cls, off in (("lumpy", 0), ("erratic", 2)):
            if cls not in peak:
                continue
            assert _num(cells[off]) == pytest.approx(peak[cls][cand]["peak_mae"], abs=5e-4), (
                f"{cls} {cand} peak_mae drifted"
            )
            assert _num(cells[off + 1]) == pytest.approx(
                peak[cls][cand]["peak_recall"], abs=5e-4
            ), f"{cls} {cand} peak_recall drifted"


def test_multistep_candidate_comparison_matches_committed_metrics() -> None:
    """The per-class candidate MAE quotes (incl. the wave-21 candidates and
    the convex ensemble) are live."""
    ms = _multistep()
    section = _multistep_section()
    comp = ms["candidate_comparison"]["per_class"]
    for cls in comp:
        for cand in comp[cls]:
            if cand in ("routed_mae", "zero_mae"):
                continue
            m = re.search(rf"{cls} {cand} MAE\s+\*\*([\d.]+)\*\*", section)
            assert m, f"{cls} {cand} MAE quote missing from README"
            assert float(m.group(1)) == pytest.approx(comp[cls][cand]["mae"], abs=5e-4)
    # the router's ML-pick count quote on lumpy ("hurdle_hgb for N series, ...")
    from collections import Counter

    classes_of = ms["demand_classes"]["series"]
    counts = Counter(
        m for sid, m in ms["routing"]["method_choices"].items() if classes_of[sid] == "lumpy"
    )
    m = re.search(r"hurdle_hgb for\s+([\d,]+) series", section)
    assert m and int(m.group(1).replace(",", "")) == counts.get("hurdle_hgb", 0)


def test_multistep_win_rates_match_committed_metrics() -> None:
    """The wave-21 win-rate quotes (per class and candidate at h=7/h=14,
    with the bootstrap CIs) are live against the committed block."""
    ms = _multistep()
    section = _multistep_section()
    wr = ms["win_rates"]["per_class"]
    for cls in wr:
        for cand, h_key, pat in (
            (
                "routed",
                "7",
                r"{} routed beats-floor h=7:\s+\*\*([\d.]+)%\*\* \(CI \[([\d.]+),\s*([\d.]+)\]\)",
            ),
            (
                "routed",
                "14",
                r"{} routed beats-floor h=14:\s+\*\*([\d.]+)%\*\* \(CI \[([\d.]+),\s*([\d.]+)\]\)",
            ),
        ):
            m = re.search(pat.format(cls), section)
            assert m, f"{cls} win-rate quote missing from README"
            item = wr[cls]["per_horizon"][h_key][cand]
            assert float(m.group(1)) == pytest.approx(100.0 * item["win_rate"], abs=5e-2)
            assert float(m.group(2)) == pytest.approx(100.0 * item["ci95"][0], abs=5e-2)
            assert float(m.group(3)) == pytest.approx(100.0 * item["ci95"][1], abs=5e-2)


# ---------------------------------------------------------------------------
# Wave-22 guards: new candidates, rmae/rmsse, newsvendor decision layer
# ---------------------------------------------------------------------------


def test_multistep_wave22_leaderboard_and_rmae_match_committed_metrics() -> None:
    """The wave-22 quotes are live: champion pooled MAE + rmae, the new
    candidates' pooled MAEs, and the rmsse summary."""
    ms = _multistep()
    section = _multistep_section()
    # champion pooled MAE and rmae vs the floor
    m = re.search(
        r"routed pipeline\s*\n?\s*\(\*\*([\d.]+)\*\* — pooled rmae \*\*([\d.]+)\*\*", section
    )
    assert m, "champion pooled MAE / rmae quote missing from README"
    assert float(m.group(1)) == pytest.approx(ms["overall_mae_test"]["routed"], abs=5e-4)
    assert float(m.group(2)) == pytest.approx(ms["rmae"]["pooled"]["routed"], abs=5e-4)
    # the floor's rmae is 1.0 by construction
    assert ms["rmae"]["pooled"]["seasonal_naive"] == pytest.approx(1.0)
    # new candidates' pooled MAEs in the wave-22 bullet
    for cand, pat in (
        ("ma_28", r"ma_28 \*\*([\d.]+)\*\*"),
        ("adida_tsb", r"adida_tsb \*\*([\d.]+)\*\*"),
        ("adida_sba", r"adida_sba \*\*([\d.]+)\*\*"),
        (
            "routed_reconciled",
            r"\(country-aggregate anchoring\) also loses on pooled\s*\n?\s*MAE — ([\d.]+)",
        ),
    ):
        m = re.search(pat, section)
        assert m, f"{cand} pooled-MAE quote missing from README"
        assert float(m.group(1)) == pytest.approx(ms["overall_mae_test"][cand], abs=5e-4), cand
    # rmsse summary: routed pooled rmsse + volume-weighted, floor rmsse
    m = re.search(
        r"routed rmsse ([\d.]+) \(volume-weighted\s*\n?\s*([\d.]+)\) vs the floor's (\d+\.\d+)",
        section,
    )
    assert m, "rmsse summary quote missing from README"
    assert float(m.group(1)) == pytest.approx(ms["rmsse"]["pooled"]["routed"]["rmsse"], abs=5e-4)
    assert float(m.group(2)) == pytest.approx(ms["rmsse"]["pooled"]["routed"]["wrmsse"], abs=5e-4)
    assert float(m.group(3)) == pytest.approx(
        ms["rmsse"]["pooled"]["seasonal_naive"]["rmsse"], abs=5e-4
    )


def test_multistep_newsvendor_quotes_match_committed_metrics() -> None:
    """The newsvendor layer quotes (per-class cost per unit-demand at q=0.90
    with the paired-bootstrap CIs) are live against the committed block."""
    ms = _multistep()
    section = _multistep_section()
    nv = ms["decision_metric"]["newsvendor"]["per_class"]
    # q=0.90 per-class quotes (the headline service level)
    m = re.search(r"erratic q=0\.90 routed\s*\n?\s*\*\*([\d.]+) vs floor ([\d.]+)\*\*", section)
    assert m, "erratic newsvendor q=0.90 quote missing from README"
    assert float(m.group(1)) == pytest.approx(
        nv["erratic"]["q_0.90"]["routed_cost_per_unit_demand"], abs=5e-4
    )
    assert float(m.group(2)) == pytest.approx(
        nv["erratic"]["q_0.90"]["floor_cost_per_unit_demand"], abs=5e-4
    )
    m = re.search(r"lumpy q=0\.90 \*\*([\d.]+)\s*\n?\s*vs ([\d.]+)\*\*", section)
    assert m, "lumpy newsvendor q=0.90 quote missing from README"
    assert float(m.group(1)) == pytest.approx(
        nv["lumpy"]["q_0.90"]["routed_cost_per_unit_demand"], abs=5e-4
    )
    assert float(m.group(2)) == pytest.approx(
        nv["lumpy"]["q_0.90"]["floor_cost_per_unit_demand"], abs=5e-4
    )
    # every committed service level appears in the section
    for q in ms["decision_metric"]["newsvendor"]["service_levels"]:
        assert f"q={q:.2f}" in section, f"newsvendor service level {q:.2f} not quoted"
    # cost assumptions stated
    assert "holding 1.0 / stockout 3.0" in section


# ---------------------------------------------------------------------------
# Wave-23 hierarchical track (protocol hierarchical_rolling_v1) drift guards
# ---------------------------------------------------------------------------


def _hier() -> dict:
    return _load_metrics(PROJECT / "reports_hier" / "metrics.json")["groups"]


def _hier_section() -> str:
    text = (PROJECT / "README.md").read_text()
    assert "## Hierarchical track" in text, "hierarchical section missing from README"
    return text.split("## Hierarchical track", 1)[1].split("## Synthetic track", 1)[0]


def test_hierarchical_headline_rmae_quotes_match_committed_metrics() -> None:
    """The per-group headline rmae quotes (raw vs reconciled lgbm, auto
    base forecasts, best variant) are live against reports_hier/metrics.json."""
    groups = _hier()
    section = _hier_section()
    # each group's quotes live inside its own bullet (anchored on the bold
    # group name) so the two groups' identical-shaped quotes never cross-match
    texts = {
        "TourismSmall": section.split("- **TourismSmall**:", 1)[1].split("- **Labour**:", 1)[0],
        "Labour": section.split("- **Labour**:", 1)[1],
    }
    quotes = (
        # (group, regex, per_level/coherence path, label)
        (
            "TourismSmall",
            r"auto_theta rmae \*\*([\d.]+)\*\*",
            ("auto_theta", "total", "rmae"),
            "tourism auto_theta",
        ),
        (
            "TourismSmall",
            r"auto_theta rmae \*\*[\d.]+\*\* / auto_ets \*\*([\d.]+)\*\*",
            ("auto_ets", "total", "rmae"),
            "tourism auto_ets",
        ),
        (
            "TourismSmall",
            r"raw total\s*\n?rmae \*\*([\d.]+)\*\*",
            ("lgbm_global", "total", "rmae"),
            "tourism lgbm raw",
        ),
        ("TourismSmall", r"coherence error \*\*([\d.]+)\*\*", None, "tourism lgbm coherence"),
        (
            "TourismSmall",
            r"lands at\s*\n?total rmae \*\*([\d.]+)\*\*",
            ("lgbm_global+mint_shrink", "total", "rmae"),
            "tourism lgbm+mint total",
        ),
        (
            "TourismSmall",
            r"lands at\s*\n?total rmae \*\*[\d.]+\*\* \(bottom \*\*([\d.]+)\*\*",
            ("lgbm_global+mint_shrink", "bottom", "rmae"),
            "tourism lgbm+mint bottom",
        ),
        (
            "TourismSmall",
            r"best total-level variant at \*\*([\d.]+)\*\*",
            ("auto_ets+bottom_up", "total", "rmae"),
            "tourism best total",
        ),
        (
            "Labour",
            r"auto_theta raw total\s*\n?rmae \*\*([\d.]+)\*\*",
            ("auto_theta", "total", "rmae"),
            "labour auto_theta",
        ),
        (
            "Labour",
            r"auto_theta raw total\s*\n?rmae \*\*[\d.]+\*\*, auto_ets \*\*([\d.]+)\*\*",
            ("auto_ets", "total", "rmae"),
            "labour auto_ets",
        ),
        (
            "Labour",
            r"auto_ets\+bottom_up` ([\d.]+)\s*vs\s*\n?\s*raw",
            ("auto_ets+bottom_up", "total", "rmae"),
            "labour ets+bu",
        ),
        (
            "Labour",
            r"raw total rmae \*\*([\d.]+)\*\*",
            ("lgbm_global", "total", "rmae"),
            "labour lgbm raw",
        ),
        (
            "Labour",
            r"lgbm_global\+bottom_up` \*\*([\d.]+)\*\*",
            ("lgbm_global+bottom_up", "total", "rmae"),
            "labour lgbm+bu",
        ),
        (
            "Labour",
            r"lgbm_global\+mint_shrink` \*\*([\d.]+)\*\*",
            ("lgbm_global+mint_shrink", "total", "rmae"),
            "labour lgbm+mint",
        ),
    )
    for group, pattern, path, label in quotes:
        m = re.search(pattern, texts[group])
        assert m, f"{label} quote missing from README"
        if path is None:
            committed = groups[group]["coherence"]["lgbm_global"]
        else:
            variant, level, metric = path
            committed = groups[group]["per_level"][variant][level][metric]
        assert _num(m.group(1)) == pytest.approx(committed, abs=5e-4), f"{label} drifted"


def test_hierarchical_bootstrap_gap_quotes_match_committed_metrics() -> None:
    """The headline MAE-gap quotes with CIs are live per group."""
    groups = _hier()
    section = _hier_section()
    # each group's quotes live inside its own bullet (anchored on the bold
    # group name) so the two groups' identical-shaped quotes never cross-match
    anchors = {
        "TourismSmall": section.split("- **TourismSmall**:", 1)[1].split("- **Labour**:", 1)[0],
        "Labour": section.split("- **Labour**:", 1)[1],
    }
    for group_key, label in (("TourismSmall", "tourism"), ("Labour", "labour")):
        head = groups[group_key]["headline"]
        text = anchors[group_key]
        for level in ("total", "bottom"):
            gap = head[level]["bootstrap"]
            lo, hi = gap["ci95"]
            m = re.search(
                # \u2212 is the unicode minus used in the README quotes
                rf"\*\*([\u2212-]?[\d.]+)\*\*\s+{level}\s+MAE\s+"
                rf"\(CI\s+\[([\u2212-]?[\d.]+),\s*([\u2212-]?[\d.]+)\]",
                text,
            )
            assert m, f"{label} {level} gap quote missing from README"
            assert _num(m.group(1)) == pytest.approx(gap["diff"], abs=5e-2), (
                f"{label} {level} gap drifted"
            )
            assert _num(m.group(2)) == pytest.approx(lo, abs=5e-2), f"{label} {level} CI lo"
            assert _num(m.group(3)) == pytest.approx(hi, abs=5e-2), f"{label} {level} CI hi"
