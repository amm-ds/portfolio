# Review — 07-open-data-mobility story.yaml (Wave 6.6)

Reviewer: Claude (Opus), read-only senior ML writer/reviewer pass.
Target: `projects/07-open-data-mobility/story.yaml` (working tree = HEAD `18adc59d`).
Gold template: `projects/01-rag-agent/story.yaml`.

Note on the diff: `git diff -- projects/07-open-data-mobility/story.yaml` is empty; the Wave 6.6
edits are already committed in `18adc59d`. This review used `git show 18adc59d -- <file>` as "the
diff of this round". That round renamed cards to "In plain terms", added 7 section transitions,
trimmed the background, and retitled and de-numbered the roadmap.

Evidence checked: `reports/metrics.json`, `reports/figures/*.json` (committed); `params.yaml`;
`README.md`, `DESIGN.md`, `MODEL_CARD.md`; `src/mobility/serving.py`. Also checked, but local-only
because `.gitignore: reports/*` ignores them: `reports/drift/*.json` and `reports/green_transfer.json`.

## Grades

| # | Dimension | Grade |
|---|---|---:|
| 1 | Structure and article logic | 7 |
| 2 | Engagement and human-like narrative | 5 |
| 3 | Language quality | 5 |
| 4 | Technical detail depth | 8 |
| 5 | Truthfulness | 6 |
| 6 | Roadmap cards | 6 |
| 7 | Consistency with gold template style | 7 |
| | **Overall** | **6 / 10** |

Language quality (5) and engagement (5) tie for lowest. Language is the weaker of the two, because
the glossary-style inline definitions and the repeated figures drive both scores down.

---

## 1. Structure and article logic — 7

