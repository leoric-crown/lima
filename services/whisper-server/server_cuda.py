"""
LIMA Faster-Whisper Server (Linux Native)
GPU-accelerated transcription using NVIDIA CUDA.

Uses faster-whisper (CTranslate2) for fast inference on NVIDIA GPUs.

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

from faster_whisper import WhisperModel
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# Model configuration
# Available: tiny, base, small, medium, large-v1, large-v2, large-v3
# Distilled: distil-small.en, distil-medium.en, distil-large-v2, distil-large-v3

def normalize_model_name(model: str) -> str:
    """Normalize model name by stripping HuggingFace prefixes.

    Converts 'Systran/faster-whisper-base' -> 'base' for consistency.
    faster-whisper accepts both formats, but we normalize for cleaner logs.
    """
    prefixes = ["Systran/faster-whisper-", "openai/whisper-"]
    for prefix in prefixes:
        if model.startswith(prefix):
            return model[len(prefix):]
    return model

DEFAULT_MODEL = normalize_model_name(os.environ.get("WHISPER_MODEL", "base"))
COMPUTE_TYPE = os.environ.get("COMPUTE_TYPE", "float16")  # float16, int8, int8_float16
DEVICE = os.environ.get("DEVICE", "cuda")  # cuda or cpu

# Seconds of inactivity after which the model is unloaded to free VRAM.
# 0 (default) disables the idle timer. The explicit POST /unload endpoint is the
# primary VRAM-release mechanism (the memo pipeline unloads deterministically
# between transcription and the LLM step); the idle timer is a fallback for
# ad-hoc callers outside the pipeline.
WHISPER_IDLE_TIMEOUT = int(os.environ.get("WHISPER_IDLE_TIMEOUT", "0") or "0")

# Lazy-load model on first request. On a 24GB GPU shared with a large LLM, the
# model can be released mid-session via POST /unload (or the idle timer) and is
# lazily reloaded on the next transcription. All load/unload transitions are
# serialized by _model_lock so concurrent requests can't double-load or observe
# a half-torn-down model.
_whisper_model = None
_model_lock = asyncio.Lock()
_last_used_monotonic: Optional[float] = None


def _load_model_locked():
    """Load the model if needed. Caller MUST hold _model_lock."""
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


def _unload_model_locked() -> bool:
    """Drop the model and force VRAM release. Caller MUST hold _model_lock.

    Returns True if a model was actually unloaded, False if none was loaded.

    Setting the sole reference to None and running gc.collect() triggers the
    CTranslate2 model's C++ destructor, which returns device memory to the
    driver. Verified with nvidia-smi: process residency falls from the model's
    footprint (e.g. large-v3 int8_float16 ~2.2GB) back to roughly the CUDA
    context size (~300MB), not merely dropping a Python reference.
    """
    global _whisper_model
    if _whisper_model is None:
        return False
    model = _whisper_model
    _whisper_model = None
    del model
    gc.collect()
    print("Model unloaded — VRAM released back to CUDA-context baseline")
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
        f"Configured: model={DEFAULT_MODEL} device={DEVICE} compute_type={COMPUTE_TYPE}"
        f" idle_timeout={WHISPER_IDLE_TIMEOUT or 'off'} (lazy-load on first request)"
    )
    task = None
    if WHISPER_IDLE_TIMEOUT > 0:
        print(f"Idle unload enabled: model releases VRAM after {WHISPER_IDLE_TIMEOUT}s idle")
        task = asyncio.create_task(_idle_monitor())
    try:
        yield
    finally:
        if task is not None:
            task.cancel()


app = FastAPI(
    title="LIMA Whisper (CUDA)",
    description="GPU-accelerated speech-to-text for Linux NVIDIA GPUs",
    version="0.3.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check endpoint. Cheap — never loads or unloads the model."""
    return {
        "status": "ok",
        "device": DEVICE,
        "model": DEFAULT_MODEL,
        "model_loaded": _whisper_model is not None,
    }


@app.post("/unload")
async def unload():
    """Unload the model and release its VRAM.

    Deterministic timesharing hook: the memo pipeline calls this between the
    transcription step and the LLM step so whisper and a large LLM never hold
    the GPU at the same instant. The next transcription lazily reloads.
    """
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
        global _last_used_monotonic
        # Hold the lock across the whole transcription: the faster-whisper
        # `segments` generator runs inference lazily as it is iterated, so a
        # concurrent /unload must not tear the model down mid-iteration.
        async with _model_lock:
            whisper = _load_model_locked()

            # Transcribe with faster-whisper
            segments, info = whisper.transcribe(
                tmp_path,
                language=language if language else None,
                beam_size=5,
                vad_filter=True,  # Voice activity detection
                vad_parameters=dict(min_silence_duration_ms=500),
            )

            # Collect all segments (drives the lazy generator to completion)
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

            _last_used_monotonic = time.monotonic()

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
    parser.add_argument("--idle-timeout", type=int, default=None,
                        help="Unload model after N idle seconds (0/unset = disabled)")

    args = parser.parse_args()

    # Override globals if specified
    global DEFAULT_MODEL, DEVICE, COMPUTE_TYPE, WHISPER_IDLE_TIMEOUT
    if args.model:
        DEFAULT_MODEL = args.model
    if args.device:
        DEVICE = args.device
    if args.compute_type:
        COMPUTE_TYPE = args.compute_type
    if args.idle_timeout is not None:
        WHISPER_IDLE_TIMEOUT = args.idle_timeout

    print(f"=" * 60)
    print(f"LIMA Faster-Whisper Server (CUDA)")
    print(f"=" * 60)
    print(f"Host: {args.host}:{args.port}")
    print(f"Model: {DEFAULT_MODEL}")
    print(f"Device: {DEVICE}")
    print(f"Compute type: {COMPUTE_TYPE}")
    print(f"Idle unload: {str(WHISPER_IDLE_TIMEOUT) + 's' if WHISPER_IDLE_TIMEOUT > 0 else 'disabled'}")
    print(f"GPU: NVIDIA CUDA acceleration")
    print(f"=" * 60)

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
