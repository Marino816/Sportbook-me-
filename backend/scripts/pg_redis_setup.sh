#!/bin/sh
# Isolated local Postgres 15 + Redis 7 for Market Tools.
# Does not delete volumes or touch production.
#
# Finds Docker Desktop even when ~/.docker/bin is not on PATH.
set -e
ROOT="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
if ! command -v docker >/dev/null 2>&1; then
  if [ -x "$HOME/.docker/bin/docker" ]; then
    PATH="$HOME/.docker/bin:$PATH"
    export PATH
  elif [ -x /Applications/Docker.app/Contents/Resources/bin/docker ]; then
    PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
    export PATH
  fi
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "BLOCKER: docker is not installed."
  echo "Required step: install and start Docker Desktop for Mac, then re-run:"
  echo "  sh backend/scripts/pg_redis_setup.sh"
  exit 2
fi
cd "$ROOT"
# Never --volumes or down. Existing named volumes are reused.
docker compose up -d
ready=0
i=0
while [ "$i" -lt 20 ]; do
  if docker compose exec -T db pg_isready -U postgres >/dev/null 2>&1; then
    ready=1
    break
  fi
  i=$((i + 1))
  sleep 1
done
if [ "$ready" != 1 ]; then
  docker compose exec -T db pg_isready -U postgres
  exit 2
fi
docker compose exec -T db pg_isready -U postgres
docker compose exec -T redis redis-cli ping
echo "ok: local db/redis are up. DATABASE_URL=postgresql+asyncpg://postgres:password@127.0.0.1:5432/apex_dfs REDIS_URL=redis://127.0.0.1:6379/0"
