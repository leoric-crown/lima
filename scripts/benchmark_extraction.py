#!/usr/bin/env python3
"""Benchmark LIMA's structured-extraction task across models.

Runs each candidate model over the held-out eval slices under the EXACT
production task (prompt + schema from finetune/extraction_task.py) with
llama.cpp schema-constrained decoding ON — identical conditions for teacher,
base student, and tuned student, so measured differences are content quality,
never JSON syntax.

Per condition it also measures the serving-economics side of the story:
cold-start seconds (first request after a full llama-swap unload, includes
model load) and resident VRAM.

Content quality scoring is a separate pass: judge_extraction.py (LLM judge
from a different model family). This script produces outputs + code-grade
(mechanical field-discipline checks) + timing.

Usage:
    uv run benchmark_extraction.py --models qwen3-coder-30b,qwen3-8b
    uv run benchmark_extraction.py --models qwen3-4b --slices real,stt
"""

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "finetune"))
import extraction_task  # noqa: E402

from system_info import get_system_info  # noqa: E402

CORPUS = Path(__file__).parent.parent / "finetune" / "corpus"
RESULTS_DIR = Path(__file__).parent / "benchmark_results"

SLICES = {
    "real": CORPUS / "eval_real.jsonl",
    "stt": CORPUS / "eval" / "eval_stt_voice_notes.jsonl",
    "garbled": CORPUS / "eval" / "eval_boundary_garbled.jsonl",
}

TEMPERATURE = 0.2  # matches the teacher-labeling condition


def load_jsonl(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def gpu_memory_mb() -> int | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        return int(out.stdout.strip().splitlines()[0])
    except Exception:
        return None


def unload_all(swap_root: str):
    try:
        requests.post(f"{swap_root}/api/models/unload", timeout=30)
        time.sleep(2)
    except requests.RequestException as e:
        print(f"  warning: unload failed: {e}")


def extract(base_url: str, model: str, transcript: str) -> tuple[dict, dict]:
    """One extraction call. Returns (parsed_output, timing/usage info)."""
    t0 = time.perf_counter()
    resp = requests.post(
        f"{base_url}/chat/completions",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": extraction_task.SYSTEM_MESSAGE},
                {"role": "user",
                 "content": extraction_task.USER_TEMPLATE.format(transcript=transcript)},
            ],
            "temperature": TEMPERATURE,
            "max_tokens": 2048,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "extraction", "strict": True,
                                "schema": extraction_task.SCHEMA},
            },
        },
        timeout=600,
    )
    resp.raise_for_status()
    latency = time.perf_counter() - t0
    data = resp.json()
    usage = data.get("usage", {})
    output = json.loads(data["choices"][0]["message"]["content"])
    completion = usage.get("completion_tokens", 0)
    return output, {
        "latency_s": round(latency, 3),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": completion,
        "tokens_per_s": round(completion / latency, 1) if completion else None,
    }


KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FALLBACK_TITLE = "Unclear memo"


def code_grade(output: dict) -> dict:
    """Mechanical field-discipline checks derived from the schema descriptions.

    Schema syntax is guaranteed by constrained decoding; these measure whether
    the model follows the softer contracts the production prompt implies.
    """
    title_words = len(output["title"].split())
    sentences = [s for s in re.split(r"[.!?]+\s*", output["summary"]) if s.strip()]
    return {
        "is_fallback": output["title"] == FALLBACK_TITLE,
        "title_5_10_words": 5 <= title_words <= 10,
        "summary_2_3_sentences": 2 <= len(sentences) <= 3,
        "tags_2_5": 2 <= len(output["tags"]) <= 5,
        "tags_kebab_case": all(KEBAB_RE.match(t) for t in output["tags"]) if output["tags"] else False,
        "nonempty_key_points_or_fallback": bool(output["key_points"]) or output["title"] == FALLBACK_TITLE,
    }


def run_condition(model: str, base_url: str, swap_root: str,
                  slices: dict[str, list[dict]]) -> dict:
    print(f"\n=== {model}")
    unload_all(swap_root)
    vram_idle = gpu_memory_mb()

    # cold start: first request after full unload includes model load time
    warm_probe = "Quick note, remember to water the plants tomorrow morning."
    t0 = time.perf_counter()
    extract(base_url, model, warm_probe)
    cold_start_s = round(time.perf_counter() - t0, 2)
    vram_loaded = gpu_memory_mb()
    print(f"  cold start {cold_start_s}s, VRAM {vram_idle} -> {vram_loaded} MiB")

    results = {}
    for slice_name, records in slices.items():
        rows = []
        for i, rec in enumerate(records, 1):
            try:
                output, timing = extract(base_url, model, rec["text"])
            except Exception as e:
                print(f"  [{slice_name} {i}/{len(records)}] {rec['id']} FAILED: {e}")
                rows.append({"id": rec["id"], "error": str(e)})
                continue
            rows.append({"id": rec["id"], "output": output,
                         "grade": code_grade(output), **timing})
            if i % 10 == 0 or i == len(records):
                print(f"  [{slice_name}] {i}/{len(records)}")
        results[slice_name] = rows

    ok = [r for rows in results.values() for r in rows if "output" in r]
    grade_rates = {}
    for check in next(iter(ok))["grade"]:
        grade_rates[check] = round(sum(r["grade"][check] for r in ok) / len(ok), 3)
    lat = sorted(r["latency_s"] for r in ok)
    return {
        "model": model,
        "cold_start_s": cold_start_s,
        "vram_loaded_mib": vram_loaded,
        "vram_idle_mib": vram_idle,
        "records_ok": len(ok),
        "records_failed": sum(len(rows) for rows in results.values()) - len(ok),
        "grade_rates": grade_rates,
        "latency_median_s": lat[len(lat) // 2],
        "tokens_per_s_median": sorted(r["tokens_per_s"] for r in ok if r["tokens_per_s"])[len(ok) // 2],
        "slices": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", required=True,
                        help="comma-separated llama-swap model names")
    parser.add_argument("--base-url", default="http://localhost:9292/v1")
    parser.add_argument("--slices", default="real,stt,garbled")
    parser.add_argument("--limit", type=int, default=0,
                        help="cap records per slice (0 = all)")
    args = parser.parse_args()

    swap_root = args.base_url.rsplit("/v1", 1)[0]
    slices = {}
    for name in args.slices.split(","):
        records = load_jsonl(SLICES[name])
        slices[name] = records[: args.limit] if args.limit else records
    print("slices:", {k: len(v) for k, v in slices.items()})

    conditions = [run_condition(m.strip(), args.base_url, swap_root, slices)
                  for m in args.models.split(",")]

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task": "lima-extraction-v0.3.1",
        "temperature": TEMPERATURE,
        "constrained_decoding": True,
        "system": asdict(get_system_info()),
        "conditions": conditions,
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"extraction_{stamp}.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    (RESULTS_DIR / "extraction_latest.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False))
    print(f"\nresults -> {out}")
    for c in conditions:
        print(f"  {c['model']}: cold {c['cold_start_s']}s | VRAM {c['vram_loaded_mib']} MiB | "
              f"median {c['latency_median_s']}s/memo @ {c['tokens_per_s_median']} tok/s | "
              f"grades {c['grade_rates']}")


if __name__ == "__main__":
    main()
