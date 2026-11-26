# Round-3 review: 10-uplift-experimentation article

- Target: `projects/10-uplift-experimentation/story.yaml`, **working tree** (448 lines; uncommitted Wave 8 edits on `wave8-articles-truthfulness-2026-11-25`, HEAD `c05accd0`). Line numbers refer to the working-tree file.
- Gold template: `projects/01-rag-agent/story.yaml`
- Prior round: `opus-round2/10-uplift-experimentation.md`. It reviewed HEAD. Every finding was re-checked against the working tree, not taken on trust.
- Evidence re-checked (all committed): `reports/metrics.json` (`multi_arm.per_arm.mens.deciles`, `multi_arm.ci.pairs`, `multi_arm.policies`, `multi_arm.policy_value`, `multi_arm.best_arm_break_even`), `reports/figures/cost_sensitivity.json`, `reports/report.html` (cost grid, CUPED/SE, power, per-arm and DR/IPW tables), `README.md`, `DESIGN.md`, `params.yaml`.
- Stance: read-only. No repository file was edited apart from this review.

## Grades

| # | Dimension | R1 | R2 | R3 |
|---|---|---|---|---|
| 1 | Structure and article logic | 6 | 6 | 6 |
| 2 | Engagement and human-like narrative | 5 | 6 | 6 |
| 3 | Language quality | 5 | 6 | 6 |
| 4 | Technical depth | 8 | 8 | 9 |
| 5 | Truthfulness | 5 | 5 | 8 |
| 6 | Roadmap cards | 7 | 6 | 8 |
| 7 | Consistency with gold template | 7 | 7 | 7 |
| | **Overall** | **6** | **6** | **7** |

Wave 8 fixed every factual error from rounds 1 and 2: Womens conversion, the 64,000 frame, "wins outright", the 0.9% baseline, the $49.8k comparator, "net profit", the untraceable T−X row, the 2× wording, and the duplicate Qini CI. It also added the planning-versus-DR sign flip. All three roadmap fixes landed. Structure and voice did not change. The edit also introduced one rendering defect in a table (L325) and a few clumsy sentences.

### 1. Structure and article logic: 6

- **Still present:** Training (L133–195) still holds the CUPED read (L174–180) and the multi-arm planning dollars (L182–189). L137 still has to excuse this with "The channel-planning figures below use these scores." The reader sees $35.5k / $49.8k / $66.3k planning money before the two-arm policy race.
- **Still present:** Evaluation opens with the final verdict (L198–199) before Results shows the evidence for it.
- **Still present:** Two policy tables carry the same numbers. The Results table is at L272–278 and the Conclusions table at L311–317. Conclusions runs L283–418, about 135 of 448 lines. The "Exact numbers" prose (L355–370) repeats CUPED, the shares, $49.8k, $66.3k, and 2× from Training and Evaluation.
- **Improved:** Results (L257–259) now draws the conclusion that the planning dollars overstate channel choice, so the channel-choice claim is argued and not only asserted.

### 2. Engagement and narrative: 6

- Unchanged. The hook (L36) is still a goal statement with no campaign, person, or decision at stake.
- The instruction tone remains. Seven lines open with "Start/Next/Read/Check", and five transitions use "X; next, the Y" (L72, L103, L127, L191, L218).
- Strong passages: L116–125 (visits versus purchases, now correct about Womens) and L250–259 (observed DR/IPW versus planning, now with the sign flip).

### 3. Language quality: 6

- **Fixed:** "below everyone" is now "below `100%` coverage" (L211–212). L346 has `0.09 pp`. The five synonyms for the metric ("net sales", "real net profit", "net profit", "value") are gone.
- **Repetition is worse:** with the synonyms collapsed, "revenue minus send cost" (including "rev. minus send cost" and "Revenue − send cost") now appears **27 times**, up from 20. "Raw revenue minus send cost" appears 4×. The compound "revenue-minus-send-cost-at-budget CI" (L16) remains. Define a short term once in Objectives (for example "net revenue: revenue minus send cost, excluding COGS") and use it.
- **New clumsy sentences (Wave 8):**
  - L118–120 says the Mens gap twice in consecutive sentences: "The Mens gap is `0.68` percentage points… Both emails increased purchases: Womens adds `0.31`…; Mens adds `0.68` points."
  - L121: "The low conversion bars, against `0.57%` no-email control, need intervals before action." Bars do not need intervals; decisions do. This line replaced a clear sentence with a garbled one.
  - L124: "average a stronger email effect with a weaker one" now runs 120+ characters on a single source line, inside an otherwise wrapped paragraph.
  - L14 and L213 each say "at $0.50" twice in one sentence.
  - L28 says "At 25% budget … At a 25% budget" in back-to-back sentences.
