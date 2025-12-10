# Voice Memo Workflow Demo Guide

Quick setup guide for demoing the LIMA voice memo workflow (v0.2.0).

## Prerequisites Checklist

- [ ] Docker & Docker Compose installed
- [ ] LM Studio installed ([download](https://lmstudio.ai/))
- [ ] A model downloaded in LM Studio (e.g., `Qwen2.5-7B-Instruct`)
- [ ] Test audio file (1-5 minutes, mp3/m4a/wav/flac)

## Quick Setup (5 minutes)

### 1. Start LIMA Services

```bash
cd lima
make up
```

Wait for services to be healthy:
```bash
make status
# All services should show "healthy" or "running"
```

### 2. Configure LM Studio

Open LM Studio and configure these settings in the **Developer** tab:

| Setting | Value |
|---------|-------|
| Just-in-Time Model (JIT) Loading | ✅ ON |
| Auto unload unused JIT loaded models | ✅ ON |
| Max idle TTL | 5 minutes |
| Only Keep Last JIT Loaded Model | ✅ ON |

Then: **Start Server** (port 1234)

> **Why these settings?** JIT loading means you don't need to manually load a model - it loads on first request from n8n and unloads when idle to save memory.

### 3. Set Up n8n Credential (first time only)

1. Open http://localhost:5678
2. Go to **Settings → Credentials → Add Credential**
3. Search for **OpenAI API**
4. Configure:
   - **Name:** `LM Studio Local`
   - **API Key:** `lm-studio`
   - **Base URL:** `http://host.docker.internal:1234/v1`

   > **Linux users:** Use your machine's IP instead of `host.docker.internal`

### 4. Import & Activate Workflow

1. In n8n: **Workflows → Import from File**
2. Select `workflows/voice-memo-v0.2.0.json`
3. Click the workflow's **LM Studio Model** node → verify credential is selected
4. **Activate** the workflow (toggle in top-right)

### 5. Create Data Directories

```bash
mkdir -p data/voice-memos/webhook data/notes data/audio-archive
chmod 777 data/voice-memos data/voice-memos/webhook data/notes data/audio-archive
```

## Demo Options

### Option A: File Drop (simplest)

```bash
# Copy audio file to watch folder
cp ~/Desktop/my-voice-memo.mp3 data/voice-memos/

# Wait ~30 seconds, then check output
ls -la data/notes/
cat data/notes/$(ls -t data/notes/ | head -1)
```

### Option B: Webhook (remote access)

```bash
# Send via curl
curl -X POST -F "file=@my-voice-memo.mp3" http://localhost:5678/webhook/memo

# Response:
# {"status":"ok","note":"2025-01-15-meeting-notes-a1b2c3d4.md","title":"Meeting Notes"}
```

### Option C: From Mobile (via Tailscale)

1. Ensure Tailscale is running on both devices
2. Create an automation to POST audio to the webhook:
   - **iOS:** Shortcuts app → Record Audio → Get Contents of URL
   - **Android:** HTTP Shortcuts or Tasker
   - URL: `http://<tailscale-hostname>:5678/webhook/memo`
   - Method: POST, Body: File

## What to Show in Demo

1. **Input:** Voice memo file (play a few seconds)
2. **Processing:** n8n execution view showing the workflow running
3. **Output:** Generated markdown note with:
   - Title and summary extracted by LLM
   - Key points as bullet list
   - Action items as checkboxes
   - Collapsible raw transcript
4. **Obsidian:** Open `data/` folder as vault, show note with working tags and checkboxes

## Troubleshooting

### "Connection refused" to LM Studio
- Ensure LM Studio server is running (Developer → Start Server)
- Check port is 1234
- Linux: Use actual IP, not `host.docker.internal`

### Workflow doesn't trigger on file drop
- Check workflow is **Active** (green toggle)
- Verify file is in `data/voice-memos/` (not a subdirectory)
- Check n8n logs: `make logs`

### LLM returns empty/bad JSON
- Model may need more time to load (first request after JIT load)
- The workflow has `retryOnFail: true` with 250ms delay
- Try a different model if issues persist

### Whisper transcription fails
- First request downloads the model (~300MB), allow 5 minutes
- Check whisper container: `docker logs lima-whisper-1`

## Clean Up After Demo

```bash
# Remove generated files
rm -rf data/notes/* data/audio-archive/*

# Stop services
make down
```

## Sample Test Files

If you need test audio, record a quick voice memo on your phone or use:
```bash
# Generate a 10-second test tone (for testing pipeline, not LLM quality)
ffmpeg -f lavfi -i "sine=frequency=440:duration=10" -ac 1 test-tone.mp3
```

For meaningful LLM output, use an actual voice recording with speech content.
