.PHONY: manifest setup db ingest test lint eval-dev eval-bar serve export-160

setup:
	uv sync --all-extras
	uv run pre-commit install || true

db:
	docker compose up -d db
	@echo "schema is applied on first start via docker-entrypoint-initdb.d"

manifest:
	uv run python -m src.ingest.manifest

ingest: manifest
	uv run python -m src.ingest.pipeline

test:
	uv run pytest -q

lint:
	uv run ruff check src tests && uv run mypy

eval-dev:
	uv run python -m src.eval.run_eval --set dev100 --leave-one-out

eval-bar:
	uv run python -m src.eval.run_eval --set bar_labor

serve:
	uv run uvicorn src.api.main:app --reload & uv run streamlit run src/ui/app.py

# Phase 2 only
export-160:
	uv run python -m src.eval.export_for_grading --set test160
