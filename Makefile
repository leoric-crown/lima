# LIMA - Local Intelligent Memo Assistant

.PHONY: up down dev-up dev-down update status hooks pre-commit seed

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
	docker compose ps

hooks:
	pre-commit install || uvx pre-commit install

pre-commit:
	pre-commit run --all-files || uvx pre-commit run --all-files

# seed: Import workflows & credentials (requires N8N_API_KEY for workflows)
# WARNING: Creates new workflows - will duplicate if run multiple times!
seed:
	@echo "⚠️  WARNING: This creates NEW workflows from ./workflows/seed/"
	@echo "   Running multiple times will create DUPLICATES."
	@echo "   Only run on fresh n8n installs or to create a copy from repo version."
	@echo ""
	@if [ -z "$$N8N_API_KEY" ]; then \
		echo "❌ N8N_API_KEY not set."; \
		echo "   1. Create one in n8n UI: Settings → API → Create API Key"; \
		echo "   2. Add to .env: N8N_API_KEY=your_key"; \
		echo "   3. Run: source .env && make seed"; \
		exit 1; \
	fi
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ] || (echo "Aborted." && exit 1)
	@echo ""
	@echo "Seeding n8n..."
	@echo "Importing credentials (CLI)..."
	@docker compose exec n8n n8n import:credentials --input=/home/node/.n8n/workflows/seed/credentials/lm-studio.json 2>&1 | grep -v "^$$" || true
	@echo "Importing workflows (API)..."
	@for f in workflows/seed/*.json; do \
		name=$$(cat "$$f" | jq -r '.name'); \
		cat "$$f" | jq '{name, nodes, connections, settings}' | \
		curl -sf -X POST http://localhost:5678/api/v1/workflows \
		-H "Content-Type: application/json" \
		-H "X-N8N-API-KEY: $$N8N_API_KEY" \
		-d @- > /dev/null && echo "✓ Imported: $$name" || echo "⚠ Failed: $$name"; \
	done
	@echo ""
	@echo "✓ Seeding complete!"
	@echo ""
	@echo "⚠️  Workflows are INACTIVE. Activate at http://localhost:5678/home/workflows"
	@echo ""
	@echo "NOTE: LM Studio credential uses http://host.docker.internal:1234/v1"
	@echo "      On Linux, edit credential to use your machine's local IP instead."
	@echo ""
