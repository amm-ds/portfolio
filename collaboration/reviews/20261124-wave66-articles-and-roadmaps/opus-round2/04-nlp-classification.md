# Round-2 review: 04-nlp-classification story.yaml

Reviewer: Claude Opus (senior ML writer/reviewer lane). Read-only review.

- **Target:** `projects/04-nlp-classification/story.yaml` at HEAD. The last change to it is e69bba84, which touched this file with +/−1029 lines, mostly reflow.
- **Gold template:** `projects/01-rag-agent/story.yaml`.
- **Prior round:** `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus/04-nlp-classification.md`.

Round-1 line numbers refer to the pre-e69bba84 file. Every line number in this review refers to the current 521-line file.

**Evidence re-checked this round:**

- Reports: `reports/metrics.json`, `reports/fresh_holdout.json`, `reports/llm_cascade.json`, `reports/selection.json`, `reports/hpo_seeds.json`, `reports/hpo_best.json`, `reports/hpo_study.json`, `reports/latency_probe.json`, `reports/history_probe4.json`, `reports/history_fulldata.json`, `reports/figures/eda_class_balance.json`.
- Project files: `params.yaml`, `README.md`, `DESIGN.md`.
- Source: `src/nlp_classification/llm_cascade.py`, `src/nlp_classification/model.py`, `src/nlp_classification/calibration.py`, `src/nlp_classification/config.py`.

**What e69bba84 actually changed in this article:**

- Re-wrapped the prose.
- Shortened every "In plain terms" note to one sentence.
- Replaced the vague macro-F1 gloss with a correct definition (L43–44).
- Lightly reworded the routing bullet (L15).

None of the round-1 truthfulness or roadmap findings was addressed.

---

## Grades

| # | Dimension | R1 | R2 |
|---|---|---|---|
| 1 | Structure and article logic | 6 | 6 |
| 2 | Engagement and human-like narrative | 5 | 5 |
| 3 | Language quality | 5 | 6 |
| 4 | Technical depth | 7 | 7 |
| 5 | Truthfulness | 5 | 5 |
| 6 | Roadmap cards | 4 | 4 |
| 7 | Consistency with gold template | 7 | 7 |
| | **Overall** | **5** | **5 / 10** |

---

## 1. Structure and article logic: 6

The section order is still sound: background → ladder → data views → EDA → training → policy → diagnostics → appendix. These problems remain:

- **The headline sells what the article later disowns.** L7 leads with "`0.954` fresh macro-F1, reviewing only 22 of 1,000", and L21 and L471 recommend the cascade "for top accuracy (95.4%)". Yet L3, L229, L303 and L513 say the cascade shows "no measurable change". The honest arc is different: the full-data transformer reaches 0.9529 fresh, and LLM review adds +0.001, which this article cannot distinguish from noise. The article should open on that.
- **L15 mixes two policies into one flow.** The bullet says "Score every item locally with the full-data transformer (or `TF-IDF` baseline at `75.4%` auto-routed)". The keyword router hands off to the *bounded* tuned transformer (`fresh_holdout.json` `cascade.transformer`), not to the LLM gate. So the parenthetical puts a different pipeline inside the routing diagram's flow.
- **Duplicate transition** at L288–292. "The exact tables and run identities in Conclusions preserve the full evidence…" is followed at once by "next, the exact tables and protocol that preserve the evidence".
- **The cascade numbers are retold four times.**
  - Evaluation (L219–235).
  - Results (L269–272, L279–281).
  - Results summary (L300–312).
  - Exact numbers (L369–382).
- **Late definitions.** HPO is used at L59, L127 and L151 but defined at L339. Data leakage is defined mid-list at L330.
- **Orphans.**
  - The 20k-row run appears at L165 and L390 without any setup. The scale ladder is 3.6k/10.8k/36k/108k.
  - Quantization is discussed at L281–283 and L462, but the int8 row was dropped from the serving table (L409–413).
  - L90 and L494 list three scale sizes, but three "tripling" steps need four rungs. The caption at L519–520 correctly lists four.

