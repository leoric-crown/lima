"""
LIMA Lightning Whisper MLX Server
GPU-accelerated transcription on Apple Silicon using Metal.

Uses lightning-whisper-mlx

OpenAI-compatible API at /v1/audio/transcriptions
"""

import asyncio
import gc
import tempfile
import os
import argparse
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from lightning_whisper_mlx import LightningWhisperMLX
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# Model configuration
# Available: tiny, base, small, medium, large, large-v2, large-v3
# Distilled: distil-small.en, distil-medium.en, distil-large-v2, distil-large-v3

def normalize_model_name(model: str) -> str:
    """Normalize model name by stripping HuggingFace prefixes.

    Converts 'Systran/faster-whisper-base' -> 'base' for compatibility
    with lightning-whisper-mlx which expects short model names.
    """
    prefixes = ["Systran/faster-whisper-", "openai/whisper-"]
    for prefix in prefixes:
        if model.startswith(prefix):
            return model[len(prefix):]
    return model

DEFAULT_MODEL = normalize_model_name(os.environ.get("WHISPER_MODEL", "base"))
BATCH_SIZE = int(os.environ.get("WHISPER_BATCH_SIZE", "12"))

# Seconds of inactivity after which the model is unloaded (0/unset = disabled).
# See server_cuda.py for the rationale. On Apple Silicon the GPU shares system
# RAM (unified memory), so reclaiming whisper's footprint matters far less than
# on a discrete 24GB card — this is a low-priority parity port. See BACKLOG.md:
# real Metal reclamation on macOS hardware is unverified.
WHISPER_IDLE_TIMEOUT = int(os.environ.get("WHISPER_IDLE_TIMEOUT", "0") or "0")

# Lazy-load model on first request. Load/unload transitions are serialized by
# _model_lock so concurrent requests can't double-load or hit a mid-teardown model.
_whisper_model = None
_model_lock = asyncio.Lock()
_last_used_monotonic: Optional[float] = None


def _load_model_locked():
    """Load the model if needed. Caller MUST hold _model_lock."""
    global _whisper_model
    if _whisper_model is None:
        print(f"Loading model: {DEFAULT_MODEL} (batch_size={BATCH_SIZE})")
        _whisper_model = LightningWhisperMLX(
            model=DEFAULT_MODEL,
            batch_size=BATCH_SIZE,
            quant=None,  # No quantization for best quality
        )
        print("Model loaded successfully")
    return _whisper_model


def _unload_model_locked() -> bool:
    """Drop the model and release memory. Caller MUST hold _model_lock.

    Returns True if a model was actually unloaded. Drops the sole Python
    reference and runs gc.collect(); additionally asks MLX to release its Metal
    buffer cache back to the unified-memory pool (best-effort — the API name has
    moved across mlx versions, so failure is non-fatal). NOTE: actual reclamation
    on macOS is unverified from this Linux repo host — see BACKLOG.md.
    """
    global _whisper_model
    if _whisper_model is None:
        return False
    model = _whisper_model
    _whisper_model = None
    del model
    gc.collect()
    try:
        import mlx.core as mx
        clear = getattr(mx, "clear_cache", None) or getattr(getattr(mx, "metal", None), "clear_cache", None)
        if clear is not None:
            clear()
    except Exception:
        pass
    print("Model unloaded")
    return True


async def _idle_monitor():
    """Background task: unload the model after WHISPER_IDLE_TIMEOUT idle seconds."""
    interval = min(WHISPER_IDLE_TIMEOUT, 15)
    while True:
        await asyncio.sleep(interval)
        async with _model_lock:
            if _whisper_model is None or _last_used_monotonic is None:
                continue
            idle = time.monotonic() - _last_used_monotonic
            if idle >= WHISPER_IDLE_TIMEOUT and _unload_model_locked():
                print(f"Idle {idle:.0f}s >= {WHISPER_IDLE_TIMEOUT}s — unloaded model")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log the effective configuration; start the idle-unload monitor if enabled."""
    print(
        f"Configured: model={DEFAULT_MODEL} batch_size={BATCH_SIZE}"
        f" idle_timeout={WHISPER_IDLE_TIMEOUT or 'off'} (lazy-load on first request)"
    )
    task = None
    if WHISPER_IDLE_TIMEOUT > 0:
        print(f"Idle unload enabled: model unloads after {WHISPER_IDLE_TIMEOUT}s idle")
        task = asyncio.create_task(_idle_monitor())
    try:
        yield
    finally:
        if task is not None:
            task.cancel()


app = FastAPI(
    title="LIMA Whisper MLX",
    description="GPU-accelerated speech-to-text for Apple Silicon (Lightning fast)",
    version="0.3.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check endpoint. Cheap — never loads or unloads the model."""
    return {
        "status": "ok",
        "model": DEFAULT_MODEL,
        "model_loaded": _whisper_model is not None,
    }


@app.post("/unload")
async def unload():
    """Unload the model and release its memory. See server_cuda.py for rationale."""
    async with _model_lock:
        unloaded = _unload_model_locked()
    return {"unloaded": unloaded}


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
    language: Optional[str] = Form(None),
    response_format: Optional[str] = Form("json"),
):
    """
    Transcribe audio file using Lightning Whisper MLX.

    OpenAI-compatible endpoint.
    """
    # Save uploaded file temporarily
    suffix = Path(file.filename).suffix if file.filename else ".mp3"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        global _last_used_monotonic
        # Hold the lock across transcription so a concurrent /unload can't tear
        # the model down mid-inference.
        async with _model_lock:
            whisper = _load_model_locked()
            # Pass language parameter if specified, otherwise auto-detect
            transcribe_args = {"audio_path": tmp_path}
            if language:
                transcribe_args["language"] = language
            result = whisper.transcribe(**transcribe_args)
            _last_used_monotonic = time.monotonic()

        text = result.get("text", "")

        if response_format == "text":
            return text
        elif response_format == "verbose_json":
            return JSONResponse(content={
                "text": text,
                "segments": result.get("segments", []),
                "language": result.get("language", language),
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
    parser = argparse.ArgumentParser(description="LIMA Lightning Whisper MLX Server")
    parser.add_argument("--port", type=int, default=9001, help="Port to run server on (default: 9001)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--model", type=str, default=None, help="Whisper model to use (overrides env var)")
    parser.add_argument("--batch-size", type=int, default=None, help="Batch size for inference (default: 12)")
    parser.add_argument("--idle-timeout", type=int, default=None,
                        help="Unload model after N idle seconds (0/unset = disabled)")

    args = parser.parse_args()

    # Override globals if specified
    global DEFAULT_MODEL, BATCH_SIZE, WHISPER_IDLE_TIMEOUT
    if args.model:
        DEFAULT_MODEL = args.model
    if args.batch_size:
        BATCH_SIZE = args.batch_size
    if args.idle_timeout is not None:
        WHISPER_IDLE_TIMEOUT = args.idle_timeout

    print(f"=" * 60)
    print(f"LIMA Lightning Whisper MLX Server")
    print(f"=" * 60)
    print(f"Host: {args.host}:{args.port}")
    print(f"Model: {DEFAULT_MODEL}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Idle unload: {str(WHISPER_IDLE_TIMEOUT) + 's' if WHISPER_IDLE_TIMEOUT > 0 else 'disabled'}")
    print(f"GPU: Apple Silicon Metal acceleration")
    print(f"=" * 60)

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
