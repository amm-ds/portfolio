# Engineering Playbook

How this repository is run — standards, review culture, and the definition of
done. Everything here is enforced by tooling, not by goodwill.

## Standards

1. **Types.** mypy strict on `libs/*`; typed function signatures everywhere.
   Pydantic models at every cross-module boundary (ADR-0002).
2. **Lint / format.** ruff (`E,F,I,UP,B,SIM,RUF`), line length 100, enforced by
   pre-commit and CI. Never argue with the formatter.
3. **Tests.** pytest + hypothesis property tests on every validator. Coverage
   gates: ≥80% on `libs/*`, ≥60% on projects. A bug fix without a regression
   test is not a fix.
4. **Config.** Zero hardcoded constants in logic. Every knob is a field on a
   pydantic `BaseModel` / `pydantic-settings` class with a documented default.
5. **Data.** No raw data in git. Dataset cards pin source, license, checksum,
   snapshot date. DQ gates halt pipelines loudly (non-zero exit + persisted
   `DQReport`).
6. **Logging.** stdlib `logging` via `portfolio_core.logging`; structured where
   it crosses stages. No `print` in library code.
7. **Dependencies.** New runtime dependencies need justification in the PR —
   this repo doubles as an engineering sample.

## Review culture

The PR template asks three design questions: *What alternatives were rejected
and why? What is the rollback path? Does any contract change, and who is
affected?* A PR that cannot answer them is draft.

## Definition of done

- [ ] `make test` green (ruff, ruff-format, mypy, pytest with coverage gates)
- [ ] `dvc repro` reproduces the changed pipeline from a clean state
- [ ] Contracts unchanged, or all consumers updated + changelog noted in PR
- [ ] Docs updated: project README results, DESIGN.md if decisions changed,
      ADR if platform conventions changed
- [ ] No secrets, raw data, or build artifacts committed (gitleaks in pre-commit)
- [ ] Figures regenerated through `portfolio_core.plotting` (ADR-0005)

## Adding a new showcase project

0. `make new-project ARGS="08-name Title"` scaffolds the standard layout
   (workspace pyproject, portfolio.yaml, 8-section story.yaml skeleton,
   params/dvc templates, typed config/schemas/cli stubs, tests dir).
1. Add project-specific deps to its `pyproject.toml`, then `uv sync --all-packages`.
2. New workspace member pyproject declaring only its own deps.
3. Reuse `portfolio-core`/`portfolio-eval`; extend them in `libs/` if genuinely
   shared — never copy contracts into a project.
4. Dataset card in `data-registry/` for every external source.
5. `DESIGN.md` with requirements → options → decision → evaluation; SLOs if it
   serves anything in real time.
6. `portfolio.yaml` manifest so the showcase API/docs pick it up automatically.
7. `story.yaml` case study (schema: `portfolio_core.story`; sections: background,
   objectives, data, eda, training, evaluation, results, conclusions — concise,
   client-readable prose; figures referenced without extension; metric keys
   matching `reports/metrics.json`). Served by `GET /projects/{id}/story`.
8. A naive baseline (mean/majority/random/lag, depending on the problem) with
   the delta-vs-baseline numbers and an honest explanation in the results.
9. A MODEL_CARD.md (intended use, data, metrics by slice, limits) — convention
   from project 07; `make release-verify` asserts metrics before releases.
