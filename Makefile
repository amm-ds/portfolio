.PHONY: setup lint typecheck test test-fast demo docs docs-serve dvc-repro docker-build docker-up new-project clean

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
