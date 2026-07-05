#!/usr/bin/env python3
"""LLM-judge pass over benchmark_extraction.py results — two-phase design.

Phase 1 (reference): for every eval transcript, the judge extracts the
expected action items ONCE, blind to any model's output. Cached in
benchmark_results/judge_reference.json. This is the fix for judge anchoring:
a judge that defines "expected" while reading a model's answer produces a
different ground truth per model (verified: 85/82/104 expected items on
identical inputs across three models).

Phase 2 (grading): each model output is scored against the transcript plus
the FIXED reference list. Recall denominators are computed in code from the
reference, never by the judge.

The judge must come from a different model family than the teacher (default
gemma-3-27b vs the Qwen teacher). Constrained decoding ON for both phases.

Aggregation notes:
- The stt slice is 16 memos x 4 STT systems = 64 rows that are NOT
  independent; it is aggregated per memo first, then across memos (n=16).
- Quality scores (1-5) saturate on easy slices; the discriminating metrics
  are hallucinated_items, action-item recall, and the code grades.

Usage:
    uv run judge_extraction.py benchmark_results/extraction_latest.json
    uv run judge_extraction.py <results.json> --judge-model gemma-3-27b
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "finetune"))

CORPUS = Path(__file__).parent.parent / "finetune" / "corpus"
RESULTS_DIR = Path(__file__).parent / "benchmark_results"
REFERENCE_PATH = RESULTS_DIR / "judge_reference.json"

SLICE_FILES = {
    "real": CORPUS / "eval_real.jsonl",
    "stt": CORPUS / "eval" / "eval_stt_voice_notes.jsonl",
    "garbled": CORPUS / "eval" / "eval_boundary_garbled.jsonl",
}

REF_SCHEMA = {
    "type": "object",
    "properties": {
        "action_items": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["action_items"],
    "additionalProperties": False,
}

REF_SYSTEM = """You are a careful analyst. Given a raw voice memo transcript (possibly disfluent, noisy, or unintelligible), list the action items a careful human would extract: concrete tasks or next steps the speaker intends, commits to, or requests. Paraphrase each concisely. Do NOT include facts, observations, or questions. If the transcript contains none, or is unintelligible, return an empty list."""

REF_TEMPLATE = """TRANSCRIPT:
{transcript}

List the action items."""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "title_quality": {"type": "integer", "minimum": 1, "maximum": 5},
        "summary_quality": {"type": "integer", "minimum": 1, "maximum": 5},
        "action_items_captured": {"type": "integer", "minimum": 0},
        "hallucinated_items": {"type": "integer", "minimum": 0},
        "fallback_appropriate": {"type": "boolean"},
        "notes": {"type": "string"},
    },
    "required": ["title_quality", "summary_quality", "action_items_captured",
                 "hallucinated_items", "fallback_appropriate", "notes"],
    "additionalProperties": False,
}

JUDGE_SYSTEM = """You are a strict evaluator of a voice-memo extraction system. You receive a raw voice memo transcript, a REFERENCE list of expected action items (prepared independently), and a JSON note extracted by a model. Judge ONLY faithfulness to the transcript — never reward invented specifics.

Scoring guide:
- title_quality / summary_quality: 5 = specific, faithful, captures the point; 3 = generic but not wrong; 1 = misleading or fabricated.
- action_items_captured: how many of the REFERENCE action items appear in the output's action_items (paraphrase counts; count each reference item at most once).
- hallucinated_items: count entries across key_points, action_items, and questions that are NOT grounded in the transcript.
- fallback_appropriate: the correct fallback for unintelligible input is exactly title "Unclear memo" with empty lists. True if the output correctly used the fallback for garbage input OR correctly did NOT use it for extractable input. False otherwise.
- notes: one short sentence, the biggest problem if any."""

JUDGE_TEMPLATE = """TRANSCRIPT:
{transcript}

REFERENCE ACTION ITEMS (expected; may be empty):
{reference}

EXTRACTED NOTE (JSON):
{output}

