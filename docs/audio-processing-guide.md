# LIMA Audio Processing Guide

This document covers how LIMA handles audio files, including long recordings (1-4+ hours), and the recommended architecture for reliable transcription workflows.

---

## Why ffmpeg?

n8n has no native audio processing nodes. To handle audio files, LIMA uses a **custom n8n Docker image** that includes ffmpeg.

**What ffmpeg enables:**
- Splitting long recordings into chunks for parallel transcription
- Converting between audio formats (FLAC, WAV, MP3, etc.)
- Extracting audio from video files
- Optimizing audio for transcription (mono, 16kHz)

### Custom n8n Image

The image is defined in `n8n.Dockerfile`:

```dockerfile
FROM docker.n8n.io/n8nio/n8n:1.123.5
USER root
RUN apk add --no-cache ffmpeg
USER node
```

### Building the Image

The image builds automatically on first `docker compose up`. To rebuild after Dockerfile changes:

```bash
docker compose build n8n
docker compose up -d n8n
```

### Using ffmpeg in Workflows

Use the **Execute Command** node in n8n to run ffmpeg:

```bash
# Optimize for transcription (mono, 16kHz, low bitrate)
ffmpeg -i /data/audio/input.mp3 -ac 1 -ar 16000 -b:a 64k /data/audio/optimized.mp3

# Extract audio from video
ffmpeg -i /data/audio/meeting.mp4 -vn -acodec libmp3lame -q:a 2 /data/audio/meeting.mp3
```

---

## Table of Contents

