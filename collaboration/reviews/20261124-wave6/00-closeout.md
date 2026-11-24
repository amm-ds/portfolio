# Wave 6 closeout — experiments, apps, and demos (Opus-aligned)

- **Branch:** `wave6-polish-2026-11-24` (from `main` @ `18bdf770`)
- **Constraint:** zero hosted LLM calls (agent-chat re-capture uses the scripted
  mock transport; document-intelligence uses the deterministic fixture analyzer)
- **Status:** Tasks 1–15 executed in order; full §8 verification suite green.
- **Not committed, not pushed** — Claude reviews, validates, commits, merges.

Handoffs read first: `collaboration/reviews/20261124-orchestrator-review/00-review.md`
(§4–6, §8) and `collaboration/designs/20261124-wave6-experiments-apps-and-demos/03-implementation-handoff.md`.
Owner decisions applied as instructed: D1 interim truthful judge wording, D6 02
rewrite, D9 dead/orphan PNG deletion, D10 `/Users/` scrub, D3 agent-chat
re-capture via `VITE_MOCK=1` with scripted-caption disclosure, D7 Proposal A
grid sizing (width caps, 2 columns kept).

## Part A — judge calibration, headline numbers, figures (Tasks 1–7)

- **T1 attribution:** all five surfaces now carry the interim truthful wording:
  `projects/01-rag-agent/README.md`, `story.yaml` (incl. roadmap/key_concept),
  `docs/projects/01-rag-agent.md`, `docs/projects/index.md`, root `README.md`
  (hero + projects table row), and the synced generated copy
  (`apps/showcase-web/src/lib/cardCopy.ts`, `storyShort.ts`). Short version
  (259 chars): "Grounding-hardened cited QA over 593 Wikipedia articles. S3
  hybrid retrieval reaches 0.946 recall@5. Judge sample: reviewer-agent audit
  30/30; owner hand-label pending. Final 120-question pass: F1 0.909,
  precision 0.952, faithfulness 0.872, 1/120 unsupported."
- **T2–3:** V1 offline re-aggregation run and faithfulness CI fixed to
  `[0.8092, 0.9304]` in README/story/docs (`reports/experiment_log.json`,
  `reports/final_v3_e2e/f1_summary.json` regenerated).
- **T4:** `scripts/check_headline_numbers.py` extended with `_m01()` covering
  `0.9091`/`0.946`; KNOWN_DRIFT now only `uncovered:04-nlp-classification`
  (12 claims, 0 findings). Tests added in
  `scripts/tests/test_check_headline_numbers.py` (20 pass).
- **T5:** new builders in `projects/01-rag-agent/src/rag_agent/figures.py`
  (`retrieval_ladder_figure`, `final_outcome_figure`, `verify_funnel_figure`;
  `taxonomy_figure` gained a `scope` kwarg) driven by
  `projects/01-rag-agent/scripts/build_final_figures.py` (asserts converted to
  an `_expect()` RuntimeError helper; ruff/mypy clean). Four figure JSON+HTML
  pairs written to `reports/figures/`: `retrieval_ladder` (S3 final_v3
  recall@5 0.9457 vs R0 0.9239; Wilson whiskers; S1/S2 deliberately absent on
  final_v3), `final_outcome` (80/4/24/12 confusion + slices),
  `failure_taxonomy` (now n=120: 104/10/4/1/1), `verify_funnel`
  (166/16/150/148/159/7, mean support 0.9739). Story results section now
  figures `[retrieval_ladder, final_outcome, failure_taxonomy]`, conclusions
  `[verify_funnel]`; captions block exactly 11 keys, 65-question figures
  labelled "Development history:", fusion caption corrected to committed
  numbers (tuning tie 0.831; sealed 0.533 vs 0.600; n=15);
  `retrieval_hpo_frontier` caption removed (artifact JSON/HTML remains on disk
  but is no longer referenced).