## 2. Engagement and human-like narrative: 5

The notes are now one sentence each, which helps. The body still runs on a "The [figure/diagram] shows…" + glossary-sentence loop. Examples:

- L264–266: "CPU is the computer's main processor. MPS is Apple's framework… A GPU is…"
- L402–407: seven column definitions packed into one paragraph.

The story with real stakes is buried: tuning bought nothing, data bought everything, and a paid LLM pass barely registers. The gold opens with a question and a concrete risk ("A footnote looks safe, yet…"). This article opens with a scoreboard.

## 3. Language quality: 6 (up from 5)

**Improvements:**

- The macro-F1 definition (L43–44, L491) is now correct and plain.
- The "In plain terms" notes are one sentence each.

**Still present:**

- **Seven-decimal F1 values** (L221–223, L239, L270–271, L303, L305, L374–376, L513). At n = 1,000 the resolution is 0.001. The ladder tables already use four decimals.
- **The caveat is repeated many times.**
  - "No persisted paired interval" or a variant appears 7 times: L233–235, L280–281, L310–311, L327–329, L381–382, L458–459, L514.
  - "No measurable change" now appears 4 times, down from 6.
- **Circular "within seed noise"** at L154 and L325. The ± 0.0042 *is* the seed noise. The real point is that the HPO margin is about 1.7 seed SDs on one seed while the paired CI crosses zero.
- **L435–436:** "Calibration uses ECE with one temperature". ECE is the metric. Temperature scaling is the method.
- **L248 and L294 contradict the "no measurable change" framing.** "Lifting accuracy slightly" and "nudges it to 95.4%" are tonally at odds with it.

## 4. Technical depth: 7

The strengths are unchanged:

- seeded protocol;
- paired bootstrap (2,000 resamples, seed 42);
- validation-only selection;
- disjoint fresh holdout (seeds 43/45);
- device twins;
- temperature-scaling excerpt;
- epoch probe.

Round-1 gaps, all still open:

- **The gate signal is never named.** The cascade thresholds the *raw softmax* max probability of the full-data model:
  - `llm_cascade.py` L163 calls `predict_proba_nn`.
  - `model.py` L388–400 computes a plain `torch.softmax` with no temperature.
  - The fitted T = 0.927 is not applied.
- **The reviewer model is never named.** `llm_cascade.json` records `challenger_model: kimi-for-coding`, and `README.md` L65 names it. The story never does.
- **The τ selection basis is unstated.** On validation, τ = 0.6 gains +0.00005 macro-F1 with 6 reviews, and `fit_threshold` (`llm_cascade.py` L117–142) breaks ties toward fewer reviews. "Validation alone selects τ=0.6" (L220) hides that the choice is essentially a tie-break.
- **The ECE values are withheld.** L158–160 defer to DESIGN.md instead of stating ECE 0.0360 → 0.0227 (`DESIGN.md` L115).
- **The fresh-side device claim is weak.** The twin gap on fresh is 0.0105 (`DESIGN.md` L162, `README.md` L204). That matches the last fresh scale step (+1.0 pt). So "Device choice does not explain the gain" (L148–149) holds on test (0.0002) but not cleanly on fresh.

**New minor issue:** the code excerpt (L173–187) is labelled "Excerpt" but edits the source.

- `calibration.py` L57 is `fitted = float(...)`.
- The excerpt instead shows `return float(...)` as the final line.

Either mark the excerpt as condensed or copy the code verbatim.

## 5. Truthfulness: 5

I re-verified these numbers against committed files. All of them match:

