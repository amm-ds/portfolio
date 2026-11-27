# Message for Kimi — 08 grade record fix (owner decision: keep 8.8)

Owner decided on 2026-11-27: **project 08 stays at 8.8**. This is the owner-accepted grade on one host, as recorded in pass 4 (`00-plan.md`: "08 … 9/9/8/9 → 8.8 on one host").

The phase 7 table has the T axis at 6, which gives 8.3 under the overall formula. The owner's decision is that the T axis is 8, consistent with the pass-4 projection and the E10 stop record. Fix the record to match.

## Change (docs only)
1. `collaboration/reviews/20261126-grades-pass-5-close-to-9/phase-7-result.md`, the 08 row:
   - per-axis after: `9/9/8/9` (was `9/9/6/9`);
   - overall after: `8.8`;
   - keep the cap text: "T capped at 8: E10 stopped at its re-measurement gate (+20.5%/+6.0% drift, Ollama 0.40.4→0.40.17, co-tenant load); owner accepted 8.8 on one host, 2026-11-27."
2. In the same file, replace the line "08: axes 9/9/6/9 give 8.3 by the overall formula; the owner accepted 8.8; pending owner confirmation of which axes back 8.8." with: "08: axes 9/9/8/9 give 8.8 by the overall formula. Owner decision 2026-11-27: keep 8.8 on one host (T capped at 8)."
3. Check the headline line that says "12 of 14 at 9.0; 01 and 08 at 8.8" still reads correctly. It should.
4. Re-run the copy gates: `check_headline_numbers`, `check_docs`, `git diff --check`. Record exit codes in `phase-6-result.md` as a short addendum.
5. Commit as `docs(review): record owner decision to keep 08 at 8.8`. No co-author trailer.

## Do not
- Change any copy, metric, or grade other than the 08 row and its note.
- Change any project 08 code, data, or the gitignored `bench_run_repeat.json`.
- Push, deploy, or fast-forward `main`.

## Still open (not part of this change)
- Acknowledgement of the 13 short-version rewrite in `f88b259d` (owner to acknowledge).
- The 09 test deadline change: not approved; no test edits.

## Report back
Commit hash, the three gate exit codes, and the final 08 line as written.
