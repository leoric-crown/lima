"""
LIMA Faster-Whisper Server (Linux Native)
GPU-accelerated transcription using NVIDIA CUDA.

Uses faster-whisper (CTranslate2) for fast inference on NVIDIA GPUs.

OpenAI-compatible API at /v1/audio/transcriptions
"""

import tempfile
import os
import sys
import argparse
from pathlib import Path
from typing import Optional

# Add NVIDIA cuDNN and cuBLAS libraries to path
def setup_cuda_paths():
    """Add NVIDIA CUDA libraries from venv to library path."""
    venv_path = Path(sys.prefix)

    if sys.platform == "win32":
        # Windows .venv structure: Lib/site-packages
        site_packages = venv_path / "Lib" / "site-packages"
        libs = [
            site_packages / "nvidia" / "cudnn" / "bin",
            site_packages / "nvidia" / "cublas" / "bin"
        ]

        for lib_path in libs:
            if lib_path.exists():
                os.environ["PATH"] = str(lib_path) + ";" + os.environ.get("PATH", "")
                print(f"Added CUDA path: {lib_path}")
    else:
        # Linux .venv structure: lib/pythonX.Y/site-packages
        # We need to find the python version directory
        lib_dir = venv_path / "lib"
        # Simple heuristic: find first python* directory
        python_dirs = list(lib_dir.glob("python3*"))
        if python_dirs:
            site_packages = python_dirs[0] / "site-packages"
            cudnn_lib = site_packages / "nvidia" / "cudnn" / "lib"

            if cudnn_lib.exists():
                ld_library_path = os.environ.get("LD_LIBRARY_PATH", "")
                new_paths = [str(cudnn_lib)]
                if ld_library_path:
                    new_paths.append(ld_library_path)
                os.environ["LD_LIBRARY_PATH"] = ":".join(new_paths)
                print(f"Added cuDNN path: {cudnn_lib}")

setup_cuda_paths()

from faster_whisper import WhisperModel
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(
    title="LIMA Whisper (CUDA)",
    description="GPU-accelerated speech-to-text for Linux NVIDIA GPUs",
    version="0.2.0",
)

# Model configuration
# Available: tiny, base, small, medium, large-v1, large-v2, large-v3
# Distilled: distil-small.en, distil-medium.en, distil-large-v2, distil-large-v3
DEFAULT_MODEL = os.environ.get("WHISPER_MODEL", "base")
COMPUTE_TYPE = os.environ.get("COMPUTE_TYPE", "float16")  # float16, int8, int8_float16
DEVICE = os.environ.get("DEVICE", "cuda")  # cuda or cpu

# Lazy-load model on first request
_whisper_model = None


def get_model():
    """Get or initialize the Whisper model."""
    global _whisper_model
    if _whisper_model is None:
        print(f"Loading model: {DEFAULT_MODEL} (device={DEVICE}, compute_type={COMPUTE_TYPE})")
        _whisper_model = WhisperModel(
            DEFAULT_MODEL,
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
        )
        print("Model loaded successfully")
    return _whisper_model


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "device": DEVICE, "model": DEFAULT_MODEL}


@app.get("/v1/models")
async def list_models():
    """List available models."""
    return {
        "data": [
            {"id": "tiny", "description": "Fastest, lowest accuracy"},
            {"id": "base", "description": "Fast, good accuracy"},
            {"id": "small", "description": "Balanced speed/accuracy"},
            {"id": "medium", "description": "Good accuracy, slower"},
            {"id": "large-v3", "description": "Best accuracy, slowest"},
            {"id": "distil-small.en", "description": "Fast, English only"},
            {"id": "distil-medium.en", "description": "Balanced, English only"},
            {"id": "distil-large-v3", "description": "Best distilled, fast + accurate"},
        ]
    }


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: Optional[str] = Form(None),
    language: Optional[str] = Form("en"),
    response_format: Optional[str] = Form("json"),
):
    """
    Transcribe audio file using faster-whisper with CUDA.

    OpenAI-compatible endpoint.
    """
    # Save uploaded file temporarily
    suffix = Path(file.filename).suffix if file.filename else ".mp3"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        whisper = get_model()

        # Transcribe with faster-whisper
        segments, info = whisper.transcribe(
            tmp_path,
            language=language if language else None,
            beam_size=5,
            vad_filter=True,  # Voice activity detection
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        # Collect all segments
        all_segments = []
        full_text = []

        for segment in segments:
            all_segments.append({
                "id": segment.id,
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
            })
            full_text.append(segment.text)

        text = " ".join(full_text).strip()

        if response_format == "text":
            return text
        elif response_format == "verbose_json":
            return JSONResponse(content={
                "text": text,
                "segments": all_segments,
                "language": info.language,
                "duration": info.duration,
            })
        else:
            return {"text": text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temp file
        os.unlink(tmp_path)


def main():
    """Run the server."""
    parser = argparse.ArgumentParser(description="LIMA Faster-Whisper Server (CUDA)")
    parser.add_argument("--port", type=int, default=9001, help="Port to run server on (default: 9001)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--model", type=str, default=None, help="Whisper model to use (overrides env var)")
    parser.add_argument("--device", type=str, default=None, choices=["cuda", "cpu"], help="Device to use (default: cuda)")
    parser.add_argument("--compute-type", type=str, default=None, choices=["float16", "int8", "int8_float16"],
                        help="Compute type for inference (default: float16)")

    args = parser.parse_args()

    # Override globals if specified
    global DEFAULT_MODEL, DEVICE, COMPUTE_TYPE
    if args.model:
        DEFAULT_MODEL = args.model
    if args.device:
        DEVICE = args.device
    if args.compute_type:
        COMPUTE_TYPE = args.compute_type

    print(f"=" * 60)
    print(f"LIMA Faster-Whisper Server (CUDA)")
    print(f"=" * 60)
    print(f"Host: {args.host}:{args.port}")
    print(f"Model: {DEFAULT_MODEL}")
    print(f"Device: {DEVICE}")
    print(f"Compute type: {COMPUTE_TYPE}")
    print(f"GPU: NVIDIA CUDA acceleration")
    print(f"=" * 60)

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