- **Ladder:** 0.1000, 0.2533, 0.8714, 0.8982, 0.9021, 0.9011, 0.9460.
- **Fresh:** 0.8785, 0.8962, 0.9031, 0.9074, 0.9529.
- **Scale steps:** test +1.5/+1.6/+1.3 (0.9019 → 0.9170 → 0.9331 → 0.9460); fresh +1.5/+2.1/+1.0.
- **Cascade:** triples 0.9601531 → 0.9602051, 0.9460236 → 0.9490153, 0.9529432 → 0.9539265; 6/16/22 reviews; 96.933 s; $0.023671 (= 9,807 × $1/M + 3,466 × $4/M).
- **Paired CIs:** validation [−0.0048, +0.0204]; fresh [−0.0025, +0.0161].
- **Seeds:** 0.8953/0.8852/0.8926, mean 0.8910 ± 0.0042.
- **Selection:** 0.8880 → 0.8953 on validation.
- **Calibration and training curves:** T = 0.927; probe peak 0.9477 at epoch 3 with validation loss rising after epoch 2; headline 0.9464.
- **Error analysis:** 25/250 and 24 → 15 → 14.
- **Class balance:** 900/100/250 per class. Training text has p10/p50/p90 of 27/37/48 words, and 91% of items fall between 20 and 50 words.
- **Serving:** 4,477.8 and 112.5 items/s (≈40×).
- **Hyperparameters:** lr 2e-5, wd 0.01, warmup 0.1, batch 32, patience 1, max_length 128.
- **Data sizes:** 127,600 = 120k + 7,600; 108k/12k; 3,600/400/1,000.
- **Router:** τ = 0.5 sends 24.6% to the transformer at 0.9061 (so 75.4% stay on keywords).

**Untraceable numbers: 0.**

**Contradicted or misleading claims (all carried over from round 1, none fixed):**

| Line(s) | Claim | Evidence | Verdict |
|---|---|---|---|
| L229, L326, L458 | Cascade "macro-F1 point deltas of at most `+0.001`" | Bounded test moves 0.9460 → 0.9490, which is **+0.0030** (`llm_cascade.json`) | Contradicted |
| L279–280 | "the cascade delta (`+0.001`) covers 44 reviews" | +0.001 is the fresh delta from 22 reviews. The 44 reviews span three splits with different deltas. | Conflated |
| L438–439 | "The 12 trials produce seed bests 0.8953 / 0.8852 / 0.8926" | The seed bests come from 3 seeds × **6** trials (`hpo_seeds.json` `n_trials_per_seed: 6`; `params.yaml` L30). The 12-trial study is a separate run (`hpo_study.json`). | Contradicted |
| L87 | "`1,000` articles come from the sample's unused 6,600" | The 6,600 are the complement of the bounded test draw inside the 7,600-row **test partition** (`fresh_holdout.json` `n_total_test_partition: 7600`). | Misleading |
| L480 (roadmap) | "the default stays" | Validation selects **HPO** (`selection.json` `winner: hpo_retrained`; article L59, L151–152, L423). | Contradicted |
| L485–486 (roadmap) | "Ship the cascade with calibrated confidence … the uncertain quarter routes to review" | The gate is raw softmax (`model.py` L388–400). LLM review covers 2.2% of fresh rows, not a quarter. The 24.6% "quarter" belongs to the keyword router, which escalates to the transformer and is "raw, uncalibrated" (article L441). | Contradicted twice |
| L397–400 (and L238, L310) | The router table shows only τ = 0.50/0.90 and bolds **0.9061** | `fresh_holdout.json` has τ = 0.6 at **0.9082** (40.4% escalated), which is higher, and τ = 0.7/0.8 also exist. | Selective presentation |

**Minor:**

- **L241:** "~111 items/s on the transformer" is the bounded tuned model (110.7). The cascade's full-data model runs at 112.5.
- **L27:** "trained on all 120k rows". Training used 108k rows, with 12k held out for validation (`DESIGN.md` L78).
- **L26:** "under a fixed compute budget". No budget is defined anywhere.
- **L21 and L471:** "for top accuracy (95.4%)" presents a +0.1 pt, interval-free point estimate as the reason to choose the cascade.

## 6. Roadmap cards: 4

