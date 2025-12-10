# LIMA - Local Intelligent Memo Assistant

.PHONY: up down dev-up dev-down hooks pre-commit

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

hooks:
	pre-commit install || uvx pre-commit install

pre-commit:
	pre-commit run --all-files || uvx pre-commit run --all-files
