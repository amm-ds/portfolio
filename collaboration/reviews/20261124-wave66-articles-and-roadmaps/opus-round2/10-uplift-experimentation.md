# Round-2 review: 10-uplift-experimentation article

- Target: `projects/10-uplift-experimentation/story.yaml` at `HEAD` (444 lines; last touched in `e69bba84`)
- Gold template: `projects/01-rag-agent/story.yaml`
- Prior round: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus/10-uplift-experimentation.md`. Its line numbers refer to a 516-line version. This review maps each finding onto the current file and re-checks it.
- Evidence re-checked: `reports/metrics.json` (top-level policies and `multi_arm`), `reports/segment_summary.json`, `reports/figures/cost_sensitivity.json`, `reports/report.html` (text tables), `README.md`, `DESIGN.md`, `params.yaml`, `src/uplift_experimentation/cli.py`.
- Stance: read-only. No repository file was edited apart from this review.

## Grades

| # | Dimension | R1 | R2 |
|---|---|---|---|
| 1 | Structure and article logic | 6 | 6 |
| 2 | Engagement and human-like narrative | 5 | 6 |
| 3 | Language quality | 5 | 6 |
| 4 | Technical depth | 8 | 8 |
| 5 | Truthfulness | 5 | 5 |
| 6 | Roadmap cards | 7 | 6 |
| 7 | Consistency with gold template | 7 | 7 |
| | **Overall** | **6** | **6** |

This round shortened the article by about 70 lines and cleaned up the prose. The four factual errors that round 1 ranked as the top three fixes are still in the text, and so are all three roadmap findings.

### 1. Structure and article logic: 6

- **Still present:** Training (L135–189) still carries the CUPED variance read and the multi-arm planning dollars ($35.5k / $16.6k / $49.8k / ≈$0.31). L138 still has to explain this with "The channel-planning figures below use these scores." The reader sees channel-planning money before the two-arm policy race is explained.
- **Still present:** Evaluation opens with the final verdict (L198, "Use targeted sends when sends are budgeted or costly. Otherwise, mail everyone.") before Results shows the evidence for it.
- **New duplication:** Results now ends with a summary table (L270–276), and Conclusions repeats the same five policies with CIs (L306–312). Two tables carry the same numbers about 35 lines apart.
- Conclusions is still long: 131 lines (L282–413) out of 444. The "Exact numbers" paragraphs (L324–366) repeat the CUPED, 2×-hot, 76/20/3.8, $49.8k, and ≈$0.31 figures already given in Training and Evaluation.
- **Improved:** the Results plain-terms card (L278) now matches the lead and no longer adds a claim the lead leaves out.

### 2. Engagement and narrative: 6

- **Improved:** Background now opens on a goal, "Find buyers who act because of the email, not ones who would buy anyway" (L36), not a definition. The hook is still abstract: there is no person, campaign, or decision maker.
- **Still present:** the body still reads as reading instructions. There are 14 lines of the form "Start with…", "Next, compare…", "Read the…", "Check whether…", "…; next, the…".
- **Still present:** the transitions still follow one template ("The profile clears the design; next, …", "Cross-fitting sets the scores; next, …", "The figures set the trust level; next, …", "The claims are bounded; …"). The gold varies them and previews the next section's content by name.
- Strongest passages: L116–121 (visits versus purchases) and L250–257 (observed DR/IPW versus planning).

### 3. Language quality: 6

- **Improved:** the broken appositive "policy race, a recipient-selection rule", the phrase "The money metric judging uses", and the wedged "log-transformed" definition are all gone.
- **Partly fixed:** "revenue minus send cost" fell from 24 to 20 occurrences (case-insensitive, including hyphenated forms). The fused compound "revenue-minus-send-cost-at-budget CI" (L16) remains. The article now also uses "net sales" (L45, L50), "real net profit" (L75), "Net profit" (L270 table header), "net profit" (L293), and "value" (L285, L304) for the same quantity. That is five names for one metric. Pick one term, define it once, and use only that term.
- **Still present:** L211–212 "The best targeting share drops below everyone near `$0.20.`" The phrase "below everyone" does not parse. It should say "below 100% coverage".
- **Still present:** L342 "is 0.09" has no unit. README L38 says "SE 0.09pp".
- **New formatting defects:** punctuation has been pulled inside code spans: `$0.01.` and `≈$0.30,` (L211–213), `≈$0.31.` (L189), `$16,103.` (L240), `+$718,` (L242), `$10,881,` (L253, L355), and `$16,563.` (L359). Percent signs sit outside the span in `0.95`% (L180, L349). Some numbers that should be formatted are not ("3.8%" at L186 and L360, "61 of 145" at L330). These render as visible glitches.
- Very long source lines: L285 is 711 characters, and nine other lines exceed 200 characters. They render fine, but L285 is a single paragraph that crams six results together.

### 4. Technical depth: 8

- Still strong: the cross-fitting excerpt, the paired-bootstrap tables, the separation of observed DR/IPW value from model-estimated planning value, the analytic break-even, and the scoping of the X-learner result to strong overlap and near-constant propensity.
- **Partly fixed (duplicate Qini CIs):** L285 now places the two-arm interval `12.03 [0.77, 24.39]` next to the per-arm interval `[−0.47, 24.21]`, and caption L26 says "Mens is the same score". The article still does not say that these are two bootstrap intervals (seed 1041 versus seed 2041) for one score, `metrics.json` `multi_arm.per_arm.mens.qini_coefficient` = `binary_t_learner.qini_coefficient` = 12.0252. The honest reading is that this score's lower bound sits right at zero. As written, L285 presents a significant result and a non-significant one as if they were different findings.
- **Still present ("2× hot"):** L11, L207, L296, L362, and L400. In `multi_arm.per_arm.mens.deciles`, the top decile predicts 0.0250 against 0.0111 measured (2.25×). The bottom decile predicts −0.0083 against +0.0033 measured. The mean prediction is close to the mean measured value. So the *spread* is too wide; uplift is not hot across the board. The difference matters because planning dollars are sums of predictions.
- **New gap:** the planning best-arm minus single-arm difference is +$6,027, with a model-estimated CI of [+$5,742, +$6,347] (`multi_arm.ci.pairs`). The observed DR difference is −$2,902 [−$7,702, +$1,965]. That is a sign flip between planning and observation. The article reports both but never points out the reversal, which is the strongest evidence that the planning dollars overstate channel choice. One sentence in Results would fix this.
- Still omitted: the single-protocol causal-forest comparison in `reports/single_protocol/`. Leaving it out is acceptable.

### 5. Truthfulness: 5

**Verified (no issue):**
- Data and arms: 64,000 / 42,613; arm sizes 21,307 / 21,387 / 21,306; visit 18.3 / 15.1 / 10.6%; conversion 1.25 / 0.88 / 0.57%; mean prior spend $242.8 / $242.5 / $240.9 (`segment_summary.json`).
- Two-arm policy race: $6,838 / $4,881 / $4,564 / $4,026 / $16,103; deltas +$2,812 / +$856 / +$539 (`metrics.json`).
- Qini and paired CIs: Qini 13.01 / 12.03 / 5.90 with CIs; paired CIs [−8.18, 9.52], [−$3,617, −$48], [+$718, +$4,767], and [−$13,125, −$5,808] with point −$9,265 (`report.html`).
- Cost grid: $16,103 / $12,268 / $8,065 [$8,007] / $4,230 [$3,745] / $1,618 [−$4,777] (`cost_sensitivity.json`, `report.html`).
- Experiment read: CUPED 0.08 / 0.52 / 0.12 / 0.95%; power 3,063 per arm with 21,306 available (`report.html`).
- Multi-arm planning: $35,514, $29,487, $16,563, $49,819; break-even 0.308; shares 76.0 / 20.2 / 3.8% (`multi_arm`).
- Observed DR/IPW: all values and CIs at L252–257 and L354–357 (`multi_arm.policy_value`).
- Per-arm AUUC and incremental-conversion CIs (`multi_arm.per_arm`).
- Constants: seeds 1041 / 2041 / 3041 / 1042 (DESIGN `seed+999/1999/2999`; `cli.py` `seed + 1000`); $114 (README L68, DESIGN L42); ~61 of ~145 (README L77).

**Untraceable (1)**

| Line | Claim | Status |
|---|---|---|
| L320 | "T-learner − X-learner, rev. minus send cost @25% \| [−$323, $4,343]" | Still not found in `metrics.json`, `demo_payload.json`, `report.html`, `README.md`, `DESIGN.md`, or figure JSON. `metrics.json` `_meta` still has only provenance keys, even though README promises `_meta.ci`. |

**Contradicted or misleading (7)**

| Line | Claim | Evidence |
|---|---|---|
| L8, L119–120, L125 | "conversion rises materially only for Mens"; "Only the Mens email clearly increased conversion"; "a converting email with a non-converting one" | Womens conversion is 0.884% against 0.573% control (+0.31 pp). The article's own L353 gives Womens incremental conversions 66.5 [33.10, 104.69], which excludes zero. Womens did raise purchases, by less than Mens. **Unchanged from round 1.** |
| L285 | "On `64,000` randomized customers …, the `T-learner` ranking beat `random` … by `+$2,812`" | The +$2,812 result comes from the 42,613-row two-arm frame (`metrics.json` `t_learner`; README L35). The short version (L2) has it right. **Unchanged.** |
| L212 | "Above `≈$0.30,` the top-25% list wins outright" | At $0.30, the best share is 90% ($4,230). Top-25% is about $3,749, essentially tied with mail-everyone ($3,745). Top-25% becomes the best policy only at the $0.50 grid point. **Unchanged.** (Key concept L428 is now worded correctly.) |
| L121, L366 | "near a `0.9%` baseline"; "`~0.9%` base conversion" | The no-email baseline is 0.57%. 0.9% is the pooled three-arm rate, which includes treated customers. **Unchanged.** |
| L29, L189, L361 | "Unconstrained mail-everyone-Mens leads raw revenue minus send cost at $49.8k until sends cost ≈$0.31" | The 0.308 break-even is against *best-arm at the 25% budget* (`multi_arm.best_arm_break_even.vs = mail_everyone_mens`, `policy_budget 0.25`). Unconstrained best-arm planning value is $66,253 (`policies.best_arm.profit_full`), so mail-everyone-Mens does not "lead" unconstrained. L29 is worse than round 1 because it now adds "raw revenue minus send cost". |
| L75, L270, L293 (new) | "real net profit"; "Net profit @ 25% budget"; "wins on net profit" | The metric is revenue minus send cost. L364–365 and DESIGN L121 say $114 is revenue, not margin, and COGS is excluded. Calling it "profit" or "real net profit" contradicts the article's own caveat. |
| L293 | "`T-learner` trails the `response` model on `Qini` (`12.03` vs `13.01`)" | Softer than round 1's "loses the Qini race", but it still states an ordering that L318 calls "ranking not established". Add "nominally" or the CI. **Partly fixed.** |

### 6. Roadmap cards: 6

- All titles are verb-first and all details are ≤90 characters (longest about 70). Four cards are shipped and one is next.
- "Shipped" claims, checked against the repo:
  - Card 1: ATE +0.68 pp and power 3,063 versus 21,306 are in `report.html`.
  - Card 2: cross-fitting is in `models.py` and the bootstrap in DESIGN L57.
  - Card 3: `multi_arm.policy_value` exists, and its pairs match the detail.
  - Card 4: the cost sweep is in `cost_sensitivity.json`.
  - All four are accurate.
- **Still present:** card 1 detail (L432), "arm sizes cover the power need", has no numbers. Use "power needs 3,063 per arm; 21,306 available".
- **Still present:** card 4 detail (L441), "overtakes mail-everyone above the break-even cost", is circular. Use "≈$0.30 per email".
- **Still present:** card 5 title (L443), "Decide the next live-campaign test". "Decide" is not a deliverable. Use "Run a prospective randomized holdout".
- The grade drops one point because none of the three round-1 roadmap fixes were applied.

### 7. Consistency with gold template: 7

- Every section has an "In plain terms" card, and transitions use the gold's `([Section →](#sec-x))` link format.
- **Partly fixed:** plain-terms cards now carry numbers in seven of eight sections. Objectives (L75) still has none. The gold's Objectives card names a threshold.
- **Partly fixed:** L268 now names figures in backticks (`qini_curves`, `profit_frontier`, `qini_per_arm`), as the gold does. The other sections still use prose names.
- **Fixed:** the Data plain-terms card (L106) no longer copies the Data lead.
- Unlike the gold, the transitions do not preview the next section's content. The repeated "X; next, the Y" pattern remains.

## Round-1 finding status

| # | Round-1 finding | Current lines | Status |
|---|---|---|---|
| 1 | CUPED and multi-arm planning sit in Training | L175–189, L195 | STILL PRESENT |
| 2 | Evaluation opens with the verdict before Results | L198 | STILL PRESENT |
| 3 | Conclusions too long and duplicative | L282–413 | PARTLY FIXED (shorter; a new duplicate table at L270) |
| 4 | Results lead and plain-terms card disagree | L225–227, L278 | FIXED |
| 5 | No human hook; opens on a definition | L36 | PARTLY FIXED |
| 6 | Checklist or instruction tone | throughout | STILL PRESENT |
| 7 | Seven identical transition templates | L72, L103, L128, L191, L218, L268 | STILL PRESENT |
| 8 | "Revenue minus send cost" repeated 24× and fused compounds | L16 and others | PARTLY FIXED (20×; five synonyms introduced) |
| 9 | "Model-estimated" and "spans zero" repetition | 5× / 5× | PARTLY FIXED |
| 10 | "policy race, a recipient-selection rule" | — | FIXED (phrase removed; "policy" is now never defined) |
| 11 | "drops below everyone" | L212 | STILL PRESENT |
| 12 | "The money metric judging uses" | — | FIXED |
| 13 | "judge each on …, and an honest interval" | L75 | PARTLY FIXED (grammar fixed; now says "real net profit") |
| 14 | Overlong source lines | L285 (711 chars) and others | STILL PRESENT |
| 15 | SE 0.09 missing "pp" | L342 | STILL PRESENT |
| 16 | Wedged "log-transformed" definition | — | FIXED |
| 17 | Two Qini CIs for one score not explained | L285, L26 | PARTLY FIXED |
| 18 | "2× hot" should describe spread | L11, L207, L296, L362, L400 | STILL PRESENT |
| 19 | Causal forest not mentioned | — | STILL PRESENT (optional) |
| 20 | T−X CI [−$323, $4,343] untraceable | L320 | STILL PRESENT |
| 21 | Womens "did not convert" contradiction | L8, L119–120, L125 | STILL PRESENT (only old L194 removed) |
| 22 | "loses the Qini race" overclaim | L293 | PARTLY FIXED |
| 23 | +$2,812 attributed to 64,000 customers | L285 | STILL PRESENT |
| 24 | "top-25% wins outright" above $0.30 | L212 | STILL PRESENT (key concept fixed) |
| 25 | 0.9% called the baseline | L121, L366 | STILL PRESENT |
| 26 | $49.8k comparator unnamed | L29, L189, L361 | STILL PRESENT (L29 worse) |
| 27 | Roadmap card 1 vague | L432 | STILL PRESENT |
| 28 | Roadmap card 4 circular | L441 | STILL PRESENT |
| 29 | Roadmap card 5 "Decide" | L443 | STILL PRESENT |
| 30 | Plain-terms cards number-free | L75 | PARTLY FIXED |
| 31 | Data card copies the Data lead | L106 | FIXED |
| 32 | Prose figure names versus gold backticks | L268 only | PARTLY FIXED |

Totals: 5 fixed, 10 partly fixed, 17 still present.

## Top 5 remaining fixes (by severity)

1. **Correct the Womens-conversion contradiction (L8, L119–120, L125).** Replace "only for Mens", "Only the Mens email clearly increased conversion", and "a converting email with a non-converting one" with: both emails raised purchases, Mens by +0.68 pp and Womens by +0.31 pp (incremental 66.5 [33.1, 104.7]); pooling would average a strong effect with a weak one. The article's own L353 contradicts the current wording.
2. **Fix the frame size, the "wins outright" claim, the baseline, and the $49.8k comparator.**
   - L285: change "On `64,000` randomized customers" to 42,613 (the two-arm frame).
   - L212: change "wins outright" to "beats mail-everyone; the best share falls to 25% by $0.50".
   - L121 and L366: say 0.57% control, not a 0.9% baseline.
   - L29, L189, L361: say "mail-everyone-Mens ($49.8k) beats best-arm at a 25% budget until sends cost ≈$0.31". Drop "unconstrained … leads", because unconstrained best-arm planning is $66.3k.
3. **Stop calling revenue minus send cost "profit".** At L75 ("real net profit"), L270 ("Net profit @ 25% budget"), and L293 ("net profit"), and for "net sales" at L45 and L50, define one term once in Objectives L65, for example "net revenue (revenue minus send cost; excludes COGS)", and use only that term. This also removes the L16 compound and brings the 20 repetitions down.
4. **Source or delete the T−X row (L320), and say plainly that the Qini lower bound is borderline (L285).** Ask the implementer to commit `_meta.ci` to `reports/metrics.json`, as README promises, or drop the [−$323, $4,343] row. At L285, state that the same 12.03 score has lower bounds of +0.77 and −0.47 under two bootstrap seeds. While editing, soften L293 to "nominally trails on Qini (CI spans zero)" and restate "2× hot" (L11, L207, L296, L362, L400) as "the predicted spread is about 2× too wide".
5. **Apply the roadmap and language fixes from round 1.**
   - Card 1 (L432): "Power needs 3,063 per arm; 21,306 available".
   - Card 4 (L441): "…above ≈$0.30 per email".
   - Card 5 (L443): "Run a prospective randomized holdout".
   - L212: "drops below 100% coverage".
   - L342: add "pp".
   - Move trailing punctuation out of code spans (L189, L211–213, L240–243, L253, L355, L359) and put `%` inside the spans at L180 and L349.

Second tier (structure):
- Move CUPED (L175–181) to EDA and the multi-arm planning paragraph (L183–189) to Results. In Results, add one sentence on the planning-versus-DR sign flip for best-arm minus single-arm (+$6,027 planning, −$2,902 observed).
- Delete either the Results summary table (L270–276) or the Conclusions policy table (L306–312).
- Make each transition preview the next section's content, as the gold does.

## Ready to publish?

**No.** Five factual misstatements that round 1 flagged are still in the text: Womens conversion, the 64,000 frame, "wins outright", the 0.9% baseline, and the $49.8k comparator. A sixth is new: "net profit" for a revenue-only metric. One number (L320) still has no committed source. Fixes 1–4 are text-only, and about fifteen line edits would clear them.