| Line | Title | Verb-first | Detail ≤ 90 chars | Status vs repo | Issue |
|---|---|---|---|---|---|
| L476–477 | Measure the data-scale response | yes | yes (54) | shipped: true (`distilbert_scale_*` in `metrics.json`) | Fine |
| L479–480 | Keep the default under inconclusive tuning | yes | yes (63) | shipped, but content wrong | Validation selected HPO. If the point is that the full-data run uses default hyperparameters, the card should say so. |
| L482–483 | Beat every rung with full data | yes | yes (46) | shipped: true (0.9460 tops the ladder) | The detail is generic. Restore the number. |
| L485–486 | Ship the cascade with calibrated confidence | yes | yes (76) | cascade shipped (`llm_cascade.json` `selected: cascade`), but content wrong | It is not calibrated, and the review share is 2.2%, not a quarter. |
| L488–489 | Persist per-row review decisions | yes | yes (60) | next: correct (no per-row file exists) | The detail repeats the title. |

The titles are verb-first and the lengths pass. Two of the five cards still misstate the project.

## 7. Consistency with gold template: 7

**Now matching the gold:**

- The "In plain terms" notes are one sentence each, which fixes the round-1 deviation.
- The bold claim openers, the excerpt link pattern, and the roadmap, key_concepts and figure_captions blocks all match.

**Still deviating:**

- **Transition voice.** The gold uses first person: "Next, we set the rules…" (01 L17) and "next, we trace…" (01 L36). Here the transitions are verbless fragments: L19 "Next, the rungs each candidate must climb", L64, L102, L131, L200, L245, L291.
- **Section openings.** The gold opens on a narrative claim or question. Here, four sections open with "The [figure/diagram] shows/turns…": L75, L109, L209, L300.
- **Opening hook.** Gold L7–8 opens with a question plus a concrete risk. Here L7–8 is a metric dump.

---

## Round-1 finding status

| # | Round-1 finding | Status | Current location |
|---|---|---|---|
| 1 | Duplicate transition in Results | STILL PRESENT | L288–292 |
| 2 | Cascade numbers retold across Evaluation/Results/Conclusions | STILL PRESENT | L219–235, L269–281, L300–312, L369–382 |
| 3 | HPO / DistilBERT / leakage defined late | STILL PRESENT | L339, L330 |
| 4 | Orphan quantization and 20k run | STILL PRESENT | L281–283, L462; L165, L390 |
| 5 | Glossary-sentence pattern, no narrative arc | STILL PRESENT | L264–266, L402–407 |
| 6 | Seven-decimal false precision | STILL PRESENT | L221–223, L239, L270–271, L303–305, L374–376, L513 |
| 7 | Repeated "no measurable change" / "no persisted interval" boilerplate | PARTLY FIXED (4 vs 6; interval caveat still ×7) | L3, L229, L303, L513; L233–235 etc. |
| 8 | Vague macro-F1 gloss ("balancing discovery…") | FIXED | L43–44 |
| 9 | Awkward "routes 75.4% out on keywords" | PARTLY FIXED (reworded, now conflates policies) | L15 |
| 10 | Circular "within seed noise" | STILL PRESENT | L154, L325 |
| 11 | "Calibration uses ECE with one temperature" | STILL PRESENT | L435–436 |
| 12 | Serving-table glossary dump | STILL PRESENT | L402–407 |
| 13 | Gate signal (raw softmax, T not applied) unnamed | STILL PRESENT | L209–214 |
| 14 | Reviewer LLM unnamed | STILL PRESENT | L209–214, L369–370 |
| 15 | τ selection basis (tie-break, +0.00005) unstated | STILL PRESENT | L220 |
| 16 | ECE before/after withheld | STILL PRESENT | L158–160 |
| 17 | Device-twin claim weak on fresh | STILL PRESENT | L148–149 |
| 18 | "At most +0.001" contradicted by test +0.003 | STILL PRESENT | L229, L326, L458 |
| 19 | "+0.001 covers 44 reviews" conflation | STILL PRESENT | L279–280 |
| 20 | "12 trials produce seed bests" | STILL PRESENT | L438–439 |
| 21 | "sample's unused 6,600" | STILL PRESENT | L87 |
| 22 | Roadmap "the default stays" | STILL PRESENT | L479–480 |
| 23 | Roadmap "calibrated confidence … uncertain quarter" | STILL PRESENT | L485–486 |
| 24 | Router table hides τ = 0.6 (0.9082) and bolds 0.9061 | STILL PRESENT | L397–400 |
| 25 | ~111 items/s is the bounded, not the full-data, model | STILL PRESENT | L241 |
| 26 | "trained on all 120k rows" (actually 108k) | STILL PRESENT | L27 |
| 27 | "fixed compute budget" undefined | STILL PRESENT | L26 |
| 28 | Roadmap card 3 detail generic | STILL PRESENT | L483 |
| 29 | Roadmap card 5 detail repeats title | STILL PRESENT | L489 |
| 30 | "In plain terms" notes too long | FIXED | all sections |
| 31 | Verbless transitions vs gold "next, we …" | STILL PRESENT | L19, L64, L102, L131, L200, L245, L291 |
| 32 | Sections open with "The figure/diagram shows" | STILL PRESENT | L75, L109, L209, L300 |

