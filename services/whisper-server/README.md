# LIMA Native Whisper Server

Native GPU-accelerated Whisper transcription server for local development. Uses platform-specific optimizations:

- **macOS**: Lightning Whisper MLX (Apple Silicon Metal GPU)
- **Linux/Windows**: faster-whisper with CUDA (NVIDIA GPU)

## Quick Start

**From project root (recommended):**
```bash
make whisper-native         # Start in background (port from NATIVE_WHISPER_PORT, default 9001)
make whisper-native-status  # Check if running
make whisper-native-logs    # View logs
make whisper-native-stop    # Stop server
```

These commands use `scripts/whisper-native.py` - a cross-platform manager that handles:
- Background process management (start/stop/status)
- Log file management (`logs/whisper-native.log`)
- PID tracking for clean shutdown
- Loading `NATIVE_WHISPER_HOST` and `NATIVE_WHISPER_PORT` from `.env`

**Or run directly in foreground (for debugging):**
```bash
# macOS/Linux
cd services/whisper-server
./run_server.sh

# Windows (PowerShell) - must run in PowerShell, not WSL
cd services/whisper-server
.\run_server.ps1
```

The server provides an OpenAI-compatible API at `/v1/audio/transcriptions`.

## Platform-Specific Setup

### macOS (Apple Silicon)

**Requirements:**
- Apple Silicon Mac (M1/M2/M3/M4)
- macOS with Metal support

**Run:**
```bash
./run_server.sh  # Dependencies install automatically on first run
```

**Performance Notes (M4 Pro 24GB, see benchmark):**
- **First request (cold)**: Slow - model loading overhead (~8.7s for 4s audio)
- **After warmup**: Extremely fast - 155-166x realtime
- 42-minute meeting transcribed in ~15 seconds
- **Scales better with longer files** than Docker Speaches
- Benchmark: `scripts/benchmark_whisper.py`

### Linux (NVIDIA GPU)

**Requirements:**
- NVIDIA GPU with CUDA support
- NVIDIA drivers installed (verify with `nvidia-smi`)
- CUDA 12.x compatible GPU

**Run:**
```bash
# Verify NVIDIA drivers are working
nvidia-smi

# Start server (dependencies install automatically on first run)
./run_server.sh
```

**Performance (RTX 4090 on Linux, see benchmark):**
- **~71x real-time** transcription speed
- 42-minute meeting transcribed in ~36 seconds
- Excellent for batch processing
- **Note**: Windows CUDA shows ~39x realtime (1.8x slower than Linux)
- Benchmark: `scripts/benchmark_whisper.py`

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

**Performance (RTX 4090 on Windows, see benchmark):**
- **~39x real-time** transcription speed (slower than Linux)
- 42-minute meeting transcribed in ~66 seconds
- **Note**: Linux CUDA is ~1.8x faster on identical hardware
- Possible causes: driver differences, OS overhead, or WSL2 virtualization
- Benchmark: `scripts/benchmark_whisper.py`

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

**Benchmark Results** (`scripts/benchmark_whisper.py` - 42-minute test file):

| Platform | Implementation | Speed (RTF) | 42min → Time | vs Docker |
|----------|---------------|-------------|--------------|-----------|
| **macOS M4 Pro 24GB** | Docker Speaches (CPU) | 31-33x | ~82s | baseline |
| **macOS M4 Pro 24GB** | Native MLX (GPU) | **166x** | ~15s | **5.3x faster** |
| **Linux RTX 4090** | Docker Speaches (CPU) | 16.6x | ~155s | baseline |
| **Linux RTX 4090** | Native CUDA (GPU) | **71.6x** | ~36s | **4.3x faster** |
| **Windows RTX 4090** | Docker Speaches (CPU) | 14x | ~184s | baseline |
| **Windows RTX 4090** | Native CUDA (GPU) | **39x** | ~66s | **2.8x faster** |

**Key Findings:**
- **macOS MLX is fastest overall** (166x realtime after warmup)
- **Linux CUDA > Windows CUDA** (~1.8x faster on identical hardware - driver/OS difference)
- **Docker Speaches faster on macOS** than Windows/Linux (M4 Pro advantage)
- **Native GPU scales better** with longer files
- **MLX warmup critical** - first request ~60x slower (model loading)

