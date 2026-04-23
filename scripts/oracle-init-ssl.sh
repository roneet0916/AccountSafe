#!/usr/bin/env bash
# =============================================================================
# AccountSafe - Let's Encrypt SSL Bootstrap (Oracle, API-only)
# =============================================================================
# Issues a certificate for $DOMAIN using the webroot plugin via a short-lived
# nginx container. Must be run ONCE on the VM, before `make oracle-up`.
#
# Prereqs:
#   - VM bootstrap already done (docker installed, ports 80/443 open).
#   - DNS for $DOMAIN already resolves to this VM's public IP.
#   - .env in repo root with DOMAIN= and LETSENCRYPT_EMAIL= filled in.
# =============================================================================

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[ssl]${NC} $*"; }
warn() { echo -e "${YELLOW}[ssl]${NC} $*"; }
die()  { echo -e "${RED}[ssl]${NC} $*" >&2; exit 1; }

COMPOSE_FILE="docker-compose.oracle.yml"
STAGING="${STAGING:-0}"       # STAGING=1 ./scripts/oracle-init-ssl.sh to dry-run
RSA_KEY_SIZE=4096

[[ -f .env ]] || die ".env not found. Run: cp .env.oracle.example .env && edit it."
# shellcheck disable=SC1091
set -a; source .env; set +a

[[ -n "${DOMAIN:-}" ]]            || die "DOMAIN is not set in .env"
[[ -n "${LETSENCRYPT_EMAIL:-}" ]] || die "LETSENCRYPT_EMAIL is not set in .env"
[[ "$DOMAIN" != "accountsafe.duckdns.org" || "${FORCE:-0}" == "1" ]] || \
    warn "DOMAIN is still the example value; set FORCE=1 to proceed anyway."

command -v docker >/dev/null || die "docker is not installed."

# DNS sanity check
RESOLVED="$(getent hosts "$DOMAIN" | awk '{print $1}' | head -n1 || true)"
if [[ -z "$RESOLVED" ]]; then
    die "DNS for $DOMAIN does not resolve. Point it at this VM's public IP first."
fi
log "DNS $DOMAIN -> $RESOLVED"

mkdir -p ./certbot/conf ./certbot/www

# Download recommended TLS parameters (only once)
if [[ ! -e ./certbot/conf/options-ssl-nginx.conf || ! -e ./certbot/conf/ssl-dhparams.pem ]]; then
    log "Fetching TLS parameters..."
    curl -fsSL \
        https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf \
        -o ./certbot/conf/options-ssl-nginx.conf
    curl -fsSL \
        https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem \
        -o ./certbot/conf/ssl-dhparams.pem
fi

# 1) Start a tiny nginx that ONLY serves ACME challenge on :80.
#    We deliberately do NOT start the production nginx yet, because it
#    references a cert that doesn't exist.
log "Starting temporary ACME webroot server on :80..."
docker rm -f accountsafe-acme-bootstrap >/dev/null 2>&1 || true
docker run -d --name accountsafe-acme-bootstrap \
    -p 80:80 \
    -v "$(pwd)/certbot/www:/usr/share/nginx/html:ro" \
    nginx:1.27-alpine \
    >/dev/null

cleanup() {
    docker rm -f accountsafe-acme-bootstrap >/dev/null 2>&1 || true
}
trap cleanup EXIT

sleep 3

# 2) Request certificate
STAGING_ARG=""
if [[ "$STAGING" == "1" ]]; then
    warn "Using Let's Encrypt STAGING environment (test certs, not trusted)."
    STAGING_ARG="--staging"
fi

log "Requesting certificate for $DOMAIN..."
docker run --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/certbot/www:/var/www/certbot" \
    certbot/certbot:latest \
    certonly --webroot -w /var/www/certbot \
        $STAGING_ARG \
        -d "$DOMAIN" \
        --email "$LETSENCRYPT_EMAIL" \
        --rsa-key-size "$RSA_KEY_SIZE" \
        --agree-tos --no-eff-email \
        --non-interactive

cleanup
trap - EXIT

log "Certificate issued for $DOMAIN."
log "Next: make oracle-up"
