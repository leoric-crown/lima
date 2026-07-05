#!/usr/bin/env python3
"""LLM-judge pass over benchmark_extraction.py results.

Scores each extraction output against its SOURCE TRANSCRIPT (not against the
teacher's output — that would make the teacher unfalsifiable). The judge must
come from a different model family than the teacher (default: gemma-3-27b vs
the Qwen teacher) and runs with constrained decoding on the judge schema.

Rubric per output:
- title_quality, summary_quality: 1-5 (grounded, specific, faithful)
- action_items_expected: action items a careful human would extract
- action_items_captured: of those, how many the output captured
- hallucinated_items: key_points/action_items/questions NOT grounded in the
  transcript (the metric the production prompt's rule 1 cares most about)
- fallback_appropriate: whether emitting/withholding the fallback was right

Aggregates per condition and slice: mean quality, action-item recall,
hallucination rate, fallback accuracy.

Usage:
    uv run judge_extraction.py benchmark_results/extraction_latest.json
    uv run judge_extraction.py <results.json> --judge-model gemma-3-27b
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "finetune"))

CORPUS = Path(__file__).parent.parent / "finetune" / "corpus"
RESULTS_DIR = Path(__file__).parent / "benchmark_results"

SLICE_FILES = {
    "real": CORPUS / "eval_real.jsonl",
    "stt": CORPUS / "eval" / "eval_stt_voice_notes.jsonl",
    "garbled": CORPUS / "eval" / "eval_boundary_garbled.jsonl",
}

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "title_quality": {"type": "integer", "minimum": 1, "maximum": 5},
        "summary_quality": {"type": "integer", "minimum": 1, "maximum": 5},
        "action_items_expected": {"type": "integer", "minimum": 0},
        "action_items_captured": {"type": "integer", "minimum": 0},
        "hallucinated_items": {"type": "integer", "minimum": 0},
        "fallback_appropriate": {"type": "boolean"},
        "notes": {"type": "string"},
    },
    "required": ["title_quality", "summary_quality", "action_items_expected",
                 "action_items_captured", "hallucinated_items",
                 "fallback_appropriate", "notes"],
    "additionalProperties": False,
}

JUDGE_SYSTEM = """You are a strict evaluator of a voice-memo extraction system. You receive a raw voice memo transcript (possibly disfluent, noisy, or unintelligible) and a JSON note extracted from it. Judge ONLY faithfulness to the transcript — never reward invented specifics.

Scoring guide:
- title_quality / summary_quality: 5 = specific, faithful, captures the point; 3 = generic but not wrong; 1 = misleading or fabricated.
- action_items_expected: count the tasks/next-steps a careful human would extract from the transcript (0 if none or unintelligible).
- action_items_captured: how many of THOSE appear in the output's action_items (paraphrase ok).
- hallucinated_items: count entries across key_points, action_items, and questions that are NOT grounded in the transcript.
- fallback_appropriate: the correct fallback for unintelligible input is exactly title "Unclear memo" with empty lists. True if the output correctly used the fallback for garbage input OR correctly did NOT use it for extractable input. False otherwise (fallback on a valid memo, or a confident note from garbage).
- notes: one short sentence, the biggest problem if any."""

JUDGE_TEMPLATE = """TRANSCRIPT:
{transcript}

EXTRACTED NOTE (JSON):
{output}

Evaluate per the scoring guide."""


def load_jsonl(path: Path) -> dict[str, dict]:
    with path.open() as f:
        return {r["id"]: r for r in (json.loads(l) for l in f if l.strip())}


def judge_one(base_url: str, model: str, transcript: str, output: dict) -> dict:
    resp = requests.post(
        f"{base_url}/chat/completions",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": JUDGE_TEMPLATE.format(
                    transcript=transcript,
                    output=json.dumps(output, ensure_ascii=False))},
            ],
            "temperature": 0.0,
            "max_tokens": 512,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "judgement", "strict": True,
                                "schema": JUDGE_SCHEMA},
            },
        },
        timeout=600,
    )
    resp.raise_for_status()
    return json.loads(resp.json()["choices"][0]["message"]["content"])


def aggregate(rows: list[dict]) -> dict:
    judged = [r["judgement"] for r in rows if "judgement" in r]
    if not judged:
        return {}
    expected = sum(j["action_items_expected"] for j in judged)
    captured = sum(min(j["action_items_captured"], j["action_items_expected"])
                   for j in judged)
    return {
        "n": len(judged),
        "title_quality_mean": round(sum(j["title_quality"] for j in judged) / len(judged), 2),
        "summary_quality_mean": round(sum(j["summary_quality"] for j in judged) / len(judged), 2),
        "action_item_recall": round(captured / expected, 3) if expected else None,
        "hallucinated_per_memo": round(sum(j["hallucinated_items"] for j in judged) / len(judged), 2),
        "fallback_accuracy": round(sum(j["fallback_appropriate"] for j in judged) / len(judged), 3),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--judge-model", default="gemma-3-27b")
    parser.add_argument("--base-url", default="http://localhost:9292/v1")
    args = parser.parse_args()

    report = json.loads(args.results.read_text())
    transcripts = {}
    for name, path in SLICE_FILES.items():
        if path.exists():
            transcripts[name] = load_jsonl(path)

    teacher_families = ("qwen",)
    if any(fam in args.judge_model.lower() for fam in teacher_families):
        print(f"WARNING: judge '{args.judge_model}' shares the teacher's model "
              f"family — scores will not be family-independent.")

    for condition in report["conditions"]:
        print(f"\n=== judging {condition['model']} with {args.judge_model}")
        for slice_name, rows in condition["slices"].items():
            for i, row in enumerate(rows, 1):
                if "output" not in row or "judgement" in row:
                    continue
                transcript = transcripts[slice_name][row["id"]]["text"]
                try:
                    row["judgement"] = judge_one(
                        args.base_url, args.judge_model, transcript, row["output"])
                except Exception as e:
                    print(f"  [{slice_name} {i}] {row['id']} judge FAILED: {e}")
                if i % 10 == 0 or i == len(rows):
                    print(f"  [{slice_name}] {i}/{len(rows)}")
            condition.setdefault("judged", {})[slice_name] = aggregate(rows)
        condition["judged"]["all"] = aggregate(
            [r for rows in condition["slices"].values() for r in rows])

    report["judge"] = {"model": args.judge_model,
                       "judged_at": datetime.now(timezone.utc).isoformat()}
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"extraction_judged_{stamp}.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(f"\njudged results -> {out}")
    for c in report["conditions"]:
        print(f"  {c['model']}: {c['judged']['all']}")


if __name__ == "__main__":
    main()
