#!/usr/bin/env bash
# =============================================================================
# AccountSafe - Oracle Redeploy
# =============================================================================
# Idempotent: pulls latest code, rebuilds images, runs migrations, restarts.
# Safe to run repeatedly. Intended for:
#   - manual redeploys: ssh ubuntu@vm && cd AccountSafe && ./scripts/oracle-deploy.sh
#   - GitHub Actions on merge to main
# =============================================================================

set -euo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
log() { echo -e "${GREEN}[deploy]${NC} $*"; }
die() { echo -e "${RED}[deploy]${NC} $*" >&2; exit 1; }

COMPOSE_FILE="docker-compose.oracle.yml"

[[ -f .env ]]                  || die ".env missing. cp .env.oracle.example .env"
[[ -f "$COMPOSE_FILE" ]]       || die "$COMPOSE_FILE not found; wrong directory?"
[[ -d certbot/conf/live ]]     || die "SSL certs missing. Run ./scripts/oracle-init-ssl.sh first."

log "Pulling latest code..."
git fetch --all --prune
git reset --hard origin/main

log "Building images..."
docker compose -f "$COMPOSE_FILE" build --pull

log "Starting services..."
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

log "Waiting for backend to be healthy..."
for _ in $(seq 1 30); do
    if docker compose -f "$COMPOSE_FILE" exec -T backend \
        python -c "import urllib.request,sys;urllib.request.urlopen('http://localhost:8000/api/health/');" \
        >/dev/null 2>&1; then
        log "Backend healthy."
        break
    fi
    sleep 2
done

log "Pruning dangling images..."
docker image prune -f >/dev/null

log "Deploy complete. Services:"
docker compose -f "$COMPOSE_FILE" ps