**Totals:** 2 FIXED, 2 PARTLY FIXED, **28 STILL PRESENT**.

---

## Top 5 remaining fixes (by severity)

1. **L485–486, the roadmap card "Ship the cascade with calibrated confidence / the uncertain quarter routes to review".**
   - Problem: both halves are false. The gate is raw softmax, and 2.2% of fresh rows reach review.
   - Suggested title: "Ship the selective LLM cascade".
   - Suggested detail: "Rows below τ=0.6 get LLM review: 22 of 1,000 fresh, +0.001 macro-F1." (70 chars)
2. **L229, L326 and L458 ("at most `+0.001`"), plus L279–280 ("covers 44 reviews").**
   - Problem: bounded test moved +0.003.
   - Fix: state the per-split deltas (+0.0001 validation, +0.003 test, +0.001 fresh) and detach "+0.001" from "44 reviews".
   - Also fix L21, L248, L294 and L471 so the plain-terms notes do not sell a point estimate as "top accuracy".
3. **L479–480, the roadmap card "the default stays".**
   - Problem: it contradicts `selection.json` (`winner: hpo_retrained`).
   - Suggested title: "Ship full-data training at default settings".
   - Suggested detail: "HPO's bounded edge has a CI crossing zero; scale, not tuning, set the model."
4. **L438–439, "The 12 trials produce seed bests".**
   - Suggested rewrite: "A 12-trial study peaks at 0.8953; three 6-trial seed reruns give 0.8953 / 0.8852 / 0.8926 (mean 0.8910 ± 0.0042)."
   - Also fix L87: "from the test partition's other 6,600 rows".
5. **L397–400 and L209–220, Evaluation and the router table.**
   - Show all five τ rows of the router table, or drop the bold and say why τ = 0.5 is the reference (τ = 0.6 scores 0.9082).
   - In Evaluation, name the gate signal: "raw softmax max probability; T=0.927 is not applied".
   - Name the reviewer (`kimi-for-coding`) and the validation tie-break behind τ = 0.6.

**Next tier:**

- Delete L288–289.
- Round F1 values to four decimals.
- Keep the interval caveat once in Evaluation and once in Limits.
- Define HPO at L59.
- State ECE 0.0360 → 0.0227 at L158–160.
- Fix "all 120k rows" (L27) to 108k.
- Remove "fixed compute budget" (L26) or define it.
- Use first-person "next, we …" transitions.
- Replace "The X diagram shows" openers with claims.

## Ready to publish?

**No.** Two shipped roadmap cards misstate the project:

- the cascade is not calibrated and does not review a quarter of items;
- HPO, not the default, was selected.

In the body, the "at most +0.001" claim appears three times and is contradicted by the article's own test row (+0.003). The 12-trial/seed-best conflation also remains. All of these were flagged in round 1 and none was changed. They are small, local edits, and once they land the article would be publishable at about 7/10.
