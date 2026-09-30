# LaborLex-TH

Thai labor-law question answering with a system-controlled reasoning flow
(LangGraph) over a structured legal index (PostgreSQL + pgvector).
See `CLAUDE.md` for the design and `docs/PLAN.md` for the schedule.

## Quick start
```bash
make setup      # uv sync
cp .env.example .env   # fill keys
make db         # Postgres 16 + pgvector, schema applied on first start
make manifest   # hash files in data/raw/
make test
```