- The arc is sound. It moves through goal, contract, data lineage, grid/EDA, run ladder and serving
  rule, then error and band, scale and weather, and ends with operating rules. The serving-rule code
  excerpt sits at the right place, and the conclusion diagram ("dense → serve, no-borough → manual
  watch, new service → retrain, all → drift") ties the article together well.
- All 7 transitions follow the gold "…; next, … ([X →](#sec-x))" pattern. But 4 of them use one
  frame: "The figures frame…", "The figures qualify…", "The figures bound…", "The bars set…". Read
  together they sound templated. Gold transitions name the specific artifact and what it proves
  (01 L82: "The corpus table and `eda_corpus_composition` chart below confirm…").
- Ordering problem. Results (L295–311) brings in the hour-borough heatmap ("the demand scale behind
  the errors"). That is EDA content, and it lands after Evaluation has already explained
  per-borough error. The reader sees borough error before borough scale.
- The Conclusions section is about 165 lines of mixed narrative, records, protocol, and limits. It
  repeats Training and Evaluation almost word for word: the serving rule appears 4 times, no-borough
  84.7% appears 4 times, and Default vs tuned "flat within noise" appears 3 times. Cohesion suffers
  from the repetition, not from gaps.
- Background L71 "In plain terms" restates the earlier paragraph ("misses 1.8 fewer pickups") rather
  than giving the decision the reader should take away.

## 2. Engagement and human-like narrative — 5

- The best passages are concrete and visual: "Follow Midtown across the week. Its weekday evenings
  burn bright" (L172–173). The lag/zero-fill explanation is also good: "a lag could skip an empty
  hour and use the wrong time" (L163–164).
- Most other passages read as definitions chained together. The pattern is "X. X means Y. Z is W."
  Examples:
  - "Served means chosen for use." (L55)
  - "RAM is the computer's working memory, and GB means gigabytes." (L86–87)
  - "meaning rented remote computers" (L88)
  - "Weights are the model's learned numerical parameters." (L355)
  - "Lazy processing delays work until results are needed." (L456)
  - "This contract is the fixed three-file bundle format used for serving." (L432–433)

  These lines talk down to the expert reader that the technical depth targets. They also break the
  rhythm. 01 defines terms only when the reader needs them to read a figure.
- The voice is impersonal throughout ("The diagram…", "The model box…", "The figures…"). Gold 01
  uses "we" sparingly to carry the narrative ("next, we trace…").
- The reader gets no stake or tension. The Bronx persistence result and the 2025-01 coverage dip
  are interesting, but the text states them flatly or leaves them out.

## 3. Language quality — 5

- Repetition across cards:
  - "84.7%" ×9
  - "28.3%" ×7
  - "4.676" ×7
  - "90.8%" ×7
  - "no-borough" ×13
  - "persistence" ×11
  - " means " ×11
  - "The figures…" ×5
  - "The diagram…" ×5

  "In plain terms: The figures support…" opens two consecutive cards (L288, L316).
- Filler or awkward phrasing:
  - "— the headline comparison is against persistence only" (L190–191) adds nothing; the sentence
    before already says it.
  - "xGB improves relative test MAE by −4.1%" (L382). A negative improvement reads as a regression.
    Write "xGB's test MAE is 4.1% lower than `gbm_tuned`'s".
  - "flat within noise" (L203, L337, L383) is asserted, but no interval exists for gbm_mean vs
    gbm_tuned. Write "−0.2%, not separately tested".
  - "That +0.091-pickup width cost accompanies the coverage gain." (L280–281) repeats the numbers in
    the previous sentence.
- Mixed precision: short_version says "91% coverage" (L6), and every other place says 90.8%. It also
  rounds MAE to 4.68 but keeps 28.3%.
- Jargon slips: "xGB" (L27, L198) is a nonstandard abbreviation. Readers expect "XGBoost"
  everywhere; the article defines "xGB is XGBoost" anyway.

## 4. Technical detail depth — 8

Strong:
- Embargoed expanding validation, a single-shot holdout, and the serving rule backed by real code
- MASE with its in-sample scale (≈6.13)
- Paired bootstrap with circular 7-day blocks and whole-zone clusters, predeclared
- Split-conformal per demand tercile, with calibration and evaluation halves and the width cost
- A drift tolerance definition
- The green transfer vs retrain contrast
- RAM budget evidence

Gaps an expert will notice:
- The conformal offsets are fit on the first half of the **test** window (L277, L451). The article
  says "Nothing learned on test data flows back into selection" (L102–103). That is true for model
  selection, but the conformal band itself is test-derived. Say so in Limits, and state whether the
  served p90 uses the raw quantile or the conformal-adjusted band.
- Two of the three drift months (2024-11, 2024-12) lie inside the Q4 test window, so they replay
  holdout data rather than test drift. The key concept "scores the saved model on new data" (L46)
  overstates this. Only 2025-01 is new.
- The 2025-01 p90 coverage of 87.4% misses the article's own "about 2 points" bar by 2.6 pp. The
  drift bullet says only "In-window" (L422), which refers to MAE tolerance. Flag the coverage miss,
  as DESIGN.md L156 does ("slight under-cover").
- The bootstrap CIs cover challenger vs naive only. The decision that matters is xGB vs `gbm_tuned`
  (−4.1%), and it has no interval.
- The exact-numbers table (L371–377) drops `gbm_lgbm_tuned` (4.582) and `temporal_net` (5.510,
  54.5% MAPE). Yet the text cites LightGBM's validation score and paired CI, and says TemporalNet
  "wins only MAPE". The MAPE winner overall is the untuned `temporal_net` at 54.5%, which the table
  omits.

## 5. Truthfulness — 6

### Contradicted by committed evidence

| Line | Claim | Evidence |
|---|---|---|
| L24, L266–267, L472–473 | "persistence still edges the default GBM in the Bronx" / "The Bronx is the one place where persistence still edges the default GBM" | `reports/figures/borough_mae.json`: naive vs gbm_mean is Bronx 0.483 vs 0.519, but also **EWR 0.147 vs 0.279** and **Staten Island 0.022 vs 0.196**. Persistence beats every GBM in all three. "the one place" is false. |
| L358–359 | "Last week's hour matters most: lag_168 (0.80) tops lag_24 (0.64)" | Committed `gbm_feature_importance.json` subtitle reads "dominant driver: lag_1". Decoded values: lag_1 3.311 > lag_168 2.576 > lag_24 2.477. README L97 agrees. The article's own L401–402 says the last hour adds 3.31. Self-contradiction. |
| L397 | "Unknown 93.8%" | `p90_calibration.json`: 0.93747 → **93.7%** (label "93.7%"). |
| L421 | "ΔMAE versus naive +34.6%" | L366–367 defines ΔMAE as change vs lag-24, and the table uses negative = better. README L149 calls it "a 34.6% MAE **improvement**". By the article's convention it should be −34.6%. The sign comes from DESIGN L156, but under this article's definition it reads as a regression. |
| L198–199 | "Selection uses the best embargoed validation score among candidates **that beat the baseline**" | `serving.py` (excerpt L228–242) gates only on HPO result plus artifact existence. It never checks the baseline. The quoted code contradicts the prose. |

### Untraceable (not in any committed report or project doc)

| Line | Claim |
|---|---|
| L404–405 | "A second summary ranks lag_168 at 0.80, lag_24 at 0.64, lag_1 at 0.55, and hour at 0.32" (4 numbers). No source anywhere in the project. |
| L85 | "within about 2 percentage points of target". Not in DESIGN Requirements (L1–11), README, or MODEL_CARD. |
| L416–417 | 2024-11 MAPE 65.45%, p90 coverage 90.6%, 152,110 zone-hours. These exist only in gitignored `reports/drift/2024-11.json`; README's drift table shows "—" for coverage. |
| L418–419 | 2024-12 MAPE 65.59%, coverage 91.2%, 152,375 zone-hours. Same: gitignored local only. |

Count: **11 untraceable numbers** (4 + 1 + 3 + 3).

### Docs-only (traceable to README/DESIGN/MODEL_CARD/params, not to committed reports)

- 41.2M trips (L3, L51, L120)
- ~1.5 GB download (L142)
- ≈2 GB peak RAM (L340, L455). DESIGN measures 1.48–1.8 GB, so "≈2" is fair rounding.
- 2,327,760 grid rows (L160)
- 30 GBM / 10 NN trials (L443)
- MASE scale ≈6.13 (L439)
- Validation MAEs 3.165 / 3.173 / 3.182 (L199, L379–381); in committed `params.yaml`
- Green study:
  - 197,160 zone-hours
  - 337,080 zone-hours (DESIGN "337k"; exact value in gitignored `green_transfer.json`)
  - 534,240 zone-hours
  - RMSE 0.688 vs 1.100
  - MAPE 66.4% vs 81.8%
  - "−17%" RMSE and "−19%" MAPE (L427). For the yellow-trained model, MAPE is −18.5% vs naive and
    rounds to −19% only loosely.
- Drift MAEs:
  - 5.0592 / +8.19% and 5.0458 / +7.90% (README gives 3 decimals; 4 decimals only in gitignored JSON)
  - 2025-01: 4.442 / −5.01% / 59.6% MAPE / 87.4% coverage

### Verified against committed files

- All run-ladder MAE/RMSE/MAPE/MASE/ΔMAE in the table (L373–377)
- Both paired-CI rows and the 2,000/seed 42/265 zones settings
- Conformal 94.3/88.2/89.6 → 94.3/89.9/90.3, overall 90.7 → 91.5, height 7.032 → 7.124 (+0.091),
  offsets +0.09/+0.18
- p90 overall 90.8% and per-borough coverage except Unknown
- Weather ratios
- Permutation importance 3.31/2.58/2.48/1.12
- Heatmap figures: Manhattan 103.7 at 18:00, Bronx max 0.73, busiest zone 213.9
- Top-30 zones, week of 2024-10-07
- 584,855 holdout
- Green MAE 0.296/0.212/0.1805
- 1.8 fewer pickups (6.517 − 4.676)
- −4.1% xGB vs `gbm_tuned` (metrics.json `mae_reduction_pct_vs_gbm_tuned: 4.05`)

The Wave 6.6 closeout (L30) says "−4.1% … live only in story/DESIGN/MODEL_CARD, not committed
reports". **That is wrong:** `reports/metrics.json` has `deltas.gbm_xgb_tuned.mae_reduction_pct_vs_gbm_tuned = 4.05`.
Removing −4.1% from the roadmap was unnecessary.

## 6. Roadmap cards — 6

- Titles are verb-first imperatives in every card. Good. Compound titles with semicolons ("Calibrate
  the band; flag no-borough zones", "Retrain per service; keep drift in-window") are weaker than
  gold's single-action titles.
- Every detail line is ≤90 characters. The longest is L501 at 77 characters.
- The details lost their evidence. "The test leader tested better; the holdout has no vote." (L492)
  repeats the title and drops the traceable −4.1%. "Coverage lands on target" (L495) is vague, and
  90.8% is committed in metrics. Gold details carry one concrete fact ("30/30 blind owner-labelled
  audit; 104/120 final answers"). Restore one committed number per card.
- L489 "41.2M trips zero-filled…" doesn't fit its title "Replay the study with one command". The
  detail describes the panel, not the replay.
- L498 joins two unrelated shipped items, retraining and drift, in one card.
- Status is reasonable: 4 shipped, 1 next. The next card has a gate-like detail, which matches the
  gold style. Gold phrases it "Gate: …"; consider "Gate: causal-ID design and multi-hour backtest."

## 7. Consistency with gold template — 7

- "In plain terms" cards are present in all 8 sections, and the transition link format matches.
- Gold "In plain terms" cards state a quantified outcome or decision in one sentence. Here, 3 cards
  just describe a figure ("The map shows a few demand hotspots…", "The figures support…"), and
  Background's card is two sentences.
- Gold transitions name the chart IDs (`retrieval_ladder`, `eda_corpus_composition`). This article
  uses generic "the figures".
- Gold's Conclusions is shorter and points to the evaluation report. This article inlines a full
  evaluation report, which makes the section uneven.

---

## Top 5 fixes (ordered by severity)

1. **`story.yaml` L358–360 and L404–406: remove the "second summary" ranking ("lag_168 at 0.80,
   lag_24 at 0.64, lag_1 at 0.55, and hour at 0.32") and the claim "Last week's hour matters most".**
   No committed source exists for them, and they contradict the committed permutation figure
   ("dominant driver: lag_1", 3.31 > 2.58 > 2.48) and the article's own L401–402. Replace with "The
   last hour matters most: lag_1 adds 3.31 MAE when shuffled, ahead of lag_168 (2.58) and lag_24
   (2.48)."
2. **`story.yaml` L24, L266–267, L472–473: fix "The Bronx is the one place where persistence still
   edges the default GBM".** `borough_mae.json` shows persistence also beats every GBM at EWR (0.147
   vs 0.279) and Staten Island (0.022 vs 0.196). Rewrite as "In the three sparsest groups (Bronx,
   EWR, Staten Island), persistence still beats every GBM."
3. **`story.yaml` L416–422 and L46: correct the drift framing.**
   - Drop or source the gitignored-only numbers: 2024-11/12 MAPE, coverage, and zone-hours (6
     numbers).
   - Flip "ΔMAE versus naive +34.6%" to "−34.6%" to match the L366–367 sign convention.
   - Flag "coverage 87.4%" as below the ~2 pp bar.
   - Say that 2024-11 and 2024-12 are replays of test months, so only 2025-01 is new data. That
     corrects key concept L46 "on new data".
4. **`story.yaml` L198–199: fix "among candidates that beat the baseline".** The quoted `serving.py`
   code has no baseline gate. Change to "among candidates with complete mean and p90 artifacts",
   which matches the code. Also fix **L85 "within about 2 percentage points"**, which is untraceable:
   cite DESIGN, or reword to "close to 90%". Fix **L397 "Unknown 93.8%"** to 93.7%.
5. **`story.yaml` L55, L86–88, L355, L432–433, L456, plus the 9× "84.7%" and 7× "28.3%": cut the
   glossary sentences ("RAM is the computer's working memory, and GB means gigabytes", "Served means
   chosen for use", "Weights are the model's learned numerical parameters") and deduplicate the
   repeated figures.** State 84.7% once in Evaluation and once in Limits. Also restore one committed
   number per roadmap detail (L492: "xGB tested 4.1% lower; the holdout has no vote", traceable to
   `metrics.json`).
