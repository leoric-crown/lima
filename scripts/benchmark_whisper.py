#!/usr/bin/env python3
"""Benchmark script to compare Whisper server performance."""

import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from system_info import get_audio_duration, get_system_info

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Server configurations
SERVERS = {
    "speaches-cpu": {
        "transcribe_url": "http://localhost:9000/v1/audio/transcriptions",
        "base_url": "http://localhost:9000",
        "model_id": "Systran/faster-whisper-base",
        "model_name": "Systran/faster-whisper-base",  # Full name for API requests
    },
    "cuda-gpu": {
        "transcribe_url": "http://localhost:9001/v1/audio/transcriptions",
        "base_url": "http://localhost:9001",
        "model_id": None,  # Native server, model loaded at startup
        "model_name": "base",  # Short name works for native server
    },
}

# Audio files to test (will be sorted by size)
AUDIO_DIR = Path(__file__).parent.parent / "data" / "audio"


def ensure_model_installed(server_name: str, server_config: dict) -> bool:
    """Ensure the model is installed on the server (for speaches)."""
    model_id = server_config.get("model_id")
    if not model_id:
        return True  # No model installation needed

    base_url = server_config["base_url"]

    # Check if model is already installed
    try:
        response = requests.get(f"{base_url}/v1/models", timeout=10)
        if response.status_code == 200:
            models = response.json()
            # Check if our model is in the list
            model_ids = [m.get("id", "") for m in models.get("data", [])]
            if model_id in model_ids or "base" in model_ids:
                print(f"  Model already installed on {server_name}")
                return True
    except requests.exceptions.RequestException:
        pass

    # Install the model - POST /v1/models/{model_id}
    print(f"  Installing model {model_id} on {server_name}...")
    try:
        # URL-encode the model_id since it contains a slash
        import urllib.parse
        encoded_model_id = urllib.parse.quote(model_id, safe="")
        response = requests.post(
            f"{base_url}/v1/models/{encoded_model_id}",
            timeout=300,  # Model download can take a while
        )
        if response.status_code in (200, 201):
            print(f"  Model installed successfully on {server_name}")
            return True
        else:
            print(f"  Failed to install model: HTTP {response.status_code} - {response.text[:200]}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"  Failed to install model: {e}")
        return False


@dataclass
class BenchmarkResult:
    server: str
    file: str
    file_size_bytes: int
    audio_duration_sec: float | None
    request_time_sec: float
    success: bool
    error: str | None = None
    transcript_preview: str | None = None

    @property
    def realtime_factor(self) -> float | None:
        if self.audio_duration_sec and self.success:
            return self.audio_duration_sec / self.request_time_sec
        return None


def transcribe(transcribe_url: str, audio_path: Path, model_name: str) -> tuple[float, bool, str | None, str | None]:
    """Send transcription request and measure time."""
    start = time.perf_counter()
    try:
        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "audio/mpeg")}
            data = {"model": model_name, "response_format": "json"}
            response = requests.post(transcribe_url, files=files, data=data, timeout=600)

        elapsed = time.perf_counter() - start

        if response.status_code == 200:
            result = response.json()
            text = result.get("text", "")
            preview = text[:100] + "..." if len(text) > 100 else text
            return elapsed, True, None, preview
        else:
            return elapsed, False, f"HTTP {response.status_code}: {response.text[:200]}", None

    except requests.exceptions.RequestException as e:
        elapsed = time.perf_counter() - start
        return elapsed, False, str(e), None


def run_benchmark(
    audio_files: list[Path], servers: dict[str, dict], warmup_file: Path | None = None
) -> list[BenchmarkResult]:
    """Run benchmarks on all files against all servers."""
    results = []

    # Ensure models are installed on all servers
    print(f"\n{'=' * 60}")
    print("CHECKING/INSTALLING MODELS")
    print(f"{'=' * 60}")
    for server_name, server_config in servers.items():
        ensure_model_installed(server_name, server_config)

    # Warmup run (first file, twice) to ensure models are loaded
    if warmup_file:
        print(f"\n{'=' * 60}")
        print("WARMUP RUNS (to ensure models are loaded)")
        print(f"{'=' * 60}")
        for server_name, server_config in servers.items():
            transcribe_url = server_config["transcribe_url"]
            model_name = server_config["model_name"]
            print(f"\n[{server_name}] Warmup with {warmup_file.name}...")
            for i in range(2):
                duration = get_audio_duration(warmup_file)
                elapsed, success, error, preview = transcribe(transcribe_url, warmup_file, model_name)

                result = BenchmarkResult(
                    server=server_name,
                    file=warmup_file.name,
                    file_size_bytes=warmup_file.stat().st_size,
                    audio_duration_sec=duration,
                    request_time_sec=elapsed,
                    success=success,
                    error=error,
                    transcript_preview=preview,
                )
                results.append(result)

                status = "✓" if success else "✗"
                rtf = f"{result.realtime_factor:.1f}x realtime" if result.realtime_factor else "N/A"
                print(f"  Run {i + 1}: {status} {elapsed:.2f}s ({rtf})")

    # Main benchmark runs
    print(f"\n{'=' * 60}")
    print("BENCHMARK RUNS")
    print(f"{'=' * 60}")

    for audio_file in audio_files:
        if audio_file == warmup_file:
            continue  # Skip warmup file in main runs

        file_size = audio_file.stat().st_size
        duration = get_audio_duration(audio_file)
        duration_str = f"{duration:.1f}s" if duration else "unknown"

        print(f"\n[{audio_file.name}] Size: {file_size / 1024 / 1024:.2f} MB, Duration: {duration_str}")
        print("-" * 50)

        for server_name, server_config in servers.items():
            transcribe_url = server_config["transcribe_url"]
            model_name = server_config["model_name"]
            print(f"  {server_name}: ", end="", flush=True)
            elapsed, success, error, preview = transcribe(transcribe_url, audio_file, model_name)

            result = BenchmarkResult(
                server=server_name,
                file=audio_file.name,
                file_size_bytes=file_size,
                audio_duration_sec=duration,
                request_time_sec=elapsed,
                success=success,
                error=error,
                transcript_preview=preview,
            )
            results.append(result)

            if success:
                rtf = f"{result.realtime_factor:.1f}x" if result.realtime_factor else "N/A"
                print(f"✓ {elapsed:.2f}s ({rtf} realtime)")
            else:
                print(f"✗ {elapsed:.2f}s - {error}")

    return results


