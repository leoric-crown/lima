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

<details>
<summary><b>Linux/Windows: Verify NVIDIA drivers</b></summary>

Run `nvidia-smi` in a terminal (Linux) or PowerShell/cmd (Windows):

```
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 580.105.08             Driver Version: 580.105.08     CUDA Version: 13.0     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 4090        Off |   00000000:09:00.0  On |                  Off |
|  0%   48C    P8             18W /  450W |    1775MiB /  24564MiB |     19%      Default |
+-----------------------------------------+------------------------+----------------------+
```

If this fails, install or update your NVIDIA drivers.

</details>

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
| `COMPUTE_TYPE` | `float16` | Precision: `float16`, `int8`, `int8_float16` (Linux/CUDA) |
| `WHISPER_IDLE_TIMEOUT` | `0` (disabled) | Seconds of inactivity after which the model unloads to free VRAM |

> **Model/precision overrides must be make command-line variables**, not env
> prefixes — the Makefile's `-include .env` + `export` makes `.env` shadow the
> calling environment. Use
> `make whisper-native WHISPER_MODEL=large-v3 COMPUTE_TYPE=int8_float16`, not
> `WHISPER_MODEL=large-v3 make whisper-native`.

---

## VRAM management: sharing a GPU with a large LLM

The native server **loads the model lazily** on the first transcription and
holds it in VRAM until released. On a 24GB GPU shared with a large LLM this
matters: large-v3 int8 (2.2GB) plus a 30B-class LLM (20.3GB @ 16K) plus desktop
overhead does not reliably fit if whisper stays resident. Two release
mechanisms:

**1. `POST /unload` (primary, deterministic).** Drops the model and forces real
VRAM release; the next transcription lazily reloads.

```bash
curl -X POST http://localhost:9103/unload
# → {"unloaded": true}   (false if no model was loaded)

curl http://localhost:9103/health
# → {"status":"ok","device":"cuda","model":"large-v3","model_loaded":false}
```

The **Voice Memo Processor (CUDA/MLX)** workflow already calls this: an
`Unload Whisper` HTTP node sits between **Whisper Transcription** and **Extract
Insights**, so whisper releases its VRAM in the moment before the LLM step
loads. The node is **fail-soft** (`onError: continueRegularOutput`, 15s timeout,
`neverError`) — if the native server is absent (e.g. you're running Docker
Speaches instead), the unload call fails silently and the pipeline continues.
Because Extract Insights reads the transcript via
`$('Whisper Transcription').first().json.text` (by node name, not immediate
input), the intervening unload node never disturbs the transcript.

**2. `WHISPER_IDLE_TIMEOUT` (secondary, for ad-hoc callers).** A background task
unloads the model after N idle seconds. This is a safety net for callers outside
the memo pipeline — it does **not** replace the endpoint, because in the pipeline
the LLM step runs seconds after transcription, inside any reasonable idle window,
so a timer alone never frees VRAM in time. Disabled by default.

```bash
make whisper-native WHISPER_MODEL=large-v3 COMPUTE_TYPE=int8_float16 WHISPER_IDLE_TIMEOUT=600
```

`/health` is always cheap (never loads the model) and reports `model_loaded` so
you can poll residency without triggering a load.

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

### Host Firewall (Linux)

The workflow calls the native server at the **host's LAN IP** (the n8n container can't use `localhost` — that's the container itself). Container→host traffic passes through the host firewall's input chain, so a default-deny firewall silently drops it: the request **times out** (rather than being refused) even though `curl` from the host works fine.

Allow the whisper port from Docker's bridge subnets:

```bash
# ufw (Omarchy, Ubuntu, ...)
sudo ufw allow in proto tcp from 172.16.0.0/12 to any port 9103 comment 'lima: n8n container -> native whisper'

# firewalld (Fedora, ...)
sudo firewall-cmd --permanent --zone=public --add-rich-rule='rule family=ipv4 source address=172.16.0.0/12 port port=9103 protocol=tcp accept' && sudo firewall-cmd --reload
```

Use your `NATIVE_WHISPER_PORT` value if you changed it. `172.16.0.0/12` covers all default Docker bridge networks while keeping the port closed to the rest of your LAN. Verify from inside the container:

```bash
docker exec lima-n8n wget -qO- -T 5 http://<host-lan-ip>:9103/health
```

---

## Detailed Setup

For platform-specific installation instructions, troubleshooting, and advanced configuration, see:

**[services/whisper-server/README.md](../services/whisper-server/README.md)**

---

## Next Steps

- [Audio Processing Guide](audio-processing-guide.md) - Chunking strategies for long recordings
- [Troubleshooting](troubleshooting.md) - Whisper-specific issues
