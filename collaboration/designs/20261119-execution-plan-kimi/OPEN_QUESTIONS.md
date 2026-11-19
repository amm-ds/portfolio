# OPEN QUESTIONS — execution plan 20261119-execution-plan-kimi

## Q5 STOP: TabPFN-2 weights require account licence acceptance (stop condition hit)

Raised 2026-11-19 during Q5 execution.

**What happened.** Steps 1–2 completed: PyPI reports the current release as
`tabpfn 10.2.0` (the unified package that bundles TabPFN-2 weights), and the
pin was added to `projects/12-tabular-ml-lifecycle/pyproject.toml` + `uv lock`
ran cleanly (added `tabpfn 10.2.0`, `skrub 0.10.1`, `mlx-metal 0.32.4`).

Step 3 (confirm weights load offline with no token) **failed**: importing
works, but the first `.fit()` prints an authentication requirement —
`TABPFN_TOKEN` from `https://ux.priorlabs.ai` after logging in and accepting
the licence on the Licenses tab. The package route (10.x) therefore requires
a Prior Labs account with accepted licence; the earlier assumption that the
Hugging Face weights load token-free does not hold for the PyPI package.

Per the handoff's stop condition ("If a token or licence acceptance is
requested, stop and write OPEN_QUESTIONS.md") Q5 stopped immediately:

- The `tabpfn==10.2.0` pin was removed from `pyproject.toml` and `uv lock`
  re-run; both files are back to their pre-Q5 working-tree state
  (`uv lock --check` clean; `tabpfn` absent from both).
- No challenger run, no report file, no copy changes, no licence file were
  produced.
- Details: `collaboration/reviews/20261119-tabpfn2-report/00-report.md`.

**Owner decision needed.**

1. Create a Prior Labs account, accept the licence, and provide
   `TABPFN_TOKEN` (a config/secret change — outside this plan's permissions),
   then re-run Q5 from step 3; or
2. Drop the TabPFN-2 challenger (the Q1 roadmap pointer already reads
   "TabPFN-2 challenger pending; see README" — it stays accurate either way);
   or
3. Try the raw Hugging Face weights path (e.g. `TabPFN-v2-reg` checkpoints)
   instead of the PyPI package — unverified, likely the same gating.

**Licence note (confirmed during the attempt).** The Prior Labs License v1.1
(May 2025) text was fetched from the HF repo and matches the decision record:
Apache-2.0 derivative plus §10 requiring (A) a shipped licence copy and (B)
prominent "Built with PriorLabs-TabPFN" display wherever the weights or
outputs are made available — both remain required if the challenger proceeds.
