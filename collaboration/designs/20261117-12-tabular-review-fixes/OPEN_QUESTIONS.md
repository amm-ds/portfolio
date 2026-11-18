# OPEN QUESTIONS — 12 TabPFN-2.5 run blocked on license acceptance

Date: 2026-11-19 (overnight queue, item 7)
Executor: Kimi Code

## Blocked part

Brief item 7 / owner decision 11: "TabPFN-2.5 for the bike data. Install and
run it locally; no hosted calls."

## Finding

`uv add tabpfn` resolved to `tabpfn==10.2.0` (the TabPFN-2.5/3-generation
line, which documents up to 50,000 rows — the reason decision 11 chose it).
That package gates the model-weight download behind a one-time license
acceptance requiring a Prior Labs account and `TABPFN_TOKEN`:

    TabPFNLicenseError: TabPFN requires a one-time license acceptance to
    download model weights ... Set TABPFN_TOKEN="<your-api-key>"

Accepting a license / creating an account is an outward-facing action bound
to the owner's identity, and setting the token would be an environment
change — both outside the overnight hard limits. No weights can be fetched
without it (fit fails in 6 s; nothing was run).

## Options for the owner

1. Accept the license at https://ux.priorlabs.ai (Licenses tab), create an
   API key, and either export `TABPFN_TOKEN` or run
   `uv run python /tmp/tabpfn_bike.py` (script preserved; re-create from the
   morning report if /tmp was cleaned). Weights download once, then the run
   is fully local and offline.
2. Or approve the older `tabpfn` v2 package line (pre-license-gate, weights
   bundled in the wheel). Its documented evaluation scope is 10,000 samples;
   the bike train split is 14,523 rows, so this contradicts decision 11's
   stated reason (50k row support) unless a documented subsample is approved.
3. Or drop the TabPFN challenger and keep the validation-tie wording only.

Completed independently of this blocker: paired validation interval
(−0.18, 95% CI [−1.71, +1.21], committed at
`metrics.json:validation_tie_interval`), champion-label removal per decision
8, selection-isolation test, `residual_heatmap` legend confirmed.
