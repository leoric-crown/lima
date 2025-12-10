# LIMA Native Whisper Server

Native GPU-accelerated Whisper transcription server for local development. Uses platform-specific optimizations:

- **macOS**: Lightning Whisper MLX (Apple Silicon Metal GPU)
- **Linux/Windows**: faster-whisper with CUDA (NVIDIA GPU)

## Quick Start

```bash
# macOS/Linux
uv sync
./run_server.sh --port 9002
```

```powershell
# Windows (PowerShell)
uv sync
.\run_server.ps1 -Port 9002
```

The server provides an OpenAI-compatible API at `/v1/audio/transcriptions`.

## Platform-Specific Setup

### macOS (Apple Silicon)

**Requirements:**
- Apple Silicon Mac (M1/M2/M3/M4)
- macOS with Metal support

**Installation:**
```bash
uv sync  # Installs lightning-whisper-mlx
./run_server.sh --port 9002
```

**Performance Notes:**
- Best for: Interactive development, quick tests
- Small files: Similar to Docker Speaches
- Large files: May be slower than Docker Speaches
- Recommendation: **Use Docker Speaches for production** (more consistent performance)

### Linux (NVIDIA GPU)

**Requirements:**
- NVIDIA GPU with CUDA support
- NVIDIA drivers installed (verify with `nvidia-smi`)
- CUDA 12.x compatible GPU

**Installation:**
```bash
# 1. Install Python dependencies
uv sync

# 2. Install NVIDIA cuDNN for CUDA 12
uv pip install nvidia-cudnn-cu12

# 3. Verify CUDA is available
nvidia-smi
```

**Performance:**
Tested on RTX 4090:
- **~71x real-time** transcription speed
- 42-minute meeting transcribed in 36 seconds
- Excellent for batch processing

**Troubleshooting:**

If you see `libcudnn_ops.so: cannot open shared object file`:
```bash
# cuDNN libraries are installed in venv but not in system path
# The run_server.sh script handles this automatically by setting LD_LIBRARY_PATH
./run_server.sh --port 9002
```

To manually verify cuDNN installation:
```bash
uv pip list | grep nvidia-cudnn
# Should show: nvidia-cudnn-cu12
```

### Windows (NVIDIA GPU)

**Requirements:**
- NVIDIA GPU with CUDA support
- NVIDIA drivers installed (verify with `nvidia-smi`)
- PowerShell 5.1 or later

**Installation:**
```powershell
# 1. Install Python dependencies
uv sync

# 2. Install NVIDIA cuDNN for CUDA 12
uv pip install nvidia-cudnn-cu12

# 3. Verify CUDA
nvidia-smi
```

**Run Server:**
```powershell
# PowerShell
.\run_server.ps1 -Port 9002

# Or with additional options
.\run_server.ps1 -Port 9002 -Model "large-v3" -Device "cuda"
```

**Performance:**
Similar to Linux - excellent speed with NVIDIA GPUs (e.g., ~71x real-time on RTX 4090).

## Command-Line Options

```bash
./run_server.sh [OPTIONS]

Options:
  --port PORT              Port to run on (default: 9001)
  --host HOST              Host to bind to (default: 0.0.0.0)
  --model MODEL            Whisper model to use
  --device DEVICE          cuda or cpu (Linux only)
  --compute-type TYPE      float16, int8, int8_float16 (Linux only)
```

**Available Models:**
- `tiny` - Fastest, lowest accuracy
- `base` - **Default** - Good balance
- `small` - Better accuracy
- `medium` - High accuracy
- `large-v3` - Best accuracy, slower
- `distil-large-v3` - Distilled, fast + accurate

**Examples:**
```bash
# Use large model for best accuracy
./run_server.sh --port 9002 --model large-v3

# CPU mode (if no GPU)
./run_server.sh --port 9002 --device cpu
```

## API Usage

### Transcribe Audio

```bash
curl -X POST http://localhost:9002/v1/audio/transcriptions \
  -F "file=@audio.mp3" \
  -F "language=en" \
  -F "response_format=json"
```

**Response Formats:**
- `json` (default) - Simple text output
- `text` - Plain text only
- `verbose_json` - Includes segments, timestamps, language

**Example with segments:**
```bash
curl -X POST http://localhost:9002/v1/audio/transcriptions \
  -F "file=@meeting.mp3" \
  -F "response_format=verbose_json" | jq .
```

### Health Check

```bash
curl http://localhost:9002/health
```

### List Models

```bash
curl http://localhost:9002/v1/models
```

## Performance Comparison

| Platform | Hardware | Speed | Recommendation |
|----------|----------|-------|----------------|
| **Docker (Speaches)** | CPU/GPU agnostic | Consistent | ✅ **Recommended for production** |
| **macOS Native (MLX)** | Apple Silicon M4 24GB | Variable | Development/testing only |
| **Linux Native (CUDA)** | RTX 4090 | ~71x realtime | Excellent for batch processing |

**Key Findings:**
- Docker Speaches provides the most consistent performance across platforms
- macOS MLX: Small files ~same as Docker, large files slower than Docker
- Linux CUDA: Significantly faster than Docker on NVIDIA GPUs

## When to Use Native vs Docker

**Use Docker Speaches (default):**
- Production workflows
- Consistent performance needs
- macOS users (better than MLX in testing)
- Multi-platform deployments

**Use Native Server:**
- Linux development with NVIDIA GPU (very fast)
- Testing model variations quickly
- Offline development without Docker

## Development

**File Structure:**
```
services/whisper-server/
├── run_server.sh          # Launcher for macOS/Linux (auto-detects OS)
├── run_server.ps1         # Launcher for Windows (PowerShell)
├── server_mlx.py          # macOS MLX implementation
├── server_cuda.py         # Linux/Windows CUDA implementation
├── pyproject.toml         # macOS dependencies (MLX)
└── README.md              # This file
```

**Adding to n8n Workflows:**

Point your n8n HTTP Request nodes to:
```
http://localhost:9002/v1/audio/transcriptions
```

Compatible with OpenAI Whisper API format.
