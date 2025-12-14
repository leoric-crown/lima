# LIMA - Local Intelligent Memo Assistant

> Local-first, privacy-focused voice memo to knowledge workflow

**What is LIMA?** A voice-to-knowledge pipeline that runs entirely on your machine. Record voice memos, get AI-powered transcription and insight extraction, all without sending data to the cloud.

**Why local-first?**
- **Privacy**: Your voice recordings never leave your machine
- **No subscriptions**: No API costs, no monthly fees
- **Works offline**: Once set up, no internet required
- **You own your data**: Plain markdown files, open formats

---

## Quick Start

### Prerequisites

- **Docker** ([Desktop](https://docker.com) for personal use, [Engine](https://docs.docker.com/engine/install/) for Linux/corporate)
- **Local LLM**: [LM Studio](https://lmstudio.ai/) (recommended) or [Ollama](https://ollama.ai/)
- **uv**: [astral.sh/uv](https://astral.sh/uv/) - Python package manager for LIMA's scripts
- **make**: Usually pre-installed (see [Getting Started](docs/getting-started.md) if missing)

> **Corporate laptops:** Docker Desktop requires a [paid license](https://www.docker.com/pricing/) for larger organizations. See [Getting Started](docs/getting-started.md) for alternatives.

### 1. Clone and Configure

```bash
git clone https://github.com/leoric-crown/lima.git
cd lima
cp .env.example .env
```

Edit `.env` and set secure passwords:
```bash
POSTGRES_PASSWORD=<openssl rand -base64 32>
N8N_DB_PASSWORD=<openssl rand -base64 32>
N8N_ENCRYPTION_KEY=<openssl rand -hex 32>
MCP_AUTH_TOKEN=<openssl rand -hex 32>
```

### 2. Run Setup

```bash
make setup
```

The interactive wizard will:
- Build and start Docker services
- Wait for n8n to be ready
- Guide you through creating an n8n API key
- Configure your LLM (LM Studio or Ollama)
- Import the Voice Memo workflows

### 3. Activate and Record

1. Start LM Studio (Developer → Start Server) or ensure Ollama is running
2. In n8n (http://localhost:5678), open **Voice Memo Processor (Speaches)** and toggle **Active**
3. Open http://localhost:8888/lima/recorder/
4. Click the microphone, speak, click again to process

**Check your output:**
```bash
cat data/notes/*.md
```

---

## How It Works

```
🎤 Voice Recording
      ↓
🗣️ Transcription (Whisper)
      ↓
🤖 AI Analysis (Local LLM)
      ↓
📝 Markdown Note
```

The workflow:
1. Transcribes audio via local Whisper (speech-to-text)
2. Extracts title, summary, key points, action items via local LLM
3. Generates Obsidian-compatible markdown with YAML frontmatter
4. Saves to `data/notes/` and archives audio to `data/audio-archive/`

---

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| **Voice Recorder** | http://localhost:8888/lima/recorder/ | Browser-based recording |
| n8n | http://localhost:5678 | Workflow editor |
| Whisper | http://localhost:9000 | Transcription API |

---

## Common Commands

```bash
make setup           # Interactive first-time setup
make up              # Start services
make down            # Stop services
make status          # Check health
make seed            # Import workflows (safe to re-run)

docker compose logs -f         # View all logs
docker compose logs n8n -f     # View n8n logs
docker compose logs whisper -f # View Whisper (Speaches) logs

lms log stream --source server # View LM Studio Server logs
```

---

## Documentation

| Guide | Description |
|-------|-------------|
| **[Getting Started](docs/getting-started.md)** | Detailed setup walkthrough |
| [Customizing Your AI](docs/customizing-your-ai.md) | LLM configuration, context windows, prompts |
| [Using on Your Phone](docs/using-lima-on-your-phone.md) | Remote access via Tailscale |
| [Where Is My Data?](docs/where-is-my-data.md) | File locations, Obsidian, backups |
| [Recipes](docs/recipes.md) | Use case examples |
| [Troubleshooting](docs/troubleshooting.md) | Common issues |
| [Audio Processing](docs/audio-processing-guide.md) | Long recordings, ffmpeg |
| [Native Whisper](docs/native-whisper.md) | GPU acceleration |

### For Developers

| Resource | Description |
|----------|-------------|
| [MCP Setup](docs/MCP_SETUP.md) | AI-assisted workflow development |
| [BACKLOG](BACKLOG.md) | Ideas and future directions |

---

## What's Next?

> **Safe to tinker:** If you break a workflow, rename it (to keep your work) or delete it, then run `make seed` to reimport the defaults. Experiment freely!

The [BACKLOG](BACKLOG.md) is full of ideas waiting to be explored:
- Conversational memory query (ask your notes questions)
- Context-aware routing (auto-categorize memos)
- Multi-speaker diarization
- And more...

---

## Stack

- **PostgreSQL 17** with pgvector
- **n8n** workflow automation (custom image with ffmpeg)
- **Whisper** (Speaches) for transcription
- **Caddy** reverse proxy
- **LM Studio** or **Ollama** for local LLM inference
