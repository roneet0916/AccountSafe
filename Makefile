# AccountSafe Makefile
# Standardized commands for development, testing, and deployment

.PHONY: help dev build up down test test-backend test-frontend clean init-ssl deploy logs shell \
        oracle-bootstrap oracle-ssl-init oracle-up oracle-down oracle-deploy oracle-logs \
        oracle-shell oracle-ps oracle-backup oracle-restore

# Default target
help:
	@echo ""
	@echo "AccountSafe - Available Commands"
	@echo "================================"
	@echo ""
	@echo "Development:"
	@echo "  make dev          Start local development environment"
	@echo "  make build        Build all Docker images"
	@echo "  make up           Start containers (detached)"
	@echo "  make down         Stop and remove containers"
	@echo "  make logs         Tail container logs"
	@echo "  make shell        Open shell in backend container"
	@echo ""
	@echo "Testing:"
	@echo "  make test         Run all tests (backend + frontend)"
	@echo "  make test-backend Run backend tests only (pytest)"
	@echo "  make test-frontend Run frontend tests only (jest)"
	@echo ""
	@echo "Production (legacy, single-host AWS):"
	@echo "  make init-ssl     Initialize Let's Encrypt certificates"
	@echo "  make deploy       Deploy to production"
	@echo ""
	@echo "Oracle Cloud (backend-only; frontend lives on Vercel):"
	@echo "  make oracle-bootstrap   First-time VM setup (docker, firewall, swap)"
	@echo "  make oracle-ssl-init    Issue Let's Encrypt cert for \$$DOMAIN"
	@echo "  make oracle-up          Start the production stack"
	@echo "  make oracle-down        Stop the production stack"
	@echo "  make oracle-deploy      git pull + rebuild + migrate + restart"
	@echo "  make oracle-logs        Tail all service logs"
	@echo "  make oracle-shell       Open shell in backend container"
	@echo "  make oracle-ps          Show service status"
	@echo "  make oracle-backup      Trigger an immediate DB backup"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean        Remove containers, volumes, and build artifacts"
	@echo ""

# =============================================================================
# Development
# =============================================================================

dev:
	docker-compose -f docker-compose.local.yml up --build

build:
	docker-compose -f docker-compose.local.yml build

up:
	docker-compose -f docker-compose.local.yml up -d

down:
	docker-compose -f docker-compose.local.yml down

logs:
	docker-compose -f docker-compose.local.yml logs -f

shell:
	docker-compose -f docker-compose.local.yml exec backend /bin/bash

# =============================================================================
# Testing
# =============================================================================

test:
	@echo "Running all tests..."
	./scripts/run_tests.sh

test-backend:
	@echo "Running backend tests..."
	cd backend && python -m pytest -v

test-frontend:
	@echo "Running frontend tests..."
	cd frontend && npm test -- --watchAll=false

# =============================================================================
# Production
# =============================================================================

init-ssl:
	chmod +x scripts/init-letsencrypt.sh
	./scripts/init-letsencrypt.sh

deploy:
	docker-compose -f docker-compose.prod.yml up -d --build

deploy-down:
	docker-compose -f docker-compose.prod.yml down

# =============================================================================
# Maintenance
# =============================================================================

clean:
	docker-compose -f docker-compose.local.yml down -v --rmi local
	docker-compose -f docker-compose.prod.yml down -v --rmi local
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -prune -o -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true

# =============================================================================
# Oracle Cloud (backend) + Vercel (frontend)
# =============================================================================
ORACLE_COMPOSE := docker-compose.oracle.yml

oracle-bootstrap:
	chmod +x scripts/oracle-bootstrap.sh
	./scripts/oracle-bootstrap.sh

oracle-ssl-init:
	chmod +x scripts/oracle-init-ssl.sh
	./scripts/oracle-init-ssl.sh

oracle-up:
	docker compose -f $(ORACLE_COMPOSE) up -d --build

oracle-down:
	docker compose -f $(ORACLE_COMPOSE) down

oracle-deploy:
	chmod +x scripts/oracle-deploy.sh
	./scripts/oracle-deploy.sh

oracle-logs:
	docker compose -f $(ORACLE_COMPOSE) logs -f --tail=200

oracle-shell:
	docker compose -f $(ORACLE_COMPOSE) exec backend /bin/bash

oracle-ps:
	docker compose -f $(ORACLE_COMPOSE) ps

oracle-backup:
	docker compose -f $(ORACLE_COMPOSE) exec backup /backup.sh

oracle-restore:
	@echo "Usage: docker compose -f $(ORACLE_COMPOSE) exec -T db psql -U \$$DB_USER \$$DB_NAME < backups/<file>.sql"
