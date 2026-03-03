.PHONY: format lint clean ingest server install init-db reset-db run

install:
	uv sync

format:
	uv run ruff check --select I --fix src/
	uv run ruff format src/
	uv run ruff check --fix src/

lint:
	uv run ruff check src/

ingest:
	uv run python -m src.scripts.ingest_context

run:
	uv run python -m src.main

reset-db:
	uv run python -m src.scripts.reset_db

reset-all:
	uv run python -m src.scripts.reset_db --all

test:
	uv run pytest

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".build" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +