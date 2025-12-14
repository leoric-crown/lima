# Native GPU Whisper

LIMA includes optional native GPU-accelerated whisper servers for faster transcription during development.

> **Terminology:** "Docker whisper" refers to **Speaches** (faster-whisper in a container) - this is what runs when you `make up`. "Native whisper" runs directly on your machine using GPU acceleration.

## When to Use Native vs Docker (Speaches)

| Scenario | Recommendation |
|----------|----------------|
| **First-time setup** | Docker (Speaches) - just works, no extra config |
| **Production/consistency** | Docker - predictable cold starts, no warmup needed |
| **Development iteration** | Native GPU - 3-5x faster after warmup |
| **macOS Apple Silicon** | Native MLX - fastest option, but needs warmup handling |
| **Linux with NVIDIA GPU** | Native CUDA - significant speedup over Docker |

**Bottom line:** Start with Docker. Switch to native if you're processing many recordings during development and want faster iteration.

---

## Quick Start

```bash
# Start native whisper in background (auto-detects platform)
make whisper-native

# Check if running
make whisper-native-status

# View logs
make whisper-native-logs

# Stop
make whisper-native-stop
```

The native server runs on port 9001 by default (configurable via `NATIVE_WHISPER_PORT` in `.env`).

---

## Platform Support

| Platform | Technology | Requirements |
|----------|------------|--------------|
| **macOS (Apple Silicon)** | Lightning Whisper MLX | M1/M2/M3/M4 chip |
| **Linux** | faster-whisper CUDA | NVIDIA GPU + drivers (`nvidia-smi` to verify) |
| **Windows** | faster-whisper CUDA | NVIDIA GPU + drivers |

> **Windows note:** Run the native whisper server in **PowerShell or cmd**, not WSL. CUDA requires direct access to Windows GPU drivers. WSL2 can access GPUs but requires [additional configuration](https://docs.nvidia.com/cuda/wsl-user-guide/) that's beyond LIMA's default setup.

---

## Performance Comparison

Benchmark: 42-minute audio file

| Platform | Speed | Notes |
|----------|-------|-------|
| **macOS M4 Pro (MLX)** | 166x realtime (~15s) | 5.3x faster than Docker, slow cold start |
| **Linux RTX 4090 (CUDA)** | 71x realtime (~36s) | 4.3x faster than Docker |
| **Windows RTX 4090 (CUDA)** | 39x realtime (~66s) | 2.8x faster than Docker |
| **Docker Speaches** | 14-33x realtime | Consistent, no warmup needed |

### Cold Start Considerations

- **Docker Speaches:** Fast cold start, consistent performance
- **Native MLX (macOS):** First request is slow (model loading), subsequent requests are very fast
- **Native CUDA:** Moderate cold start, faster than Docker after warmup

---

## Configuration

Set these in `.env` before starting:

| Variable | Default | Purpose |
|----------|---------|---------|
| `NATIVE_WHISPER_HOST` | `0.0.0.0` | Bind address |
| `NATIVE_WHISPER_PORT` | `9001` | Server port |
| `WHISPER_MODEL` | `Systran/faster-whisper-base` | Model to use |

### Model Options

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| `tiny` | ~75MB | Fastest | Lower |
| `base` | ~150MB | Fast | Good |
| `small` | ~500MB | Medium | Better |
| `medium` | ~1.5GB | Slower | High |
| `large-v3` | ~3GB | Slowest | Highest |

---

## Using with LIMA Workflows

The Voice Memo workflow can be configured to use native whisper instead of Docker Speaches. Set `NATIVE_WHISPER_PORT` in `.env` before running `make seed` to configure the workflow automatically.

---

## Detailed Setup

For platform-specific installation instructions, troubleshooting, and advanced configuration, see:

**[services/whisper-server/README.md](../services/whisper-server/README.md)**

---

## Next Steps

- [Audio Processing Guide](audio-processing-guide.md) - Chunking strategies for long recordings
- [Troubleshooting](troubleshooting.md) - Whisper-specific issues
