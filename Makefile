# LIMA - Local Intelligent Memo Assistant

# Load .env file if it exists
-include .env
export

.PHONY: up down dev-up dev-down update status hooks pre-commit seed setup

up:
	mkdir -p data/voice-memos/webhook data/audio-archive data/notes
	docker compose up -d

down:
	docker compose down

dev-up:
	mkdir -p data/voice-memos/webhook data/audio-archive data/notes
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

dev-down:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down

update:
	docker compose build --pull n8n
	docker compose pull whisper
	docker compose up -d

status:
	@docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" | \
		sed -E 's/\[::][^,]*,?//g; s/0\.0\.0\.0:([0-9]+)->[0-9]+\/tcp/:\1/g; s/[0-9]+\/(tcp|udp),? *//g; s/, *$$//; s/  +:/  :/g'

hooks:
	pre-commit install || uvx pre-commit install

pre-commit:
	pre-commit run --all-files || uvx pre-commit run --all-files

# seed: Import workflows & credentials (requires N8N_API_KEY)
seed:
	@echo "Importing workflows and credentials from ./workflows/seed/"
	@echo "(Existing workflows detected by name - you'll be prompted before creating duplicates)"
	@echo ""
	@if [ -z "$$N8N_API_KEY" ]; then \
		echo "❌ N8N_API_KEY not set."; \
		echo "   1. Create one in n8n UI: Settings → API → Create API Key"; \
		echo "   2. Add to .env: N8N_API_KEY=your_key"; \
		echo "   3. Run: source .env && make seed"; \
		exit 1; \
	fi
	@echo "Seeding n8n..."
	@echo "Importing credentials (CLI)..."
	@for f in workflows/seed/credentials/*.json; do \
		uv run python scripts/prepare-credential.py "$$f" | \
		docker compose exec -T n8n n8n import:credentials --input=/dev/stdin 2>&1 | grep -v "^$$" || true; \
	done
	@echo "Importing workflows (API)..."
	@for f in workflows/seed/*.json; do \
		uv run python scripts/n8n-import-workflow.py "$$f" || true; \
	done
	@echo ""
	@echo "✓ Seeding complete!"
	@echo ""
	@echo "⚠️  Workflows are INACTIVE. Activate at http://localhost:$(N8N_PORT)/home/workflows"
	@echo ""

# setup: Interactive first-time setup (build, start, configure, seed)
setup:
	@uv run python scripts/setup.py
