# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LIMA (Local Intelligence Meeting Assistant) is a local-first, privacy-focused meeting intelligence tool. It provides speech-to-text transcription, workflow automation, and semantic search capabilities using a Docker-based stack.

## Common Commands

```bash
# Production stack (postgres + n8n + whisper)
make up                 # Start production services
make down               # Stop all services
make logs               # Follow logs
make status             # Check service health

# Development stack (adds n8n-mcp, postgres-mcp, pgAdmin)
make dev-up             # Start with dev tools
make dev-down           # Stop dev stack

# Database operations
make db-shell           # PostgreSQL shell (psql)
make db-backup          # Backup to timestamped file
make db-restore FILE=backup.sql

# First-time setup (after make up)
make seed               # Import workflow, prints credential setup instructions

# Rebuild custom n8n image after Dockerfile changes
docker compose build n8n
```

## Architecture

### Docker Services

**Production** (`docker-compose.yml`):
- **postgres**: PostgreSQL 17 with pgvector extension for embeddings
- **n8n**: Custom image (`n8n.Dockerfile`) with ffmpeg for audio processing
- **whisper**: Speaches (faster-whisper) for speech-to-text

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

`services/whisper-server/` provides platform-specific native GPU servers for local development:
- **macOS**: Lightning Whisper MLX (Apple Silicon Metal)
- **Linux/Windows**: faster-whisper with CUDA (NVIDIA GPU)

**Quick start** (auto-detects platform):
```bash
cd services/whisper-server
uv sync
./run_server.sh --port 9002  # macOS/Linux
# or
.\run_server.ps1 -Port 9002  # Windows PowerShell
```

**Linux CUDA setup** (NVIDIA GPU required):
```bash
uv pip install nvidia-cudnn-cu12  # Required for GPU acceleration
```

**Performance comparison** (`scripts/benchmark_whisper.py` - 42min file):
- **macOS M4 Pro MLX**: 166x realtime (~15s) - **5.3x faster** than Docker, but slow cold start
- **Linux RTX 4090 CUDA**: 71x realtime (~36s) - **4.3x faster** than Docker
- **Windows RTX 4090 CUDA**: 39x realtime (~66s) - **2.8x faster** than Docker
- **Docker Speaches**: 14-33x realtime depending on platform - consistent, no warmup

**Recommendation**:
- **Production**: Docker Speaches for consistency and predictable cold starts
- **Development**: Native GPU for 3-5x speedup (macOS MLX fastest, but needs warmup handling)

See `services/whisper-server/README.md` for detailed benchmarks and setup.

## MCP Server Integration

Connect MCP servers for AI-assisted development:

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
- `N8N_API_KEY`: Generate in n8n UI (Settings > API) for n8n-mcp workflow management
- `WHISPER_MODEL`: Default `Systran/faster-whisper-base`, options include tiny/small/medium/large-v3

## Audio Processing

n8n has no native audio processing nodes. The custom n8n image includes ffmpeg, which you invoke via the **Execute Command** node:

```bash
# Split into 15-minute chunks
ffmpeg -i /data/audio/input.mp3 -f segment -segment_time 900 -c copy /data/audio/chunks/chunk_%03d.mp3

# Optimize for transcription
ffmpeg -i /data/audio/input.mp3 -ac 1 -ar 16000 -b:a 64k /data/audio/optimized.mp3
```

Optional: Community nodes like `n8n-nodes-ffmpeg` or `n8n-nodes-mediafx` provide UI wrappers but require separate installation.

Long files (>60 min) should be chunked for parallel transcription. See `docs/audio-processing-guide.md` for detailed patterns.

## Service URLs

| Service | URL | Notes |
|---------|-----|-------|
| n8n | http://localhost:5678 | Workflow automation |
| whisper | http://localhost:9000 | OpenAI-compatible `/v1/audio/transcriptions` |
| n8n-mcp | http://localhost:8042 | Dev only, requires auth header |
| postgres-mcp | http://localhost:8700/sse | Dev only, SSE transport |
| pgAdmin | http://localhost:5050 | Dev only |

## Data Directories

The `data/` folder is an Obsidian vault for viewing processed notes:

- `data/voice-memos/`: Drop zone for audio files (workflow input)
- `data/voice-memos/webhook/`: Webhook uploads land here
- `data/audio-archive/`: Processed originals moved here after transcription
- `data/notes/`: Output markdown notes
- `workflows/`: n8n workflow exports (mounted read-only)

Benchmark test files are in `scripts/test_audio/` (not mounted to containers).

## LM Studio Configuration

If using LM Studio as the LLM backend, enable these settings in the **Developer** tab for reliable n8n integration:

| Setting | Value | Why |
|---------|-------|-----|
| Just-in-Time Model Loading | ON | Loads model on first request (no manual loading) |
| Auto unload unused JIT loaded models | ON | Frees memory when idle |
| Max idle TTL | 5 minutes | Balance between responsiveness and memory |
| Only Keep Last JIT Loaded Model | ON | Prevents memory issues with multiple models |

This ensures the model loads automatically when n8n sends a request and unloads when idle, preventing memory exhaustion.

**n8n Credential Setup:**
- Name: `LM Studio Local`
- API Key: `lm-studio` (any non-empty string)
- Base URL: `http://host.docker.internal:1234/v1` (macOS/Windows) or your machine's IP (Linux)
- n8n's Alpine container doesn't have `find -printf`, use `stat -c %Y` instead
