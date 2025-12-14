# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LIMA (Local Intelligent Memo Assistant) is a local-first, privacy-focused voice memo tool. It provides speech-to-text transcription, workflow automation, and semantic search capabilities using a Docker-based stack.

## Common Commands

```bash
# Production stack (postgres + n8n + whisper)
make up                 # Start production services
make down               # Stop all services
make status             # Check service health

# Development stack (adds n8n-mcp, postgres-mcp, pgAdmin)
make dev-up             # Start with dev tools
make dev-down           # Stop dev stack

# Native GPU whisper (optional, faster than Docker)
make whisper-native     # Start native whisper in background
make whisper-native-stop # Stop native whisper

# First-time setup
make setup              # Interactive wizard (build, configure, seed)
make seed               # Import workflows & credentials only (detects duplicates)

# Rebuild custom n8n image after Dockerfile changes
docker compose build n8n

# View logs
docker compose logs -f

# Database shell
docker compose exec postgres psql -U postgres -d lima
```

## Project Structure

```
lima/
├── docker-compose.yml      # Production stack
├── docker-compose.dev.yml  # Dev overlay (n8n-mcp, pgAdmin)
├── n8n.Dockerfile          # Custom n8n image with ffmpeg
├── Caddyfile               # Caddy reverse proxy config
├── .env.example            # Environment template
├── init-data.sh            # PostgreSQL initialization
├── Makefile                # Convenience commands
├── static/                 # Static assets served by Caddy at /lima/*
│   └── recorder/           # Voice Recorder UI
│       └── index.html
├── data/                   # Obsidian vault (open in Obsidian)
│   ├── voice-memos/        # Drop audio files here (auto-processed)
│   │   └── webhook/        # Webhook uploads (not re-watched)
│   ├── audio-archive/      # Processed originals (linked from notes)
│   └── notes/              # Markdown output
├── services/
│   └── whisper-server/     # Native GPU whisper servers (optional)
├── workflows/              # n8n workflow exports
└── docs/                   # User documentation
```

## Architecture

### Docker Services

**Production** (`docker-compose.yml`):
- **postgres**: PostgreSQL 17 with pgvector extension for embeddings
- **n8n**: Custom image (`n8n.Dockerfile`) with ffmpeg for audio processing
- **whisper**: Speaches (faster-whisper) for speech-to-text
- **caddy**: Reverse proxy serving Voice Recorder UI

**Development** (`docker-compose.dev.yml` overlay):
- **n8n-mcp**: AI assistant for n8n workflow development (HTTP transport, port 8042)
- **postgres-mcp**: Direct database access via MCP (SSE transport, port 8700)
- **pgadmin**: Database UI

### Database Schema

The `init-data.sh` script creates:
- `meetings`: Metadata (title, date, participants, tags)
- `transcripts`: Full transcription text per meeting
- `chunks`: Transcript segments with `vector(1536)` embeddings for semantic search
- `insights`: Extracted decisions, actions, risks (typed, with assignee/due date)

Uses IVFFlat index for cosine similarity search on embeddings.

### Native Whisper Alternative

`services/whisper-server/` provides platform-specific native GPU servers:
- **macOS**: Lightning Whisper MLX (Apple Silicon Metal)
- **Linux/Windows**: faster-whisper with CUDA (NVIDIA GPU)

See `docs/native-whisper.md` for details and benchmarks.

## MCP Server Integration

Connect MCP servers for AI-assisted development. See `docs/MCP_SETUP.md` for full details.

Quick setup:
```bash
source .env

# n8n-mcp (workflow management)
claude mcp add-json lima-n8n '{"type":"http","url":"http://localhost:8042/mcp","headers":{"Authorization":"Bearer '"$MCP_AUTH_TOKEN"'"}}'

# postgres-mcp (database access)
claude mcp add --transport sse lima-postgres http://localhost:8700/sse
```

## Environment Variables

Required in `.env` (generate with `openssl rand -base64 32` or `openssl rand -hex 32`):
- `POSTGRES_PASSWORD`
- `N8N_DB_PASSWORD`
- `N8N_ENCRYPTION_KEY`
- `MCP_AUTH_TOKEN`

Optional:
- `N8N_API_KEY`: Generate in n8n UI (Settings > API) for workflow seeding and n8n-mcp
- `N8N_PORT`: External port for n8n (default: 5678)
- `LOCAL_LLM_PORT`: Port for local LLM (default: 1234 for LM Studio, set to 11434 for Ollama)
- `LLM_MODEL`: LLM model name for workflows (default: `openai/gpt-oss-20b`, must support tool calling)
- `WHISPER_MODEL`: Default `Systran/faster-whisper-base`, options include tiny/small/medium/large-v3
- `NATIVE_WHISPER_HOST`: Bind address for native whisper (default: 0.0.0.0)
- `NATIVE_WHISPER_PORT`: Port for native CUDA/MLX whisper server (default: 9001)

## Service URLs

Ports are configurable in `.env`. Defaults shown:

| Service | URL | Notes |
|---------|-----|-------|
| n8n | http://localhost:${N8N_PORT} | Workflow automation |
| Voice Recorder | http://localhost:${CADDY_PORT}/lima/recorder/ | Browser voice recording UI |
| whisper | http://localhost:${WHISPER_PORT} | OpenAI-compatible `/v1/audio/transcriptions` |
| n8n-mcp | http://localhost:${MCP_PORT} | Dev only, requires auth header |
| postgres-mcp | http://localhost:${POSTGRES_MCP_PORT}/sse | Dev only, SSE transport |
| pgAdmin | http://localhost:${PGADMIN_PORT} | Dev only |

## Data Directories

The `data/` folder is an Obsidian vault for viewing processed notes:

- `data/voice-memos/`: Drop zone for audio files (workflow input)
- `data/voice-memos/webhook/`: Webhook uploads land here
- `data/audio-archive/`: Processed originals moved here after transcription
- `data/notes/`: Output markdown notes
- `workflows/`: n8n workflow exports (mounted read-only)

Benchmark test files are in `scripts/test_audio/` (not mounted to containers).

## Audio Processing

n8n has no native audio processing nodes. The custom n8n image includes ffmpeg, which you invoke via the **Execute Command** node:

```bash
# Split into 15-minute chunks
ffmpeg -i /data/audio/input.mp3 -f segment -segment_time 900 -c copy /data/audio/chunks/chunk_%03d.mp3

# Optimize for transcription
ffmpeg -i /data/audio/input.mp3 -ac 1 -ar 16000 -b:a 64k /data/audio/optimized.mp3
```

Long files (>60 min) should be chunked for parallel transcription. See `docs/audio-processing-guide.md` for detailed patterns.

## LLM Configuration

For LM Studio, Ollama, and context window configuration, see `docs/customizing-your-ai.md`.

**Note:** n8n's Alpine container doesn't have `find -printf`, use `stat -c %Y` instead.

## Documentation

- `docs/index.md` - Documentation hub
- `docs/getting-started.md` - Setup walkthrough
- `docs/customizing-your-ai.md` - LLM configuration
- `docs/using-lima-on-your-phone.md` - Tailscale remote access
- `docs/native-whisper.md` - GPU acceleration
- `docs/where-is-my-data.md` - File locations and backups
- `docs/recipes.md` - Use case examples
- `docs/troubleshooting.md` - Common issues
- `docs/audio-processing-guide.md` - Long recordings and ffmpeg
- `docs/MCP_SETUP.md` - MCP server setup for AI assistants
