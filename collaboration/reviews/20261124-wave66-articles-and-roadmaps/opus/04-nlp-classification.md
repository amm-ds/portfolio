# Review: 04-nlp-classification story.yaml (Wave 6.6)

Reviewer: Claude Opus (senior ML writer/reviewer lane). Read-only review.

Target: `projects/04-nlp-classification/story.yaml`. Gold: `projects/01-rag-agent/story.yaml`.

**Note on the diff.** `git diff -- projects/04-nlp-classification/story.yaml` is empty. The working tree is clean, and the Wave 6.6 edits are already in `HEAD` (18adc59d, +45/−25 on this file). I reviewed that commit's changes: "Business summary" was renamed to "In plain terms", one-line `next, … (→)` transitions were added to seven sections, and the roadmap was rewritten from past tense to verb-first titles with shorter details. Line numbers below refer to the current file.

Evidence checked: `reports/metrics.json`, `reports/fresh_holdout.json`, `reports/llm_cascade.json`, `reports/selection.json`, `reports/hpo_seeds.json`, `reports/hpo_best.json`, `reports/latency_probe.json`, `reports/history_probe4.json`, `reports/error_analysis.md`, `reports/figures/eda_class_balance.json`, `params.yaml`, `README.md`, `DESIGN.md`, `src/nlp_classification/llm_cascade.py`, `src/nlp_classification/model.py`, `src/nlp_classification/config.py`.

---

## Grades

| # | Dimension | Grade |
|---|---|---|
| 1 | Structure and article logic | 6 |
| 2 | Engagement and human-like narrative | 5 |
| 3 | Language quality | 5 |
| 4 | Technical detail depth | 7 |
| 5 | Truthfulness | 5 |
| 6 | Roadmap cards | 4 |
| 7 | Consistency with gold template | 7 |
| | **Overall** | **5 / 10** |

---

## 1. Structure and article logic — 6

The sections run in a sound order: background, ladder, data views, EDA, training, policy, diagnostics, conclusions. Every section except Conclusions ends with a `next, … ([X →](#sec-x))` transition.

Problems:

- **Results has two transitions in a row.** L309–310 ("The exact tables and run identities in Conclusions preserve the full evidence…") is followed directly by L312–313 ("next, the exact tables and protocol that preserve the evidence"). They say the same thing. Delete L309–310.
- **Evaluation, Results and Conclusions repeat each other.** The same cascade triple (0.9529432 → 0.9539265, 22 reviews, 44 reviews, 96.933 s, $0.023671, "no persisted paired interval") appears in full at L238–252, L291–292/L300–301, L326–335, L398–406, and again in the closing plain-terms note at L495–497. Each later section adds very little. Conclusions works as an appendix, but "Results summary" (L322–336) is a third retelling of Evaluation.
- **Definitions come late.** "HPO" is used at L68, L140 and L165 but defined at L364. "DistilBERT"/"RoBERTa" are defined at L362, after the tables and figures that use them. "Data leakage" is defined in the middle of a lessons list (L354). These definitions should move up to first use.
- **Orphan concepts.** Quantization appears only in the limits (L302–305, L486), but the int8 row that motivates it was dropped from the serving table (L433–437). The "20k rows" run (L180, L414) appears without any setup, even though the scale ladder is defined as 3.6k/10.8k/36k (L101). The reader meets a fourth data size with no explanation.

## 2. Engagement and human-like narrative — 5

The opening bold claims help, and the "In plain terms" notes give a reader something to hold on to. Most paragraphs, though, follow a "The X diagram/figure shows…" plus glossary-sentence pattern: "A seed fixes a random starting point…", "A holdout is data kept out…", "CPU is the computer's main processor. MPS is… A GPU is…" (L286–287). An expert gets nothing from these sentences, and a lay reader still cannot follow the argument through them.

There is no human moment, no surprising failure, and no decision with stakes. The genuinely interesting story is buried: tuning bought nothing, data bought everything, and the LLM barely moved the needle. The article tells that story through several restatements instead of one clear arc.

## 3. Language quality — 5

- **False precision.** Seven-decimal F1 values (0.9529432, 0.9601531, 0.9490153, …) appear at L14, L238–240, L256, L266, L291–292, L327, L329, L496. With n=1,000 the resolution is 0.001. Use four decimals, matching the ladder tables.
- **Repeated boilerplate.**
  - "no measurable change": L3, L247, L268, L315, L327, L529.
  - "no persisted paired interval" or variants: L251–252, L269, L301–302, L334–335, L351–353, L405–406, L482, L529.
  - Each one is individually honest, but together they read like a liability disclaimer pasted into every card.
