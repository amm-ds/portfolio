# Kimi → Claude: P2 language/roadmap pass + H9 — completion handover

Date: 2026-11-19
From: Kimi Code
For: Claude Code (review + next-wave planning)
Owner status: everything below is uncommitted in the working tree; the owner commits and deploys.

## What shipped

**H9 — heading slash** (`collaboration/reviews/20261119-h9-report/00-report.md`)
- `story.css` `h2::before` content `"/ "` → `"/"`: headings read "/01 Background".
- Style-contract test updated. Subtitles confirmed on `--muted` (gray) in both themes — the blue subtitle on production is the old build; deploy needed.
- 8 acceptance screenshots (375/1280 × rag-agent/agent-chat × both themes).

**P2 — language and roadmap** (`collaboration/reviews/20261119-p2-report/00-report.md`)
- Schema: `RoadmapItem` = `{status: shipped|next|blocked, title ≤60, detail ≤90}` (90-char cap enforced by pydantic; OpenAPI golden regenerated).
- All 13 `story.yaml` roadmaps rewritten (3–4 shipped + 1–2 next/blocked, ≤5 cards); approved rewrites for 03/09/12 used as written (12's six mandated cards merged to five per the cap — recorded).
- Language rules §4/§7 applied to 01, 02, 03, 06, 09, 10, 12, 13; cohesion/figure rules §5/§6 to 03, 09, 10, 12 (limits one bullet format; captions state metric + test set; 09 phantom-retry caption and 12 inverted heatmap colors fixed).
- Every number written was verified against committed metrics files — full per-project list with file paths in the report.
- Generated files regenerated: `storyShort.ts`, `staticRegistry.ts` (route manifest already current).

**Owner overrides applied same day (after first render):**
1. Roadmap block renders `shipped` only — `next`/`blocked` stay authored but hidden; pending-list CSS removed again. Verified: 753 web tests, lint, build; screenshot shows the 3-node shipped timeline only.
2. Heading number–title gap reduced to a single literal space (`.sec-num` `margin-right` removed — it stacked on the JSX space and read as a double space). Verified on both article types.

## Gates (all run, all green)

Story lint 0/0 · docs OK · short-copy 39 surfaces OK · headline numbers 11 claims/0 findings · both `--check` generators current · web 753 tests (one flaky App.test About-title failure in ~5 full runs — green in isolation and all follow-ups; worth a look) · ruff/format clean · mypy 233 files clean · full pytest 97.80% coverage.

## For your review — OPEN_QUESTIONS

`collaboration/designs/20261119-p2-language-roadmap/OPEN_QUESTIONS.md` — 8 sections, all "existing copy vs committed artifact" mismatches I was forbidden from fixing (no-number-changes rule). Most decision-relevant for you/owner:

1. **09 `short_version`** claims "Live 2026-11-19: 6/6 refusals, 19/19 budgets"; committed metrics show 5/6 (h19 refusal 0.0). Truth-in-copy issue — needs an owner decision (fix copy or run the live confirmation).
2. **06 "8 published references"** vs 5–6 instances with negative gaps in committed `results.md`.
3. **03 threshold_sweep** "115 flags (14.8%)" vs committed figure takeaway "17/120 flags" (14.2%).
4. **13** three unverifiable numbers (15% ONNX lead vs 13.8% committed; 3.3 GB / 12.8 GB; ~20% noise threshold).
5. **10** `profit_frontier.html` annotation $6,698 vs $6,838 committed (figure artifact, not story).
6. Numbers traced only to design docs (02 spike-capture, 04 ECE pair, 11 "4x").

## Notes for next waves

- The 03/06 headline-CI copy is intentionally aligned to `check_headline_numbers` rounding (`0.230`, `[3.22, 5.28]`) — earlier waves set this; don't "fix" it back to HEAD's `0.231`.
- Dev API on :8002 was restarted with the new schema (the stale process 500'd every story → "case study could not be loaded"). Production needs the same on deploy.
- The collaboration docs now reflect the rendering decisions: `01-language-and-roadmap-pass.md` §8 addendum, `repo-conventions.md` roadmap line, P2 report verification notes.
