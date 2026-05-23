.PHONY: install install-dev run test test-all lint format typecheck clean help

# ─── Help ────────────────────────────────────────────────────────────
help: ## Show this help message
	@echo Available targets:
	@echo   install       Install production dependencies
	@echo   install-dev   Install production + dev dependencies
	@echo   run           Run the agent (pass URL=... )
	@echo   test          Run unit tests
	@echo   test-all      Run all tests (unit + integration)
	@echo   lint          Run ruff linter
	@echo   format        Auto-format code with ruff
	@echo   typecheck     Run mypy type checker
	@echo   clean         Remove generated outputs and cache

# ─── Installation ────────────────────────────────────────────────────
install: ## Install production dependencies
	uv sync

install-dev: ## Install production + dev dependencies
	uv sync --extra dev

# ─── Running ─────────────────────────────────────────────────────────
run: ## Run the agent — usage: make run URL="https://youtube.com/watch?v=..."
	uv run python main.py $(URL)

# ─── Testing ─────────────────────────────────────────────────────────
test: ## Run unit tests only
	uv run pytest tests/unit/ -v

test-all: ## Run all tests (unit + integration)
	uv run pytest tests/ -v

# ─── Code Quality ────────────────────────────────────────────────────
lint: ## Run ruff linter
	uv run ruff check src/

format: ## Auto-format code with ruff
	uv run ruff format src/

typecheck: ## Run mypy type checker
	uv run mypy src/

# ─── Cleanup ─────────────────────────────────────────────────────────
clean: ## Remove generated outputs and cache
	@if exist data\cache\index.json del data\cache\index.json
	@if exist data\outputs rd /s /q data\outputs
	@mkdir data\outputs
	@echo Cleaned cache and outputs.
