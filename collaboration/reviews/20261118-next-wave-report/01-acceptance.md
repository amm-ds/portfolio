# Acceptance: next wave W1, W2, W4, W5, W6, W9

Date: 2026-11-18
Reviewer: owner (amm-ds), recorded by Claude Code
Decision: accepted

Carried forward (not closed by acceptance):
1. Full `uv run pytest -q` result is not in Kimi's report. Owner to obtain before the commit.
2. `projects/06-routing-optimization/src/routing_optimization/figures.py` changed (Pareto label step). Outside the approved items; kept, owner to confirm the reason.
3. `projects/06-routing-optimization/reports/metrics.json` `_meta` restamped (created_at, git_sha). Numbers unchanged. Same churn persists until W3 (provenance stamp) is approved.
4. `comparison.md` opening sentence still says every designed-to-fail probe refuses gracefully; the h19 note beneath it qualifies this. Tidy the sentence later.
5. The `tools.py` claim about typed `refused` results is not backed by a diff in this wave. Verify before citing.
6. W4 headline check covers 11 of 13 projects; 01 and 04 are on the known-drift list.
7. Gates in the report were not rerun by Claude.

Not approved and still open: W3, W7, W8, W10, W11, W12.