def print_summary(results: list[BenchmarkResult]) -> None:
    """Print a summary table of results."""
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}\n")

    # Group by file
    files = {}
    for r in results:
        if r.file not in files:
            files[r.file] = {}
        if r.server not in files[r.file]:
            files[r.file][r.server] = []
        files[r.file][r.server].append(r)

    # Print comparison table
    print(f"{'File':<30} {'Server':<15} {'Time (s)':<12} {'RTF':<12} {'Status'}")
    print("-" * 80)

    for file_name in files:
        for server_name in files[file_name]:
            for i, r in enumerate(files[file_name][server_name]):
                run_label = f" (run {i + 1})" if len(files[file_name][server_name]) > 1 else ""
                rtf = f"{r.realtime_factor:.1f}x" if r.realtime_factor else "N/A"
                status = "OK" if r.success else "FAIL"
                print(f"{file_name + run_label:<30} {server_name:<15} {r.request_time_sec:<12.2f} {rtf:<12} {status}")

    # Calculate speedup
    print(f"\n{'=' * 60}")
    print("SPEEDUP COMPARISON (CUDA vs CPU)")
    print(f"{'=' * 60}\n")

    for file_name in files:
        cpu_results = [r for r in files[file_name].get("speaches-cpu", []) if r.success]
        gpu_results = [r for r in files[file_name].get("cuda-gpu", []) if r.success]

        if cpu_results and gpu_results:
            # Use last run (after warmup)
            cpu_time = cpu_results[-1].request_time_sec
            gpu_time = gpu_results[-1].request_time_sec
            speedup = cpu_time / gpu_time if gpu_time > 0 else 0

            print(f"{file_name}:")
            print(f"  CPU: {cpu_time:.2f}s")
            print(f"  GPU: {gpu_time:.2f}s")
            print(f"  Speedup: {speedup:.1f}x faster on GPU\n")


def main():
    # Gather system info first
    system_info = get_system_info()

    # Find and sort audio files by size
    audio_files = sorted(AUDIO_DIR.glob("*"), key=lambda f: f.stat().st_size if f.is_file() else 0)
    audio_files = [f for f in audio_files if f.is_file() and f.suffix.lower() in (".mp3", ".flac", ".wav", ".m4a")]

    if not audio_files:
        print(f"No audio files found in {AUDIO_DIR}")
        return

    print("WHISPER SERVER BENCHMARK")
    print(f"{'=' * 60}")

    # Print system info
    print(f"\nSystem: {system_info.hostname}")
    print(f"OS: {system_info.os} ({system_info.os_version})")
    print(f"CPU: {system_info.cpu}")
    print(f"Cores: {system_info.cpu_cores_physical} physical, {system_info.cpu_cores_logical} logical")
    print(f"RAM: {system_info.ram_gb:.1f} GB")
    if system_info.gpu:
        print(f"GPU: {system_info.gpu.name} ({system_info.gpu.vram_mb / 1024:.1f} GB VRAM)")

    print(f"\n{'=' * 60}")
    print(f"Servers: {', '.join(SERVERS.keys())}")
    print(f"Audio files ({len(audio_files)}):")
    for f in audio_files:
        size = f.stat().st_size / 1024 / 1024
        duration = get_audio_duration(f)
        duration_str = f"{duration:.1f}s ({duration / 60:.1f} min)" if duration else "unknown"
        print(f"  - {f.name}: {size:.2f} MB, {duration_str}")

    # Run benchmarks
    results = run_benchmark(audio_files, SERVERS, warmup_file=audio_files[0])

    # Print summary
    print_summary(results)

    # Build output data
    output_data = {
        "timestamp": system_info.timestamp,
        "system": system_info.to_dict(),
        "servers": {name: {"model": cfg["model_name"]} for name, cfg in SERVERS.items()},
        "results": [
            {
                "server": r.server,
                "file": r.file,
                "file_size_bytes": r.file_size_bytes,
                "audio_duration_sec": r.audio_duration_sec,
                "request_time_sec": round(r.request_time_sec, 3),
                "realtime_factor": round(r.realtime_factor, 2) if r.realtime_factor else None,
                "success": r.success,
                "error": r.error,
            }
            for r in results
        ],
    }

    # Save results to timestamped JSON file
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results_dir = Path(__file__).parent / "benchmark_results"
    results_dir.mkdir(exist_ok=True)

    output_file = results_dir / f"benchmark_{timestamp_str}.json"
    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    # Also save as latest
    latest_file = results_dir / "benchmark_latest.json"
    with open(latest_file, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\nResults saved to:")
    print(f"  {output_file}")
    print(f"  {latest_file}")


if __name__ == "__main__":
    main()
