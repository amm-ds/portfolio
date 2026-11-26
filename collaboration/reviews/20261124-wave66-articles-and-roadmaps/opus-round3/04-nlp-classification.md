# Round-3 review: 04-nlp-classification story.yaml

Reviewer: Claude Opus (senior ML writer/reviewer lane). Read-only review.

- **Target:** `projects/04-nlp-classification/story.yaml`, **working tree** (518 lines) on branch `wave8-articles-truthfulness-2026-11-25`, HEAD `c05accd0`, with uncommitted Wave 8 edits.
- **Gold template:** `projects/01-rag-agent/story.yaml`.
- **Prior round:** `opus-round2/04-nlp-classification.md`. It reviewed an earlier 521-line commit. I re-verified every finding against the working tree.
- **Line numbers:** all refer to the current working-tree file.

**Evidence checked this round:**

- **Reports:** `reports/metrics.json`, `fresh_holdout.json`, `llm_cascade.json`, `selection.json`, `hpo_seeds.json`, `hpo_study.json`, `latency_probe.json`, `history_probe4.json`, `history_fulldata.json`, `scale_meta_4000.json`.
- **Figure JSON:** `llm_cascade_comparison`, `confusion_matrix_selected`, `per_class_f1_comparison`, `scale_ladder`, `training_curve`, `hpo_history`, `eda_class_balance`.
- **Project files:** `params.yaml`, `README.md`, `DESIGN.md`.
- **Source:** `calibration.py`, `llm_cascade.py`, `evaluate.py`, `data.py`, `cli.py`, `config.py`.
- **Diagrams:** `apps/showcase-web/src/diagrams/routing.ts` (`04-routing`) and `apps/showcase-web/src/diagrams/auto/04-nlp-classification-{1,2,3,4}.ts`. None of these diagram files is modified in the working tree.

**What Wave 8 changed in this file:**

- It fixed most of the round-2 truthfulness and roadmap findings:
  - "at most +0.001" is gone;
  - the 12-trial and seed-rerun runs are now told apart;
  - the 6,600-row source is correct;
  - 120k is corrected to 108k;
  - the gate signal and the reviewer are named;
  - the τ tie-break is stated;
  - ECE values are given;
  - the device-twin claim on fresh is qualified;
  - all five router τ rows are shown;
  - two roadmap cards are corrected.
- It rounded F1 values to four decimals and switched transitions to "We next …".
- It made the calibration excerpt verbatim.

---

## Grades

| # | Dimension | R2 | R3 |
|---|---|---|---|
| 1 | Structure and article logic | 6 | 6 |
| 2 | Engagement and human-like narrative | 5 | 6 |
| 3 | Language quality | 6 | 7 |
| 4 | Technical depth | 7 | 7 |
| 5 | Truthfulness | 5 | 6 |
| 6 | Roadmap cards | 4 | 9 |
| 7 | Consistency with gold template | 7 | 7 |
| | **Overall** | **5** | **6.5 / 10** |

---

## 1. Structure and article logic: 6

**Improvements:**

- The duplicate Results transition is gone.
- The headline (L7) now leads with the honest result: the full-data transformer does the work, and review adds only +0.001.
- Every section ends on a first-person forward link.

**Problems:**

- **The background prose and its diagram describe different pipelines (new in Wave 8).**
  - L13–17 now say "Follow the routing flow": full-data transformer → gate at τ = 0.6 → `kimi-for-coding`.
  - The diagram embedded at L10, `04-routing` (`routing.ts`), is the *keyword-first* router: TF-IDF → gate at τ = 0.50 → DistilBERT, with 75.4%/24.6% edges and no LLM node.
  - Round 2 flagged the TF-IDF parenthetical for mixing the two policies. Wave 8 deleted the parenthetical but kept the keyword-router diagram, so the first figure a reader sees contradicts the three bullets under it.
  - Fix: point L10 at `auto-04-nlp-classification-3`, or rebuild `04-routing` as the cascade.
- **The data diagram cannot be followed as the prose instructs.**
  - L78 says "Follow the four views in the diagram". `auto-04-nlp-classification-2` has no scale-ladder view.
  - L96 refers to "The validation branch". The diagram has no validation node. See §5.