- **Vague or wrong wording.**
  - L9 "balancing discovery with correct labels": "discovery" is not a recall synonym. Write "averaging each topic's precision–recall balance."
  - L18 "routes 75.4% out on keywords" is awkward.
  - L169 "within seed noise, the normal variation between random runs" is circular, because 0.0042 *is* the seed noise. The real point is that the mean gain (+0.003 over 0.8880) is smaller than the seed std.
  - L460 "Calibration uses ECE with one temperature": ECE is the metric, not the method.
- **Glossary dumps.** L427–431 packs seven column definitions into one paragraph. A table footnote or key would serve better.

## 4. Technical detail depth — 7

Strengths: a seeded protocol, a paired bootstrap with n=2,000 resamples and seed 42, validation-only selection, a disjoint fresh holdout with seeds 43/45, same-rows device twins, a temperature-scaling code excerpt, and an epoch probe. An expert can reconstruct most of the work.

Gaps an expert would notice:

- **The confidence signal for τ is never named.** The cascade gates on the *raw softmax max probability* of the full-data model (`llm_cascade.py` `_predict_full` → `model.py` `predict_proba_nn`, which has no temperature). The fitted T=0.927 is not applied. The article discusses calibration at length but never says the router ignores it.
- **The reviewer LLM is never named.** `llm_cascade.json` records `challenger_model: kimi-for-coding`.
- **The τ selection basis is thin and unstated.** The candidates are {0.5…0.9} (`config.py` L122–124). On validation, τ=0.6 wins by +0.00005 F1 with 6 reviews, using a tie-break toward fewer reviews. The article says "Validation alone selects τ=0.6" (L237) but not that the evidence is nearly a coin flip.
- **The ECE before/after is withheld.** L173–175 point to DESIGN.md instead of stating ECE 0.0360 → 0.0227.
- **The device-twin claim does not hold on fresh.** The twin gap on fresh is 0.0105 (L163). That is about the same size as the last fresh scale step (+1.0 pt, L162). So "Device choice does not explain the gain" (L164) is supported on test (0.0002) but not cleanly on fresh.

## 5. Truthfulness — 5

Most numbers check out against committed files:

- Ladder: 0.1000, 0.2533, 0.8714, 0.8982, 0.9021, 0.9011, 0.9460.
- Fresh: 0.8785, 0.8962, 0.9031, 0.9074, 0.9529.
- Scale steps: test +1.5/+1.6/+1.3, fresh +1.5/+2.1/+1.0.
- Cascade triples and 6/16/22 reviews.
- 96.933 s; $0.023671 (= 9,807×$1/M + 3,466×$4/M).
- Paired CIs (val [−0.0048, +0.0204], fresh [−0.0025, +0.0161]).
- Seeds 0.8953/0.8852/0.8926, mean 0.8910 ± 0.0042.
- T=0.927; probe peak 0.9477 at epoch 3 with validation loss rising; headline 0.9464.
- 25/250 and 24→15→14.
- Class bars 900/100/250 per class; text lengths p10–p90 of 27–48 words.
- Throughputs 4,477.8 and 112.5 items/s, about 40×.
- Hyperparameters lr 2e-5, wd 0.01, warmup 0.1, batch 32, patience 1.
- 127,600 = 120k + 7.6k; τ=0.5 router at 24.6%/0.9061.

**Untraceable numbers: 0.**

**Contradicted or misleading claims: 7.**

| Line(s) | Claim | Evidence | Verdict |
|---|---|---|---|
| L246, L350, L482 | "macro-F1 point deltas of at most +0.001" | Bounded test moves 0.9460 → 0.9490 = **+0.0030** (`llm_cascade.json`) | Contradicted. Only the fresh delta is +0.001. |
| L300–301 | "the cascade delta (+0.001 macro-F1) covers 44 reviews" | +0.001 is the fresh delta, which comes from 22 reviews. The 44 reviews span three splits with different deltas. | Conflated |
| L462–463 | "The 12 trials produce seed bests 0.8953 / 0.8852 / 0.8926" | Seed bests come from 3 seeds × 6 trials (`hpo_seeds.json` `n_trials_per_seed: 6`; `params.yaml` `hpo_seeds.n_trials: 6`). The 12-trial study is a separate single-seed run. | Contradicted |
| L98 | "1,000 articles come from the sample's unused 6,600" | The 6,600 are the complement of the bounded test draw inside the 7,600-row **test partition** (`fresh_holdout.json` provenance), not unused rows of the training sample. | Misleading |
| L507 (roadmap) | "the default stays" | Validation selects **HPO** (`selection.json` `winner: hpo_retrained`; article L68, L447). The router's transformer leg is `distilbert_tuned`. | Contradicted |
| L512–513 (roadmap) | "Ship the cascade with calibrated confidence … the uncertain quarter routes to review" | The cascade gates on raw softmax (`llm_cascade.py` → `predict_proba_nn`, no temperature). LLM review covers 22/1,000 = **2.2%** of fresh rows. The "quarter" (24.6%) belongs to the keyword router, which escalates to the transformer, not to review, and is "raw, uncalibrated" (L465). | Contradicted on both halves |
| L419–425 | Router table bolds τ=0.50 at **0.9061** and shows only τ=0.50 and 0.90 | `fresh_holdout.json` has τ=0.6 at 0.9082 (40.4% escalated), which is higher. The bolding implies a best value that the omitted row beats. | Selective presentation |