- **Partly fixed formatting:** L189 and L363 had punctuation inside code spans, and those are cleaned. It remains at L211 (`$0.01.`), L213 (`$0.50.`), L240 (`$16,103.`), L242–243, L253–257, and L359–361 (`$10,881,`-style CI bounds). `%` still sits outside the span at L179 and L353 (`0.95`%). "61 of 145" (L334) is unformatted, while L185 still has bare "3.8%" against formatted `76.0%`/`20.2%`.
- 13 source lines exceed 200 characters (longest L288, 272). The 711-character line is gone.

### 4. Technical depth: 9

- **Fixed:** the two Qini intervals are now explained as two bootstrap protocols for one score, with the per-arm lower bound "just below zero" (L288–290).
- **Fixed:** the miscalibration is now described as spread: "the top decile over-predicts, while the bottom decile predicts a loss despite a measured gain" (L206–207). Evidence: decile 1 predicts 0.0250 against 0.0111 measured, and decile 10 predicts −0.0083 against +0.0033 measured.
- **Added:** the planning-versus-observed sign flip (L257–258). Planning best-arm minus single-arm is +$6,027 (35,514 − 29,487; CI [+$5,742, +$6,347] in `multi_arm.ci.pairs`). Observed DR is −$2,902.
- Remaining gap: the article uses ≈$0.30 in two senses without separating them (see Truthfulness). The causal-forest single-protocol comparison is still omitted, which is acceptable.

### 5. Truthfulness: 8

Every number was re-traced. All Wave 8 additions check out:
- +$6,027 matches the policies difference and `ci.pairs`.
- $66.3k / $66,253 matches `policies.best_arm.profit_full`.
- $49.8k against best-arm at 25%, with break-even 0.308, matches `best_arm_break_even` (`vs: mail_everyone_mens`, `policy_budget: 0.25`).
- 66.5 [33.10, 104.69] matches the `report.html` per-arm table.
- The decile spread claim matches `per_arm.mens.deciles`.
- `0.09 pp` matches `report.html` SE 0.00092 and README L38.
- The grid ($8,065/$8,007 at $0.20 with 90%; $4,230/$3,745 at $0.30 with 90%; $1,618/−$4,777 at $0.50 with 25%) matches `report.html`.
- Top-25% at $0.30 ≈ $3,748 against $3,745 ("essentially ties") was derived from the 25% value at $0.01 ($6,838).
- Seed 42 matches `params.yaml` L1.
- +21% / +13% / 42% are arithmetic on committed values.

**Untraceable (0).** The T−X row [−$323, $4,343] was deleted.

**Contradicted or imprecise (2, both minor)**

| Line | Claim | Evidence / problem |
|---|---|---|
| L46, L221, L432 | "targeting wins once send cost passes ≈$0.30"; "sending costs more than 30 cents"; key concept "≈$0.30, above which targeted sending beats mailing everyone" | ≈$0.30 is the analytic break-even for the **fixed top-25%** list (README L83–84). The optimized targeting share (90%) already beats mail-everyone at **$0.20** ($8,065 vs $8,007, `report.html`). Say "the top-25% list beats mail-everyone above ≈$0.30" and leave the general "targeting wins" claim out. |
| L299 vs L212 and card 4 (L445) | Lesson: the T-learner list "overtakes near ≈$0.30 and wins above it". L212: "At `$0.30`, top-25% essentially ties". Card 4: "Top-25% first leads the grid at $0.50". | Each statement can be defended on its own: analytic break-even, grid tie, grid winner. Together they give three different thresholds with no bridge. Add one sentence that names the analytic break-even (≈$0.30), the grid's first sub-100% share ($0.20), and the first grid point where top-25% wins ($0.50). |

### 6. Roadmap cards: 8

