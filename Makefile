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

seed:
	@echo "⚠️  This will import/overwrite workflows and credentials using the contents of ./workflows/seed"
	@echo "    If you've made changes in the n8n UI to these workflows/credentials, they will be lost."
	@echo ""
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ] || (echo "Aborted." && exit 1)
	@echo ""
	@echo "Seeding n8n..."
	@docker compose exec n8n n8n import:credentials --input=/home/node/.n8n/workflows/seed/credentials/lm-studio.json
	@docker compose exec n8n n8n import:workflow --separate --input=/home/node/.n8n/workflows/seed 2>&1 | grep -v "Active version not found\|Error: Active version not found\|at .*n8n\|at process\|at Import\|at Command\|Could not remove webhooks\|Deactivating workflow\|Remember to activate" || true
	@echo ""
	@echo "✓ Workflows and credentials imported!"
	@echo ""
	@echo "⚠️ Imported workflows are INACTIVE by default. To activate:"
	@echo "   1. Go to http://localhost:5678/home/workflows"
	@echo "   2. Toggle 'Inactive' -> 'Active' for each workflow as needed."
	@echo "   3. Open Workflows and verify Credentials are set up correctly and connection tests pass"
	@echo ""
	@echo "NOTE: LM Studio credential uses http://host.docker.internal:1234/v1"
	@echo "      On Linux, you may need to edit the credential to use your machine's local IP instead."
	@echo ""