- **T6:** `scripts/export_readme_figures.py` — hero renamed
  `rag-retrieval-ladder.png` ← `retrieval_ladder`; docs figures for 01 =
  (retrieval_ladder, final_outcome, failure_taxonomy, verify_funnel,
  chunk_size_sweep); pruned 02 (key removed), 04 epochs_probe, 05 cost_surface,
  11 normalized_heatmap. Root `README.md:36` and
  `docs/projects/01-rag-agent.md` updated (4 new embeds + "Development
  history." label). PNGs rendered via kaleido; unrelated re-rendered PNGs
  restored via `git checkout` to keep the diff tight. Deleted
  `docs/assets/readme/rag-quality-cost-frontier.png` and five orphan
  `docs/assets/projects/**` PNGs.
- **T7:** `projects/02-demand-forecasting/story.yaml` erratic-copy rewrite:
  full-panel test 0.6235 vs champion 0.6211, +0.0025 ≈ 3.9× the paired
  bootstrap noise band (delta_point 0.0024879, noise_tol 0.0006438), win-rate
  slip 0.8247 vs 0.8260, adoption gate rejected on both checks and the test
  window reused a second time (disclosed); "wave-34 Huber early stop" phrased
  as "the screening pass stopped it after origin 1, 0.8683 against 0.7409".
  57.3% → 57.2% everywhere (story, caption `m5_full_pooling_panel`,
  `docs/projects/02-demand-forecasting.md:63`), matching
  `reports_m5_full/metrics.json` `zero_day_accuracy` 0.57243956.

## Part B — apps alignment (Tasks 8–12)

- **T8 dots:** `.terminal-dots` removed from all three apps
  (`showcase-web/src/components/Terminal.tsx` + `styles/shell.css`;
  `agent-chat/web/src/components/chat/ChatSurface.tsx` + `styles.css`;
  `document-intelligence/web/src/App.tsx` + `styles.css`).
  `git grep -n "terminal-dots" apps` → empty.
- **T9 sizing:** `cards-grids.css` — `.demo-grid`/`.project-grid`/`.apps-grid`
  capped at `max-width: 72rem`; `.app-card__shot` → `aspect-ratio: 16/10`,
  `max-height: 22rem`, `object-fit: cover`; `.study-card__content` capped at
  `70ch`. `demos.css` — `.wb-root` capped at `109rem` (workbench chart card
  measures 1396 px at 1920/2560); `.wb-canvas-slot .figure-card` →
  `clamp(400px, 48vh, 640px)`. `demos-workbench.css` — `.wb-secondary` →
  `clamp(240px, 24vh, 360px)`.
- **T10 verification:** Playwright sweep 375/768/1280/1440/1920/2560 × 5 pages,
  30 screenshots + `report.json` under `artifacts/wave6-viewports/`
  (script: `artifacts/wave6-viewports/shoot.cjs`). Zero horizontal overflow at
  every width; demo cards 566 px at ≥1280; workbench chart card 1396 px at
  1920/2560.
- **T11 media:** `record-demo.mjs` gained a mock branch (`AGENT_CHAT_MOCK=1`,
  identity defaults `mock-agent-1@mock`): question → approval capture →
  approve → done → UI capture; memory shot from the seeded
  "example: incident triage" conversation. New `agent-chat-{ui,approval,
  memory}-v3.png` + re-encoded `agent-chat-demo.{webm,mp4}` (5.56 s). The
  stale 44.8 s scene-description VTT no longer described the clip: the
  `<track>` was removed from `AgentChatArticle.tsx` and
  `apps/showcase-web/public/apps/agent-chat-demo.vtt` deleted (no test
  referenced it; flagged here for re-timing at the next live capture).
  Document-intelligence re-captured against the real local stack (homebrew
  Postgres 14 `review` role, fixture analyzer, leased worker): new
  `document-intelligence-{summary,qa}.png`. All five PNGs synced byte-identical
  into `docs/assets/apps/` (md5-verified). Article copy updated to the
  scripted-mock disclosure; docs captions (`docs/apps/agent-chat-ui.md`,
  `docs/apps/chatbot-agent.md`) updated to restart_service/seeded-conversation
  wording, including the "Memory in the UI" paragraph, which now states the
  capture is the mock transport and the behavior rests on the committed
  evaluation evidence.
- **T12 cleanup:** deleted the six dead web PNGs
  (`agent-chat-{ui,approval,memory}{,-v2}.png`). `git grep` over
  `apps docs README.md projects scripts` confirms every remaining
  `agent-chat-*.png` reference points at `docs/assets/apps/` copies that
  exist; `AppNavigation.test.tsx` (7 tests) passes against the v3 names.

## Part C — hygiene (Tasks 13–15)

- **T13 `/Users/` scrub:** `build_final_v3.py` access log now records
  repo-relative paths (home-relative `~` outside the repo) via
  `_display_path()`; the forbidden-read check still uses the raw path.
  `m5_data.py` gained `_repo_rel()`; `m5_full.py` and `m5_full_catalog.py`
  import it (provenance_ref ×2, weights_source ×2). Committed artifacts
  regenerated with the identical transform:
  `reports/final_v3_file_access.json` (3365 → 0 absolute user paths),
  02 `evaluation_metadata.json` ×2, `report.html` ×2, `demo_payload.json`,
  `catalog_meta.json`. `git grep -c "/Users/" -- projects` → empty (exit 1).
- **T14 compose:** root `docker-compose.yml` — `api` healthcheck now probes
  `/ready` (matches the Wave 5 deploy contract); `web-dev` gained an anonymous
  `/web/node_modules` volume so the container's own install is never shadowed
  by the host's macOS arm64 tree (npm optional-deps bug). arm64 node note
  added to `AGENTS.md`.
- **T15 em-dashes:** script-assisted pass over the nine top-offender files
  (helper kept at `artifacts/emdash_cleanup.py`): definitional bullet/bold/
  heading dashes → colons, clause joins → commas/periods; tables, code fences,
  and YAML untouched. Final counts per file (all < 8, all remaining instances
  are inside tables or headings): 06: 2, 04: 2, 02: 1, 11: 1, 10-uplift
  README: 6, 09: 7, 01-rag-agent docs: 0, chatbot-agent: 2, 10-uplift docs:
  2. No numbers were altered; manual review fixed the ~10 joins the
  mechanical rules got wrong (heading splits, comma splices, one parenthetical
  aside).

## §8 verification results (all exit 0)

- `uv sync --all-packages --dev` — OK
- `uv run ruff check .` — OK (figures.py reformatted once)
- `uv run ruff format --check .` — 881 files formatted
- `uv run mypy libs projects apps` — 248 source files, no issues
- `HF_HUB_OFFLINE=1 uv run pytest -q` (root) — green, 97.71 % total coverage
  (80 % gate)
- `projects/01-rag-agent`: `HF_HUB_OFFLINE=1 uv run pytest --cov` — 185 passed, 87 %
- Repo scripts: `check_docs.py` OK; `check_short_copy.py --check` OK (39
  surfaces / 13 stories); `check_demo_contract.py` OK (2 demos);
  `check_headline_numbers.py` OK (12 claims, 0 findings, no unknown drift);
  `lint_story_language.py` 0 errors, 1 pre-existing-style warning
  (01 evaluation section 685 words vs 550 soft budget — content grew with the
  new figures/disclosure); `gen_static_registry.py [--check]` current;
  `gen_story_short.py [--check]` current; `gen_route_manifest.py [--check]`
  current (27 routes; regenerated `generated_at` timestamp)
- `uv run mkdocs build --strict` — OK
- `apps/showcase-web`: `npm ci` (arm64 native), 753/753 vitest tests,
  eslint clean, `npm run build` OK (re-run after the VTT removal: 753/753)
- `apps/agent-chat`: ruff OK, mypy 64 files OK, pytest 90.19 % coverage
  (≥ 89.8 % gate), web vitest + build OK
- `apps/document-intelligence`: ruff OK, mypy OK, pytest 85.00 % coverage
  (≥ 84.5 % gate), web vitest + build OK
- Targeted greps: `terminal-dots` in apps → none; `/Users/` in projects →
  none; `owner hand-labelled|owner-validated|owner blind` → none (9 truthful
  "owner hand-label pending" remain)

## Deviations and flags for the reviewer

1. **D3 mock recording (decided):** the video and screenshots show the scripted
   mock transport with a visible `mock-agent-1@mock` badge; the article
   discloses this next to the media. The old clip's "44.8-second
   kimi-for-coding recording" claim and the recall-claim captions were
   replaced; the stale VTT was removed rather than re-timed blind.
2. **short_version trim:** keeping `gen_story_short.py --check` under its
   character budget required dropping "(title-anchored chunks, BM25+dense RRF,
   diversity cap)"; the same trimmed string was synced into README hero, root
   README table row, project README, and both docs pages.
