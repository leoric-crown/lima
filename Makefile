# LIMA - Local Intelligence Meeting Assistant
# Makefile for common operations
#
# Usage:
#   make help     - Show all commands
#   make init     - First-time setup
#   make up       - Start production stack
#   make dev-up   - Start with development tools (n8n-mcp)

.PHONY: help init up down dev-up dev-down restart logs status pull validate \
        db-shell db-backup db-restore clean prune env-setup

# Colors for output (disabled on Windows where they render as garbage)
ifeq ($(OS),Windows_NT)
CYAN :=
GREEN :=
YELLOW :=
RED :=
RESET :=
else
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m
endif

# Default target
.DEFAULT_GOAL := help

# =============================================================================
# Help
# =============================================================================

help: ## Show this help message
	@echo ""
	@echo "$(CYAN)LIMA - Local Intelligence Meeting Assistant$(RESET)"
	@echo ""
	@echo "$(GREEN)Setup:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(init|env)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-15s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Production:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -vE '(dev-|init|env|db-|clean|prune|help)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-15s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Development:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E 'dev-' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-15s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Database:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E 'db-' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-15s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Maintenance:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(clean|prune)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-15s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# =============================================================================
# Setup
# =============================================================================

init: env-setup pull up ## Complete first-time setup (env + pull + start)
	@echo "$(GREEN)LIMA initialized successfully!$(RESET)"
	@echo ""
	@echo "$(CYAN)Next steps:$(RESET)"
	@echo "  1. Access n8n at http://localhost:5678"
	@echo "  2. Create your admin account"
	@echo "  3. Generate API key for n8n-mcp (Settings > API)"
	@echo "  4. Run 'make dev-up' to enable AI-assisted development"
	@echo ""

env-setup: ## Create .env from .env.example
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(YELLOW)Created .env from .env.example$(RESET)"; \
		echo "$(RED)IMPORTANT: Edit .env and set secure passwords!$(RESET)"; \
	else \
		echo "$(GREEN).env already exists$(RESET)"; \
	fi

# =============================================================================
# Production Commands
# =============================================================================

up: ## Start production stack (postgres + n8n)
	@echo "$(CYAN)Starting LIMA production stack...$(RESET)"
	docker compose up -d
	@echo "$(GREEN)LIMA is running at http://localhost:5678$(RESET)"

down: ## Stop all services
	@echo "$(CYAN)Stopping LIMA...$(RESET)"
	docker compose down
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down 2>/dev/null || true
	@echo "$(GREEN)LIMA stopped$(RESET)"

restart: ## Restart all services
	@echo "$(CYAN)Restarting LIMA...$(RESET)"
	docker compose restart
	@echo "$(GREEN)LIMA restarted$(RESET)"

logs: ## Follow logs for all services
	docker compose logs -f

status: ## Show service status and health
	@echo "$(CYAN)=== LIMA Service Status ===$(RESET)"
	@echo ""
	@docker compose ps
	@echo ""
	@echo "$(CYAN)=== Health Checks ===$(RESET)"
	@echo -n "PostgreSQL: " && (curl -sf http://localhost:5432 2>/dev/null && echo "$(GREEN)UP$(RESET)" || docker compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1 && echo "$(GREEN)UP$(RESET)" || echo "$(RED)DOWN$(RESET)")
	@echo -n "n8n:        " && (curl -sf http://localhost:5678/healthz >/dev/null 2>&1 && echo "$(GREEN)UP$(RESET)" || echo "$(RED)DOWN$(RESET)")
	@echo -n "n8n-mcp:    " && (curl -sf http://localhost:8042/health >/dev/null 2>&1 && echo "$(GREEN)UP$(RESET)" || echo "$(YELLOW)NOT RUNNING$(RESET)")
	@echo ""

pull: ## Pull latest images
	@echo "$(CYAN)Pulling latest images...$(RESET)"
	docker compose pull
	docker compose -f docker-compose.yml -f docker-compose.dev.yml pull 2>/dev/null || true
	@echo "$(GREEN)Images updated$(RESET)"

validate: ## Validate docker-compose files
	@echo "$(CYAN)Validating docker-compose.yml...$(RESET)"
	docker compose config -q && echo "$(GREEN)docker-compose.yml is valid$(RESET)"
	@echo "$(CYAN)Validating docker-compose.dev.yml...$(RESET)"
	docker compose -f docker-compose.yml -f docker-compose.dev.yml config -q && echo "$(GREEN)docker-compose.dev.yml is valid$(RESET)"

# =============================================================================
# Development Commands
# =============================================================================

dev-up: ## Start with development tools (n8n-mcp, postgres-mcp, pgAdmin)
	@echo "$(CYAN)Starting LIMA with development tools...$(RESET)"
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
	@echo "$(GREEN)LIMA dev stack running$(RESET)"
	@echo ""
	@echo "$(CYAN)Service URLs:$(RESET)"
	@echo "  n8n:          http://localhost:5678"
	@echo "  n8n-mcp:      http://localhost:8042/health"
	@echo "  postgres-mcp: http://localhost:8700"
	@echo "  pgAdmin:      http://localhost:5050"
	@echo ""

dev-down: ## Stop development stack
	@echo "$(CYAN)Stopping LIMA dev stack...$(RESET)"
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down
	@echo "$(GREEN)LIMA dev stack stopped$(RESET)"

dev-logs: ## Follow logs for dev services
	docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f


# =============================================================================
# Database Commands
# =============================================================================

db-shell: ## Access PostgreSQL shell
	@echo "$(CYAN)Connecting to LIMA database...$(RESET)"
	docker compose exec postgres psql -U postgres -d lima

db-backup: ## Backup database to backup.sql
	@echo "$(CYAN)Backing up LIMA database...$(RESET)"
	docker compose exec -T postgres pg_dump -U postgres -d lima > backup-$$(date +%Y%m%d-%H%M%S).sql
	@echo "$(GREEN)Backup created$(RESET)"

db-restore: ## Restore database from backup.sql (usage: make db-restore FILE=backup.sql)
	@if [ -z "$(FILE)" ]; then \
		echo "$(RED)Usage: make db-restore FILE=backup.sql$(RESET)"; \
		exit 1; \
	fi
	@echo "$(CYAN)Restoring LIMA database from $(FILE)...$(RESET)"
	docker compose exec -T postgres psql -U postgres -d lima < $(FILE)
	@echo "$(GREEN)Database restored$(RESET)"

db-reset: ## Reset database (WARNING: destroys all data)
	@echo "$(RED)WARNING: This will destroy all data!$(RESET)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	docker compose down -v
	docker volume rm lima_postgres_data 2>/dev/null || true
	@echo "$(GREEN)Database reset. Run 'make up' to reinitialize.$(RESET)"

# =============================================================================
# Maintenance
# =============================================================================

clean: ## Remove stopped containers and unused images
	@echo "$(CYAN)Cleaning up...$(RESET)"
	docker compose down --remove-orphans
	docker image prune -f
	@echo "$(GREEN)Cleanup complete$(RESET)"

prune: ## Deep clean (WARNING: removes all unused Docker resources)
	@echo "$(RED)WARNING: This will remove all unused Docker resources!$(RESET)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	docker system prune -af
	@echo "$(GREEN)Deep clean complete$(RESET)"

# =============================================================================
# Data Directories
# =============================================================================

dirs: ## Create data directories
	@mkdir -p data/audio data/transcripts data/notes workflows
	@echo "$(GREEN)Data directories created$(RESET)"
