# TabPFN-2 challenger report: STOP at step 3 (weights require licence acceptance)

Date: 2026-11-19
Handoff: `collaboration/designs/20261119-tabpfn2-challenger/03-implementation-handoff.md`
Status: **STOPPED at step 3** — the handoff's stop condition (token/licence
acceptance requested) fired. Nothing beyond dependency probing landed; the
pin and lock changes were reverted. Open question:
`collaboration/designs/20261119-execution-plan-kimi/OPEN_QUESTIONS.md`.

## What was done

1. **PyPI version check** (recorded, not assumed): current release is
   **`tabpfn 10.2.0`** — the unified package bundling TabPFN-2 weights.
2. **Pin + lock**: added `tabpfn==10.2.0` to
   `projects/12-tabular-ml-lifecycle/pyproject.toml`, ran `uv lock`
   (added `tabpfn 10.2.0`, `skrub 0.10.1`, `mlx-metal 0.32.4`).
3. **Offline-load check**: `from tabpfn import TabPFNRegressor` imports, but
   the first `.fit()` requires authentication: a `TABPFN_TOKEN` from
   `https://ux.priorlabs.ai` after login + licence acceptance on the
   Licenses tab. **Stop condition hit.**
4. **Revert**: pin removed, `uv lock` re-run; `pyproject.toml` and `uv.lock`
   match their pre-Q5 working-tree state (`uv lock --check` clean, `tabpfn`
   absent from both). No challenger script, no `reports/tabpfn2_challenger.json`,
   no README/story/short-copy changes, no `LICENSE-TABPFN.txt`.

## Licence text checked

Fetched verbatim from
`https://huggingface.co/Prior-Labs/TabPFN-v2-clf/blob/main/LICENSE.txt` (201
lines): Prior Labs License, Version 1.1, May 2025 — Apache-2.0 derivative
with an added §10 attribution requirement. Confirmed against the handoff:
(A) ship a licence copy with the materials; (B) prominently display
"Built with PriorLabs-TabPFN"; models built FROM the weights must begin with
"TabPFN". §10 also notes internal benchmarking without external
communication requires no attribution — the public portfolio is not that.

## Commands run

- `uv run python -c "…urllib…pypi.org/pypi/tabpfn/json…"` → 10.2.0
- `curl -sL …/LICENSE.txt` → licence confirmed
- `uv lock` (add), `uv run python -c "…TabPFNRegressor().fit…"` (token demand)
- `uv lock` (revert), `uv lock --check`

## What did not run (and why)

Steps 4–7 (challenger run, paired-bootstrap comparison, copy updates,
attribution, licence file) — blocked on the owner decision recorded in
OPEN_QUESTIONS: provide `TABPFN_TOKEN`, drop the challenger, or attempt the
raw HF-weights path. The validation comparison numbers therefore do not
exist; no numbers were produced or changed by Q5.

## Files touched by Q5 (all reverted)

- `projects/12-tabular-ml-lifecycle/pyproject.toml` — pin added then removed;
  file is back to its pre-Q5 working-tree diff (1 deletion vs HEAD, from the
  earlier session's pin revert).
- `uv.lock` — locked and re-locked; final content equals the pre-Q5 state
  (tabpfn/skrub/mlx-metal absent).
