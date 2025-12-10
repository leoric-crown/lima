#!/bin/bash
# LIMA Whisper Server Launcher
# Automatically detects platform and runs the appropriate server:
# - macOS: Lightning Whisper MLX (Apple Silicon GPU acceleration)
# - Linux: faster-whisper with CUDA (NVIDIA GPU acceleration)

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect operating system
OS="$(uname -s)"

case "$OS" in
    Darwin*)
        echo "Detected macOS - using Lightning Whisper MLX"
        echo "============================================================"
        exec uv run server_mlx.py "$@"
        ;;
    Linux*)
        echo "Detected Linux - using faster-whisper with CUDA"
        echo "============================================================"

        # Find the venv python site-packages for CUDA libraries
        VENV_PATH="$SCRIPT_DIR/.venv"

        # Auto-detect Python version in venv
        PYTHON_VER=$(find "$VENV_PATH/lib" -maxdepth 1 -name 'python3.*' -type d | head -n1 | xargs basename)
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

        exec uv run server_cuda.py "$@"
        ;;
    *)
        echo "Error: Unsupported operating system: $OS"
        echo "Supported platforms: macOS (Darwin), Linux"
        echo "On Windows, run ./run_server.ps1 instead."
        exit 1
        ;;
esac
