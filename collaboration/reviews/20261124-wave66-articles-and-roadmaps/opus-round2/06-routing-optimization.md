# Round-2 review: 06-routing-optimization story.yaml

- Reviewer: Claude Opus (read-only, second round)
- Target: `projects/06-routing-optimization/story.yaml` at HEAD (`a55e37ae`; story last changed in `e69bba84`, 422 lines)
- Gold: `projects/01-rag-agent/story.yaml`
- Prior round: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus/06-routing-optimization.md`
- Evidence re-checked: `reports/metrics.json` (summary, instances, ranking, intervals, frontier, tuning, unhinted_cp_sat, family_vehicle_deltas), `reports/figures/eda_instance_map.json`, `data/raw/C101.txt`, `data/raw/dataset_card.json`, `best_known_supplement.csv` (42 data rows), `params.yaml`, `README.md`, `DESIGN.md`, `src/routing_optimization/`.

Line numbers refer to the current HEAD file.

## What changed since round 1

`e69bba84` reindented the whole file and rewrote the Background section (new three-bullet solver-ladder walk-through, L13–17), the `short_version`, and every **In plain terms** card. The body of Objectives through Conclusions, the key concepts, the captions and the roadmap are textually unchanged apart from indentation. As a result, most round-1 findings remain. The rewritten plain-terms cards fixed the "eight" in the old Conclusions card, but added one new unit error (L206) and one new runtime contradiction (L55).

## Grades

| # | Dimension | Grade | Change |
|---|---|---|---|
| 1 | Structure and article logic | 7 | = |
| 2 | Engagement and human-like narrative | 6 | = |
| 3 | Language quality | 6 | = |
| 4 | Technical depth | 8 | = |
| 5 | Truthfulness | 5 | = |
| 6 | Roadmap cards | 7 | = |
| 7 | Consistency with gold template | 7 | = |
| | **Overall** | **6.5** | = |

The lowest dimension is still truthfulness (5).

## 1. Structure and article logic (7)

- The order matches the gold exactly: background, objectives, data, eda, training, evaluation, results, conclusions. Each section ends with a forward link and one **In plain terms** card (8 of 8).
- The new Background (L7–21) is better. It states the question, the headline numbers and a three-step ladder in about 150 words, close to the gold's 163.
- Objectives (L25–26) still opens by repeating the Background question (L7): "Measure how close simple, repeatable search gets to the best published plans".
- Evaluation (L209–239) still adds little. It repeats the seed, the validator and the exact-solver role. Its only new fact is "about ten times the runtime" (L232–233), which is correct (12.00 s / 1.15 s = 10.4).
- Conclusions (L275–383, about 890 words) still restates Training and Results. "Restarts never pay" and "13.75% → 13.63%" appear at L167–169, L297–298 and in the roadmap at L394. "Best-known is not proof" appears again at L300.
- The article still never explains *why* ALNS uses +3.73 more vehicles than best-known. README L95–98 states the cause: the Solomon references optimize vehicles first and distance second, while ALNS minimizes distance. L33–34 and L47–50 mention fleet-first ranking and a "benchmark convention", but they never say the references were built under that objective. Without this, the headline vehicle delta reads as a weakness of ALNS rather than a difference in objective.

## 2. Engagement and human-like narrative (6)

- The Background bullets and the "What to do with this" close (L377–380) are good.
- Diagram-tour narration is now more frequent than in round 1. Instances: L13 "Follow the solver ladder", L27 "Follow it from the input rules", L71 "Follow the six family branches", L87 "Follow that merge", L212 "Follow the search branch", L224 "Three diagram paths carry", L279 "Follow the `ALNS` path in the conclusion diagram", L290 "The diagram's search path", L292 "Its fleet-first branch", L294 "Its exact-solver branch", L297 "Its tuning path", L299 "Its reference comparison", L307 "These tables quantify the diagram's paths", L351 "These details qualify every path in the conclusion diagram". The 06 file uses "follow" 6 times; the gold uses it twice. The argument gets lost under directions for reading the figures.
- The gold uses a first-person "we" voice ("we set the rules", "we trace"). This article is impersonal outside the plain-terms cards, which makes the body feel like a specification.

## 3. Language quality (6)

- Inline glosses still interrupt sentences: L84 "reject nulls, meaning missing values", L103–104 "feasible arrival time, meaning arrival that meets all constraints", L89–90 "an optimality certificate, which is a proof that no better valid plan exists", L256–257 "dynamic re-optimization, which means revising routes as conditions change", L35–36 "a fixed seed, which is a fixed starting point for random choices".
- "Best-known is not a proof" is repeated at L89–90, L252–253, L300, L308–309, L367–368, in the key concepts (L403) and in the caption at L422. One statement in Data and one in Limits would be enough.
- "Machine-checked" or "feasible and checked" appears at L16, L138, L280–281, L290–291 and L378. Repetition has worn the phrase out.
- "Reading rules" is still overloaded: the families "set the reading rules" (L92), then the EDA figure "sets three rules for reading the results" (L112), then "the map sets three reading rules" (L123).
- Filler remains: "This measured trade-off gives a fleet-first client a clear choice" (L150–151) and "a measured choice" (L293).
- Inline-code formatting of numbers is inconsistent. Compare `` `4.23%` `` (L136) with `` `18.31`% `` (L135), `` `13.63`% `` (L136), `` `3.22` % `` (L137), `` `11.67`% `` (L156) and `` `−3.85`% `` (L155). Depending on the renderer, the percent sign may sit outside the code span.

## 4. Technical depth (8)

- Still the strongest dimension. The article covers the regret-2 definition, random, worst and Shaw destroy, annealing acceptance with a real code excerpt (L180–196), the `distance + 10,000 × vehicles` proxy, hinted versus unhinted CP-SAT, the cold-start anytime frontier, and a bootstrap CI. It also states honestly that the hinted CP-SAT arm is not independent of ALNS (L158–160, L336).
- Gaps an expert would notice, all unchanged since round 1:
  - The tuned ALNS settings are never stated. L359–361 only points to `params.yaml`. The values are committed: segment 100, reaction 0.5 and uniform init (`metrics.json` `tuning.alns_best`), plus `alns_destroy_q: 10` and `alns_max_iterations: 120` (`params.yaml` L88–89).
  - The article never says why C2 and C203 lag (L155–156, L346). README L200–202 gives the reason: a destroy size of 10 under-diversifies on wide horizons, and tight chains resist q-customer destroy/repair.
  - The vehicle-first reference convention is not explained (see section 1).

## 5. Truthfulness (5)

### Verified against committed files

These claims check out:

- `metrics.json` `summary`: 4.23% (4.2322), +3.73 / +3.66, 4.30% (4.2993), 316.95, 71.64, 18.31, 13.75, 13.63, ALNS 1.15 s, hinted CP-SAT 12.00 s, and the headline-table "Δ gap vs nn" column (+245.31, −58.01, −67.41, −67.34).
- The bootstrap CI [3.22, 5.28] (`intervals.mean_gap_pct`).
- The rankings 52/4 and 38/5/13 (NN 10 + randomized 3).
- ALNS negative gaps: RC202 −3.85, R207, R211, RC105, R202, which is 5. Adding RC102 for `alns_fleet` gives 6.
- C203 19.48%, C103 11.67% and C2 6.50%.
- Family vehicle deltas +1.00 to +6.75.
- Unhinted CP-SAT: UNKNOWN on all 56, mean 13.09 s.
- Frontier medians: 6.58% at 0.25 s, 0.0006% at 10 s, and 17.60% → 17.06% for CP-SAT.
- The C101 plan: 860.21, 11 routes, 3.77% against 828.94.
- 42 supplement rows; family counts 9/8/12/11/8/8.
- Small-case proofs: 286.3 → 191.8 in 2.9 s and 0.1 s (README L176–179). About 20 accepted moves (README L209).
- 24 and 12 HPO trials on a 6-instance subset; a pinned SHA-256 (`dataset_card.json`); the SINTEF mirror; DQ gates (DESIGN L61).
- "About ten times" (10.4×). "About eleven minutes" for hinted CP-SAT (56 × 12.0 s = 11.2 min, derived).

### Untraceable or contradicted claims

| Line | Claim | Problem | Round 1 |
|---|---|---|---|
| L299 | "8 best-known plans undercut" | **Contradicted.** ALNS has 5 negative gaps (6 with `alns_fleet`), which the story itself says at L17, L152–154, L273 and L382. Reaching 8 requires counting C207, C108 and C109 at −0.0004% to −0.0006%, which is floating-point noise. README L204 is stale. | still present |
| L144–146 | "naive solvers 13 by using more trucks at far worse distance" | **Contradicted.** Under fleet-first ranking a solver can only win with *fewer* vehicles. L345 and README L140–141 say "fewer". NN wins on R2/RC2, where its mean vehicle delta is +5.36 / +6.00 against ALNS's +6.73 / +6.75. | still present |
| L101–102, caption L407–408 | "C101 customers form one tight cluster around it"; "narrow windows are scattered through that cluster" | **Contradicted by figure data.** `eda_instance_map.json` customers span x 0–95 and y 5–85 in several separate groups around a depot at (40, 50). Every C101 window is narrow: widths run 37–89 against a 1,236 horizon. "Narrow windows scattered through" implies some windows are wide. | still present |
| L37–38 | "Finish the 56-problem heuristic ladder, including tuning, in about 130 seconds" | **Misattributed.** 130 s is the sum of mean evaluation runtimes for the seven heuristic rungs (129.5 s), excluding tuning. README L85 says "benchmark + both HPO searches + ALNS ≈ 2 min". Either cite README's ≈2 min or drop "including tuning". | still present |
| L284–285 | "Seven tuned heuristic rungs take about 130 seconds; all eight solvers with hinted CP-SAT take about 13 minutes" | 130 s is derivable as above. 13 min (801.5 s summed) is not stated anywhere, and README L13 and L86 say "~15 min" for the full stage. Both numbers should be labeled as summed evaluation runtimes, or aligned with the README. | still present (13 min part) |
| L55 | "keep the entire search under two minutes" | **New, contradicted.** It conflicts with L37 (about 130 s, which is over 2 min), L39 (+11 min hinted CP-SAT) and L285 (about 13 min). | new |
| L206 | "a truck-saving variant trades 0.07% distance for slightly fewer trucks" | **New, wrong unit.** The trade is +0.07 *percentage points* of mean gap (L149, L292). The mean-distance difference is 1062.23 against 1062.02, or 0.02%. | new |
| L152–155, L346 | "6 counting `alns_fleet`, with RC202 best at −3.85%" | **Imprecise.** −3.85% is ALNS's best. `alns_fleet` reaches −5.79% on RC202, so once the variant is counted, the best is −5.79%. | new (not caught in round 1) |
| L282–284 | "per-instance spread, not a sampling-uncertainty interval" | **Self-contradiction.** L136–137 reports a 95% bootstrap CI over the instances (`intervals.mean_gap_pct`). | still present |
| L340 | "42 omitted cases" | **Misleading.** The supplement *restores* 42 references (L88, L388, DESIGN L50). All 56 instances are scored. | still present |
| L394 | "2-opt HPO gains 0.12 points" | Double rounding. 13.7535 − 13.6272 = 0.126, which rounds to 0.13. Minor. | still present |

Untraceable or contradicted **numbers**: 7. They are L299 "8", L37 "130 s including tuning", L285 "13 minutes", L55 "two minutes", L206 "0.07% distance", L154/L346 "best at −3.85%" (when counting `alns_fleet`), and L394 "0.12". There are also 4 contradicted non-numeric claims: L145, L101/L407, L283 and L340.

Stale evidence outside the story, which the owner should fix in those files rather than in the story: README L155 "~0.8 s", README L204 "8 instances", and DESIGN L53/L154 "~5x runtime" all disagree with `metrics.json`.

## 6. Roadmap cards (7)

- All titles are verb-first: Pin, Build, Tune, Tie, Extend. Details are 47–66 characters, all within 90.
- The shipped claims check out against the repo:
  - Supplement: `best_known_supplement.csv` has 42 data rows.
  - Validated eight-solver ladder: `schemas.py` `RoutePlan.validate_against`; 8 solvers in `metrics.json` `summary`.
  - Seeded HPO: `tuning.py`, and `solver_best` / `alns_best` in `params.yaml`.
  - CP-SAT arms: `ortools_solver.py` and `metrics.json` `unhinted_cp_sat`.
  - The `next` Gehring–Homberger card is correctly not shipped (README L305–306).
- L396 "Tie hinted CP-SAT to ALNS" still reads as if a tie was the goal. Suggested replacement: "Add hinted and unhinted CP-SAT arms", detail "Hinted ties ALNS at ~10× runtime; unhinted finds no plan at 10 s."
- L394 "0.12 points" should read "0.13".
- L400: the `next` card still names a blocker ("Needs an owner scope decision"), not a gate. The gold pattern is "Gate: …".

## 7. Consistency with gold template (7)

- Matches the gold: the same eight section ids, one plain-terms card per section, `([X →](#sec-x))` links, a code excerpt with a source link, and `##` subheadings in Conclusions. The gold also has five `##` headings, so the round-1 remark that the gold lacks them was overstated. Conclusions is about 890 words against the gold's 729, which is a modest overrun.
- All plain-terms cards are now one sentence, so the round-1 issue with two-sentence cards is fixed.
- Transitions still follow the mechanical "X sets Y; next, Z" template at L52, L92, L123, L203, L236 and L270. The gold ties each transition to a concrete artifact in its own words.
- The gold's `short_version` packs exact headline metrics. The 06 version does the same and is accurate.

## Round-1 finding status

| # | Round-1 finding | Status | Evidence (HEAD lines) |
|---|---|---|---|
| 1 | Objectives repeats the Background opener | STILL PRESENT | L7 vs L25–26 |
| 2 | Evaluation section adds little | STILL PRESENT | L209–239 |
| 3 | Conclusions is a second article and repeats Training/Results | STILL PRESENT | L167–169, L297–298, L394 |
| 4 | Vehicle-first reference convention unexplained | STILL PRESENT | L33–34, L47–50; README L95–98 not reflected |
| 5 | Too many "follow the diagram" directions | STILL PRESENT (worse: 14) | L13, L27, L71, L87, L212, L224, L279, L290–299, L307, L351 |
| 6 | "Both diagrams pass plans through one machine validator" | FIXED | Background rewritten (L13–17) |
| 7 | Inline glosses clutter sentences | STILL PRESENT | L35, L84, L89–90, L103–104, L256–257 |
| 8 | "Best-known is not proof" repeated | STILL PRESENT | L89, L252, L300, L308, L367, L403, L422 |
| 9 | "Machine-checked" / "feasible" overuse | STILL PRESENT | L16, L138, L280, L291, L378 |
| 10 | "Reading rules" used twice for different things | STILL PRESENT | L92, L112, L123 |
| 11 | Filler "measured choice" | STILL PRESENT | L150–151, L293 |
| 12 | ALNS knobs, destroy size and iterations missing | STILL PRESENT | L359–361 |
| 13 | No explanation for C2/C203 lag | STILL PRESENT | L155–156, L346 |
| 14 | "eight beaten references" (old Conclusions plain terms) | FIXED | L382 now "5 of 56" |
| 15 | "8 best-known plans undercut" | STILL PRESENT | L299 |
| 16 | Fleet-first "more trucks" reversed | STILL PRESENT | L144–146 |
| 17 | "130 s including tuning" / "13 minutes" untraceable | STILL PRESENT | L37–38, L284–285 |
| 18 | C101 "one tight cluster" contradicted by data | STILL PRESENT | L101–102, L407–408 |
| 19 | "not a sampling-uncertainty interval" contradicts CI | STILL PRESENT | L282–284 vs L136–137 |
| 20 | "42 omitted cases" | STILL PRESENT | L340 |
| 21 | "0.12 points" should be 0.13 | STILL PRESENT | L394 |
| 22 | Roadmap title "Tie hinted CP-SAT to ALNS" | STILL PRESENT | L396 |
| 23 | `next` card has no gate | STILL PRESENT | L400 |
| 24 | Mechanical "X sets Y; next, Z" transitions | STILL PRESENT | L52, L92, L123, L203, L236, L270 |
| 25 | Two-sentence plain-terms cards (one with the wrong "eight") | FIXED | all eight cards are one sentence |
| 26 | Conclusions heavier than the gold | PARTLY FIXED (overstated in round 1) | the gold also has 5 `##`; 887 against 729 words |

Totals: 3 FIXED, 1 PARTLY FIXED, 22 STILL PRESENT.

## Top 5 remaining fixes, by severity

1. **L299, plus L152–155 and L346: fix the undercut count and the best value.** Replace "8 best-known plans undercut, best RC202 at −3.85%" with "5 best-known references undercut by ALNS (6 with `alns_fleet`); best RC202 at −3.85% (−5.79% for `alns_fleet`)". Optionally add that C108, C109 and C207 at about −0.0005% are rounding ties.
2. **L144–146: reverse the fleet-first explanation.** Change "by using more trucks" to "by using fewer trucks", so it matches L345 and README L140–141.
3. **L101–102 and caption L407–408: correct the C101 description.** Say that customers form several tight clusters spread across the map around the depot, and that every window is narrow (37–89 units in a 1,236-unit horizon). The point that the clock constrains visit order still holds.
4. **L37–38, L55 and L284–285: make the runtime claims consistent and sourced.** Use README L85 ("≈ 2 min including both HPO searches") and README L13 ("~15 min with hinted CP-SAT"), or label 130 s and 13 min as summed evaluation runtimes that exclude tuning. Rewrite the L55 card so it does not claim "the entire search under two minutes".
5. **Precision and explanation pass:**
   - L206: change "0.07% distance" to "0.07 points of gap".
   - L282–284: delete "not a sampling-uncertainty interval", because the bootstrap CI is reported.
   - L340: change "42 omitted cases" to "42 references restored".
   - L394: change "0.12" to "0.13".
   - Add one sentence near L33–34 or L47–50 saying that Solomon best-known references minimize vehicles first and distance second, while ALNS minimizes distance. This is why the +3.73 vehicle delta partly reflects a different objective (README L95–98).

## Ready to publish?

**No.** The three highest-severity truthfulness errors from round 1 are still in the file: the 8-versus-5 contradiction (L299), the reversed fleet-first logic (L145) and the C101 description that the data contradicts (L101, L407). The rewritten plain-terms cards also add a runtime contradiction (L55) and a unit error (L206). Fixes 1–4 are each one-line edits, and once they and the precision pass in fix 5 are applied, the article would be close to publishable. The narrative issues (diagram-tour phrasing, repeated caveats) can follow.