- **The objectives diagram does not match L58.** L58 says "The final node in the diagram records the main caveat. Validation selects [HPO] … interval crosses zero". The final node of `auto-04-nlp-classification-1` reads "Test-set role disclosed".
- **The cascade numbers are still retold about eight times:**
  - L17, L222–239, L273–275, L301–306, L324–325, L366–376, L457–458;
  - also roadmap L483 and caption L509–511.
  - Wave 8 added a per-split delta bullet in "What the experiment taught" (L324–325), so the count went up.
- **Late definition:** "data leakage" is still defined mid-list at L326. HPO is now defined at first use (L59). Fixed.

## 2. Engagement and human-like narrative: 6

**Better:**

- The opening is now a bold claim that matches the evidence.
- The "In plain terms" notes are honest. L21, L251, L293 and L468 no longer sell 95.4% as a reason to adopt the cascade.

**Still weak:**

- The gold opens with a question and a concrete risk ("When every answer carries a citation, what can still go wrong?"). This article opens with a scoreboard.
- Sections still open on "The X figure/diagram shows/turns…": L109, L137, L211, L255, L299.
- Glossary runs still break the flow:
  - L267–269 (CPU / MPS / GPU);
  - L400–405 (MB, p50, pred/s, $/1k, acc, fp32 in one paragraph).
- The real story (data beat tuning, and a paid LLM pass barely registers) is told well in the training bullets but not used as the narrative spine.

## 3. Language quality: 7

**Fixed:**

- Seven-decimal values are gone from the prose.
- The circular "within seed noise" is replaced by "about 1.7 times the 0.0042 SD" (L154–156, L322–323).
- "Calibration was nearly free" is replaced by concrete ECE values.

**Remaining:**

- **Inconsistent rounding of one quantity (new).** The validation cascade delta is `+0.00005` at L223 but `+0.0001` at L234, L324 and L457. Precision is also mixed within one list: `+0.0030` for test against `+0.001` for fresh (fresh is 0.00098, or `+0.0010` at four decimals). Pick one precision.
- **L433–434:** "Calibration uses ECE with one temperature". ECE is the metric and temperature scaling is the method. Still present.
- **Glossary dumps:** L267–269 and L400–405.
- **L61:** "would spend the budget". The fixed compute budget was removed at L25–26, so "the budget" now has no referent.
- **L8 and L71** both restate `127,600` / `120k`.

## 4. Technical depth: 7

**Added by Wave 8:**

- The raw-softmax gate signal (L213).
- The named reviewer (L16, L215).
- The τ tie-break basis (L223–224).
- ECE 0.0360 → 0.0227 (L160).
- A fair test-versus-fresh device-twin reading (L147–150).
- The 12-trial and 6-trial HPO runs separated (L436–438).
- A verbatim calibration excerpt; it matches `calibration.py` L47–60 apart from stripped `type: ignore` comments.

**Gaps:**

- **The cascade's "validation" split is probably not held out for the full-data model (new finding; structural inference, not measured).**
  - `run_cascade` (`llm_cascade.py` L190–201) fits τ on `cfg.val_dir`, the bounded 400-row validation split. That split is carved out of the AG News **train** partition.
  - The full-data transformer trains on a separate 90/10 carve-out of the same 120k train partition (`data.py` `load_full_train`, `stratified_split(..., seed=cfg.seed + 2)`).
  - So roughly 90% of those 400 rows are expected to be in its training set.
  - This fits the evidence: validation macro-F1 is 0.9602, above the model's own 12k-val 0.9464 and test 0.9460, and only 6 rows fall below τ.
  - "Validation alone selects τ=0.6" (L223) is accurate about test and fresh leakage, but the article should disclose that the τ fit runs on rows the model has largely seen. Better still, the τ fit should move to the full model's 12k validation split.
- **The calibration scope is unattributed.**
  - T = 0.927 and ECE 0.0360 → 0.0227 belong to the **bounded selected** model (`evaluate.py` L652–659; `DESIGN.md` L114–115, "selected model").
  - L160 places them in a section about the full-data model, and L213 implies they belong to the full-data gate (see §5).

