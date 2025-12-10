"""
LIMA Lightning Whisper MLX Server
GPU-accelerated transcription on Apple Silicon using Metal.

Uses lightning-whisper-mlx

OpenAI-compatible API at /v1/audio/transcriptions
"""

import tempfile
import os
import argparse
from pathlib import Path
from typing import Optional

from lightning_whisper_mlx import LightningWhisperMLX
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(
    title="LIMA Whisper MLX",
    description="GPU-accelerated speech-to-text for Apple Silicon (Lightning fast)",
    version="0.2.0",
)

# Model configuration
# Available: tiny, base, small, medium, large, large-v2, large-v3
# Distilled: distil-small.en, distil-medium.en, distil-large-v2, distil-large-v3
DEFAULT_MODEL = os.environ.get("WHISPER_MODEL", "base")
BATCH_SIZE = int(os.environ.get("WHISPER_BATCH_SIZE", "12"))

# Lazy-load model on first request
_whisper_model = None


def get_model():
    """Get or initialize the Whisper model."""
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


@app.get("/health")
async def health():
    """Health check endpoint."""
    return "OK"


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
        whisper = get_model()
        result = whisper.transcribe(audio_path=tmp_path)

        text = result.get("text", "")

        if response_format == "text":
            return text
        elif response_format == "verbose_json":
            return JSONResponse(content={
                "text": text,
                "segments": result.get("segments", []),
                "language": language,
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

    args = parser.parse_args()

    # Override globals if specified
    global DEFAULT_MODEL, BATCH_SIZE
    if args.model:
        DEFAULT_MODEL = args.model
    if args.batch_size:
        BATCH_SIZE = args.batch_size

    print(f"=" * 60)
    print(f"LIMA Lightning Whisper MLX Server")
    print(f"=" * 60)
    print(f"Host: {args.host}:{args.port}")
    print(f"Model: {DEFAULT_MODEL}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"GPU: Apple Silicon Metal acceleration")
    print(f"=" * 60)

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
