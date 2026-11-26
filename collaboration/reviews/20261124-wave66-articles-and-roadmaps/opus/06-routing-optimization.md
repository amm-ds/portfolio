# Review: 06-routing-optimization story.yaml (Wave 6.6)

- Reviewer: Claude Opus (read-only review)
- Target: `projects/06-routing-optimization/story.yaml` (454 lines)
- Gold: `projects/01-rag-agent/story.yaml`
- Evidence checked: `reports/metrics.json`, `reports/results.md`, `README.md`, `DESIGN.md`, `best_known_supplement.csv`, `reports/figures/eda_instance_map.json`

Note on the diff: `git diff -- projects/06-routing-optimization/story.yaml` is empty. The working tree is clean, and the Wave 6.6 edits are already committed in `18adc59d` (+50/−29 on this file). I reviewed the file as committed at HEAD. Line numbers below refer to that file.

## Grades

| # | Dimension | Grade |
|---|---|---|
| 1 | Structure and article logic | 7 |
| 2 | Engagement and human-like narrative | 6 |
| 3 | Language quality | 6 |
| 4 | Technical detail depth | 8 |
| 5 | Truthfulness | 5 |
| 6 | Roadmap cards | 7 |
| 7 | Consistency with gold style | 7 |
| | **Overall** | **6.5** |

The lowest dimension is truthfulness (5). The article mostly holds to the metrics, but it states two different counts of beaten references (5 and 8). It also gets the fleet-first ranking backwards in one bullet and describes the C101 map in a way the figure data contradicts.

## 1. Structure and article logic (7)

- The section order works: question, contract, data, EDA, ladder, evaluation, results, conclusions. Every section ends with a transition line (`Next, ... ([X →](#sec-x))`) and an **In plain terms** card.
- Background (L7–17) and Objectives (L37–38) open with almost the same sentence: "How close can simple, repeatable search get to the best published plans" and then "Measure how close simple, repeatable search gets to the best published plans". The Objectives section starts by repeating the Background section instead of moving forward.
- Evaluation (L227–259) adds little. It repeats the seed, the validator and the CP-SAT role, which Objectives (L42–53) and Training (L173–182) already cover. Its only new number is "about ten times the runtime".
- Conclusions (L297–406) is a full second article: summary, findings, exact numbers, protocol, limits and a recommendation. Most of the bullets repeat Training and Results almost word for word. For example, "restarts never pay; 2-opt HPO moves mean gap only 13.75% → 13.63%" appears at L184–185, L319–320 and L418.
- The article never explains why ALNS uses +3.73 more vehicles than best-known. README L97 gives the reason: the references are hierarchical (vehicles first, then distance), while ALNS minimizes distance. The story mentions only a "benchmark convention" (L61) and never states this. Without it, readers cannot interpret the headline vehicle delta.

## 2. Engagement and human-like narrative (6)

- The concrete parts are good. The C101 walk-through (L114–120), the dispatcher framing (L231, L244) and the "What to do with this" line (L399–402) read naturally.
- Too much of the text tells the reader how to look at diagrams. Examples: "Follow it from the input rules" (L39), "Follow the six family branches in the diagram" (L85), "Follow that merge" (L101), "Follow the search branch" (L229), "Follow the ALNS path in the conclusion diagram" (L301), "The diagram's search path" (L312), "Its fleet-first branch" (L314), "Its exact-solver branch" (L316), "Its tuning path" (L319), "Its reference comparison" (L321). Ten instructions to follow a diagram make the article feel like a tour of figures rather than an argument.
- L19–20 "Both diagrams pass plans through one machine validator" is hard to parse. Diagrams do not pass plans. The pipeline does.

## 3. Language quality (6)

