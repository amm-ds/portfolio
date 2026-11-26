"""Committed figure titles state their own trace data (grade pass 4).

The committed payloads were title-patched without a full pipeline re-run;
these assertions pin every headline number/claim to the figure's own traces.
"""

import json
from pathlib import Path

FIGURES = Path(__file__).parents[1] / "reports" / "figures"


def _load(name: str) -> dict:
    return json.loads((FIGURES / f"{name}.json").read_text())


def _top_two(values: list[float]) -> set[int]:
    return set(sorted(range(len(values)), key=lambda i: -values[i])[:2])


def test_committed_figure_titles_state_their_own_data() -> None:
    qini = _load("qini_per_arm")
    title = qini["layout"]["title"]["text"]
    assert title.startswith("Neither arm's AUUC interval excludes zero")
    trace = qini["data"][0]
    points = trace["x"]
    lo = [p - m for p, m in zip(points, trace["error_x"]["arrayminus"], strict=True)]
    hi = [p + a for p, a in zip(points, trace["error_x"]["array"], strict=True)]
    assert all(low <= 0.0 <= high for low, high in zip(lo, hi, strict=True))
    # axes-gate fix: the window keeps every whisker and stays within 4x span
    rng = qini["layout"]["xaxis"]["range"]
    assert rng[0] <= min(lo) and rng[1] >= max(hi)
    assert rng[1] - rng[0] <= 4.0 * (max(points) - min(points))

    decile = _load("uplift_by_decile")
    dtitle = decile["layout"]["title"]["text"]
    assert dtitle.startswith("Predicted uplift tracks the observed contrast")
    predicted = next(t for t in decile["data"] if "predicted" in t["name"])
    empirical = next(t for t in decile["data"] if t["name"] == "empirical uplift")
    assert _top_two(predicted["y"]) == _top_two(empirical["y"]) == {0, 1}

    cuped = _load("cuped_variance")
    ctitle = cuped["layout"]["title"]["text"]
    for outcome, label in (("conversion", "conversion"), ("visit", "visits")):
        trace = next(t for t in cuped["data"] if t["name"] == outcome)
        reduction = 1.0 - trace["y"][1] / trace["y"][0]
        assert f"{reduction:.2%} for {label}" in ctitle

    eda = _load("eda_segment_profile")
    etitle = eda["layout"]["title"]["text"]
    assert "about 21k" in etitle
    customers = next(t for t in eda["data"] if t["name"] == "customers")
    assert all(20_500 <= n <= 21_500 for n in customers["y"])
    visits = next(t for t in eda["data"] if t["name"] == "visit rate")
    top_arm = visits["x"][visits["y"].index(max(visits["y"]))]
    assert top_arm == "Mens E-Mail"
    assert "Mens mail lifts visits most" in etitle

    frontier = _load("profit_frontier_multi_arm")
    ftitle = frontier["layout"]["title"]["text"]
    assert ftitle.startswith("Best-arm targeting at 25% budget")
    assert "model-estimated value, not observed" in ftitle
    star = next(t for t in frontier["data"] if t["name"] == "best-arm @ 25%")
    assert abs(star["x"][0] - 0.25) < 0.01