**Caveat**: These are initial findings from limited testing. Performance varies by:
- Audio quality, silence detection, language complexity
- System load, thermal throttling, background processes
- CUDA driver versions, Docker resource limits

### Why is MLX faster than RTX 4090?

We're not entirely sure! Some hypotheses:
- **Unified memory** - Apple Silicon avoids PCIe bottlenecks when moving tensors between CPU/GPU
- **MLX optimization** - Lightning Whisper MLX may be more optimized than faster-whisper for this workload
- **Memory bandwidth** - M4 Pro has excellent memory bandwidth relative to its compute
- **Our test setup** - The RTX 4090 was paired with an older Ryzen 7 3700X (2019), which could be a bottleneck

**Further reading:**
- [MLX vs CUDA Benchmark](https://towardsdatascience.com/mlx-vs-mps-vs-cuda-a-benchmark-c5737ca6efc9/) - Comprehensive MLX/MPS/CUDA comparison
- [Whisper GPU Benchmarks (Tom's Hardware)](https://www.tomshardware.com/news/whisper-audio-transcription-gpus-benchmarked) - 18 GPUs tested
- [RTX 4090 vs M1 Pro MLX](https://owehrens.com/whisper-nvidia-rtx-4090-vs-m1pro-with-mlx/) - Direct comparison with insanely-fast-whisper
- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper) - CUDA implementation we use
- [MLX Benchmark Repo](https://github.com/TristanBilot/mlx-benchmark) - Community benchmarks across Apple Silicon chips

### Contribute Your Results!

We're missing benchmarks for:
- **AMD GPUs** (ROCm) - Linux/Windows
- **Intel Arc** GPUs - Linux/Windows
- **Older NVIDIA** (3080, 3090, A100, etc.)
- **Other Apple Silicon** (M1, M2, M3, M1/M2/M3 Ultra)
- **Different Whisper models** (large-v3, distil-large-v3)

**Note:** The run scripts currently support CUDA and MLX. AMD ROCm, Intel Arc, or other backends may require modifications to `run_server.sh` and potentially new server implementations. PRs welcome!

Run the benchmark and open a PR:
```bash
cd scripts
uv run python benchmark_whisper.py --native-port 9002
# Results saved to scripts/benchmark_results/
```

## When to Use Native vs Docker

**Use Docker Speaches (default):**
- Production workflows requiring consistency
- Multi-platform deployments
- Quick setup without GPU drivers
- When you need predictable cold-start performance

**Use Native Server:**
- **macOS development** - MLX gives 5x speedup after warmup (best for batch processing)
- **Linux with NVIDIA GPU** - CUDA gives 4x speedup (excellent performance)
- **Windows with NVIDIA GPU** - CUDA gives 3x speedup (consider Linux instead for 2x more)
- Testing different model sizes quickly
- Offline development without Docker

**Production Recommendation:**
- **macOS**: Native MLX is significantly faster but needs warmup handling
- **Linux**: Native CUDA for maximum speed, Docker for simplicity
- **Windows**: Docker is simpler; native CUDA has OS overhead issues

## Development

**Architecture:**
```
Makefile commands
       ↓
scripts/whisper-native.py    # Cross-platform manager (background, logs, PID)
       ↓
services/whisper-server/
├── run_server.sh            # macOS/Linux launcher (auto-detects OS)
├── run_server.ps1           # Windows launcher (PowerShell)
       ↓
├── server_mlx.py            # macOS: Lightning Whisper MLX
└── server_cuda.py           # Linux/Windows: faster-whisper CUDA
```

**File Structure:**
```
scripts/
└── whisper-native.py        # Process manager (start/stop/status/logs)

services/whisper-server/
├── run_server.sh            # Launcher for macOS/Linux (auto-detects OS)
├── run_server.ps1           # Launcher for Windows (PowerShell)
├── server_mlx.py            # macOS MLX implementation
├── server_cuda.py           # Linux/Windows CUDA implementation
├── pyproject.toml           # Python dependencies
└── README.md                # This file
```

**Adding to n8n Workflows:**

Point your n8n HTTP Request nodes to:
```
http://localhost:${NATIVE_WHISPER_PORT}/v1/audio/transcriptions
```

Default port is `9001`. Compatible with OpenAI Whisper API format.
