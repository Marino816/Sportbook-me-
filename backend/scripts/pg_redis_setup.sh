#!/bin/sh
# Isolated local Postgres 15 + Redis 7 for Market Tools.
# Does not delete volumes or touch production.
#
# REQUIRED INSTALLATION STEP (this Mac has no docker binary):
#   1. Install Docker Desktop for Mac:
#      https://docs.docker.com/desktop/setup/install/mac-install/
#   2. Open Docker Desktop and wait until it is running.
#   3. Re-run this script from the isolated worktree.
#
set -e
ROOT="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
if ! command -v docker >/dev/null 2>&1; then
  echo "BLOCKER: docker is not installed."
  echo "Required step: install and start Docker Desktop for Mac, then re-run:"
  echo "  sh backend/scripts/pg_redis_setup.sh"
  exit 2
fi
cd "$ROOT"
docker compose up -d
docker compose exec -T db pg_isready -U postgres
docker compose exec -T redis redis-cli ping
echo "ok: local db/redis are up. DATABASE_URL=postgresql+asyncpg://postgres:password@127.0.0.1:5432/apex_dfs REDIS_URL=redis://127.0.0.1:6379/0"