1. [Speaches/Faster-Whisper Capabilities](#speachesfaster-whisper-capabilities)
2. [Processing Constraints](#processing-constraints)
3. [Chunking Strategy](#chunking-strategy)
4. [n8n Workflow Architecture](#n8n-workflow-architecture)
5. [Configuration Recommendations](#configuration-recommendations)
6. [Troubleshooting](#troubleshooting)

---

## Speaches/Faster-Whisper Capabilities

### Built-in Features

LIMA uses [Speaches](https://github.com/speaches-ai/speaches), an OpenAI-compatible API wrapper for faster-whisper.

**Key capabilities:**

| Feature | Description |
|---------|-------------|
| **30-second chunking** | Whisper processes audio in 30-second windows internally |
| **VAD filtering** | Voice Activity Detection skips silent portions automatically |
| **Streaming output (SSE)** | Results sent progressively as transcription proceeds |
| **int8 quantization** | Reduces memory usage by ~40% with minimal accuracy loss |

### Memory Requirements

Memory does **NOT** scale linearly with file duration because processing happens in 30-second chunks:

| Model | GPU (VRAM) | CPU (RAM) |
|-------|------------|-----------|
| faster-whisper fp16 | ~4.7 GB | ~4 GB |
| faster-whisper int8 | ~3.1 GB | ~3 GB |

A 4-hour file uses roughly the same memory as a 5-minute file.

### Processing Time Estimates

| Hardware | Speed | 4-hour file |
|----------|-------|-------------|
| GPU (RTX 3070+) | ~4x real-time | ~1 hour |
| CPU (modern Intel/AMD) | ~1-2x real-time | 2-4 hours |

---

## Processing Constraints

### No Hard Limits in Speaches

Unlike OpenAI's Whisper API (25 MB limit), self-hosted Speaches has:
- No documented maximum file size
- No documented maximum duration
- Memory footprint remains stable for long files

### Practical Constraints

| Constraint | Impact | Mitigation |
|------------|--------|------------|
| **Processing time** | Long files take hours on CPU | Use GPU or chunk for parallelism |
| **n8n HTTP timeouts** | Default 5-10 min timeout | Increase timeout or use async pattern |
| **LLM context window** | 4-hour transcript = 40-60K words | Chunk transcript for extraction |
| **Memory leaks** | Reported with 5+ hour files | Monitor memory; restart container if needed |

### Known Issues

1. **Issue #59**: Files over 20 seconds could fail with empty language detection
   - **Fix**: Set `DEFAULT_LANGUAGE=en` in environment

2. **Issue #249**: Memory gradually grows on very long files (5+ hours)
   - **Mitigation**: Monitor container memory; consider pre-chunking

---

## Chunking Strategy

### When to Chunk

| File Duration | Recommendation |
|---------------|----------------|
| < 15 minutes | Direct transcription (no chunking) |
| 15-60 minutes | Optional chunking for parallelism |
| > 60 minutes | Recommended chunking |
| > 2 hours | Required chunking for reliability |

### Optimal Chunk Size

**Recommendation: 10-15 minute chunks**

| Chunk Size | Pros | Cons |
|------------|------|------|
| 30 seconds | Fast parallel processing | Context loss at boundaries |
| 2-5 minutes | Good parallelism | Some context loss |
| **10-15 minutes** | Best accuracy/speed balance | Moderate parallelism |
| 30+ minutes | Maximum context | Slow, less parallel benefit |

### Audio Splitting with ffmpeg

```bash
# Split into 15-minute (900 second) chunks
ffmpeg -i input.mp3 -f segment -segment_time 900 -c copy chunk_%03d.mp3

# Output: chunk_000.mp3, chunk_001.mp3, etc.
```

**Options:**
- `-segment_time 900` - Duration in seconds (15 min)
- `-c copy` - No re-encoding (fast, preserves quality)
- `-f segment` - Segment muxer

### Chunk Overlap (Optional)

For maximum accuracy at boundaries, use 1-2 second overlap:

```bash
ffmpeg -i input.mp3 -f segment -segment_time 900 -segment_overlap 2 -c copy chunk_%03d.mp3
```

---

## n8n Workflow Architecture

### Pattern 1: Synchronous (Short Files)

```
Webhook → Transcribe → Extract Insights → Store
```

Best for: Files under 15 minutes, quick turnaround needed.

### Pattern 2: Async with Job ID (Long Files)

```
1. Webhook receives audio → Return Job ID immediately
2. Background workflow:
   └── Split audio (ffmpeg)
   └── Transcribe chunks (parallel sub-workflows)
   └── Merge transcripts
   └── Extract insights
   └── Store results
   └── Update job status in DB
3. Client polls /status?jobId=xyz
```

Best for: Files over 15 minutes, production use.

### Pattern 3: File Drop Trigger

```
1. User drops file in /data/audio
2. Workflow triggers on new file
3. Process async (same as Pattern 2)
4. Results written to /data/transcripts and /data/notes
```

Best for: Batch processing, no API needed.

### Workflow Components

#### Audio Splitting (Execute Command Node)

```bash
ffmpeg -i /data/audio/{{$json.filename}} \
  -f segment \
  -segment_time 900 \
  -c copy \
  /data/audio/chunks/{{$json.basename}}_%03d.mp3
```

#### Parallel Transcription

Use **Split In Batches** + **Execute Sub-Workflow** with `waitForSubWorkflow: false`:

```javascript
// Code node - Track chunk metadata
const chunks = [];
const chunkDuration = 900; // 15 minutes

for (let i = 0; i < totalChunks; i++) {
  chunks.push({
    id: i,
    start_time: i * chunkDuration,
    file: `chunk_${String(i).padStart(3, '0')}.mp3`
  });
}

return chunks.map(c => ({ json: c }));
```

#### Transcript Merging

```javascript
// Code node - Merge with timestamp adjustment
const mergedTranscript = {
  text: "",
  segments: []
};

for (const chunk of $input.all()) {
  const offsetSeconds = chunk.json.start_time;

  // Adjust timestamps
  chunk.json.transcript.segments.forEach(segment => {
    segment.start += offsetSeconds;
    segment.end += offsetSeconds;
    mergedTranscript.segments.push(segment);
  });

  mergedTranscript.text += chunk.json.transcript.text + " ";
}

return [{ json: mergedTranscript }];
```

---

## Configuration Recommendations

### Speaches Environment Variables

```bash
# docker-compose.yml - whisper service
environment:
  # Model selection
  WHISPER__MODEL: Systran/faster-whisper-base  # or small, medium, large-v3

  # Performance
  WHISPER__COMPUTE_TYPE: int8  # Reduces memory by 40%
  WHISPER__CPU_THREADS: 8      # Adjust to your CPU
  WHISPER__NUM_WORKERS: 1      # Parallel workers

  # Reliability
  DEFAULT_LANGUAGE: en         # Avoid auto-detection issues

  # Memory management
  STT_MODEL_TTL: 300          # Unload model after 5 min idle (-1 = never)
```

### n8n Environment Variables

```bash
# docker-compose.yml - n8n service
environment:
  # Timeout for long workflows
  EXECUTIONS_TIMEOUT: 3600          # 1 hour (default: 120s)
  EXECUTIONS_TIMEOUT_MAX: 7200      # Max 2 hours

  # Memory for large file handling
  NODE_OPTIONS: "--max-old-space-size=4096"
```

### Model Selection Guide

| Model | Speed | Accuracy | Memory | Use Case |
|-------|-------|----------|--------|----------|
| `tiny` | Fastest | Lowest | ~1 GB | Real-time preview |
| `base` | Fast | Good | ~1.5 GB | Quick transcription |
| `small` | Medium | Better | ~2 GB | General use |
| `medium` | Slower | High | ~3 GB | Production quality |
| `large-v3` | Slowest | Highest | ~4 GB | Maximum accuracy |

**Recommendation**: Start with `base` for development, use `small` or `medium` for production.

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Timeout during transcription | n8n default timeout too short | Set `EXECUTIONS_TIMEOUT=3600` |
| Memory grows over time | Known faster-whisper issue | Restart container after very long files |
| Empty transcript | Language detection failed | Set `DEFAULT_LANGUAGE=en` |
| 500 error on large files | Missing model files | Check whisper_cache volume, re-download model |
| Duplicate words at boundaries | Chunk overlap not handled | Implement deduplication in merge step |

### Monitoring

```bash
# Check Whisper container memory
docker stats lima-whisper

# Check processing logs
docker logs -f lima-whisper

# Test Whisper health
curl http://localhost:9000/health
```

### Performance Tuning

1. **Enable VAD**: Automatically skips silence (enabled by default)
2. **Use int8**: 40% less memory, minimal accuracy loss
3. **Increase batch_size**: 16-24 for long files (requires API parameter)
4. **Pre-process audio**: Convert to mono, lower bitrate for faster upload

```bash
# Optimize audio before processing
ffmpeg -i input.mp3 -ac 1 -ar 16000 -b:a 64k optimized.mp3
```

---

## Alternative: Native MLX Whisper (Apple Silicon / Linux GPU)

LIMA includes an optional native Whisper server using Lightning Whisper MLX for GPU acceleration outside Docker.

### When to Use

- **Linux with NVIDIA GPU**: May provide significant speedup over CPU
- **Apple Silicon**: Available but benchmarks show Docker CPU is often faster
- **No Docker**: When you need a lightweight native solution

### Setup

The Native Whisper server is located in `services/whisper-server/`.

**Requirements:**
- Python 3.11+
- uv (Python package manager)
- Apple Silicon Mac or Linux with NVIDIA GPU

**Installation:**

```bash
cd services/whisper-server
uv sync
```

**Start the server:**

```bash
# Default: distil-large-v3 model on port 9001
uv run server.py

# Or with custom settings
WHISPER_MODEL=base PORT=9001 uv run server.py
```

### Available Models

| Model | Speed | Accuracy | Notes |
|-------|-------|----------|-------|
| `tiny` | Fastest | Lowest | Testing only |
| `base` | Fast | Good | Quick transcription |
| `small` | Medium | Better | General use |
| `medium` | Slower | High | Production quality |
| `large-v3` | Slowest | Highest | Best accuracy |
| `distil-large-v3` | Fast | High | **Recommended** - best speed/accuracy |
| `distil-medium.en` | Fast | Good | English only, smaller |

### API Usage

The server exposes an OpenAI-compatible API:

```bash
# Health check
curl http://localhost:9001/health

# List models
curl http://localhost:9001/v1/models

# Transcribe audio
curl -X POST http://localhost:9001/v1/audio/transcriptions \
  -F "file=@audio.mp3" \
  -F "language=en"
```

### Connecting from n8n (Docker)

To call the native MLX server from n8n running in Docker:

```bash
# In n8n HTTP Request node, use:
http://host.docker.internal:9001/v1/audio/transcriptions
```

### Running as a Service (macOS)

Create a launchd plist for automatic startup:

```xml
<!-- ~/Library/LaunchAgents/com.lima.whisper-server.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.lima.whisper-server</string>
    <key>WorkingDirectory</key>
    <string>/path/to/lima/services/whisper-server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/.local/bin/uv</string>
        <string>run</string>
        <string>server.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/lima-whisper-server.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/lima-whisper-server.err</string>
</dict>
</plist>
```

Load with: `launchctl load ~/Library/LaunchAgents/com.lima.whisper-server.plist`

### Running as a Service (Linux systemd)

```ini
# /etc/systemd/system/lima-whisper-server.service
[Unit]
Description=LIMA Whisper MLX Server
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/lima/services/whisper-server
Environment="WHISPER_MODEL=distil-large-v3"
Environment="PORT=9001"
ExecStart=/path/to/.local/bin/uv run server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable with: `sudo systemctl enable --now lima-whisper-server`

---

## References

- [Speaches GitHub](https://github.com/speaches-ai/speaches)
- [Speaches Configuration](https://speaches.ai/configuration/)
- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper)
- [lightning-whisper-mlx GitHub](https://github.com/mustafaaljadery/lightning-whisper-mlx)
- [MLX Community Whisper Models](https://huggingface.co/collections/mlx-community/whisper-663256f9964fbb1177db93dc)
- [n8n Community: Split Audio File](https://community.n8n.io/t/split-audio-file/65792)
- [n8n Workflow #10870: Transcribe Long Audio Files](https://n8n.io/workflows/10870)
- [Whisper GPU Benchmarks (Tom's Hardware)](https://www.tomshardware.com/news/whisper-audio-transcription-gpus-benchmarked)
