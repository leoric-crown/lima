# LIMA - Local Intelligence Meeting Assistant

> Local-first, privacy-focused meeting intelligence tool

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Local LLM server (one of):
  - [LM Studio](https://lmstudio.ai/) (recommended) - GUI app with OpenAI-compatible API
  - [Ollama](https://ollama.ai/) - CLI-based, simpler setup

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

### 4. Configure Local LLM

The Voice Memo workflow uses a local LLM for extracting insights from transcripts.

**Option A: LM Studio (recommended)**

1. Download and install [LM Studio](https://lmstudio.ai/)
2. Download a model (e.g., `Qwen2.5-7B-Instruct` or similar)
3. Configure recommended settings in **Developer** tab:

   | Setting | Value | Why |
   |---------|-------|-----|
   | Just-in-Time Model Loading | ON | Loads model on first request |
   | Auto unload unused JIT loaded models | ON | Frees memory when idle |
   | Max idle TTL | 5 minutes | Balance responsiveness vs memory |
   | Only Keep Last JIT Loaded Model | ON | Prevents memory issues |

4. Start the local server: **Developer → Start Server** (runs on `http://localhost:1234`)
5. In n8n, create an OpenAI API credential:
   - **Settings → Credentials → Add Credential → OpenAI API**
   - Name: `LM Studio Local`
   - API Key: `lm-studio` (any non-empty string works)
   - Base URL: `http://host.docker.internal:1234/v1`

   > **macOS/Windows**: Use `host.docker.internal` to reach host services
   > **Linux**: Use your machine's IP address (e.g., `http://192.168.1.100:1234/v1`) - `host.docker.internal` doesn't work on Linux by default

**Option B: Ollama**

1. Install Ollama: `curl -fsSL https://ollama.com/install.sh | sh`
2. Pull a model: `ollama pull llama3.2`
3. Ollama runs automatically on `http://localhost:11434`
4. In n8n, create an OpenAI API credential:
   - Name: `Ollama Local`
   - API Key: `ollama`
   - Base URL: `http://host.docker.internal:11434/v1` (or your IP on Linux)

### 5. Create Data Directories

The workflow requires these directories to exist and be writable:

```bash
# Create directory structure
mkdir -p data/voice-memos/webhook data/notes data/audio-archive

# Make writable (choose one):
chmod 777 data/voice-memos data/voice-memos/webhook data/notes data/audio-archive
# Or change ownership to match your user
```

- `data/voice-memos/` - Drop audio files here for automatic processing
- `data/voice-memos/webhook/` - Webhook uploads are saved here (to avoid re-triggering)
- `data/notes/` - Generated markdown notes output
- `data/audio-archive/` - Original audio files are moved here after processing (linked from notes)

### 6. Import Voice Memo Workflow

Import the pre-built workflow from `workflows/voice-memo-v0.2.0.json`:

1. In n8n, go to **Workflows → Import from File**
2. Select `workflows/voice-memo-v0.2.0.json`
3. Update the LLM credential if needed (click the **LM Studio Model** node → select your credential)
4. **Activate** the workflow (toggle in top-right)

See [docs/PRD-voice-memo-workflow.md](docs/PRD-voice-memo-workflow.md) for full architecture details, or [docs/demo-voice-memo.md](docs/demo-voice-memo.md) for a quick demo guide.

### 7. Test the Workflow

**Option A: File Drop (recommended)**

Simply copy or move audio files to the watch folder:

```bash
cp your-recording.mp3 data/voice-memos/
# Workflow triggers automatically, check output:
ls -la data/notes/
```

**Option B: Webhook**

Send an audio file via HTTP:

```bash
curl -X POST -F "file=@data/audio/test-sample.flac" http://localhost:5678/webhook/memo

# Expected response:
# {"status":"ok","note":"2025-12-10-your-memo-title-abc123de.md","title":"Your Memo Title"}
```

Check the output:
```bash
ls -la data/notes/
cat data/notes/2025-12-10-*.md
```

The workflow:
1. Transcribes audio via Whisper
2. Extracts title, summary, key points, action items via LLM
3. Generates Obsidian-compatible markdown with YAML frontmatter
4. Saves to `data/notes/` with hash-based filename (idempotent - same audio = same file)

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

## Remote Access with Tailscale

Tailscale lets you access LIMA from your phone or laptop anywhere, without exposing ports to the internet.

### Why Tailscale?

- **No port forwarding** - Works through NAT and firewalls automatically
- **No dynamic DNS** - Stable hostname for your machine
- **Encrypted** - WireGuard encryption built-in
- **Private** - Only your devices can access your tailnet

### Setup

**1. Install on your Mac (LIMA server):**
```bash
brew install tailscale
sudo tailscaled &      # Start the daemon
tailscale up           # Authenticate
```

Follow the browser link to authenticate.

**2. Install on your phone:**
- iOS: App Store → "Tailscale"
- Android: Play Store → "Tailscale"
- Sign in with the same account

**3. Verify connection:**
```bash
tailscale status
# Shows all devices on your tailnet with their IPs and hostnames
```

**4. Access LIMA remotely:**
```
http://<tailscale-hostname>:5678          # n8n UI
http://<tailscale-hostname>:5678/webhook/memo  # Voice memo webhook
```

### iOS Shortcut Example

Create a Shortcut to send voice memos to LIMA:
1. **Record Audio** action
2. **Get Contents of URL** action:
   - URL: `http://<tailscale-hostname>:5678/webhook/memo`
   - Method: POST
   - Request Body: File (the audio)
3. **Show Notification** with result

### Cost

The free tier (100 devices, 3 users) is plenty for personal use.

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
├── data/                   # Obsidian vault (open this folder in Obsidian)
│   ├── voice-memos/        # Drop audio files here (auto-processed)
│   │   └── webhook/        # Webhook uploads (not re-watched)
│   ├── audio-archive/      # Processed originals (linked from notes)
│   ├── audio/              # Meeting recordings (manual input)
│   ├── transcripts/        # Transcriptions (output)
│   └── notes/              # Markdown notes (output)
├── services/
│   └── whisper-server/     # Native GPU whisper servers (optional)
└── workflows/              # n8n workflow exports
```

## Stack

- **PostgreSQL 17** with pgvector extension
- **n8n** workflow automation (custom image with ffmpeg)
- **Whisper** (speaches) local speech-to-text via Docker
  - Alternative: Native GPU servers ([see docs](services/whisper-server/README.md)) for macOS Metal / NVIDIA CUDA
- **n8n-mcp** AI assistant for workflow development (dev)
- **LM Studio** or **Ollama** - local LLM inference (runs on host, configure in n8n)

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
