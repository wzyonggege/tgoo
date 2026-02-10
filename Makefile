# ==========================================================
# TGO Development Makefile (lean stack)
# ==========================================================
# This Makefile only covers the remaining core services:
#   - Backend: tgo-api, tgo-platform
#   - Frontend: tgo-web, tgo-widget-app
#   - Infrastructure: PostgreSQL, Redis, WuKongIM (via docker-compose.dev.yml)
# ==========================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

ENV_FILE := .env.dev
COMPOSE_DEV := docker-compose.dev.yml

API_DIR := repos/tgo-api
PLATFORM_DIR := repos/tgo-platform
WEB_DIR := repos/tgo-web
WIDGET_DIR := repos/tgo-widget-app

API_PORT := 8000
PLATFORM_PORT := 8003
WEB_PORT := 5173
WIDGET_PORT := 5174

CYAN := [36m
GREEN := [32m
YELLOW := [33m
RED := [31m
RESET := [0m

.PHONY: help
help:
	@echo ""
	@echo "$(CYAN)TGO Development Commands$(RESET)"
	@echo "========================="
	@echo ""
	@echo "$(GREEN)Setup:$(RESET)"
	@echo "  make install          Install backend + frontend deps"
	@echo "  make install-api      Install tgo-api"
	@echo "  make install-platform Install tgo-platform"
	@echo "  make install-frontend Install tgo-web & widget"
	@echo ""
	@echo "$(GREEN)Infrastructure (Docker):$(RESET)"
	@echo "  make infra-up         Start PostgreSQL / Redis / WuKongIM"
	@echo "  make infra-down       Stop infrastructure"
	@echo "  make infra-logs       Tail infra logs"
	@echo "  make infra-ps         Show running containers"
	@echo ""
	@echo "$(GREEN)Database:$(RESET)"
	@echo "  make migrate          Run migrations (api + platform)"
	@echo ""
	@echo "$(GREEN)Backend Services:$(RESET)"
	@echo "  make dev-api          Start tgo-api (port $(API_PORT))"
	@echo "  make dev-platform     Start tgo-platform (port $(PLATFORM_PORT))"
	@echo "  make dev-backend      Start both backends in background"
	@echo ""
	@echo "$(GREEN)Frontend Services:$(RESET)"
	@echo "  make dev-web          Start tgo-web (port $(WEB_PORT))"
	@echo "  make dev-widget       Start widget (port $(WIDGET_PORT))"
	@echo "  make dev-frontend     Start both frontends in background"
	@echo ""
	@echo "$(GREEN)Combined:$(RESET)"
	@echo "  make dev-all          Start api/platform/web/widget"
	@echo "  make stop-all         Stop local uvicorn + vite"
	@echo ""
	@echo "$(GREEN)Utilities:$(RESET)"
	@echo "  make check-env        Ensure .env.dev exists"
	@echo "  make logs SERVICE=x   Tail docker-compose.dev logs"
	@echo "  make shell SERVICE=x  Shell into docker service"
	@echo "  make psql             Open psql"
	@echo "  make redis-cli        Open redis-cli"
	@echo ""

.PHONY: check-env
check-env:
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "$(RED)Error: $(ENV_FILE) not found$(RESET)"; \
		echo "$(YELLOW)Run: cp .env.dev.example .env.dev$(RESET)"; \
		exit 1; \
	fi

.PHONY: infra-up infra-down infra-logs infra-ps
infra-up:
	@echo "$(CYAN)Starting development infrastructure...$(RESET)"
	@docker compose -f $(COMPOSE_DEV) up -d
	@echo "$(GREEN)Infrastructure started!$(RESET)"

infra-down:
	@echo "$(CYAN)Stopping development infrastructure...$(RESET)"
	@docker compose -f $(COMPOSE_DEV) down
	@echo "$(GREEN)Infrastructure stopped$(RESET)"

infra-logs:
	@docker compose -f $(COMPOSE_DEV) logs -f

infra-ps:
	@docker compose -f $(COMPOSE_DEV) ps

.PHONY: install install-backend install-frontend install-api install-platform
install: install-backend install-frontend
	@echo "$(GREEN)Dependency installation completed!$(RESET)"

install-backend: install-api install-platform
	@echo "$(GREEN)Backend deps installed$(RESET)"

install-api:
	@echo "  $(CYAN)Installing tgo-api...$(RESET)"
	@cd $(API_DIR) && poetry install --no-root

install-platform:
	@echo "  $(CYAN)Installing tgo-platform...$(RESET)"
	@cd $(PLATFORM_DIR) && poetry install --no-root

install-frontend:
	@echo "$(CYAN)Installing frontend dependencies...$(RESET)"
	@cd $(WEB_DIR) && npm install
	@cd $(WIDGET_DIR) && npm install
	@echo "$(GREEN)Frontend dependencies installed$(RESET)"

.PHONY: migrate migrate-api migrate-platform
migrate: check-env migrate-api migrate-platform
	@echo "$(GREEN)All migrations completed!$(RESET)"

migrate-api: check-env
	@echo "$(CYAN)Running tgo-api migrations...$(RESET)"
	@cd $(API_DIR) && set -a && source ../../$(ENV_FILE) && set +a && PYTHONPATH=. poetry run alembic upgrade head

migrate-platform: check-env
	@echo "$(CYAN)Running tgo-platform migrations...$(RESET)"
	@cd $(PLATFORM_DIR) && set -a && source ../../$(ENV_FILE) && set +a && \
		DATABASE_URL=postgresql+asyncpg://tgo:tgo@localhost:5432/tgo \
		API_BASE_URL=http://localhost:$(API_PORT) \
		PYTHONPATH=. poetry run alembic upgrade head

.PHONY: dev-api dev-platform dev-web dev-widget

dev-api: check-env
	@echo "$(CYAN)Starting tgo-api on port $(API_PORT)...$(RESET)"
	@cd $(API_DIR) && set -a && source ../../$(ENV_FILE) && set +a && \
		PORT=$(API_PORT) \
		REDIS_URL=redis://localhost:6379/0 \
		DATABASE_URL=postgresql+asyncpg://tgo:tgo@localhost:5432/tgo \
		poetry run uvicorn app.main:app --host 0.0.0.0 --port $(API_PORT) --reload

dev-platform: check-env
	@echo "$(CYAN)Starting tgo-platform on port $(PLATFORM_PORT)...$(RESET)"
	@cd $(PLATFORM_DIR) && set -a && source ../../$(ENV_FILE) && set +a && \
		PORT=$(PLATFORM_PORT) \
		REDIS_URL=redis://localhost:6379/0 \
		DATABASE_URL=postgresql+asyncpg://tgo:tgo@localhost:5432/tgo \
		API_BASE_URL=http://localhost:$(API_PORT) \
		poetry run uvicorn app.main:app --host 0.0.0.0 --port $(PLATFORM_PORT) --reload

dev-web: check-env
	@echo "$(CYAN)Starting tgo-web on port $(WEB_PORT)...$(RESET)"
	@cd $(WEB_DIR) && \
		VITE_API_BASE_URL=http://localhost:$(API_PORT) \
		VITE_DEBUG_MODE=true \
		npm run dev -- --port $(WEB_PORT)

dev-widget: check-env
	@echo "$(CYAN)Starting tgo-widget-app on port $(WIDGET_PORT)...$(RESET)"
	@cd $(WIDGET_DIR) && \
		VITE_API_BASE=http://localhost:$(API_PORT) \
		npm run dev -- --port $(WIDGET_PORT)

.PHONY: dev-backend dev-frontend dev-all stop-all

dev-backend: check-env
	@echo "$(CYAN)Starting backend services in background...$(RESET)"
	@$(MAKE) dev-api > /dev/null 2>&1 & \
	$(MAKE) dev-platform > /dev/null 2>&1 & \
	echo "$(GREEN)Backend services started (check ps aux | grep uvicorn).$(RESET)"

dev-frontend: check-env
	@echo "$(CYAN)Starting frontend services in background...$(RESET)"
	@$(MAKE) dev-web > /dev/null 2>&1 & \
	$(MAKE) dev-widget > /dev/null 2>&1 & \
	echo "$(GREEN)Frontend services started in background.$(RESET)"

dev-all: dev-backend dev-frontend

stop-all:
	@echo "$(YELLOW)Stopping uvicorn / vite processes...$(RESET)"
	@pkill -f "uvicorn.*app.main:app" || true
	@pkill -f "vite" || true
	@echo "$(GREEN)All local dev servers stopped.$(RESET)"

.PHONY: logs shell psql redis-cli clean

logs:
	@if [ -z "$(SERVICE)" ]; then \
		docker compose -f $(COMPOSE_DEV) logs -f; \
	else \
		docker compose -f $(COMPOSE_DEV) logs -f $(SERVICE); \
	fi

shell:
	@if [ -z "$(SERVICE)" ]; then \
		echo "$(RED)Usage: make shell SERVICE=postgres$(RESET)"; \
		exit 1; \
	fi
	@docker compose -f $(COMPOSE_DEV) exec $(SERVICE) sh

psql:
	@docker compose -f $(COMPOSE_DEV) exec postgres psql -U tgo -d tgo

redis-cli:
	@docker compose -f $(COMPOSE_DEV) exec redis redis-cli

clean:
	@echo "$(YELLOW)Cleaning up...$(RESET)"
	@docker compose -f $(COMPOSE_DEV) down -v
	@echo "$(GREEN)Cleanup complete$(RESET)"
