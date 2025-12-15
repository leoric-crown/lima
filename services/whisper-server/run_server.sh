#!/bin/bash
# LIMA Whisper Server Launcher
# Automatically detects platform and runs the appropriate server:
# - macOS: Lightning Whisper MLX (Apple Silicon GPU acceleration)
# - Linux: faster-whisper with CUDA (NVIDIA GPU acceleration)

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env from project root if it exists
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [ -f "$PROJECT_ROOT/.env" ]; then
    # Export only the variables we care about (avoid shellcheck issues with dynamic source)
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ -z "$key" || "$key" =~ ^# ]] && continue
        # Remove surrounding quotes from value
        value="${value%\"}"
        value="${value#\"}"
        value="${value%\'}"
        value="${value#\'}"
        # Only export specific variables we need
        case "$key" in
            NATIVE_WHISPER_HOST|NATIVE_WHISPER_PORT)
                export "$key=$value"
                ;;
        esac
    done < "$PROJECT_ROOT/.env"
fi

# Detect operating system
OS="$(uname -s)"

case "$OS" in
    Darwin*)
        echo "Detected macOS - using Lightning Whisper MLX"
        echo "============================================================"

        # Use env vars if set, otherwise use defaults
        HOST="${NATIVE_WHISPER_HOST:-0.0.0.0}"
        PORT="${NATIVE_WHISPER_PORT:-9001}"

        exec uv run server_mlx.py --host "$HOST" --port "$PORT" "$@"
        ;;
    Linux*)
        echo "Detected Linux - using faster-whisper with CUDA"
        echo "============================================================"

        # Sync dependencies (creates venv if needed, updates if outdated)
        echo "Syncing dependencies..."
        uv sync

        # Find the venv python site-packages for CUDA libraries
        VENV_PATH="$SCRIPT_DIR/.venv"

        # Auto-detect Python version in venv
        PYTHON_VER=$(find "$VENV_PATH/lib" -maxdepth 1 -name 'python3.*' -type d 2>/dev/null | head -n1 | xargs -r basename)
        SITE_PACKAGES="$VENV_PATH/lib/$PYTHON_VER/site-packages"

        CUDNN_LIB="$SITE_PACKAGES/nvidia/cudnn/lib"
        CUBLAS_LIB="$SITE_PACKAGES/nvidia/cublas/lib"

        # Add CUDA libraries to LD_LIBRARY_PATH (required for CUDA acceleration)
        CUDA_PATHS=""
        if [ -d "$CUDNN_LIB" ]; then
            CUDA_PATHS="$CUDNN_LIB"
            echo "✓ Added cuDNN library path"
        fi

        if [ -d "$CUBLAS_LIB" ]; then
            CUDA_PATHS="$CUBLAS_LIB${CUDA_PATHS:+:$CUDA_PATHS}"
            echo "✓ Added cuBLAS library path"
        fi

        if [ -n "$CUDA_PATHS" ]; then
            export LD_LIBRARY_PATH="$CUDA_PATHS:$LD_LIBRARY_PATH"
        else
            echo "⚠ Warning: CUDA libraries not found."
            echo "  Run: uv sync"
            echo "  Falling back to CPU mode..."
        fi

        # Use env vars if set, otherwise use defaults
        HOST="${NATIVE_WHISPER_HOST:-0.0.0.0}"
        PORT="${NATIVE_WHISPER_PORT:-9001}"

        exec uv run server_cuda.py --host "$HOST" --port "$PORT" "$@"
        ;;
    *)
        echo "Error: Unsupported operating system: $OS"
        echo "Supported platforms: macOS (Darwin), Linux"
        echo "On Windows, run ./run_server.ps1 instead."
        exit 1
        ;;
esac
