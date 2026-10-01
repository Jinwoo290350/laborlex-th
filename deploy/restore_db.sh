#!/usr/bin/env bash
# On the VM: restore deploy/laborlex.dump into the prod db container.
set -euo pipefail
cd "$(dirname "$0")"
docker compose -f docker-compose.prod.yml --env-file ../.env up -d db
until docker compose -f docker-compose.prod.yml exec -T db pg_isready -U laborlex >/dev/null; do sleep 1; done
docker compose -f docker-compose.prod.yml exec -T db pg_restore -U laborlex -d laborlex --clean --if-exists < laborlex.dump
