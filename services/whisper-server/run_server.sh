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

        # Find the venv python site-packages for cuDNN libraries
        VENV_PATH="$SCRIPT_DIR/.venv"
        CUDNN_LIB="$VENV_PATH/lib/python3.11/site-packages/nvidia/cudnn/lib"

        # Add cuDNN libraries to LD_LIBRARY_PATH (required for CUDA acceleration)
        if [ -d "$CUDNN_LIB" ]; then
            export LD_LIBRARY_PATH="$CUDNN_LIB:$LD_LIBRARY_PATH"
            echo "✓ Added cuDNN library path for GPU acceleration"
        else
            echo "⚠ Warning: cuDNN libraries not found. Run 'uv pip install nvidia-cudnn-cu12'"
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
