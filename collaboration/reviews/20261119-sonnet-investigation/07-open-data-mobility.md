# 07 NYC mobility (flagship): investigation

Date: 2026-11-19 (searches on 2026-11-18). Labels: SB / SEC / GAP. Source IDs map to `99-sources.md`.

## Current state (committed)
- 41.2M real 2024 yellow-taxi trips plus public weather; strict Oct-Dec holdout; served GBM cuts error 28.3% vs the persistence floor (4.68 vs 6.52 MAE); 90% band reached 91% coverage (90.8% in the roadmap), no-borough bucket 84.7%. Validation winner served over test leader (xGB tested 4.1% better). Retrain per service; drift stays in-window. Source: `projects/07-open-data-mobility/story.yaml`; metrics `projects/07-open-data-mobility/reports/metrics.json`.
- Roadmap "next": causal weather and longer horizons; needs a new study contract.
- Note: the experiment review (`collaboration/reviews/20261117-experiment-review/07-open-data-mobility.md`) computed -28.2% from 4.676 vs 6.517 against the card's -28.3%. I did not recompute from unrounded values and do not propose changing the number; if the rounding mismatch is still open, that is a handoff item, not a finding here.

## Gaps against the state of the art
| # | Gap | Label | Source |
|---|---|---|---|
| G1 | Interval method: adaptive and conformalised quantile methods (CONTINA for taxi and bike demand; ACI under shift) give coverage guarantees and handle drift. Our band is calibrated and reports coverage by borough; it has no online adaptation. | SEC | S24, S25 |
| G2 | Causal weather: rain is used as an instrument for taxi and ride-hail demand in NYC studies; validity depends on weather not affecting supply directly (exclusion restriction); weak-instrument caution. | SEC | S26 |
| G3 | Baselines: persistence only; a seasonal model with weather covariates is a stronger floor (from the experiment review; the literature check is a GAP). | GAP | none |
| G4 | Horizon: multi-hour forecasting needs a new contract (roadmap). No benchmark found for NYC zone-hour multi-hour demand. | GAP | none |

## Candidate improvements
**A. Seasonal-with-weather baseline row (hour-of-week mean plus weather regression).**
- Method: fit on the training window only, score on the same Oct-Dec holdout; add as a new row. It shows how much of the 28.3% is already available from calendar structure.
- Reference: none primary found for the exact baseline (GAP); motivation in the experiment review.
- Cost: compute only, under 1 day.
- Stop condition: baseline within 2% of the served GBM; then say so in the card.

**B. Adaptive conformal update of the band, evaluated per borough.**
- Method: apply ACI on rolling residuals over the holdout; compare coverage by borough and by month with the static calibrated band; report width cost.
- Reference: https://arxiv.org/abs/2106.00170 (S25); https://arxiv.org/html/2504.13961v2 (S24).
- Cost: compute only, about 1 day.
- Stop condition: coverage in no-borough bucket stays under 88% or widths grow by more than 25%.

**C. Rain instrumental-variable or fixed-effect estimate as a separate study.**
- Method: zone-hour panel with zone and hour-of-week fixed effects; treat precipitation as the exposure and report the effect with clustered CIs; label as association unless an instrument is argued. Needs the new study contract the roadmap names.
- Reference: https://aeaweb.org/conference/2018/preliminary/paper/eF2rFtsd (S26; preliminary conference paper).
- Cost: compute; 2-3 engineering days.
- Stop condition: first-stage strength weak or supply channel cannot be separated; report as descriptive.

**D. Direct multi-horizon (h=1..6) with the same holdout.**
- Method: train direct models per horizon; report MAE by horizon versus persistence at the same horizon.
- Reference: none primary (GAP).
- Cost: compute; larger than A-B.
- Stop condition: h=6 does not beat persistence; state the decay.

## Ranked recommendation
1. A (stronger baseline): cheapest, strengthens the headline's context.
2. B (adaptive conformal).
3. D (horizon), then C (causal weather; needs owner contract).

## Queries used (standard, 2026-11-18)
- "conformalized quantile regression time series prediction intervals demand forecasting spatiotemporal taxi"
- "NYC taxi demand forecasting weather causal effect precipitation instrumental variable"
- "adaptive conformal inference distribution shift Gibbs Candès time series coverage"
