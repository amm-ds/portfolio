# Open questions — Wave 8 round-3 fixes

## Project 08 repeat-file decision — resolved

The owner selected **option (b)** on 2026-11-26. Remove every claim that depends on the gitignored `projects/08-inference-serving/data/bench_run_repeat.json`: its committed-status wording, the `5–35×` range, Ollama `0.40.12`, and `2026-10-30`. Retain one Limits sentence identifying the repeat as an uncommitted observation. Do not commit that file or change `.gitignore`.

## Project 02 demo regeneration — disclosure fallback required

`uv run python -m demand_forecasting.cli demo-payload-m5-full` was attempted from `projects/02-demand-forecasting` on 2026-11-26. It stopped before writing at `m5_full_payload.py:_catalog_guards` because the committed catalog ensemble does not match the committed `metrics.json` ensemble. The catalog still carries the earlier `0.60/0.10/0.30` blend; regenerating its curves would require the prohibited catalog model refit.

Per handoff item 2, the payload and catalog curves remain unchanged. The article and sample caption disclose that they come from the earlier `0.6161` blend, while demo headline labels distinguish that historical payload from the committed `0.6211` champion.
