# LIMA - Local Intelligence Meeting Assistant

.PHONY: up down dev-up dev-down hooks pre-commit

up:
	docker compose up -d

down:
	docker compose down

dev-up:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

dev-down:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down

hooks:
	pre-commit install || uvx pre-commit install

pre-commit:
	pre-commit run --all-files || uvx pre-commit run --all-files