## 5. Truthfulness: 6

**Re-verified, all match:**

- **Ladder:** 0.1000, 0.2533, 0.8714, 0.8982, 0.9021, 0.9011, 0.9460.
- **Fresh:** 0.8785, 0.8962, 0.9031, 0.9074, 0.9529.
- **Fresh paired delta:** +0.0069, CI [−0.0025, +0.0161].
- **Validation paired delta:** +0.0073, CI [−0.0048, +0.0204].
- **Validation selection:** 0.8880 → 0.8953.
- **Seed reruns:** 0.8953 / 0.8852 / 0.8926, mean 0.8910, SD 0.0042, 6 trials per seed (`hpo_seeds.json`). The 12-trial study is separate (`hpo_study.json`). 0.0073 / 0.0042 ≈ 1.74.
- **Scale ladder:** test 0.9019 → 0.9170 → 0.9331 → 0.9460 (+1.5 / +1.6 / +1.3); fresh 0.9067 → 0.9219 → 0.9428 → 0.9529 (+1.5 / +2.1 / +1.0); twins 0.0002 test and 0.0105 fresh.
- **Cascade:** 0.9602 → 0.9602, 0.9460 → 0.9490, 0.9529 → 0.9539; reviews 6 / 16 / 22; validation delta 0.000052; 96.933 s; $0.023671; `kimi-for-coding`; candidates {0.5 … 0.9} (`config.py` L122–126).
- **Router rows:** all five τ rows (0.9061 / 0.9082 / 0.9051 / 0.9041 / 0.9041, with escalation shares).
- **Serving table:** all values (`latency_probe.json`); ~40× = 4,477.8 / 112.5.
- **Training:** T = 0.927; probe peak 0.9477 at epoch 3 with validation loss rising; headline 0.9464.
- **Errors:** 25/250 Business → Sci/Tech (decoded `confusion_matrix_selected.json`); 24 → 15 → 14 with the 20k subset at 18k/2k (`DESIGN.md` L77, `README.md` L216).
- **Scale hyperparameters:** lr 2e-5, wd 0.01, warmup 0.1, batch 32, patience 1 (`scale_meta_4000.json`).
- **Data sizes:** 7,600 / 6,600 / seeds 43 and 45.

**Untraceable numbers in story.yaml text: 0.** The only weak spot is ECE 0.0360 → 0.0227, which traces to `DESIGN.md` L115 prose only. `README.md` L258 says it is in `metrics.json → _meta.calibration`, but the current `_meta` has no calibration block. **Untraceable or contradicted numbers in embedded diagrams: 1** (`0.9020`, below).

**Untraceable claim:** the "wins a tie-break toward fewer reviews" wording at L223–224 cannot be checked against any artifact. No per-τ validation sweep is persisted, so it is inferred from the code (`fit_threshold`).

**Contradicted or misleading claims:**