- All titles are verb-first and all details are ≤90 characters (longest is 70 characters, L448). Four cards are shipped and one is next.
- **Fixed:** card 1 (L436) "Power needs 3,063 per arm; 21,306 are available." matches `report.html`.
- **Fixed:** card 4 (L445) "Top-25% first leads the grid at $0.50 per email." is true (`report.html` grid), but it now differs from the ≈$0.30 framing in Background and Key concepts (see above).
- **Fixed:** card 5 (L447) "Run a prospective randomized holdout".
- Minor: the card 5 detail "pre-register margin, fatigue costs, arms, and the send budget" says margin and fatigue can be pre-registered. They are measurements. Use "Gate: pre-registered arms and budget; measured margin and fatigue costs."
- Shipped claims re-checked: card 2 (cross-fitting in `models.py`, bootstrap in DESIGN L57) and card 3 (`multi_arm.policy_value` pairs: DR/IPW beat random, best-arm vs single-arm spans zero). Both are accurate.

### 7. Consistency with gold template: 7

- Every section has an "In plain terms" card, and transitions use the gold link format.
- The Objectives card (L75) still carries no number. The gold's Objectives names thresholds and includes a target table.
- The gold's transitions preview the next section's content. The repeated "X; next, the Y" pattern here does not.
- Backticked figure names appear only at L270.

## New errors introduced by Wave 8

| # | Line | Defect | Severity |
|---|---|---|---|
| N1 | L325 | The paired-differences row `T-learner − random` is indented **8 spaces** in a block indented 4. That leaves 4 spaces of leading indentation inside the Markdown. GFM parsers such as markdown-it end a table at a line indented 4+ spaces, so this row, which carries the **headline CI [+$718, +$4,767]**, will likely render as an indented code block. The `T − mail-everyone` row after it would be left as stray text. | High (rendering) |
| N2 | L118–121 | The Mens +0.68 is repeated in consecutive sentences, and the new sentence "The low conversion bars, against `0.57%` no-email control, need intervals before action" is garbled. | Medium |
| N3 | L14, L213 | "at $0.50" appears twice in one sentence. | Low |
| N4 | L28 | "At 25% budget …. At a 25% budget …" appears in back-to-back sentences. | Low |
| N5 | L299 vs L212 vs L445 | Three different thresholds for "targeting wins" ($0.30 overtake, $0.30 tie, $0.50 grid lead) are given with no bridge sentence. The card 4 rewrite surfaced this. | Medium |
| N6 | L14, L28, L119, L124, L213, L257, L287–290 | The new text is not re-wrapped, which leaves uneven 140–272-character source lines. | Cosmetic |

## Round-2 finding status

