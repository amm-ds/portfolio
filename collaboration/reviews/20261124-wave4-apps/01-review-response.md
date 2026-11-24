# Review response: Wave 4 — Apps Alignment (`agent-chat` & `document-intelligence`)

Date: 2026-11-24
Reviewer: Claude Code
Implementation: working tree on `phase0-infra-2026-11-22`, reported in `collaboration/reviews/20261124-wave4-apps/00-closeout.md`
Status: approved

## Verdict

Wave 4 satisfies `collaboration/designs/20261124-wave4-apps-alignment/03-implementation-handoff.md`:

- Both `apps/agent-chat/README.md` and `apps/document-intelligence/README.md` now carry the house `## Common errors` table (`| symptom | cause | fix |`) aligned with real failure modes and status codes.
- `DocumentIntelligenceArticle.tsx` fixed the em-dash clause join; all metrics across both articles and `apps.ts` trace to committed `reports/` artifacts.
- Pre-existing `mypy` strict errors in both apps' `test_error_contract.py` and `test_api_rate_limit.py` were resolved cleanly with typing-only changes.
- All app gates (`agent-chat` 90.19%, `document-intelligence` 85.00%), `showcase-web` tests/lint/build, and `check_docs.py` pass.
