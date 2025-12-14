# LIMA - Local Intelligent Memo Assistant

# Load .env file if it exists
-include .env
export

.PHONY: up down dev-up dev-down update status hooks pre-commit seed setup \
        whisper-native whisper-native-stop whisper-native-logs whisper-native-status

up:
	@uv run python -c "from pathlib import Path; [Path(p).mkdir(parents=True, exist_ok=True) for p in ['data/voice-memos/webhook', 'data/audio-archive', 'data/notes']]"
	docker compose up -d

down:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down

dev-up:
	@uv run python -c "from pathlib import Path; [Path(p).mkdir(parents=True, exist_ok=True) for p in ['data/voice-memos/webhook', 'data/audio-archive', 'data/notes']]"
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

dev-down:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down

update:
	docker compose build --pull n8n
	docker compose pull whisper
	docker compose up -d

status:
	@uv run python -c "import subprocess,re; out=subprocess.run(['docker','compose','ps','--format','table {{.Name}}\t{{.Status}}\t{{.Ports}}'],capture_output=True,text=True).stdout; print(re.sub(r'\[::\][^,]*,?|0\.0\.0\.0:(\d+)->\d+/tcp|[\d]+/(tcp|udp),? *|, *$$|  +:',lambda m:':'+m.group(1) if m.group(1) else '',out))"

hooks:
	pre-commit install || uvx pre-commit install

pre-commit:
	pre-commit run --all-files || uvx pre-commit run --all-files

# seed: Import workflows & credentials (requires N8N_API_KEY)
seed:
	@uv run python scripts/seed.py

# setup: Interactive first-time setup (build, start, configure, seed)
setup:
	@uv run python scripts/setup.py

# Native GPU whisper server (optional, faster than Docker whisper)
# Runs on port 9001 by default (Docker whisper uses 9000)
whisper-native:
	@uv run python scripts/whisper-native.py start

whisper-native-stop:
	@uv run python scripts/whisper-native.py stop

whisper-native-status:
	@uv run python scripts/whisper-native.py status

whisper-native-logs:
	@uv run python scripts/whisper-native.py logs