| Line(s) | Claim | Evidence | Verdict |
|---|---|---|---|
| L241 | "The figure also keeps the cheaper baseline in view." | `llm_cascade_comparison.json` has only two traces, `transformer` and `transformer + selective Kimi review`. No keyword baseline is shown. | Contradicted (pre-existing, missed in R2) |
| L213 (new) | "fitted temperature `T=0.927` is not applied" to the full-data gate | T = 0.927 was fitted on the **bounded selected** model (`evaluate.py` L652–659: `calibration_report(selected_model, …)`; `DESIGN.md` L115). No temperature was fitted for the full-data model. | Misleading attribution |
| L264–265, caption L514–515 | "The same Business and Sci/Tech blur accounts for the residual gap" | Confusion matrix rows: World 206/250 correct (44 errors), Business 220 (30), Sci/Tech 233 (17). Per-class F1: World 0.886, Business 0.870, Sci/Tech 0.883. World errors are as large as the Business errors. | Overstated |
| L395 bold vs L242, L307, L494 | The table bolds τ = 0.6 (0.9082), while the prose cites 0.9061 and 75.4% (τ = 0.5) without naming τ | `fresh_holdout.json`. Bolding the best *fresh* row reads as fresh-based selection, which L98 and L493 forbid. | Inconsistent (partly fixed) |
| L10 diagram `04-routing` | "routed system scores 0.9020 fresh macro-F1" (gate and output facts) | `fresh_holdout.json` gives τ = 0.5 → **0.9061**. 0.9020 matches no fresh router row. | Contradicted |
| L10 diagram `04-routing` | Node "Fine-tuned DistilBERT · 120k rows", with facts 0.9529 fresh and 110.7 pred/s | The router escalates to `distilbert_tuned` (bounded) (`fresh_holdout.json` `cascade.transformer`). 0.9529 is the full-data model; 110.7 pred/s and $0.0656 are the bounded model. | Mixed models |
| L93 diagram `auto-…-2` | Edge "Shared test set → Model selection · biased by design" | Contradicts L59–60, L96 and L424 (validation selects; test labels excluded; `selection.json` `selection_split: validation`). | Contradicted |
| L93 diagram `auto-…-2` | "6,600 complement" edge drawn from "Seeded sample" | The complement is of the 7,600-row **test partition** (`fresh_holdout.json`). The prose (L87) is now right, but the diagram is not. | Contradicted |
| L55 diagram `auto-…-1` | "Same model, 120k rows" | 108k train / 12k val (L27, `DESIGN.md` L78) | Imprecise |
| L465 diagram `auto-…-4` | "0.9539265 fresh macro-F1" | Seven decimals, against four everywhere else | Precision drift |

**Minor:**

- **L245:** "~111 items/s on the transformer". This is the bounded model (110.7). The full-data model runs at 112.5. Still present.
- **L151–152:** "follow the running best … lifts validation macro-F1 from 0.8880 to 0.8953". The `hpo_history` running best starts at 0.8923. The 0.8880 default is not in the figure.

## 6. Roadmap cards: 9

| Line | Title | Verb-first | Detail length | Status vs repo |
|---|---|---|---|---|
| L472–474 | Measure the data-scale response | yes | 54 | shipped: true (`distilbert_scale_*` in `metrics.json`) |
| L475–477 | Ship full-data training at default settings | yes | 76 | shipped: true. The full-data run uses params defaults (lr 2e-5); `selection.json` shows the HPO CI crossing zero. |
| L478–480 | Beat every rung with full data | yes | 72 | shipped: true (0.9460 tops the ladder) |
| L481–483 | Ship the selective LLM cascade | yes | 64 | shipped: true (`llm_cascade.json` `selected: cascade`, τ 0.6, 22 fresh, +0.00098) |
| L484–486 | Persist per-row review decisions | yes | 66 | next: correct (no per-row artifact in `reports/`). Follows the gold "Gate: …" pattern. |

All five cards are accurate. The only nit is L483: shipping a stage with an unproven +0.001 is fine, but the card could add "(no CI yet)" to match the body.

## 7. Consistency with gold template: 7

**Matching the gold:**

- "We next …" transitions;
- one-sentence plain-terms notes;
- bold claim openers;
- excerpt link pattern;
- "Gate:" roadmap phrasing;
- the key_concepts and figure_captions blocks.

**Still deviating:**

- The opening has no question or concrete-risk hook (gold L7–8).
- Four or five sections open on "The X figure/diagram shows" rather than a narrative claim.
- The gold's background diagram matches its three bullets. Here the two disagree (§1).

---

## Round-2 finding status