| # | Round-2 finding | Working-tree lines | Status |
|---|---|---|---|
| 1 | CUPED and multi-arm planning sit in Training | L174–189 | STILL PRESENT |
| 2 | Evaluation opens with the verdict | L198–199 | STILL PRESENT |
| 3 | Conclusions long; duplicate policy tables | L272–278, L311–317 | STILL PRESENT |
| 4 | Results lead and plain-terms card disagree | L225–227, L280 | FIXED |
| 5 | No human hook | L36 | PARTLY FIXED (unchanged since R2) |
| 6 | Checklist or instruction tone | throughout | STILL PRESENT |
| 7 | Identical transition template | L72, L103, L127, L191, L218 | STILL PRESENT |
| 8 | Metric phrase repeated; synonyms; fused compound | 27×; L16 | PARTLY FIXED (synonyms gone; repetition up from 20 to 27; L16 compound remains) |
| 9 | "Model-estimated"/"spans zero" repetition | throughout | PARTLY FIXED (unchanged) |
| 10 | "policy race, a recipient-selection rule" | — | FIXED |
| 11 | "drops below everyone" | L211–212 | FIXED |
| 12 | "The money metric judging uses" | — | FIXED |
| 13 | "real net profit" in Objectives card | L75 | FIXED |
| 14 | Overlong source lines | 13 lines >200 chars | PARTLY FIXED (711-char line split) |
| 15 | SE 0.09 missing "pp" | L346 | FIXED |
| 16 | Wedged "log-transformed" definition | — | FIXED |
| 17 | Two Qini CIs for one score | L288–290 | FIXED |
| 18 | "2× hot" should describe spread | L12, L206–207, L301, L366, L404 | FIXED |
| 19 | Causal forest not mentioned | — | STILL PRESENT (optional) |
| 20 | T−X CI untraceable | — | FIXED (row deleted) |
| 21 | Womens "did not convert" contradiction | L9, L119–120, L124, L130 | FIXED |
| 22 | "Trails on Qini" overclaim | L298 | FIXED ("nominally… difference CI spans zero") |
| 23 | +$2,812 attributed to 64,000 customers | L287–288 | FIXED |
| 24 | "Top-25% wins outright" above $0.30 | L212–213; L46, L299, L432 | PARTLY FIXED (L212 and caption L14 corrected; L46, L299, and L432 still imply a single ≈$0.30 threshold for "targeting") |
| 25 | 0.9% called the baseline | L121, L370 | FIXED |
| 26 | $49.8k comparator unnamed | L28–29, L187–189, L364–366 | FIXED |
| 27 | Roadmap card 1 vague | L436 | FIXED |
| 28 | Roadmap card 4 circular | L445 | FIXED |
| 29 | Roadmap card 5 "Decide" | L447 | FIXED |
| 30 | Objectives plain-terms card number-free | L75 | PARTLY FIXED (unchanged) |
| 31 | Data card copies the Data lead | L106 | FIXED |
| 32 | Prose figure names versus gold backticks | L270 only | PARTLY FIXED (unchanged) |
| 33 | Planning-versus-DR sign flip not stated (R2 "new gap") | L257–258 | FIXED |
| 34 | "Profit" for a revenue-only metric (R2 new) | L45, L50, L75, L272, L298, L425 | FIXED |
| 35 | Punctuation inside code spans; `%` outside span | L211, L213, L240–243, L253–257, L359–361; L179, L353 | PARTLY FIXED (L189 and L363 cleaned) |

Totals: 21 fixed, 8 partly fixed, 6 still present (one of them optional).

## Top 5 remaining fixes

1. **L325: remove the extra 4 spaces** so the `T-learner − random` row is indented like its neighbours. As it stands, the headline CI row probably drops out of the table. Fix it before publishing.
2. **Unify the break-even story (L46, L221, L299, L432, L445).** Use one sentence and reuse it: "The top-25% list beats mail-everyone above ≈$0.30 (analytic break-even). On the grid, the best share first drops below 100% at $0.20 (90%) and falls to 25% at $0.50." Change "targeting wins once send cost passes ≈$0.30" (L46) and the key concept (L432) to say "the top-25% list".
3. **Rewrite L118–121.** Suggested: "Both emails raised purchases: Mens by `0.68` pp and Womens by `0.31` pp (`66.5` incremental conversions, `[33.1, 104.7]`) over a `0.57%` control. Effects this small need intervals before anyone acts on them." Also re-wrap L124.
4. **Cut repetition and duplication.**
   - Define one short name for revenue minus send cost in Objectives (L65) and use it in place of most of the 27 occurrences, including the L16 compound.
   - Delete either the Results table (L272–278) or the Conclusions table (L311–317).
   - Trim "Exact numbers" (L355–366) of figures already given in Training.
   - Fix the doubled "at $0.50" (L14, L213) and "At 25% budget" (L28).
5. **Restructure.**
   - Move CUPED (L174–180) to EDA, where it belongs with the randomization check.
   - Move multi-arm planning (L182–189) into Results, next to the DR/IPW paragraph it is contrasted with.
   - Open Evaluation with what the figures test, not with the verdict.
   - Vary the transitions so each previews the next section's content, as the gold does.
   - While editing, move trailing punctuation out of code spans (L211, L213, L240–243, L253–257, L359–361) and put `%` inside the spans at L179 and L353.

## Ready to publish?

**No, but close.** The article is now truthful: no untraceable numbers and no material contradictions. Two things block publishing:
- **L325 rendering defect:** this one-character-class indentation slip will probably break the paired-differences table and hide the headline CI.
- **Inconsistent ≈$0.30 threshold:** it is stated three ways (L46/L432, L212, L445).

Fixes 1–3 are about ten line edits. After them the article is publishable. Fixes 4–5 are quality improvements, not blockers.