- Glossing everything inline makes some sentences hard to read. For example, "meaning arrival that meets all constraints" (L119), "reject nulls, meaning missing values" (L98), "an optimality certificate, which is a proof that no better valid plan exists" (L103–104), and "which means revising routes as conditions change" (L276).
- "Best-known is not proof" is said at least seven times: L16–17, L103, L272–273, L322, L330–331, L389, L406, plus two key concepts and a caption. Once in Background and once in Limits is enough.
- "machine-checked" and "feasible" appear in almost every section and stop carrying meaning.
- L105–107 "The six families set the reading rules; next, the C101 map". The EDA section then also "sets three rules for reading the results" (L127). Calling both of them "reading rules" is confusing.
- "a measured choice" (L315) and "This measured trade-off gives a fleet-first client a clear choice" (L166–167) are filler.

## 4. Technical detail depth (8)

- This is the strongest part. It covers the regret-2 repair definition, Shaw, worst and random destroy, simulated-annealing acceptance with the code excerpt (L195–212), the `distance + 10,000 × vehicles` lexicographic proxy, CP-SAT with and without a hint, the cold-start anytime frontier, and the bootstrap CI.
- The story also says honestly that the hinted CP-SAT arm is not independent (L174–177, L358). That is good practice.
- Gaps an expert would notice:
  - It never gives the ALNS knobs, even though they are committed (`metrics.json` `tuning.alns_best`: segment 100, reaction 0.5, uniform init). It also omits the destroy size (10, README L201) and the iteration budget.
  - It does not say why C2 and C203 lag. README L200–202 explains: destroy size 10 under-diversifies on wide horizons, and tight chains resist destroy/repair. The story only lists the numbers.
  - It does not explain the vehicle-first convention, as noted in section 1.

## 5. Truthfulness (5)

These claims match `metrics.json` / `results.md`: 4.23% (4.2322), CI [3.22, 5.28], +3.73 / +3.66 vehicles, 316.95 / 71.64 / 18.31 / 13.75 / 13.63, wins 52/4 by distance, fleet-first 38/5/13 (NN 10 + randomized 3), RC202 −3.85%, C203 19.48%, C103 11.67%, C2 6.50%, the family vehicle range +1.00 to +6.75, ALNS 1.15 s and hinted CP-SAT 12.0 s (about 10×), unhinted 13.1 s, the frontier medians 6.58% → ~0.0% at 10 s and 17.60% → 17.06%, the C101 route 860.21 / 11 / 3.77%, the 42-row supplement, the 25-customer proof (286.3 → 191.8 in 2.9 s), the 5-customer proof in 0.1 s, the ~20-move saturation, and the 24 and 12 HPO trials.

Untraceable or contradicted claims:

| Line | Claim | Problem |
|---|---|---|
| L294 | "eight beaten references" | **Contradicted.** `metrics.json` gives 5 ALNS gaps below zero (RC202, R207, R211, RC105, R202) and 6 counting `alns_fleet` (adds RC102). The number 8 only appears if you also count C207, C108 and C109, whose gaps are −0.0004% to −0.0006%, which is floating-point rounding. The story itself says "5 of 56" at L168–169, L368, L405 and L448. README L204 also says 8 and is stale. |
| L321 | "8 best-known plans undercut" | Same contradiction as L294. |
| L161–162 | "naive solvers 13 by using more trucks at far worse distance" | **Contradicted by logic and by L367.** Under fleet-first ranking a solver can only win by using *fewer* vehicles. L367 says "using fewer vehicles". This error predates Wave 6.6 and survived it. |
| L49–50, L306 | "including tuning, in about 130 seconds" / "Seven tuned heuristic rungs take about 130 seconds" | **Untraceable.** No committed file states 130 s. The summed mean runtimes give about 128 s for the evaluation rungs alone (ALNS and `alns_fleet` are about 64 s each). The ALNS HPO adds about 30 s (DESIGN L49) and the 24 2-opt trials add more, so "including tuning" is not supported. L307 "about 13 minutes" and L51 "about eleven minutes" can be derived (56 × 12.0 s ≈ 11.2 min) but are not stated in any committed file. |
| L115–116 (and caption L432–433) | "C101 customers form one tight cluster around it"; "the geographic cluster" | **Contradicted by figure data.** In `eda_instance_map.json`, the customers span x 0–95 and y 5–85 in several separate groups, not one cluster around the depot at (40, 50). Window widths are 37–89 time units against a horizon of about 1,236. Every C101 window is narrow, so "narrow windows are scattered through that cluster" (L116–117) is misleading as well. |
| L304–305 | "per-instance spread, not a sampling-uncertainty interval" | **Self-contradiction.** L152–153 reports a 95% bootstrap CI over the instances, and `metrics.json` `intervals.mean_gap_pct` contains it. |
| L362 | "42 omitted cases" | **Misleading.** The supplement *restores* references for 42 instances (L102, L412, the CSV header). Nothing is omitted, and all 56 are scored. |
| L418 | "2-opt HPO gains 0.12 points" | Rounded twice. The metrics give 13.7535 − 13.6272 = 0.126, which rounds to 0.13. This is minor. |

