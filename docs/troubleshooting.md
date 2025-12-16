# Troubleshooting

Common issues and how to fix them.

## Quick Diagnostics

```bash
# Check all services
make status

# View recent logs
docker compose logs --tail=50

# Follow logs in real-time
docker compose logs -f
lms log stream --source server # View LM Studio Server logs
```

---

## Services Won't Start

### Docker Not Running

**Symptom:** `Cannot connect to the Docker daemon`

**Fix:** Start Docker Desktop (or Docker Engine on Linux).

### Port Already in Use

**Symptom:** `Bind for 0.0.0.0:5678 failed: port is already allocated`

**Fix:** Either stop the conflicting service or change LIMA's port in `.env`:
```bash
N8N_PORT=5679
```

Then restart: `make down && make up`

### Out of Disk Space

**Symptom:** Services crash or fail to start with disk-related errors.

**Fix:**
```bash
# Check disk usage
df -h

# Clean up Docker
docker system prune -a
```

---

## Workflow Doesn't Trigger

### Workflow Not Activated

**Symptom:** Files sit in `data/voice-memos/` without processing.

**Fix:**
1. Open n8n: http://localhost:5678
2. Open Voice Memo Processor workflow
3. Toggle **Inactive → Active** in top right

### File Permissions

**Symptom:** Workflow triggers but can't read/write files.

**Fix (Linux/macOS):**
```bash
chmod -R 755 data/
```

### Wrong File Location

**Symptom:** Files not detected.

**Fix:** Ensure files are in `data/voice-memos/`, not subdirectories (except `webhook/` for uploads).

---

## LLM Errors

### "Connection refused" to LLM

**Symptom:** Workflow fails at the AI node with connection errors.

**Fixes:**
1. **LM Studio:** Ensure server is running (Developer → Start Server)
2. **Ollama:** Check it's running: `ollama list`
3. **Verify URL:** Should be `http://host.docker.internal:1234/v1` (LM Studio) or `:11434/v1` (Ollama)

### "Unexpected end of JSON input" / JSON Parse Errors

**Symptom:** LLM responds but n8n can't parse it, or you see JSON-related errors.

**Possible causes:**
- Model doesn't support tool calling well
- Model outputs malformed JSON (common with `gpt-oss-20b`)
- Harmony parser issue (see below)

**Fixes:**
- Try a different model — we've had success with `mistralai/ministral-3b-instruct` on Linux
- Check model supports function/tool calling
- Experiment! Local LLM compatibility varies by platform and model version. Expect some hitches as you find what works best for your setup

### Harmony 0.3.5 Issue (LM Studio + gpt-oss-20b)

**Symptom:** Tool calling fails with "Unexpected end of content" on Linux/Windows.

**Details:** LM Studio's Harmony 0.3.5 parser has issues with `gpt-oss-20b` on some platforms.

| Platform | Harmony 0.3.4 | Harmony 0.3.5 |
|----------|---------------|---------------|
| macOS    | Works | Works |
| Linux    | Works | Fails |
| Windows  | Works | Fails |

**Fixes:**
- **Linux/macOS:** Pin Harmony to 0.3.4 in LM Studio settings
- **Windows:** Use another model or try Ollama (`ollama run gpt-oss:20b` - make sure to increase the context window)
- **Any platform:** Try a different model (Qwen, Llama)

### Model Not Loading

**Symptom:** Long delays, then timeout or "model not found".

**Fixes:**
1. **LM Studio:** Enable "Just-in-Time Model Loading" in Developer settings
2. **Ollama:** Pull the model first: `ollama pull <model-name>`
3. **Memory:** Model may be too large for your RAM/VRAM

---

## Transcription Fails

### Whisper Container Not Healthy

**Symptom:** Transcription step fails or times out.

**Check:**
```bash
docker compose ps  # Look for whisper service status
curl http://localhost:9000/health  # Or your WHISPER_PORT
```

**Fixes:**
- Restart whisper: `docker compose restart whisper`
- Check logs: `docker compose logs whisper`

### Unsupported Audio Format

**Symptom:** "Invalid audio" or format errors.

**Supported formats:** MP3, WAV, M4A, FLAC, OGG, WebM (audio)

**Fix:** Convert to a supported format:
```bash
ffmpeg -i input.unsupported -acodec libmp3lame output.mp3
```

### File Too Large

**Symptom:** Timeout or memory errors on long recordings.

**Fix:** Chunk the file before processing. See [Audio Processing Guide](audio-processing-guide.md).

---

## Remote Access Issues (Tailscale)

### Tailscale Not Connecting

**Symptom:** `tailscale status` shows disconnected or errors.

**Fixes:**
```bash
# Reconnect
sudo tailscale up

# Check daemon status
systemctl status tailscaled

# View logs
journalctl -u tailscaled -f
```

### Key Expired

**Symptom:** Was working, now can't connect.

**Fix:**
1. Re-authenticate: `sudo tailscale up`
2. Disable expiry in admin console (see [Using LIMA on Your Phone](using-lima-on-your-phone.md))

### Certificate Errors (Not Just CT Warning)

**Symptom:** Browser refuses to connect, not just a bypassable warning.

**Fixes:**
```bash
# Check serve configuration
tailscale serve status

# Reset and reconfigure
tailscale serve reset
tailscale serve --bg --https 443 http://localhost:8888
```

### Can't Access from Phone

**Symptom:** Phone shows "connection refused" or timeout.

**Checklist:**
1. Both devices on same Tailscale account?
2. Tailscale app running on phone?
3. `tailscale serve` configured on server?
4. Correct URL? (should be `https://hostname.tailnet.ts.net/...`)

---

## Database Issues

### Lost Encryption Key

**Symptom:** n8n starts but credentials don't work.

**Bad news:** If you lost `N8N_ENCRYPTION_KEY`, encrypted credentials are unrecoverable.

**Fix:**
1. Delete the n8n data: `docker volume rm lima_n8n_data` (or similar)
2. Generate new encryption key
3. Restart and reconfigure credentials manually

**Prevention:** Back up your `.env` file securely.

### Database Connection Failed

**Symptom:** n8n can't connect to PostgreSQL.

**Fixes:**
```bash
# Check postgres is running
docker compose ps postgres

# Check logs
docker compose logs postgres

# Verify credentials match .env
```

---

## Getting More Help

If these solutions don't work:

1. **Check logs:** `docker compose logs` often reveals the root cause
2. **Search issues:** [LIMA GitHub Issues](https://github.com/leoric-crown/lima/issues)
3. **n8n community:** [community.n8n.io](https://community.n8n.io/) for workflow-specific questions
4. **LM Studio Discord:** For model and inference issues

---

## Next Steps

- [Getting Started](getting-started.md) - Verify your setup
- [Customizing Your AI](customizing-your-ai.md) - LLM configuration
- [Where Is My Data?](where-is-my-data.md) - Backup and recovery
