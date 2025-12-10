# LIMA - Local Intelligence Meeting Assistant

> Local-first, privacy-focused meeting intelligence tool

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Ollama (installed on host for local LLM inference)

### 1. Setup Environment

```bash
cd lima
cp .env.example .env
```

Edit `.env` and set secure passwords:

```bash
# Required - generate secure values:
POSTGRES_PASSWORD=<openssl rand -base64 32>
N8N_DB_PASSWORD=<openssl rand -base64 32>
N8N_ENCRYPTION_KEY=<openssl rand -hex 32>
MCP_AUTH_TOKEN=<openssl rand -hex 32>
```

### 2. Start Services

**Production** (postgres + n8n):
```bash
make up
```

**Development** (adds n8n-mcp for AI-assisted workflow development):
```bash
make dev-up
```

### 3. Configure n8n

1. Open http://localhost:5678
2. Create your admin account
3. **Unlock free paid features**:
   - Go to **Settings → Usage and plan**
   - Click "Unlock selected paid features for free"
   - Enter your email to receive a free lifetime license key
   - Check your inbox for the license email from n8n
   - Click the activation button in the email (or copy the license key and paste it in the UI)
   - Once successful, you should see "You're on the Community Edition"
   - Features unlocked: workflow history, advanced debugging, execution search, folders
4. Generate API key: **Settings → API → Create API Key**
5. Add key to `.env`:
   ```
   N8N_API_KEY=your_generated_key
   ```
6. Restart n8n-mcp to enable workflow management:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml restart n8n-mcp
   ```

### 4. Download Whisper Model

The whisper service requires a model to be downloaded before first use:

```bash
curl -X POST "http://localhost:9000/v1/models/Systran/faster-whisper-base"
```

Available models (smaller = faster, larger = more accurate):
- `Systran/faster-whisper-tiny` (~75MB)
- `Systran/faster-whisper-base` (~145MB) - recommended
- `Systran/faster-whisper-small` (~488MB)
- `Systran/faster-whisper-medium` (~1.5GB)
- `Systran/faster-whisper-large-v3` (~3GB)

### Alternative: Native GPU Whisper Servers

For local development, LIMA provides platform-specific GPU-accelerated servers:
- **macOS**: Lightning Whisper MLX (Apple Silicon Metal)
- **Linux/Windows**: faster-whisper with CUDA (NVIDIA GPU)

**Quick start:**
```bash
cd services/whisper-server
uv sync
./run_server.sh --port 9002  # macOS/Linux
```

**Performance:** Docker Speaches (above) is recommended for production. Native servers are best for:
- Linux with NVIDIA GPU: ~71x real-time transcription
- macOS development/testing (similar to Docker speed)

See [services/whisper-server/README.md](services/whisper-server/README.md) for detailed setup and Windows support.

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| n8n | http://localhost:5678 | Workflow automation |
| whisper | http://localhost:9000 | Speech-to-text API |
| n8n-mcp | http://localhost:8042 | AI workflow assistant (dev) |
| postgres-mcp | http://localhost:8700 | Database MCP server (dev) |
| pgAdmin | http://localhost:5050 | Database UI (dev) |

## Common Commands

```bash
make help          # Show all commands
make up            # Start production stack
make dev-up        # Start with dev tools (n8n-mcp)
make down          # Stop all services
make logs          # Follow logs
make status        # Check service health
make db-shell      # Access PostgreSQL shell
make db-backup     # Backup database
```

## Project Structure

```
lima/
├── docker-compose.yml      # Production stack
├── docker-compose.dev.yml  # Dev overlay (n8n-mcp, pgAdmin)
├── .env.example            # Environment template
├── init-data.sh            # PostgreSQL initialization
├── Makefile                # Convenience commands
├── data/
│   ├── audio/              # Meeting recordings (input)
│   ├── transcripts/        # Transcriptions (output)
│   └── notes/              # Markdown notes (output)
├── services/
│   └── whisper-server/        # Native GPU whisper servers (optional)
└── workflows/              # n8n workflow exports
```

## Stack

- **PostgreSQL 17** with pgvector extension
- **n8n** workflow automation (custom image with ffmpeg)
- **Whisper** (speaches) local speech-to-text via Docker
  - Alternative: Native GPU servers ([see docs](services/whisper-server/README.md)) for macOS Metal / NVIDIA CUDA
- **n8n-mcp** AI assistant for workflow development (dev)
- **Ollama/LMStudio** local LLM inference (runs on host, configure in n8n)

## Audio Processing

LIMA uses a custom n8n Docker image that includes **ffmpeg** for audio file manipulation.

### Why ffmpeg?

n8n has no native audio processing nodes. ffmpeg enables:
- Splitting long recordings into chunks for parallel transcription
- Converting between audio formats (FLAC, WAV, MP3, etc.)
- Extracting audio from video files
- Optimizing audio for transcription (mono, 16kHz)

### Custom n8n Image

The custom image is defined in `n8n.Dockerfile`:

```dockerfile
FROM docker.n8n.io/n8nio/n8n:latest
USER root
RUN apk add --no-cache ffmpeg
USER node
```

### Building the Image

The image builds automatically on first `docker compose up`. To rebuild after changes:

```bash
docker compose build n8n
docker compose up -d n8n
```

### Using ffmpeg in Workflows

Use the **Execute Command** node in n8n:

```bash
# Split audio into 15-minute chunks
ffmpeg -i /data/audio/meeting.mp3 -f segment -segment_time 900 -c copy /data/audio/chunks/chunk_%03d.mp3

# Convert FLAC to WAV
ffmpeg -i /data/audio/recording.flac /data/audio/recording.wav

# Optimize for transcription (mono, 16kHz, low bitrate)
ffmpeg -i /data/audio/input.mp3 -ac 1 -ar 16000 -b:a 64k /data/audio/optimized.mp3
```

### Long File Handling

For recordings over 1 hour, LIMA recommends chunking into 10-15 minute segments:
- Enables parallel transcription
- Prevents timeouts
- Keeps LLM context windows manageable

See `docs/audio-processing-guide.md` for detailed architecture and configuration.