Evaluate per the scoring guide."""


def load_jsonl(path: Path) -> dict[str, dict]:
    with path.open() as f:
        return {r["id"]: r for r in (json.loads(l) for l in f if l.strip())}


def chat_json(base_url: str, model: str, system: str, user: str, schema: dict) -> dict:
    resp = requests.post(
        f"{base_url}/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": 0.0,
            "max_tokens": 512,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "judgement", "strict": True, "schema": schema},
            },
        },
        timeout=600,
    )
    resp.raise_for_status()
    return json.loads(resp.json()["choices"][0]["message"]["content"])


def build_reference(base_url: str, model: str,
                    transcripts: dict[str, dict[str, dict]]) -> dict[str, list[str]]:
    """Phase 1: blind expected-action-item extraction, cached across runs."""
    cache = {"judge_model": model, "refs": {}}
    if REFERENCE_PATH.exists():
        prior = json.loads(REFERENCE_PATH.read_text())
        if prior.get("judge_model") == model:
            cache = prior
    refs = cache["refs"]
    todo = [(sl, rid, rec) for sl, recs in transcripts.items()
            for rid, rec in recs.items() if rid not in refs]
    print(f"reference: {len(refs)} cached, {len(todo)} to build")
    for n, (sl, rid, rec) in enumerate(todo, 1):
        refs[rid] = chat_json(base_url, model, REF_SYSTEM,
                              REF_TEMPLATE.format(transcript=rec["text"]),
                              REF_SCHEMA)["action_items"]
        if n % 10 == 0 or n == len(todo):
            print(f"  reference {n}/{len(todo)}")
            REFERENCE_PATH.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
    REFERENCE_PATH.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
    return refs


def aggregate(rows: list[dict], cluster_of: dict[str, str] | None = None) -> dict:
    """Aggregate judged rows; with cluster_of, average within clusters first."""
    judged = [r for r in rows if "judgement" in r]
    if not judged:
        return {}

    def stats(group: list[dict]) -> dict:
        expected = sum(r["expected_action_items"] for r in group)
        captured = sum(min(r["judgement"]["action_items_captured"],
                           r["expected_action_items"]) for r in group)
        return {
            "title_quality_mean": sum(r["judgement"]["title_quality"] for r in group) / len(group),
            "summary_quality_mean": sum(r["judgement"]["summary_quality"] for r in group) / len(group),
            "action_item_recall": captured / expected if expected else None,
            "hallucinated_per_memo": sum(r["judgement"]["hallucinated_items"] for r in group) / len(group),
            "fallback_accuracy": sum(r["judgement"]["fallback_appropriate"] for r in group) / len(group),
        }

    if cluster_of:
        clusters = defaultdict(list)
        for r in judged:
            clusters[cluster_of.get(r["id"], r["id"])].append(r)
        per_cluster = [stats(g) for g in clusters.values()]
        n_key = {"n_clusters": len(clusters), "n_rows": len(judged)}
        merged = {}
        for key in per_cluster[0]:
            vals = [c[key] for c in per_cluster if c[key] is not None]
            merged[key] = round(sum(vals) / len(vals), 3) if vals else None
        return {**n_key, **merged}

    s = stats(judged)
    return {"n": len(judged), **{k: (round(v, 3) if v is not None else None)
                                 for k, v in s.items()}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--judge-model", default="gemma-3-27b")
    parser.add_argument("--base-url", default="http://localhost:9292/v1")
    args = parser.parse_args()

    report = json.loads(args.results.read_text())
    transcripts = {name: load_jsonl(path)
                   for name, path in SLICE_FILES.items() if path.exists()}

    teacher_families = ("qwen",)
    if any(fam in args.judge_model.lower() for fam in teacher_families):
        print(f"WARNING: judge '{args.judge_model}' shares the teacher's model "
              f"family — scores will not be family-independent.")

    refs = build_reference(args.base_url, args.judge_model, transcripts)

    # stt rows cluster by underlying memo (16 memos x 4 STT systems)
    stt_cluster = {rid: rec.get("memo", rid)
                   for rid, rec in transcripts.get("stt", {}).items()}

    for condition in report["conditions"]:
        print(f"\n=== judging {condition['model']} with {args.judge_model}")
        for slice_name, rows in condition["slices"].items():
            for i, row in enumerate(rows, 1):
                if "output" not in row or "judgement" in row:
                    continue
                rec = transcripts[slice_name][row["id"]]
                reference = refs[row["id"]]
                row["expected_action_items"] = len(reference)
                ref_text = "\n".join(f"- {a}" for a in reference) or "(none)"
                try:
                    row["judgement"] = chat_json(
                        args.base_url, args.judge_model, JUDGE_SYSTEM,
                        JUDGE_TEMPLATE.format(
                            transcript=rec["text"], reference=ref_text,
                            output=json.dumps(row["output"], ensure_ascii=False)),
                        JUDGE_SCHEMA)
                except Exception as e:
                    print(f"  [{slice_name} {i}] {row['id']} judge FAILED: {e}")
                if i % 10 == 0 or i == len(rows):
                    print(f"  [{slice_name}] {i}/{len(rows)}")
            cluster = stt_cluster if slice_name == "stt" else None
            condition.setdefault("judged", {})[slice_name] = aggregate(rows, cluster)
        condition["judged"]["all_rows_unclustered"] = aggregate(
            [r for rows in condition["slices"].values() for r in rows])

    report["judge"] = {
        "model": args.judge_model,
        "design": "two-phase: blind reference action items, then grading",
        "judged_at": datetime.now(timezone.utc).isoformat(),
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"extraction_judged_{stamp}.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(f"\njudged results -> {out}")
    for c in report["conditions"]:
        print(f"  {c['model']}:")
        for sl, agg in c["judged"].items():
            print(f"    {sl}: {agg}")


if __name__ == "__main__":
    main()
