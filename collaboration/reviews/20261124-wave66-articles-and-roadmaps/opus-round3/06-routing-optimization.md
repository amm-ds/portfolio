# Round-3 review: 06-routing-optimization story.yaml

- Reviewer: Claude Opus (read-only, third round)
- Target: `projects/06-routing-optimization/story.yaml`, **working tree** on `wave8-articles-truthfulness-2026-11-25` (HEAD `c05accd0` plus uncommitted Wave 8 edits, 427 lines)
- Gold: `projects/01-rag-agent/story.yaml`
- Prior round: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus-round2/06-routing-optimization.md`
- Evidence re-checked: `reports/metrics.json` (`summary`, `instances`, `ranking`, `intervals`, `families`, `family_vehicle_deltas`, `frontier`, `tuning`, `unhinted_cp_sat`), `reports/results.md`, `reports/figures/eda_instance_map.json`, `data/raw/C101.txt`, `params.yaml`, `README.md` and `DESIGN.md` (working tree), `apps/showcase-web/src/diagrams/solverLadder.ts` and `auto/06-routing-optimization-{2..5}.ts`.

Line numbers refer to the working-tree file.

## What changed in Wave 8

The diff to `story.yaml` is a focused truthfulness pass. It touches:

- the runtime claims (L37–38, L57, L285–287),
- the vehicle-objective explanation (L49–52),
- the C101 description and caption (L103–106, L412–413),
- the fleet-first "fewer trucks" logic (L147),
- the RC202 and undercut counts (L156–157, L301–303, L349),
- the "42 references restored" wording (L343),
- the tuned ALNS settings and the C2/C203 explanation (L363–366),
- the Training plain-terms card (L208),
- the roadmap (L399, L401–402, L405).

README L155 and L204–205 and DESIGN L53 and L154 were brought in line with `metrics.json` in the same pass. The narrative, language and structure issues are untouched.

## Grades

| # | Dimension | Grade | Round 2 |
|---|---|---|---|
| 1 | Structure and article logic | 7 | 7 |
| 2 | Engagement and human-like narrative | 6 | 6 |
| 3 | Language quality | 6 | 6 |
| 4 | Technical depth | 8.5 | 8 |
| 5 | Truthfulness | 8.5 | 5 |
| 6 | Roadmap cards | 9 | 7 |
| 7 | Consistency with gold template | 7 | 7 |
| | **Overall** | **7.5** | 6.5 |

The lowest dimension is now **engagement (6)**, tied with language quality (6).

## 1. Structure and article logic (7)

- The section order matches the gold. All 8 sections end with a forward link and one **In plain terms** card.
- **Fixed:** the vehicle-first reference convention is now explained (L50–52). This was the main logical gap in rounds 1 and 2. However, the inference it draws is too strong (see section 5, N1).
- **Still present:** Objectives (L25–26) reopens with the Background question (L7).
- **Still present:** Evaluation (L213–241) adds one new fact, "about ten times the runtime" (L234–235). Everything else repeats the seed, the validator and the role of the exact solver.
- **Still present, and slightly worse:** Conclusions has grown to about 946 words, against the gold's 729. It restates Training and Results:
  - RC202 −3.85% / −5.79% now appears three times (L156–157, L302–303, L349).
  - "restarts never pay" / "13.75% → 13.63%" appears at L170–171, L299–300 and in the roadmap (L399).
- **Misplaced:** the C2/C203 explanation (L364–366) sits in Protocol, so the reader meets the 6.50% and 19.48% gaps at L157 and L253 without it. It belongs beside the gaps, in Training or Results.

## 2. Engagement and human-like narrative (6)

- The strongest passages are unchanged: the Background bullets (L13–17) and the "What to do with this" close (L382–385).
- **Still present:** diagram-tour narration. The file uses "follow" 6 times, against 2 in the gold. Examples:
  - "Follow the solver ladder" (L13)
  - "Follow it from the input rules" (L27)
  - "Follow the six family branches" (L73)
  - "Follow that merge" (L89)
  - "Follow the search branch" (L213)
  - "Follow the `ALNS` path" (L281)

  The "Its … branch/path" bullets (L292–303), "These tables quantify the diagram's paths" (L310) and "These details qualify every path" (L354) add to it.
- **Still present:** an impersonal voice. Outside the plain-terms cards, the file has 4 uses of "we/our"; the gold has 14.

## 3. Language quality (6)

- **Still present:** inline glosses interrupt sentences:
  - L35–36 "a fixed seed, which is a fixed starting point"
  - L86 "reject nulls, meaning missing values"
  - L91–92 "an optimality certificate, which is a proof…"
  - L106 "feasible arrival time, meaning arrival that meets all constraints"
  - L258–259 "dynamic re-optimization, which means revising routes…"
- **Still present:** "best-known is not proof" is repeated at L91, L254–255, L303, L311–312, L372–373, L408 and L427.
- **Still present:** "machine-checked" / "feasible and checked" is repeated at L16, L140, L283, L292–293 and L383.
- **Still present:** "reading rules" means two different things (L94, L114, L125).
- **Still present:** filler at L152–153 ("gives a fleet-first client a clear choice") and L295 ("a measured choice").
- **Still present:** the percent sign is formatted inconsistently. Compare `` `4.23%` `` (L138) with `` `18.31`% `` (L137), `` `13.63`% `` (L138), `` `3.22` % `` (L139), `` `11.67`% `` (L158), `` `13.63`% `` (L170, L300). Wave 8 added more `` `X%` `` spans (L157, L302), so the file now mixes both styles in one paragraph.
- **New hygiene issue:** Wave 8 left unwrapped lines inside wrapped paragraphs (L49, L106, L157). They render correctly but break the file's own wrapping convention.

## 4. Technical depth (8.5)

- **Improved:**
  - The tuned ALNS settings are now stated (L363–364).
  - The C2/C203 failure modes are named (L364–366; README L199–202).
  - The vehicles-first reference objective is introduced (L50–52).
- **Still strong:** the regret-2, destroy-operator and annealing definitions; the real code excerpt (L182–197); the hinted/unhinted CP-SAT honesty (L159–168, L339); the cold-start frontier (L264–270); the bootstrap CI.
- **Remaining depth gap:** the new objective sentence never uses the article's own controlled experiment. `alns_fleet` optimizes the vehicles-first objective and still sits at +3.66 vehicles. So the difference in objective explains only about 0.07 of the +3.73 delta. The rest is a limit of the search: a 10,000-per-vehicle penalty, 120 iterations, and destroy size 10. That observation is the more interesting technical point, and it is missing.

## 5. Truthfulness (8.5)

### Verified against committed files (working tree)

- `summary`: 4.23 (4.2322), 4.30 (4.2993), +3.73 / +3.66, 316.95, 71.64, 18.31, 13.75 → 13.63, ALNS 1.15 s ("~1.1 s"), hinted CP-SAT 12.00 s, unhinted 13.09 s ("13.1 s"). The headline Δ-vs-nn column checks out.
- 12.00 / 1.15 = 10.4, so "about ten times" (L234) and "~10×" (L402) hold.
- `intervals.mean_gap_pct`: [3.2232, 5.2815], n = 56, 2000 bootstrap draws. "Include a 95% bootstrap interval" (L285) is now correct.
- `ranking`: by distance, ALNS 52 and `alns_fleet` 4. By vehicles then distance: 38 / 5 / 13 (NN 10 + randomized 3). "Fewer trucks" (L147) is now correct: NN's family vehicle deltas on R2 (+5.36) and RC2 (+6.00) are below ALNS's (+6.73 / +6.75).
- Negative gaps: ALNS has R202, R207, R211, RC105 and RC202 (5 non-trivial), and `alns_fleet` adds RC102 (6). RC202 is −3.8478 for ALNS and −5.7898 for `alns_fleet`.
- C203 19.48, C103 11.67, C2 family 6.50.
- Family vehicle deltas run from +1.00 to +6.75.
- No solver has a negative vehicle delta on any instance (minimum 0), so "No solver beats the best-known fleet size" (L148) holds.
- C101 (`eda_instance_map.json`, `data/raw/C101.txt`): customer windows are 37–89 wide, the depot horizon is 1236, and the depot is at (40, 50) with several separate groups of customers. L103–106 and the caption at L412–413 are now correct.
- Runtimes: README L85–86 gives "≈ 2 min" including both HPO searches and "≈ 15 min" total, and README L13 gives "~15 min". L37–38, L57 and L286–287 match.
- `best_known_supplement.csv` has 42 rows, matching "42 references restored" (L343).
- The ALNS winner settings are segment 100, reaction 0.5 and uniform (`tuning.alns_best`; `params.yaml` L118–121). The destroy size of 10 and the 120 iterations are in `params.yaml` L88–89.
- 2-opt HPO: 13.7535 − 13.6272 = 0.126, which rounds to 0.13 (L399).
- Frontier: ALNS median 6.58% at 0.25 s and 0.0006% at 10 s. CP-SAT median 17.60%, dropping to 17.06% at 30 s.
- C101 plan: 860.21 over 11 routes, 3.77% above 828.94.
- The small-case proofs (191.8 in 2.9 s, 286.3 → 191.8, 0.1 s) and "~20 accepted moves" match README L176–179 and L210.
- Diagram labels match the article: 316.95%, 4.23%, ~1.1 s, +3.73 vehicles, "42 cases", "8 solvers, 56 instances", seed 42.

### Untraceable, contradicted or misleading claims

| ID | Line | Claim | Problem | Severity |
|---|---|---|---|---|
| N1 | L50–52 | "The `+3.73` vehicle delta therefore partly reflects a different objective" | **Misleading inference (new).** The article's own control contradicts the weight this sentence implies. `alns_fleet` uses the vehicles-first objective and still averages +3.66 (`summary.alns_fleet.mean_vehicle_delta`), so the objective accounts for 0.07 of 3.73, about 2%. "Partly" is technically true but reads as the main explanation. README L95–98 makes the same framing, so the sentence is traceable to the README but not supported by the metrics. | Medium |
| N2 | L363–364 | "The `ALNS` winner uses segment 100, reaction 0.5, uniform initial weights, destroy size 10, and 120 iterations" | **Misattribution (new, minor).** The HPO space was segment/reaction/init only (`params.yaml` L101–108; DESIGN L49). The destroy size and iteration count are fixed parameters, not part of the tuned winner. | Low |
| S1 | L154–156 | "beats the best-known reference on 5 of 56 instances in the per-instance record (`reports/results.md`)" | **Soft attribution (pre-existing).** `results.md` shows 8 ALNS rows with a minus sign: C108, C109 and C207 print as `-0.00` (−0.0004% to −0.0006%). The count of 5 is right once those rounding ties are excluded, but the cited file does not state that exclusion. One clause ("excluding three −0.00% rounding ties") closes it. | Low |
| S2 | L21 vs L3, L387 | "roughly 4 extra trucks" vs "3.7 more vehicles" / "~3.7 extra trucks" | Inconsistent rounding of the same 3.73 (pre-existing). Not wrong, but a careful reader will notice. | Cosmetic |

Hard untraceable or contradicted **numbers: 0.** S1 is a soft attribution gap on one number.

Out-of-story evidence: README and DESIGN are now aligned with `metrics.json` (~1.1 s, 5/6 undercuts, ~10×). One diagram issue predates this round: `solverLadder.ts` L6 titles the diagram "The eight-rung solver ladder" but draws nine nodes. The ninth is the unhinted CP-SAT arm, which is not one of the 8 solvers in `metrics.json` `summary`. Either retitle it ("eight solvers plus an unhinted probe") or mark that node as a probe.

## 6. Roadmap cards (9)

- All titles are verb-first: Pin, Build, Tune, Add, Extend.
- Detail lengths are 61, 49, 47, 71 and 79 characters, all ≤ 90.
- The shipped claims check out against the repo:
  - Supplement: 42 rows.
  - Eight-solver validated ladder: `metrics.json` `summary` has 8 solvers, and `RoutePlan.validate_against` validates plans.
  - Seeded HPO: `tuning.py`, plus `solver_best` and `alns_best` in `params.yaml`.
  - Hinted and unhinted arms: `ortools_solver.py` and `metrics.json` `unhinted_cp_sat`.
- "0.13 points" (L399) is now correct, and "~10× runtime" (L402) matches 10.4×.
- The `next` card now states a gate in the gold's "Gate: …" pattern (L405). Gehring–Homberger is correctly not shipped.
- Nit: the L399 detail repeats the Conclusions tuning bullet word for word. A different angle would read better, for example: "Seeded 2-opt and ALNS searches; negative results kept".

## 7. Consistency with gold template (7)

- Matches the gold:
  - the same eight section ids,
  - one-sentence plain-terms cards,
  - `([X →](#sec-x))` links,
  - a code excerpt with a source link,
  - `##` subheadings in Conclusions,
  - an exact-metric `short_version`.
- Diverges from the gold:
  - **Still present:** mechanical "X sets Y; next, Z" transitions (L54, L94, L125, L205, L238, L272).
  - Conclusions is now about 30% over the gold's length (946 vs 729 words).
  - The voice is less personal than the gold's (see section 2).

## Round-2 finding status

The table covers the round-2 list (its round-1 carry-overs plus its own new findings).

| # | Finding | Status | Evidence (working-tree lines) |
|---|---|---|---|
| 1 | Objectives repeats the Background opener | STILL PRESENT | L7 vs L25–26 |
| 2 | Evaluation section adds little | STILL PRESENT | L213–241 |
| 3 | Conclusions repeats Training/Results | STILL PRESENT (worse) | RC202 now three times: L156–157, L302–303, L349; tuning: L170, L299, L399 |
| 4 | Vehicle-first reference convention unexplained | FIXED (new over-claim, see N1) | L50–52 |
| 5 | Too many "follow the diagram" directions | STILL PRESENT | L13, L27, L73, L89, L213, L281, L292–303, L310, L354 |
| 6 | "Both diagrams pass plans through one validator" | FIXED (round 2) | — |
| 7 | Inline glosses clutter sentences | STILL PRESENT | L35, L86, L91, L106, L258 |
| 8 | "Best-known is not proof" repeated | STILL PRESENT | L91, L254, L303, L311, L372, L408, L427 |
| 9 | "Machine-checked" overuse | STILL PRESENT | L16, L140, L283, L292, L383 |
| 10 | "Reading rules" overloaded | STILL PRESENT | L94, L114, L125 |
| 11 | Filler "measured choice" | STILL PRESENT | L152–153, L295 |
| 12 | ALNS knobs, destroy size and iterations missing | FIXED (minor misattribution, see N2) | L363–364 |
| 13 | No explanation for the C2/C203 lag | FIXED (placed in Protocol, far from the numbers) | L364–366 |
| 14 | "eight beaten references" in the plain-terms card | FIXED (round 2) | L387 |
| 15 | "8 best-known plans undercut" | FIXED | L301–303 |
| 16 | Fleet-first "more trucks" reversed | FIXED | L147 |
| 17 | "130 s including tuning" / "13 minutes" | FIXED | L37–38, L286–287 |
| 18 | C101 "one tight cluster" | FIXED | L103–106, L412–413 |
| 19 | "Not a sampling-uncertainty interval" vs the CI | FIXED | L285 |
| 20 | "42 omitted cases" | FIXED | L343 |
| 21 | "0.12 points" | FIXED | L399 |
| 22 | Roadmap title "Tie hinted CP-SAT to ALNS" | FIXED | L401–402 |
| 23 | `next` card has no gate | FIXED | L405 |
| 24 | Mechanical "X sets Y; next, Z" transitions | STILL PRESENT | L54, L94, L125, L205, L238, L272 |
| 25 | Two-sentence plain-terms cards | FIXED (round 2) | — |
| 26 | Conclusions heavier than the gold | PARTLY FIXED (now 946 vs 729 words, grew this round) | L277–389 |
| 27 | L55 "entire search under two minutes" | FIXED | L57 |
| 28 | L206 "0.07% distance" (wrong unit) | FIXED | L208 "0.07 points of benchmark gap" |
| 29 | "RC202 best at −3.85%" when counting `alns_fleet` | FIXED | L156–157, L302–303, L349 |
| 30 | Inconsistent `X`% vs `X%` formatting | STILL PRESENT (more mixed now) | L137–139, L157–158, L170, L300 |

Totals: **18 FIXED, 1 PARTLY FIXED, 11 STILL PRESENT.** All 10 truthfulness findings from round 2 are fixed. Every finding still present concerns narrative, language or structure.

## New errors introduced by Wave 8

1. **N1, L50–52: the objective explanation overstates its case.** The article's own `alns_fleet` arm shows that switching to the vehicles-first objective cuts the fleet delta by only 0.07.
2. **N2, L363–364: fixed parameters presented as tuned.** Destroy size 10 and 120 iterations are listed as part of the HPO "winner", but they were never searched.
3. **More repetition:** the RC202 pair (−3.85% / −5.79%) now appears three times, and Conclusions grew by about 60 words.
4. **Hygiene:** there are unwrapped long lines inside wrapped paragraphs (L49, L106, L157), and percent-sign formatting is more mixed than before (L157, L302 vs L137–139).

## Top 5 remaining fixes

1. **L50–52 (truthfulness/depth).** Replace the sentence with the controlled evidence. Suggested: "The Solomon references optimize vehicles first; the main `ALNS` arm minimizes distance. Switching `ALNS` to a vehicles-first objective (`alns_fleet`) trims the delta only from `+3.73` to `+3.66`, so most of the fleet gap is a search limit, not a convention." Mirror the change in README L95–98.
2. **L363–366 (accuracy and placement).** Split the sentence: "HPO chose segment 100, reaction 0.5 and uniform initial weights; destroy size 10 and 120 iterations are fixed in `params.yaml`." Move the C2/C203 explanation up to the residual-gap bullet at L157–158, where the reader meets those numbers.
3. **L154–156 (attribution).** Add "excluding three `−0.00%` rounding ties (C108, C109, C207)" so the count of 5 matches what a reader sees in `reports/results.md`.
4. **Conclusions de-duplication (L292–303, L349).** Cut the "What the results show" bullets that restate Training (tuning, RC202, exact solver) and keep the tables and Limits. Leave RC202 −3.85/−5.79 in one place, Training L156–157 plus the record table. This also brings the section back toward the gold's length.
5. **Narrative and language pass.**
   - Cut half of the "follow / its branch / its path" directions (L13, L27, L73, L89, L213, L281, L292–303).
   - Keep "best-known is not proof" only in Data (L91) and Limits (L372).
   - Fold the inline glosses into the key concepts.
   - Rewrite the six "X sets Y; next, Z" transitions in concrete words.
   - Normalize the percent formatting to `` `X%` ``.
   - Make the truck rounding consistent (L21 "about 4" → "about 3.7").

## Ready to publish?

**Yes.** Every hard truthfulness error from rounds 1 and 2 is fixed. Each number in the article traces to `metrics.json`, `params.yaml`, `results.md` or the README, with no contradicted figures left. What remains is one misleading inference (N1, a one-sentence fix that should ideally land before publishing), one minor misattribution (N2), and narrative and language polish that keeps the article at about 7.5 rather than the 8.5+ the gold reaches. None of these misstates a result.
