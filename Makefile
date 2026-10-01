.PHONY: manifest setup db ingest test lint eval-dev eval-bar serve export-160 demo

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
	uv run python -m src.ingest.load_cases
	uv run python -m src.index.embed
	uv run python -m src.index.embed --cases
	uv run python -m src.calc.build_rates

dev100:
	uv run python -m src.eval.import_dev100

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
	uv run python -m src.eval.export_for_grading --set test160 --confirm-phase2

# Free demo from this Mac: api + ui + Cloudflare quick tunnel (URL printed in demo.log; changes on restart).
# Keeps the Mac awake while running. Stop with: pkill -f "cloudflared tunnel"; pkill -f uvicorn; pkill -f streamlit
demo:
	uv run --env-file .env uvicorn src.api.main:app --host 127.0.0.1 --port 8000 > api.log 2>&1 &
	uv run --env-file .env streamlit run src/ui/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true > ui.log 2>&1 &
	caffeinate -dims cloudflared tunnel --url http://127.0.0.1:8501 > demo.log 2>&1 &
	@sleep 15; grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' demo.log | head -1
