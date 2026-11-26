# Round-2 review: 05-ml-pipeline-churn story.yaml

Reviewer: Claude (Opus), read-only senior ML writer/reviewer pass, round 2
Target: `projects/05-ml-pipeline-churn/story.yaml` at HEAD (409 lines, last touched in `e69bba84`)
Gold template: `projects/01-rag-agent/story.yaml`
Prior round: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus/05-ml-pipeline-churn.md`
Date: 2026-11-25

All line numbers below are from the current HEAD file. The round-1 review cited
line numbers from the older 422-line version, so each finding was found again by
its text.

## What changed in e69bba84

The commit rewrote 807 lines of the file, but most of that is re-indentation:
the `sections:` list moved from a 2-space to a 0-space indent. The real changes
are these:

- The background section was rewritten to follow the gold pattern. It now has a
  bold lead claim, the decision diagram, a three-step "Follow the cycle" walkthrough,
  and a transition (L7-21).
- Every "In plain terms" card became a single everyday-language line.
- Backticks were added around numbers in the opening sections.
- The glossary-style opener and the "Accuracy, the share correct" fragment were removed.

Sections from objectives through conclusions, the roadmap, the key concepts, and
the figure captions are unchanged in substance. Almost every round-1 finding in
those parts is therefore still present.

Evidence re-checked this round:

- `reports/metrics.json`, `reports/sensitivity.json`
- `reports/figures/{permutation_importance,fairness_slices,bootstrap_ci,eda_churn_profile}.json`: binary arrays decoded, panel titles read
- `data/{model_selection,operating_policy}.json`, `params.yaml`
- `README.md`, `DESIGN.md`
- `src/churn_pipeline/serving.py`
- `apps/showcase-web/src/diagrams/{churnCycle.ts,auto/05-ml-pipeline-churn-1.ts,auto/05-ml-pipeline-churn-3.ts}`

## Grades

| # | Dimension | R1 | R2 |
|---|---|---|---|
| 1 | Structure and article logic | 7 | 7 |
| 2 | Engagement and human-like narrative | 5 | 6 |
| 3 | Language quality | 5 | 5 |
| 4 | Technical depth | 8 | 8 |
| 5 | Truthfulness | 6 | 5 |
| 6 | Roadmap cards | 6 | 6 |
| 7 | Consistency with gold template | 7 | 7 |
| | **Overall** | **6.3** | **6.3 / 10** |

Lowest dimensions: truthfulness (5) and language (5).

Truthfulness went down because the new background text adds a factual error
(L15) and puts the correct interval (L17) directly under a diagram that still
prints the stale one. None of the round-1 truth findings were fixed.

## 1. Structure and article logic (7)

The new background works better than the old one. It states the problem, shows
the cycle, walks the three steps, and gives the outcome, which is the gold arc.
The rest of the article still has the round-1 problems:

- **L19.** "Next, the cost-model diagram that sets the gates." The objectives
  diagram (`auto/05-ml-pipeline-churn-1.ts`) has six boxes: cost model,
  candidates, grid, argmin, served policy, and stability. It sets no gates.
  "Gates" still means three different things in this article: data-quality
  gates, success tests, and rollout gates.
- **L46-47.** "Three tests for success need one real panel and one twin" is
  still a non sequitur. The twin is CI-only evidence (L75-79).
- **L81-82.** The transition still says the churn-profile figure "sets the
  judging rules", but the rules are in the text, not in the figure.
- **Headline repetition is unchanged.** "601 versus 1,035" or "1,035 → 601"
  appears at L3, L17, L21, L148/L128, L187, L235, L262, L300, L367, and in the
  L403 caption. The interval [−508, −353] appears at L3, L17, L235, L264, L302,
  L313, and L409. The new background adds two more copies (L17, L21) on top of
  `short_version`.
- **Results (L232-249) and Conclusions/Limits (L354-365) still overlap.** They
  share the snapshot/no-time-axis, raw-versus-served fairness,
  one-operator/21-columns, and selection-instability bullets, nearly word for word.

## 2. Engagement and human-like narrative (6)

The opener is now a claim ("Stop guessing who will churn — pick the cheapest
contact list…") and is immediately concrete about $1 versus $5. That fixes the
main round-1 complaint. The body still reads as machine-assembled:

- **Inline "X, or Y," glosses are still stacked:**
  - L40 "A grid, or list, of 41 thresholds"
  - L61 "null, or missing-value, rates"
  - L76 "outlier, or extreme, charge"
  - L193-194 "a CRM, or customer relationship management, system"
  - L211-212 "Rollout, or real release"
  - L242-244, the worst case: "drift, meaning change over time, seasonality,
    meaning repeating time patterns, or causation, meaning that the policy
    caused an outcome"
- **Every section still opens with a reader instruction:**
  - L60 "Follow both source branches"
  - L89 "Compare the contract bars"
  - L127 "Start with the flat line"
  - L130 "Compare the logistic policies"
  - L154 "Read permutation importance from top to bottom"
  - L197 "Follow the measurement chain"
  - L225 "Read the fairness-slices figure one customer group at a time"
- **Terms are still defined more than once:**
  - OOF at L140-141 and again at L198-199.
  - Calibration at L71-72, calibration error at L104-105, and ECE at L144-146.
  - Holdout at L31-32, with the idea revisited at L70.

## 3. Language quality (5)

| R1 item | Status | Current line |
|---|---|---|
| "Accuracy, the share correct" | FIXED | removed |
| Semicolon splice "a learned rule estimating churn; serving uses it…" | FIXED | removed |
| Broken wrap "Training and serving / use this same / pipeline" | STILL PRESENT | L123-125 |
| "An F1-first search chose a different model family. The figure's cost-based winner therefore depends…" | STILL PRESENT | L133-135 |
| "The pipeline diagram separates… That comparison gives the ECE improvement" (a diagram does not produce a metric) | STILL PRESENT | L267-269 |
| Link row has no blank line before it, so it renders inside the paragraph | STILL PRESENT | L273-274 |
| Diagram fence indented 10 spaces inside a 4-space block | STILL PRESENT | L331-332 |

New language issues:

- **L8 against L187/L221/L367.** The background prices errors in dollars ($1,
  $5). Later sections speak of "601 units", and L283 says "voucher". Pick one
  unit. README L93 uses dollars, so dollars are defensible, but the article
  should use them throughout.
- **L17.** "bootstrap saving `−508` to `−353`." A saving stated as a negative
  number is confusing. Either "saving of 353 to 508" or "cost delta −508 to
  −353".
- **L26.** "contact-nobody policy is `73.5%` accurate but saves nothing." It
  actually costs 1,870, which is far worse than doing nothing useful. "Saves
  nothing" understates it.

## 4. Technical depth (8)

This is still the article's strength: the priced-confusion-matrix objective with
a faithful `evaluate.py` excerpt, OOF threshold freezing, the train-side
isotonic carve-out, paired bootstraps against two comparators, FN-cost
sensitivity, and separation of raw-model fairness from the served policy.

All four round-1 depth gaps are STILL PRESENT:

- Why ROC-AUC falls after calibration (0.8387 → 0.8317, L297-298). Isotonic
  ties reduce ranking resolution, and the article does not say so.
- The calibrated model's base learner sees only 80% of the training rows.
- Whether the grid's 0.025 step is meaningful. OOF training costs are 2,440
  raw versus 2,425 calibrated (`operating_policy.json`), so the gap is small.
- ECE uses 10 bins (`params.yaml` L64). The article never says so.

## 5. Truthfulness (5)

Numbers re-verified this round:

| Claim | Lines | Source | Result |
|---|---|---|---|
| 601 / 1,035 / 691 / 655 / 644 | many | `metrics.json` | match |
| −41.9% | L17, L263, L301 | 434/1035 = 41.93% | match |
| −434 [−508, −353], n=2,000 | L263-264, L302 | `sensitivity.json` fn5, `bootstrap_ci.json` title | match |
| ROC-AUC 0.5000/0.8292/0.8292/0.8387/0.8317; F1 0.2098/0.7022/0.6796/0.6981/0.6745 | L294-298 | `metrics.json` | match |
| ECE 0.028 → 0.016 | L146-147, L268 | `metrics.json` (0.02835, 0.01643) | match |
| thresholds 0.450 / 0.225 / 0.175; OOF cost 2,425 | L132, L148, L324 | `operating_policy.json` | match |
| FN 3/5/8 thresholds 0.250/0.175/0.150, costs 514/601/718, CIs | L150-151, L312-314 | `sensitivity.json` | match |
| fairness recalls 0.834/0.829/0.898/0.808/0.918/0.250/0.000 | L227-229, L325 | `fairness_slices.json` | match |
| 1,870 contact-nobody | L129 | 374 × 5 | match |
| 73.5% contact-nobody accuracy | L26 | 1 − 0.2654 | derivable, but not "in the cost-model diagram" |
| 42.7% / 2.8% contract churn | L90 | `eda_churn_profile.json` (0.4271, 0.0283) | match |
| XGBoost hyperparameters | L323 | `data/model_selection.json` | match |

### Untraceable or contradicted claims

1. **L15: contradicted (NEW).** "Train boosted trees on `7,043` pinned
   customers." The model trains on 5,634 rows (`operating_policy.json`
   `n_train: 5634`; L70 and L338 of this file). 7,043 is the whole panel,
   including the 1,409-row holdout. This is exactly the leakage-style claim the
   rest of the article works hard to rule out.
2. **L17 against the diagram directly above it (L10): contradicted, STILL
   PRESENT and now worse.** The text says −508 to −353. `churnCycle.ts` L70
   prints "CI −485 to −343". `auto/05-ml-pipeline-churn-3.ts` L31 (shown at
   L205) prints "CI -485 to -343". The new walkthrough now explicitly narrates
   the diagram above it, so the conflict sits on screen together.
3. **L155-157 and caption L404-405: contradicted, STILL PRESENT.** "Contract,
   tenure, and charges rank highest." Decoded `permutation_importance.json`:
   tenure 0.213, contract 0.174, internet_service 0.088, monthly_charges 0.033.
   Internet service ranks third, and the order is tenure first, not contract.
4. **L90-91: contradicted, STILL PRESENT.** "The other panels show 41.7%
   churn for senior citizens and 41.9% for fiber-optic users." The figure's
   three panels are "Churn rate by contract", "Monthly charges distribution",
   and "Tenure distribution". There is no senior or fiber panel. The numbers
   themselves trace to README L120.
5. **L95: contradicted, STILL PRESENT.** "Use all three figures." The EDA
   section has two figures (L115).
6. **L303-304: untraceable, STILL PRESENT.** "−90 with 95% CI [−159, −26]."
   This appears only in README L96 and DESIGN L169 prose. No JSON report holds it.
7. **L323: untraceable, STILL PRESENT.** "CV cost 2,416" and "25 trials,
   median pruning." `data/model_selection.json` still records
   `"best_score": NaN, "n_trials": 0, "family_scores": {}`. Only README L79
   prose carries 2,416.
8. **L133-135: misattributed, STILL PRESENT.** "An F1-first search chose a
   different model family." This is a synthetic-era DESIGN log entry
   presented as part of the telco story, and no committed telco artifact
   shows it.
9. **L248 and L364: overstated, STILL PRESENT.** "covers one operator and 21
   columns." The pipeline consumes 6 features (`churn.parquet` is 7043×7).
   21 is the raw source width (L55 is correct as a source description).
10. **L152-153: selective, STILL PRESENT.** "Calibration helps at five… and at
    eight." `sensitivity.json` fn3 also improves (518 → 514).
11. **L34: overstated, STILL PRESENT.** "when a missed churner costs between 3
    and 8." Only 3, 5, and 8 were tested.
12. **L26: misattributed (NEW wording, same text as R1 pre-round).** "In the
    cost-model diagram, the contact-nobody policy is 73.5% accurate." The
    diagram (`auto/05-ml-pipeline-churn-1.ts`) shows neither contact-nobody
    nor 73.5%.
13. **L221: overstated (NEW).** "The packaged model scores raw customer rows
    after automatic quality checks." `serving.py` runs no DQ gate. The pipeline
    caps and imputes, which is preprocessing, not a quality check that rejects
    rows. The DQ gates run on the training data (`reports/dq_report.md`).
14. **L40, L283: framing, STILL PRESENT.** "voucher" is not defined anywhere in
    the project.

**Untraceable-number count: 2.** These are −90 [−159, −26] and CV cost 2,416.
Both appear only in README/DESIGN prose, not in any metrics file.

Contradicted by committed artifacts: 5 (items 1-5). Overstated or misattributed: 7 (items 8-14).

## 6. Roadmap cards (6)

Unchanged from round 1 (L370-384). All titles are verb-first, and every detail is 90 characters or fewer (61-79).

| Title | Detail chars | Status vs repo | Issue |
|---|---|---|---|
| Pin one reproducible panel and twin | 70 | shipped: ok (`dataset_contract.json`, synthetic track) | "DQ", "CI" jargon |
| Choose the cutoff from OOF cost | 67 | shipped: ok (`operating_policy.json`) | detail describes HPO + calibration, not the cutoff; "25-trial search" is not evidenced by `model_selection.json` (`n_trials: 0`) |
| Price the served policy by bootstraps | 76 | shipped: ok (`sensitivity.json` n_boot 2000) | a bootstrap bounds the saving and does not price it; detail lost its "2,000" and "95%" |
| Re-freeze the cutoff as prices move | 79 | shipped: ok | vague; "0.250 → 0.150 as FN price goes 3 → 8" fits in budget |
| Gate rollout on owner data | 61 | blocked: plausible | no `next` card; gold ends with a `next` card that names its gate |

All five round-1 roadmap findings are STILL PRESENT.

## 7. Consistency with gold template (7)

What now matches gold:

- The background has the lead, the diagram, a "Follow the … in three steps" list,
  a "Next, …" transition, and a one-line plain-terms card.
- Every section ends in "**In plain terms:**".
- Backticked numbers are used in the opening sections.

Remaining gaps:

- **Gold transitions are sentences with a subject and a verb.** For example,
  gold L18: "Next, we set the rules each answer must clear". This article still
  uses verbless "X; next, the Y" fragments at L19, L46-47, L81-82, L111-112,
  L184-185, L218-219, and L251-252.
- **The gold opener is a question.** This opener is an imperative claim. That
  is acceptable, but it differs from gold (PARTLY FIXED).
- **Backtick tagging is applied unevenly.** Background and data use it (L8,
  L15-17, L54-76). Training and evaluation mostly do not (L128 "1,035", L131
  "691", L148 "644", L151 "514, 601, and 718").
- **There is no `next` roadmap card** (see section 6).

## Round-1 finding status

| # | R1 finding | Status | Current line(s) |
|---|---|---|---|
| S1 | "cost-model diagram that sets the gates" | STILL PRESENT | L19 |
| S2 | "Three tests… need one real panel and one twin" | STILL PRESENT | L46-47 |
| S3 | "churn-profile figure that sets the judging rules" | STILL PRESENT | L81-82 |
| S4 | Headline numbers repeated many times | STILL PRESENT (worse: +2) | L3, L17, L21, L187, L235, L262, L300, L367 |
| S5 | Results bullets duplicate Conclusions Limits | STILL PRESENT | L232-249 vs L354-365 |
| E1 | Opens with glossary sentences | FIXED | L7-8 |
| E2 | Stacked "X, or Y," gloss chains | STILL PRESENT | L40, L61, L76, L193, L211, L242-244 |
| E3 | Imperative figure-reading lines in every section | STILL PRESENT | L60, L89, L127, L130, L154, L197, L225 |
| E4 | OOF / calibration error / ECE defined twice | STILL PRESENT | L140-141 & L198-199; L104-105 & L144-146 |
| L1 | "Accuracy, the share correct" | FIXED | — |
| L2 | Semicolon splice in background | FIXED | — |
| L3 | Broken line wrap | STILL PRESENT | L123-125 |
| L4 | F1-first "therefore" non sequitur | STILL PRESENT | L133-135 |
| L5 | "diagram… gives the ECE improvement" | STILL PRESENT | L267-269 |
| L6 | Link row inside paragraph | STILL PRESENT | L273-274 |
| L7 | Over-indented diagram fence | STILL PRESENT | L331-332 |
| D1 | AUC drop after calibration unexplained | STILL PRESENT | L297-298 |
| D2 | 80% base-learner cost of carve-out unstated | STILL PRESENT | L72-73, L339-340 |
| D3 | 0.025 grid granularity vs close OOF costs | STILL PRESENT | L286, L324 |
| D4 | ECE bin count not stated | STILL PRESENT | L144-146 |
| T1 | −90 [−159, −26] untraceable | STILL PRESENT | L303-304 |
| T2 | Permutation-importance ranking wrong | STILL PRESENT | L155-157, L404-405 |
| T3 | Senior/fiber "panels" do not exist | STILL PRESENT | L90-91 |
| T4 | "all three figures" in EDA | STILL PRESENT | L95 |
| T5 | Stale −485/−343 CI in diagrams | STILL PRESENT | L10/L17, L205 (diagram sources unchanged) |
| T6 | CV cost 2,416 / 25-trial search untraceable | STILL PRESENT | L136-137, L323 |
| T7 | F1-first search misattributed | STILL PRESENT | L133-135 |
| T8 | "21 columns" overstates pipeline | STILL PRESENT | L248, L364 |
| T9 | Calibration gain at FN=3 omitted | STILL PRESENT | L152-153 |
| T10 | "between 3 and 8" | STILL PRESENT | L34 |
| T11 | "voucher" undefined | STILL PRESENT | L40, L283 |
| R1 | Card 2 detail does not match title | STILL PRESENT | L374-375 |
| R2 | "Price… by bootstraps" wrong verb | STILL PRESENT | L377 |
| R3 | Details made vaguer | STILL PRESENT | L378, L381 |
| R4 | Jargon in cards (DQ, OOF, CI) | STILL PRESENT | L372, L374 |
| R5 | No `next` card | STILL PRESENT | L370-384 |
| G1 | Verbless transition fragments | STILL PRESENT | L19, L46, L81, L111, L184, L218, L251 |
| G2 | Opener differs from gold question hook | PARTLY FIXED | L7 |

Totals: 38 round-1 findings. 3 FIXED, 1 PARTLY FIXED, 34 STILL PRESENT. There are also 3 new issues: L15 (contradicted), L221 (overstated), and L8 against L187 (unit inconsistency).

## Top 5 remaining fixes (by severity)

1. **Correct the training-set size and the stale interval in the background.**
   - L15 should say "Train boosted trees on `5,634` training rows" (or "on the
     training split of 7,043 pinned customers").
   - Update `churnCycle.ts` L70 and `auto/05-ml-pipeline-churn-3.ts` L31 from
     "−485 to −343" to "−508 to −353". L17 and L205 currently sit directly
     beside the contradicting labels.
2. **Fix the permutation-importance ranking.** Change L155-157 and caption
   L404-405 to "Tenure and contract dominate (0.213, 0.174); internet service
   is third (0.088); monthly charges add little (0.033)." README L117-118
   carries the same error.
3. **Stop pointing readers at figure content that does not exist.**
   - L90-91: reword as text-only facts ("Outside the figure, seniors churn at
     41.7% and fiber users at 41.9%").
   - L95: change "all three figures" to "both figures".
   - L26: drop "In the cost-model diagram" before the 73.5% claim.
4. **Persist or drop the two untraceable numbers and the misattributed search
   claim.**
   - L323 "CV cost 2,416" and the 25-trial claim: write the search result into
     `data/model_selection.json` (it currently has `n_trials: 0`, `best_score:
     NaN`) or remove them.
   - L303-304 "−90 [−159, −26]": persist the logistic-at-0.5 bootstrap in
     `metrics.json` or `sensitivity.json`.
   - L133-135: delete the F1-first sentence and its "therefore".
5. **Tighten the scope and limit claims.**
   - L248 and L364: "source has 21 columns; the pipeline uses 6 features".
   - L221: drop "after automatic quality checks" or name the actual preprocessing.
   - L152-153: add FN=3 (518 → 514).
   - L34: "at missed-churner prices of 3, 5, and 8".
   - Merge the Results bullets (L232-249) with Conclusions Limits (L354-365).

Next tier: rewrite the transition fragments as sentences (L19, L46, L81, L111,
L184, L218, L251). Thin the gloss chains (L242-244 first). Restore the concrete
roadmap details and add a `next` card. Fix the L123-125 wrap, the L273-274 link
row, and the L331 fence indent.

## Ready to publish?

**No.** The round-2 edit improved the opening and the plain-terms cards but
fixed none of the truthfulness findings. The article now opens with a
factual error: it says the model trained on all 7,043 customers, when it
trained on 5,634. In an article whose central claim is holdout discipline,
that is the worst place for such an error. Two diagrams still print a
different confidence interval from the text beside them. The feature-importance
ranking still contradicts the committed figure data. Two headline-adjacent
numbers trace only to README prose. All of these are small text edits, plus
two diagram-label edits and optionally two JSON persistence steps.
