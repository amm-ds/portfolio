# 12 Tabular ML lifecycle: investigation

Date: 2026-11-19 (searches on 2026-11-18). Labels: SB / SEC / GAP. Source IDs map to `99-sources.md`.

## Current state (committed)
- UCI Capital Bikeshare hourly demand, 17,379 rows; validation-selected PyTorch MLP reaches 25.4 test MAE (25.4316 in metrics) vs 83.2 for seasonal-naive on the frozen 8-week test window; hourly 95% bootstrap CI 52.5-63.1; week-block sensitivity 38.8-73.4. MLP and LightGBM tied on validation (paired interval lo -1.7054, hi +1.2134; "Negative favors the MLP"; reported as tied per owner decision 8). 26 DQ gates; ablation test scores are post-freeze diagnostics. Source: `projects/12-tabular-ml-lifecycle/story.yaml`; metrics `projects/12-tabular-ml-lifecycle/reports/metrics.json`.
- Roadmap "next": TabPFN-2.5 challenger, blocked on a licence decision (owner-held).

## Gaps against the state of the art
| # | Gap | Label | Source |
|---|---|---|---|
| G1 | TabPFN-2.5: built for up to 50,000 data points and 2,000 features; leads TabArena; distillation into an MLP or tree ensemble. Our 17,379 rows fit. | SB (abstract page) | S07 |
| G2 | Licence: the model card says weights are under "tabpfn-2.5-license-v1.1"; research and limited internal evaluation permitted; model, derivatives and outputs may not be used for any commercial or production purpose; examples include competitive benchmarking for procurement and internal commercial decision-making. A search snippet quoted the same terms as v1.0 citing the paper's section 6 (I could not read section 6). Version conflict; whether a public portfolio page counts is the owner's decision. | SB (model card) vs SEC (snippet) | S04 |
| G3 | TabArena: gradient-boosted trees remain strong; foundation models do best on small data; best results come from ensembling tuned configurations. | SEC | S35 |
| G4 | Validation design: a practitioner write-up on the same UCI hourly data reports that random 5-fold CV makes LightGBM look best while time-series CV puts a seasonal baseline ahead. Our frozen time-ordered split avoids this; the point supports keeping it. | SEC (blog) | S64 |
| G5 | A 2026 forward-chaining study on UCI hourly and Seoul data (probabilistic transformer, 80% interval calibration under holidays and extreme weather). Abstract-level only. | SEC | S63 |
| G6 | No external benchmark of TabPFN vs LightGBM on bike data. | GAP | none |

## Candidate improvements
**A. Rolling-origin check of the MLP vs LightGBM tie.**
- Method: re-fit both on 3-4 earlier expanding windows with the same features and scoring; report paired MAE differences with block-bootstrap CIs. It tests whether the validation tie is stable and supplies a number the single window cannot.
- Reference: https://search.r-project.org/CRAN/refmans/forecast/html/tsCV.html (S57); S64 for the motivation.
- Cost: compute only, about 1 day.
- Stop condition: ordering flips across origins; report "no stable winner", which strengthens the tie wording.

**B. TabPFN challenger in research-only mode, blocked on the owner licence decision.**
- Method: if the owner allows it, fit TabPFN-2.5 on the training window, score on validation only (never selecting on test), and label the result "research use under the Prior Labs licence; not served". If the owner declines, use an Apache-licensed tabular challenger (for example CatBoost or an ensemble per TabArena) instead.
- Reference: https://arxiv.org/abs/2511.08667 (S07); https://huggingface.co/Prior-Labs/tabpfn_2_5 (S04).
- Cost: compute only; the licence is the cost.
- Stop condition: owner does not approve, or the licence reading excludes a public portfolio.

**C. Tie reporting with an equivalence margin.**
- Method: add a two one-sided test or an explicit margin (for example 2 MAE) to the paired validation interval so the tie is "within margin" rather than "interval crosses zero"; no change to existing numbers.
- Reference: none primary found (GAP).
- Cost: under 1 day.
- Stop condition: margin cannot be justified from a cost argument; then do not add it.

**D. Probabilistic band for the served MLP (conformal on validation).**
- Method: split-conformal width from validation residuals; report test coverage.
- Reference: https://arxiv.org/abs/2106.00170 (S25) if coverage drifts.
- Cost: compute only.
- Stop condition: test coverage outside 0.75-0.85 at a 0.80 target.

## Ranked recommendation
1. A (rolling-origin tie check): cheap, offline, no licence issue.
2. D (conformal band).
3. B (TabPFN or Apache alternative), pending owner licence decision.
4. C.

## Queries used (standard, 2026-11-18)
- "TabPFN-2.5 license Prior Labs non-commercial terms"
- "TabArena living benchmark tabular machine learning LightGBM vs foundation models"
- "bike sharing demand forecasting UCI hourly LightGBM neural network benchmark 2026"
- Fetched: huggingface.co/Prior-Labs/tabpfn_2_5; arxiv.org/abs/2511.08667.
