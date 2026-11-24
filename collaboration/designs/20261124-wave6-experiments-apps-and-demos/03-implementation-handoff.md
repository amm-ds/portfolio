# Implementation handoff: Wave 6 — Experiment Validation, RAG 01 Visualizations, Apps UI/Media & Demo Responsive Sizing

Date: 2026-11-24
Designer: Claude Code
Executor: Kimi Code
Status: approved for execution (zero hosted LLM calls)
Branch: `main` (or `wave6-polish-2026-11-24` branched from `main`)

## Objective

1. **Part A — Experiments Validation Round & RAG 01 Visualizations:**
   - Update `projects/01-rag-agent` figure generation (`src/rag_agent/figures.py` / scripts) so `projects/01-rag-agent/reports/figures/{failure_taxonomy,retrieval_funnel}.{json,html}` and static PNGs in `docs/assets/projects/01-rag-agent/` and `docs/assets/readme/rag-quality-cost-frontier.png` reflect the finalized `S3` retrieval (`0.9457` recall@5, `0.8333` multi-hop) and `final_v3` 120-question E2E pass (`F1 = 0.9091`, `104 correct / 10 empty-answer / 4 budget-terminated / 1 unsupported-claim / 1 retrieval-miss`). Verify `story.yaml` figure captions match the updated charts.
   - Run a full validation round across all 13 experiments (`uv run pytest -q` and `uv run mypy libs projects apps` + `ruff check . && ruff format --check .`) and summarize performance/health across projects 01–13 in the closeout.
2. **Part B — Apps Holistic Pass (`agent-chat` & `document-intelligence`): Remove Mac Dots & Refresh Media:**
   - Remove the decorative macOS-style traffic-light buttons (`.terminal-dots`) from:
     - `apps/agent-chat/web/src/components/chat/ChatSurface.tsx` (lines 46–50) and `apps/agent-chat/web/src/styles.css` (lines 183–205).
     - `apps/document-intelligence/web/src/App.tsx` (line 25) and `apps/document-intelligence/web/src/styles.css` (lines 118–121, 364).
   - Run backend + frontend gates for both `apps/agent-chat` and `apps/document-intelligence` (`ruff`, `mypy`, `pytest`, `npm test && npm run lint && npm run build`).
   - Re-capture the app screenshots (`apps/showcase-web/public/apps/*.png`, `docs/assets/apps/*.png`) and `agent-chat-demo.{mp4,webm}` (using Playwright / existing media scripts) so the showcase articles (`AgentChatArticle.tsx`, `DocumentIntelligenceArticle.tsx`) display the updated dot-free UI.
3. **Part C — Demos Responsive Autosizing (`apps/showcase-web`):**
   - Improve responsive sizing of `.demo-grid`, `.study-card` inside `.demo-grid`, `.demo-shell`, and `.wb-*` cards (`apps/showcase-web/src/styles/{cards-grids,demos,demos-workbench}.css`) so demo cards do not stretch excessively on large desktop monitors (`>= 1440px`) while staying crisp and readable on mobile (`< 720px`) and laptop (`720px–1439px`) viewports (e.g., sensible `max-width` / `grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr))` or balanced column constraints + compact vertical padding on wide screens).
   - Verify `apps/showcase-web` (`npm test && npm run lint && npm run build`) and `uv run python scripts/check_demo_contract.py` + `check_docs.py` + `mkdocs build --strict`.

## Affected surfaces

- `projects/01-rag-agent/src/rag_agent/figures.py`, `reports/figures/`, `story.yaml` (captions if needed), `docs/assets/projects/01-rag-agent/`, `docs/assets/readme/rag-quality-cost-frontier.png`
- `apps/agent-chat/web/src/{components/chat/ChatSurface.tsx,styles.css}`
- `apps/document-intelligence/web/src/{App.tsx,styles.css}`
- `apps/showcase-web/public/apps/`, `docs/assets/apps/`
- `apps/showcase-web/src/styles/{cards-grids,demos,demos-workbench}.css`
- `collaboration/reviews/20261124-wave6/00-closeout.md` (new)

## Gates & Close-out

Run from repo root and app dirs:
```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run pytest -q
uv run python scripts/check_docs.py
uv run python scripts/check_short_copy.py --check
uv run python scripts/check_headline_numbers.py
uv run python scripts/check_demo_contract.py
uv run python scripts/lint_story_language.py
uv run mkdocs build --strict
cd apps/agent-chat && uv run pytest -q && cd web && npm test && npm run build
cd /Users/alejandro/work/portfolio/apps/document-intelligence && uv run pytest -q && cd web && npm test && npm run build
cd /Users/alejandro/work/portfolio/apps/showcase-web && npm test && npm run lint && npm run build
```

Write `collaboration/reviews/20261124-wave6/00-closeout.md` with exact validation results across all 13 experiments, updated figures/media, and responsive demo sizing. Do NOT commit or push.
