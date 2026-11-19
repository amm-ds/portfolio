# 04 AG News classification: investigation

Date: 2026-11-19 (searches on 2026-11-18). Labels: SB / SEC / GAP. Source IDs map to `99-sources.md`.

## Current state (committed)
- Selected transformer plus selective LLM cascade: fresh-holdout macro-F1 0.953 to 0.954 (+0.001), accuracy 0.953 to 0.954, 22 of 1,000 fresh items reviewed; "no measurable change". Source: `projects/04-nlp-classification/story.yaml`; `projects/04-nlp-classification/reports/llm_cascade.json` (threshold 0.6, routing fit on validation only; bounded test 0.9460 to 0.9490 macro-F1 with 16 reviews; validation 6 reviews).
- Test macro-F1 0.9460; ECE 0.0360 to 0.0227 after one temperature (story roadmap).
- Per-row review decisions are not persisted, so a paired cascade interval is not possible today (roadmap "next"). The earlier gap analysis said coverage could be computed "from committed predictions"; that holds only for the transformer's own confidence on the fresh holdout if the model artifact in `reports/models` can be re-run offline. Cascade-specific coverage needs a rerun of the hosted review (cap needed).

## Gaps against the state of the art
| # | Gap | Label | Source |
|---|---|---|---|
| G1 | No selective-classification report: AURC / risk-coverage is the standard summary; AURC has known weaknesses and AUGRC was proposed to fix them. | SEC | S19, S20 |
| G2 | Cascades with abstention (early abstention thresholds, AUARC) and confidence-based gating failing under specialists or label noise. | SEC | S19 |
| G3 | AG News SOTA: no 2025-2026 paper with a clear fine-tuned-LLM figure found. A community BERT card claims 94.74%; not peer-reviewed, do not use. | GAP (SOTA), SEC (card) | S60 (HF card, pointer only) |
| G4 | LabelFusion 92.4% and the cost-aware paper 2602.06370 come from the earlier gap analysis; I did not re-open them. Our 0.954 is on a different split and metric. | SEC (inherited, unverified this pass) | S62 |
| G5 | Fine-tuned encoders beat zero-shot LLMs by about 10-25 points on AG News in one 2025 study; exact numbers not verified. | SEC | S60b |

## Candidate improvements
**A. Risk-coverage curve and AURC/AUGRC for the transformer alone on the fresh holdout.**
- Method: re-run the committed model over the 1,000 fresh items offline, sort by max-softmax (and temperature-scaled softmax), report accuracy at coverage 100/90/80/50% with bootstrap CIs, AURC and AUGRC. New file, for example `reports/selective_curve.json`.
- Reference: https://arxiv.org/pdf/2407.01032 (S20); https://arxiv.org/html/2502.09054v2 (S19).
- Cost: compute only, under 1 day (CPU inference on 1,000 items).
- Stop condition: model artifact missing or cannot reproduce the committed 0.953 accuracy to within rounding; then stop and tell the owner.

**B. Persist per-row cascade decisions and compute the paired interval.**
- Method: rerun the selective review on the fresh set with per-row logging (id, transformer label and confidence, reviewer label, final label). Paired McNemar or bootstrap on the 22 reviewed rows plus coverage-vs-accuracy.
- Reference: S19 for cascade evaluation framing.
- Cost: hosted review calls for 22-40 items (a known, small count); owner-approved cap needed.
- Stop condition: the reviewer changes fewer than 5 labels; then the interval is too wide to say anything and the result is reported as "no measurable change".

**C. Cost-aware comparison table: transformer vs cascade vs LLM-only on one slice.**
- Method: report the committed $0.023671 full-evaluation cost beside accuracy at each coverage level.
- Reference: S62 (inherited).
- Cost: compute plus reuse of committed cost fields.
- Stop condition: no LLM-only arm is committed, so this stays a table of what exists; do not add a hosted arm without a cap.

## Ranked recommendation
1. A (risk-coverage on the transformer): cheapest and closes the stated gap.
2. B (persist per-row decisions): unlocks the paired interval; needs a hosted cap.
3. C (cost table): low.

## Queries used (standard, 2026-11-18)
- "selective classification risk-coverage curve AURC evaluation text classification LLM cascade deferral"
- "AG News text classification state of the art accuracy 2025 2026 paper fine-tuned LLM"
