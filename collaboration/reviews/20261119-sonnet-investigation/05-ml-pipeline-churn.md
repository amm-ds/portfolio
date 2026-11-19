# 05 Churn pipeline: investigation

Date: 2026-11-19 (searches on 2026-11-18). Labels: SB / SEC / GAP. Source IDs map to `99-sources.md`.

## Current state (committed)
- 7,043 IBM telco customers; calibrated policy frozen at cutoff 0.175 from training OOF predictions; cost 601 vs 1,035 for contact-everyone, 95% paired bootstrap CI -508 to -353. Served threshold moves 0.250 to 0.150 as the missed-churner price goes 3 to 8. Isotonic calibration on a train-side split; 25-trial seeded search. Source: `projects/05-ml-pipeline-churn/story.yaml`; metrics `projects/05-ml-pipeline-churn/reports/metrics.json`.
- Roadmap "blocked": rollout gates wait on owner data (time-stamped feed; fresh-data fairness for the served policy).

## Gaps against the state of the art
| # | Gap | Label | Source |
|---|---|---|---|
| G1 | A 2026 audit of the same IBM Telco benchmark reports isotonic as the strongest default calibrator across 15 seeds and the cost-optimal threshold 5-10x below the F1-optimal one; its dollar figures depend on its own assumed offer cost and CLV. Consistent with our direction (low frozen cutoff, isotonic). | SEC | S21 |
| G2 | Profit-based evaluation (e-Profits) reorders model rankings versus accuracy metrics on IBM Telco. Our cost-by-OOF selection is in the same family. | SEC | S22 |
| G3 | Cost-sensitive evaluation guidance for binary classifiers (expected-cost curves). | SEC | S23 |
| G4 | Fairness: Fairlearn documents per-group selection rate, TPR, FPR via MetricFrame and difference/ratio metrics. The IBM data has no time stamp, and fresh-data fairness is blocked. A static, in-sample subgroup audit on the committed OOF predictions is possible but is not a rollout claim. | SEC | S27 |
| G5 | Time-stamped rollout evaluation: no source found for a time-stamped version of the IBM telco data. | GAP | none |

## Candidate improvements
**A. Subgroup audit on committed OOF predictions (gender, senior citizen, partner) with MetricFrame.**
- Method: compute selection rate, TPR, FPR and expected cost per group at the frozen 0.175 cutoff with bootstrap CIs; label it a diagnostic on the training-era data, not a fairness clearance. New file.
- Reference: https://fairlearn.org/main/user_guide/assessment (S27).
- Cost: compute only, under 1 day. Needs OOF predictions to be on disk with group columns.
- Stop condition: group sizes under about 300 give intervals too wide to read; report the width.

**B. Calibration audit: reliability curve, ECE and Brier at the frozen model, isotonic vs Platt vs none, 15 seeds.**
- Method: reproduces the audit logic of S21 on our pipeline; report in a new file; keep the current calibrator unless the audit shows a coverage hole.
- Reference: https://arxiv.org/pdf/2610.00118 (S21; preprint, one source).
- Cost: compute only.
- Stop condition: a calibrator ranks differently on ECE and on expected cost; report both, do not change the served model.

**C. Expected-cost curve over the missed-churner price (extend the existing 3 to 8 sweep to a full curve).**
- Method: plot cost versus threshold for several price ratios; mark each frozen threshold. Existing numbers unchanged.
- Reference: https://arxiv.org/pdf/2510.22016 (S23).
- Cost: compute only.
- Stop condition: none material; presentation change.

## Ranked recommendation
1. A (subgroup audit, labelled diagnostic): fills the stated fairness gap without new data.
2. B (calibration audit).
3. C (cost curve).
Rollout and time-stamped evaluation stay blocked on owner data (GAP).

## Queries used (standard, 2026-11-18)
- "churn prediction cost-sensitive threshold calibration fairness telco IBM dataset evaluation expected cost"
- "Fairlearn equalized odds demographic parity evaluation binary classifier subgroup metrics MetricFrame"
