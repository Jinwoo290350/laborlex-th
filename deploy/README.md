# Demo deployment (30 days, CLAUDE.md §2 phase 1)

One VM with **≥ 8 GB RAM** (bge-m3 + bge-reranker-v2-m3 ≈ 4.3 GB, plus Postgres).
Streamlit Community Cloud is not enough (≈ 1 GB RAM, no Postgres).

1. On your machine: `deploy/dump_db.sh` → `deploy/laborlex.dump`
2. Copy the repo + `deploy/laborlex.dump` + `.env` to the VM (scp/rsync; never commit `.env`).
3. On the VM (Docker installed), fill in `.env`: `GEMINI_API_KEY`, `APP_PASSWORD`, `DB_PASSWORD`,
   `DOMAIN` (DNS A record → VM IP), `BASIC_USER`, `BASIC_HASH`
   (`docker run --rm caddy caddy hash-password --plaintext '<password>'`).
4. `deploy/restore_db.sh`
5. `cd deploy && docker compose -f docker-compose.prod.yml --env-file ../.env up -d --build`
   The first request downloads the models into the `models` volume (a few minutes).
6. Open `https://$DOMAIN`, log in, ask one dev100 question, check the sources panel.

Stop after the 30-day test: `docker compose -f docker-compose.prod.yml down` (data volumes stay).
