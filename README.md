# LIMA - Local Intelligence Meeting Assistant

> Local-first, privacy-focused voice memo to knowledge workflow

**What is LIMA?** A complete voice-to-knowledge pipeline that runs entirely on your machine. Record voice memos, get AI-powered transcription and insight extraction, all without sending data to the cloud.

**Why local-first?**
- **Privacy**: Your voice recordings and notes never leave your machine
- **No subscriptions**: No API costs, no monthly fees
- **Works offline**: Once set up, no internet required
- **You own your data**: Plain markdown files, open formats

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Local LLM server (one of):
  - [LM Studio](https://lmstudio.ai/) (recommended) - GUI app with OpenAI-compatible API
  - [Ollama](https://ollama.ai/) - CLI-based, simpler setup

> **Note**: You *could* use OpenAI, Anthropic, or other cloud providers instead of a local LLM, but this demo focuses on the **local-first** approach where everything runs on your hardware.

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

The Voice Memo workflow uses a local LLM for extracting insights from transcripts. This is where LIMA's **local-first** philosophy shines - your transcripts are processed by an AI running on your own hardware.

> **Cloud alternative**: If you prefer, you can use OpenAI, Anthropic, or other providers by creating their respective credentials in n8n. But for true privacy, we recommend local inference.

---

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

---

**Option B: Ollama**

1. Install Ollama: `curl -fsSL https://ollama.com/install.sh | sh`
2. Pull a model: `ollama pull llama3.2`
3. Ollama runs automatically on `http://localhost:11434`

---

### 5. Create LLM Credential in n8n

This step connects n8n to your local LLM server. The credential uses the "OpenAI API" type because LM Studio and Ollama both provide OpenAI-compatible APIs.

1. In n8n, go to **Settings → Credentials → Add Credential**
2. Search for and select **OpenAI API**
3. Fill in the fields:

   | Field | LM Studio | Ollama |
   |-------|-----------|--------|
   | **Credential Name** | `LM Studio Local` | `Ollama Local` |
   | **API Key** | `lm-studio` (any non-empty string) | `ollama` (any non-empty string) |
   | **Base URL** | `http://host.docker.internal:1234/v1` | `http://host.docker.internal:11434/v1` |

4. Click **Save**

> **Platform notes:**
> - **macOS/Windows**: Use `host.docker.internal` to reach services running on your host machine
> - **Linux**: Use your machine's IP address instead (e.g., `http://192.168.1.100:1234/v1`) - `host.docker.internal` doesn't work on Linux by default. Find your IP with `hostname -I | awk '{print $1}'`

### 6. Create Data Directories

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

### 7. Import Workflows

LIMA requires two workflows to be imported into n8n:

| Workflow | File | Purpose |
|----------|------|---------|
| **Voice Memo Processor** | `workflows/voice-memo-v0.2.0.json` | Transcribes audio, extracts insights, saves notes |
| **Voice Recorder UI** | `workflows/voice-recorder-ui.json` | Serves the browser-based recording interface |

**Method A: Import from File**

1. In n8n, click the **+** button or go to **Workflows**
2. Click **Import from File**
3. Select `workflows/voice-memo-v0.2.0.json` from this repository
4. Repeat for `workflows/voice-recorder-ui.json`

**Method B: Copy-Paste JSON**

1. Open the workflow JSON file in a text editor
2. Copy the entire JSON contents
3. In n8n, create a new workflow
4. Press `Ctrl+V` / `Cmd+V` to paste - n8n will import the nodes
5. Repeat for the second workflow

---

**After importing Voice Memo Processor, configure the LLM credential:**

1. Find the **LM Studio Model** node (or similar OpenAI Chat node) in the workflow
2. Click on it to open the settings
3. In the **Credential to connect with** dropdown, select the credential you created in Step 5 (e.g., `LM Studio Local` or `Ollama Local`)
4. Click outside the node to save

**Activate both workflows:**

1. Toggle the **Active** switch in the top-right corner of each workflow
2. Voice Memo Processor: Now listening for files in `data/voice-memos/` and webhook requests at `/webhook/memo`
3. Voice Recorder UI: Now serving the recorder interface at `/webhook/recorder`

See [docs/PRD-voice-memo-workflow.md](docs/PRD-voice-memo-workflow.md) for full architecture details, or [docs/demo-voice-memo.md](docs/demo-voice-memo.md) for a quick demo guide.

### 8. Test the Workflow

**Option A: File Drop**

Simply copy or move audio files to the watch folder:

```bash
cp your-recording.mp3 data/voice-memos/
# Workflow triggers automatically, check output:
ls -la data/notes/
```

**Option B: Webhook (curl)**

Send an audio file via HTTP:

```bash
curl -X POST -F "file=@your-recording.mp3" http://localhost:5678/webhook/memo

# Expected response:
# {"status":"ok","note":"2025-12-10-your-memo-title-abc123de.md","title":"Your Memo Title"}
```

**Option C: Voice Recorder UI (recommended)**

LIMA includes a browser-based voice recorder that lets you record and process memos without any file management:

1. Open http://localhost:8888/webhook/recorder
2. Click the microphone button to start recording
3. Click again to stop and upload
4. Watch the processing status
5. See your generated note!

> **Why port 8888?** The Voice Recorder uses the browser's microphone API, which requires a "secure context". We use Caddy as a reverse proxy on port 8888 to strip n8n's restrictive security headers that would otherwise block microphone access.

---

Check the output:
```bash
ls -la data/notes/
cat data/notes/2025-12-10-*.md
```

**What the workflow does:**
1. Transcribes audio via local Whisper (speech-to-text)
2. Extracts title, summary, key points, action items via local LLM
3. Generates Obsidian-compatible markdown with YAML frontmatter
4. Saves to `data/notes/` with hash-based filename (idempotent - same audio = same file)
5. Archives original audio to `data/audio-archive/` (linked from the note)

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

**1. Install Tailscale on your LIMA server:**

```bash
# Linux (Fedora/Ubuntu/Debian)
curl -fsSL https://tailscale.com/install.sh | sh

# macOS
brew install tailscale

# Start and authenticate (sets up operator permissions)
sudo tailscale up --operator=$USER
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

**4. Serve the Voice Recorder with HTTPS:**

The Voice Recorder requires HTTPS for microphone access. Use Tailscale to serve it securely:

```bash
tailscale serve --bg --https 443 http://localhost:8888
```

This makes the recorder accessible at:
```
https://<your-machine-name>.your-tailnet.ts.net/webhook/recorder
```

**Certificate Transparency Warning:**

On first access, your phone browser may show a "Certificate Transparency" warning. This is expected with `tailscale serve` (tailnet-only certificates). You can safely bypass it:

- **Android Chrome/Samsung Internet:** Tap "Advanced" → "Proceed to... (unsafe)"
- **iOS Safari:** Tap "Show Details" → "visit this website"

**Why this is safe:**
- Tailscale encrypts all traffic with WireGuard end-to-end
- The certificate is valid, just not CT-logged (Tailscale limitation)
- Only devices on your tailnet can access this URL

**Make it persistent (auto-start on boot):**

On boot, tailscaled may start before the network is fully ready, leaving it disconnected. We use two mechanisms to handle this:

1. **NetworkManager dispatcher** - Runs `tailscale up` when real connectivity is established
2. **Systemd service with retry** - Configures serve, retrying until tailscale is connected

**Step 1: Create the NetworkManager dispatcher:**

```bash
sudo tee /etc/NetworkManager/dispatcher.d/99-tailscale <<'EOF'
#!/bin/bash
# Connect tailscale when network connectivity is established

if [ "$2" = "connectivity-change" ] && [ "$CONNECTIVITY_STATE" = "FULL" ]; then
    # Only if tailscale is disconnected
    if ! tailscale status >/dev/null 2>&1; then
        logger -t tailscale-dispatcher "Network up, connecting tailscale..."
        tailscale up
    fi
fi
EOF

sudo chmod +x /etc/NetworkManager/dispatcher.d/99-tailscale
```

**Step 2: Create the systemd service:**

```bash
sudo tee /etc/systemd/system/tailscale-serve-lima.service > /dev/null <<EOF
[Unit]
Description=Tailscale Serve for LIMA Voice Recorder
After=network-online.target tailscaled.service
Wants=network-online.target
Requires=tailscaled.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/tailscale serve --bg --https 443 http://localhost:8888
ExecStop=/usr/bin/tailscale serve --https=443 off
User=root
# Retry if tailscale not ready yet
Restart=on-failure
RestartSec=5
StartLimitBurst=10

[Install]
WantedBy=multi-user.target
EOF
```

**Step 3: Enable and start:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable tailscale-serve-lima.service
sudo systemctl start tailscale-serve-lima.service
```

**How it works on boot:**
1. `tailscaled` starts (may be in NoState if network isn't ready)
2. NetworkManager detects full connectivity → dispatcher runs `tailscale up`
3. `tailscale-serve-lima.service` retries every 5s until tailscale connects, then configures serve

**Manual mode:** Alternatively, just use `--bg` and re-run the command after reboots:
```bash
# Start serve
tailscale serve --bg --https 443 http://localhost:8888

# Stop serve
tailscale serve reset                    # Remove all serve configs
# or
tailscale serve --https=443 off          # Stop specific port
```

**Troubleshooting & Status Commands:**

```bash
# Check Tailscale network and connected devices
tailscale status

# Check current serve configuration
tailscale serve status

# Check tailscaled daemon status
systemctl status tailscaled.service

# Check serve service status
systemctl status tailscale-serve-lima.service

# Check if dispatcher ran on boot
journalctl -b 0 | grep tailscale-dispatcher

# Test connectivity from phone
tailscale ping <your-phone-hostname>

# View serve logs (if issues)
journalctl -u tailscaled.service -f
```

**Expected `serve status` output:**
```
https://<your-machine>.tail63f25b.ts.net (tailnet only)
|-- / proxy http://localhost:8888
```

### Key Expiry

**Important:** Tailscale machine keys expire after **180 days** (6 months) by default.

**Check your key expiry:**
```bash
tailscale status --json | grep KeyExpiry | head -1
```

**What happens when it expires:**
- ❌ Tailscale can't connect to your tailnet
- ❌ The serve service fails (can't configure proxy)
- ✅ Boot continues normally (no delays or hangs)
- **Fix:** Re-authenticate with `tailscale up`

**Disable expiry for personal devices (recommended):**
1. Visit https://login.tailscale.com/admin/machines
2. Find your machine in the list
3. Click **⋯** menu → **Disable key expiry**
4. Confirm

This makes authentication permanent - ideal for personal servers you control.

**5. Access LIMA remotely:**
```
https://<tailscale-hostname>.your-tailnet.ts.net/                  # n8n UI
https://<tailscale-hostname>.your-tailnet.ts.net/webhook/recorder  # Voice Recorder
https://<tailscale-hostname>.your-tailnet.ts.net/webhook/memo      # Voice memo webhook
```

All traffic goes through Tailscale (HTTPS) → Caddy → n8n, so no port numbers needed.

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
| **Voice Recorder** | http://localhost:8888/webhook/recorder | Browser-based voice recording UI |
| n8n | http://localhost:5678 | Workflow automation |
| Caddy | http://localhost:8888 | Reverse proxy (strips CSP for mic access) |
| Whisper | http://localhost:9000 | Speech-to-text API |
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
├── Caddyfile               # Caddy reverse proxy config
├── .env.example            # Environment template
├── init-data.sh            # PostgreSQL initialization
├── Makefile                # Convenience commands
├── static/                 # Static assets served by n8n
│   └── recorder.html       # Voice Recorder UI
├── data/                   # Obsidian vault (open this folder in Obsidian)
│   ├── voice-memos/        # Drop audio files here (auto-processed)
│   │   └── webhook/        # Webhook uploads (not re-watched)
│   ├── audio-archive/      # Processed originals (linked from notes)
│   └── notes/              # Markdown notes (output)
├── services/
│   └── whisper-server/     # Native GPU whisper servers (optional)
└── workflows/              # n8n workflow exports
```

## Stack

- **PostgreSQL 17** with pgvector extension
- **n8n** workflow automation (custom image with ffmpeg)
- **Caddy** reverse proxy (enables microphone access in Voice Recorder)
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