3. **02 artifact drift (left as-is, flagged):**
   `reports_m5_full/metrics.json` zero_day_accuracy 0.57243956 (→ 57.2%) vs
   `demo_payload.json` / `m5_full_pooling_panel.json` 0.5734145 (→ 57.3%) for
   the same quantity. Copy now follows metrics.json; unifying the committed
   artifacts is a regeneration task outside this handoff.
4. **chunk_size_sweep.png:** left as the committed render (it matches its
   unchanged JSON artifact and still shows the pre-S3 tuning panel, now
   explicitly labelled "Development history").
5. **Test lock updated:** `ProjectsIndex.test.tsx` locked the old fixed
   180 px shot height; it now locks the new aspect-ratio contract (the lock
   sat outside the handoff's frozen ranges 315–325/394–409).
6. **Environment notes:** both app vite servers bind IPv6 localhost on this
   host, so the capture/recorder runs used `http://localhost:...` via their
   existing env overrides; agent-chat and document-intelligence web
   node_modules needed `npm i --no-save @rollup/rollup-darwin-arm64` after
   their lockfiles last resolved under Rosetta (documented in AGENTS.md;
   showcase-web's `npm ci` under the arm64 node resolved natively).
7. All dev servers (showcase api/vite, agent-chat web, document-intelligence
   api/worker/web) were stopped after capture; nothing is left running.