Minor:

- L258 "~111 items/s on the transformer" matches the bounded tuned model (110.7). The cascade's full-data model runs at 112.5.
- L36 "trained on all 120k rows": training used 108k, with 12k held for validation.
- L34 "under a fixed compute budget": no budget is defined anywhere.

## 6. Roadmap cards — 4

| Line | Title | Verb-first | Detail ≤90 | Status | Issue |
|---|---|---|---|---|---|
| L503–504 | Measure the data-scale response | yes | yes (54) | shipped OK | Fine |
| L506–507 | Keep the default under inconclusive tuning | yes | yes (63) | shipped | **Contradicts selection**: HPO was selected. The served full-data model does use default hyperparameters, but the card does not say so. |
| L509–510 | Beat every rung with full data | yes | yes (46) | shipped OK | Detail is generic and lost its numbers in this round ("0.9460 test macro-F1" was cut). |
| L512–513 | Ship the cascade with calibrated confidence | yes | yes (76) | shipped | **Factually wrong twice** (see §5). |
| L515–516 | Persist per-row review decisions | yes | yes (60) | next OK | The detail repeats the title ("once rows are persisted"). Better: "Unlocks a paired bootstrap CI for the +0.001 fresh delta." |

Verb-first titles and the character limits pass. The content does not: two of five cards misstate the project, and the round made the details vaguer. There are no "later" items, although obvious candidates exist: route on calibrated confidence, run multi-label Business/Sci-Tech.

## 7. Consistency with gold template — 7

What matches the gold: the "In plain terms" label, a bold claim opening most sections, the `next, … ([X →](#sec-x))` transition format, the excerpt-link pattern, and the roadmap/key_concepts/figure_captions blocks.

Deviations:

- **"In plain terms" length.** The gold notes are one concrete sentence of about 20–25 words (01 L19, L45, L69, L90). Here, L28–30 and L218–221 run to three sentences, and L76–78, L265–269 and L315–318 to two or more. Several restate numbers instead of giving the plain-language meaning.
- **Transition voice.** The gold uses a first-person "next, we …" (01 L17, L35). These are verbless fragments ("next, the rungs each candidate must climb").
- **Section openings.** The gold opens sections with a narrative claim. Here, four sections open with "The [figure/diagram] shows…" (L86, L122, L226, L324).

---

## Top 5 fixes (by severity)

1. **L512–513 (roadmap):** rewrite "Ship the cascade with calibrated confidence" / "the uncertain quarter routes to review". The cascade uses raw softmax, and only 2.2% of fresh rows reach LLM review. Suggested: title "Ship the selective LLM cascade", detail "Rows below τ=0.6 get LLM review: 22 of 1,000 fresh, +0.001 macro-F1."
2. **L246, L350, L482 (and L300–301):** "at most +0.001" is false. Bounded test moved +0.003 (0.9460 → 0.9490). State the per-split deltas (+0.0001 val, +0.003 test, +0.001 fresh), and stop attaching "+0.001" to "44 reviews".
3. **L506–507 (roadmap):** "the default stays" contradicts validation selecting HPO (L68, L447, `selection.json`). Either "Ship full-data training at default settings" with detail "HPO's bounded edge has a CI crossing zero; scale, not tuning, set the model", or drop the card.
4. **L462–463:** "The 12 trials produce seed bests 0.8953 / 0.8852 / 0.8926" conflates two studies. Write "A 12-trial study peaks at 0.8953; three 6-trial seed reruns give 0.8953 / 0.8852 / 0.8926 (mean 0.8910 ± 0.0042)."
5. **L419–425 and L228/L237:** the router table bolds 0.9061 while hiding τ=0.6 = 0.9082. Show all five τ rows, or remove the bold and explain why τ=0.5 is the reference. In Evaluation, also name the gate signal ("raw softmax max probability; T=0.927 not applied") and the reviewer (`kimi-for-coding`).

Next tier (language and structure): delete the duplicate transition at L309–310. Cut the seven-decimal values to four. Collapse the repeated "no persisted paired interval" caveat into one Limits bullet plus one mention in Evaluation. Move the HPO/DistilBERT definitions to first use. Fix L98 "the sample's unused 6,600" to "the test partition's other 6,600". Shorten the "In plain terms" notes at L28–30 and L218–221 to one sentence each.