| # | Round-2 finding | Status | Current location / note |
|---|---|---|---|
| 1 | Duplicate transition in Results | FIXED | L290–291 single transition |
| 2 | Cascade numbers retold many times | STILL PRESENT | L17, L222–239, L273–275, L301–306, L324–325, L366–376, L457–458 |
| 3 | HPO / leakage defined late | PARTLY FIXED | HPO at L59. Leakage still mid-list at L326. |
| 4 | Orphan quantization and 20k run | FIXED | Quantization removed; 20k explained at L384–386 |
| 5 | Glossary-sentence pattern | STILL PRESENT | L267–269, L400–405 |
| 6 | Seven-decimal false precision | FIXED (prose) | Remains in diagram `auto-…-4` label (see new findings) |
| 7 | Repeated interval boilerplate | PARTLY FIXED | "No measurable change" now only in L3. The interval caveat is still about 5× (L17, L237–239, L376, L458, L511). |
| 8 | Macro-F1 gloss | FIXED | L43–44 |
| 9 | L15 mixes two policies | PARTLY FIXED | Prose is clean, but it now contradicts the embedded `04-routing` diagram |
| 10 | Circular "within seed noise" | FIXED | L154–156, L322–323 |
| 11 | "Calibration uses ECE with one temperature" | STILL PRESENT | L433–434 |
| 12 | Serving-table glossary dump | STILL PRESENT | L400–405 |
| 13 | Gate signal unnamed | FIXED | L213 (but see the new T-attribution issue) |
| 14 | Reviewer LLM unnamed | FIXED | L16, L215 |
| 15 | τ tie-break unstated | FIXED | L223–224 (not traceable to an artifact) |
| 16 | ECE before/after withheld | FIXED | L160, L329 |
| 17 | Device-twin claim weak on fresh | FIXED | L147–150, L267–271, L318–320 |
| 18 | "At most +0.001" contradicted by test | FIXED | Per-split deltas at L234, L324, L457 |
| 19 | "+0.001 covers 44 reviews" | FIXED | L283–284 |
| 20 | "12 trials produce seed bests" | FIXED | L436–438 |
| 21 | "sample's unused 6,600" | FIXED (prose) | L87. Diagram `auto-…-2` still draws it from the sample. |
| 22 | Roadmap "the default stays" | FIXED | L475–477 |
| 23 | Roadmap "calibrated … uncertain quarter" | FIXED | L481–483 |
| 24 | Router table hides τ = 0.6 | PARTLY FIXED | All rows shown, but the bold sits on τ = 0.6 while the prose uses τ = 0.5 unnamed |
| 25 | ~111 items/s is the bounded model | STILL PRESENT | L245 |
| 26 | "trained on all 120k rows" | FIXED (prose) | L27. Diagrams `auto-…-1` and `04-routing` still say 120k. |
| 27 | "fixed compute budget" undefined | FIXED | Removed; residual "the budget" at L61 |
| 28 | Roadmap card 3 generic | FIXED | L480 |
| 29 | Roadmap card 5 repeats title | FIXED | L486 |
| 30 | Plain-terms notes too long | FIXED | All sections |
| 31 | Verbless transitions | FIXED | "We next …" throughout |
| 32 | Sections open with "The figure/diagram shows" | STILL PRESENT | L109, L137, L211, L255, L299 |

**Totals:** 22 FIXED, 4 PARTLY FIXED, **6 STILL PRESENT**.

---

## New errors

### Introduced by Wave 8

1. **L10 + L13–17: the background prose no longer matches its diagram.** The bullets describe the LLM cascade. The `04-routing` diagram shows the keyword-first router at τ = 0.50.
2. **L213: T = 0.927 is attributed to the full-data gate.** It was fitted on the bounded selected model.
3. **L223 vs L234, L324 and L457: one validation delta appears as `+0.00005` and `+0.0001`.** Fresh `+0.001` also sits beside test `+0.0030`.
4. **L395: the router table now bolds the fresh-best τ = 0.6.** The prose and key concept cite τ = 0.5 (0.9061, 75.4%) without naming τ.

### Pre-existing, first flagged this round (diagrams, figures, evidence)

5. **`routing.ts`:** "routed system scores 0.9020 fresh macro-F1" (×2) is contradicted; the value is 0.9061. The node "Fine-tuned DistilBERT · 120k rows" mixes full-data and bounded-model facts.
6. **`auto-04-nlp-classification-2`:**
   - the test set feeds "Model selection · biased by design", which contradicts validation-only selection;
   - the 6,600 complement is drawn from the sample;
   - there is no validation branch and no scale-ladder view, although L78 and L96 refer to both.