Count: **5 untraceable or contradicted numbers** (the "8" at L294 and L321, the "130 s including tuning" at L49 and L306, and "0.12" at L418), plus 4 contradicted non-numeric claims (L161, L115, L304, L362).

Stale evidence outside the story, for the owner: README L155 "~0.8 s" ALNS, README L204 "8 instances", and DESIGN L53/L154 "~5x runtime" disagree with `metrics.json` (1.15 s, 5/6 instances, about 10×). The story is right on runtime and should not be "fixed" to match those files.

## 6. Roadmap cards (7)

- All titles start with a verb, and all details are 90 characters or fewer (the longest is 72). The statuses make sense: four shipped and one next.
- "Tie hinted CP-SAT to ALNS" (L420) reads as if the goal was to produce a tie. The work was to add hinted and unhinted CP-SAT arms. Suggest "Add hinted and unhinted CP-SAT arms" with detail "Hinted ties ALNS at ~10× runtime; unhinted finds no plan at 10 s."
- L418 "0.12 points" should be 0.13 (see above).
- The `next` card (L423–424) gives no gate, while the gold cards each name one ("Gate: cross-judge check ..."). "Needs an owner scope decision" is a blocker, not a gate. Suggest "Gate: owner scope; 200-customer GH subset with same validator."

## 7. Consistency with gold style (7)

- Each section has one **In plain terms** card, and the transitions use the `([Section →](#sec-x))` form, as in the gold.
- The gold writes transitions as one sentence tied to a table or chart ("The corpus table ... setting a clean base for search tuning"). This article uses a fixed template, "X sets Y; next, Z", in nearly every section (L106, L138, L219, L254, L290). It reads as mechanical.
- Gold plain-terms cards are one sentence. Here, L222–224 and L293–295 are two sentences, and L293–295 repeats the wrong "eight".
- The Conclusions section uses `##` subheadings and long tables, which the gold does not have to the same extent. That makes this article much longer than the gold's closing section.

## Top 5 fixes (by severity)

1. **L294 and L321: fix the beaten-reference count.** Replace "eight beaten references" and "8 best-known plans undercut" with "5 beaten references (6 with `alns_fleet`)". Add a note that the C108, C109 and C207 ties (−0.0004%) are rounding, not real wins.
2. **L161–162: reverse the fleet-first explanation.** Replace "naive solvers 13 by using more trucks at far worse distance" with "naive solvers 13 by using fewer trucks at far worse distance", so it agrees with L367.
3. **L115–117 and caption L432–433: correct the C101 description.** Replace "C101 customers form one tight cluster around it" with a statement that customers form several tight clusters across the map, and say that every window is narrow (37–89 units in a ~1,236 horizon). The point about the clock still holds.
4. **L49–50 and L306–307: remove or source "about 130 seconds", "including tuning".** Either cite a committed timing or say "evaluation rungs total about 2 minutes (summed mean runtimes); tuning is extra". Also remove the self-contradiction at L304–305 "not a sampling-uncertainty interval", because L153 reports a bootstrap CI.
5. **L59–62 or L12–14: explain the vehicle-first convention.** Add one sentence: best-known references minimize vehicles first and distance second, while ALNS minimizes distance, so the +3.73 vehicles partly reflects a different objective. This is in README L97. In the same pass, fix L362 "42 omitted cases" to read "42 references restored" and L418 "0.12" to read "0.13".
