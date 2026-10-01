#!/usr/bin/env bash
# Dump the local index DB (statutes, cases, embeddings) for the demo VM.
# Usage: deploy/dump_db.sh  → deploy/laborlex.dump (gitignored)
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T db pg_dump -U laborlex -Fc laborlex > deploy/laborlex.dump
ls -lh deploy/laborlex.dump
