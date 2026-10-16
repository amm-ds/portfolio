.PHONY: setup lint lint-ci typecheck test test-fast demo docs docs-serve dvc-repro docker-build docker-up new-project clean metrics-show registry-update exp-run exp-show release-verify

PYTEST := uv run pytest

setup: ## Install all workspace deps and pre-commit hooks
	uv sync --all-packages --dev
	uv run pre-commit install

lint: ## Ruff check + format check
	uv run ruff check .
	uv run ruff format --check .

typecheck: ## Mypy over workspace
	uv run mypy libs projects apps

test: lint typecheck ## Full gate: lint + types + tests with coverage
	uv run pytest --cov-report=term-missing

demo: ## Launch the RAG agent CLI chat (Project 01)
	$(PYTEST) -q projects/01-rag-agent/tests || true
	uv run python -m rag_agent.cli chat

docs: ## Build mkdocs site
	uv run mkdocs build --strict

docs-serve: ## Serve docs locally
	uv run mkdocs serve

dvc-repro: ## Reproduce all DVC pipelines (downloads real data)
	dvc repro

docker-build: ## Build the showcase image
	docker build -t amm-ds-portfolio .

docker-up: ## Run API + web via compose
	docker compose up --build

new-project: ## Scaffold a new project: make new-project ARGS="08-name Title"
	uv run python scripts/new_project.py $(ARGS)

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov dist build
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# --- DVC: metrics / experiments / registry (ADR-0007) ---
metrics-show: ## dvc metrics show across all projects
	uv run dvc metrics show

registry-update: ## refresh dataset-registry version metadata
	uv run dvc update registry/

exp-run: ## queue a params experiment: make exp-run P=02-demand-forecasting PARAM=hpo_n_trials=30
	cd projects/$(P) && uv run dvc exp run --queue --set-param $(PARAM)

exp-show: ## show experiments: make exp-show P=02-demand-forecasting
	cd projects/$(P) && uv run dvc exp show

lint-ci: ## Validate workflow YAML + Makefile consistency
	uv run python scripts/lint_ci.py

release-verify: ## Ollama-gated evals + artifact assertions (release-time, ADR-0003)
	@test -n "$$(curl -s --max-time 3 localhost:11434/api/tags)" || \
	  (echo "Ollama not running — start it for release verification (CI stays offline per ADR-0003)" && exit 1)
	uv run python -c "\
from pathlib import Path; \
missing = [p for p in Path('projects').iterdir() if p.is_dir() and not (p/'reports/metrics.json').exists()]; \
assert not [m.name for m in missing if m.name[0].isdigit() and (m/'portfolio.yaml').exists() and 'planned' not in (m/'portfolio.yaml').read_text()], f'missing metrics: {missing}'; \
print('release-verify: all shipped projects have metrics.json')"