7. **`auto-04-nlp-classification-1`:** "120k rows", and the final node is "Test-set role disclosed", while L58 says the final node records the HPO caveat.
8. **`auto-04-nlp-classification-4`:** the label reads "0.9539265".
9. **L241:** "The figure also keeps the cheaper baseline in view" is false for `llm_cascade_comparison`.
10. **L264–265 and caption L514–515:** "Business/Sci-Tech accounts for the residual gap" overstates the evidence. World has the most errors (44 of 250).
11. **τ is fitted on rows the full-data model has likely seen.** The bounded 400-row validation split comes from the same 120k train partition as the full-data model's 108k training rows. This is undisclosed.
12. **Calibration evidence:** `README.md` L258 cites `metrics.json → _meta.calibration`, which is absent. The ECE values trace only to `DESIGN.md` prose.

Note: the `auto-*` files carry "generated from story.yaml — do not hand-edit" headers, but story.yaml no longer contains Mermaid sources. Fixing them therefore needs either a direct TS edit or a converter-source update. That is a design decision for the owner.

---

## Top 5 remaining fixes

1. **L10 / L13–17: make the background diagram match its bullets.**
   - Embed `auto-04-nlp-classification-3`, which already shows "Full-data transformer → τ=0.6 → Kimi review · 8 rows per call".
   - Alternatively, rebuild `04-routing` as the cascade.
   - If the keyword router keeps its own diagram, fix its `0.9020` to `0.9061` and its "120k rows" DistilBERT node to the bounded `distilbert_tuned` (0.9031 fresh, 110.7 pred/s).
2. **`auto-04-nlp-classification-2` (rendered at L93): redraw the data lineage so it matches L80–100.**
   - Seeded sample → validation → model selection.
   - Test partition (7,600) → bounded test (1,000) and the 6,600 complement → fresh holdout.
   - Add a scale-ladder node.
   - Remove "Shared test set → Model selection · biased by design".
3. **L213 and L160: attribute calibration correctly.**
   - Suggested L213: "The gate uses the full-data model's raw softmax maximum; no temperature was fitted for this model (T=0.927 belongs to the bounded selected model)."
   - At L160, add "for the bounded selected model".
   - At L433, change "Calibration uses ECE with one temperature" to "Temperature scaling fits one T on validation; ECE measures the result."
4. **L241 and L264–265 / L514–515: correct the figure claims.**
   - L241: "The comparison figure shows only the transformer and cascade; the keyword router's numbers come from `fresh_holdout.json`."
   - L264–265: "Business → Sci/Tech is the largest single cell (25); World also loses 44 of 250 across Business and Sci/Tech."
5. **L223 / L234 / L324 / L457 and L395 / L242 / L307: make the precision and the router reference consistent.**
   - Report all cascade deltas at four decimals (+0.0001, +0.0030, +0.0010).
   - Either drop the bold at L395 or name τ = 0.5 as the reference wherever 0.9061 and 75.4% appear, and add "fresh rows are not used to choose τ".
   - Add one sentence near L223 disclosing that the bounded 400-row validation split overlaps the full-data model's training partition.

**Next tier:**

- Collapse the cascade retellings to Evaluation, the Exact-numbers table and Limits.
- Move the CPU/MPS/GPU and serving-column glosses into key_concepts.
- Replace "The X figure shows" openers with claims.
- Open Background with a question hook.
- Fix "the budget" at L61.
- Fix `auto-…-1`: "120k" → "108k", and make the final node the HPO caveat.
- Fix `auto-…-4`: "0.9539265" → "0.9539".

## Ready to publish?

**No.** The story.yaml text is now largely truthful: 22 of 32 round-2 findings are fixed, and all five roadmap cards check out. Three problems still block publication:

- The first diagram a reader sees depicts a different pipeline from the bullets under it, and carries a wrong number (0.9020).
- The data-lineage diagram shows the test set feeding model selection, the exact leakage the article says it avoids.
- L241 and L213 make claims the figure and the code contradict.

These are small, local edits, mostly in diagram files. Once they land, together with the calibration attribution, the article would be publishable at about 7.5/10.
