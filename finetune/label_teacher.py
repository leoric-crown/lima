#!/usr/bin/env python3
"""Label memo transcripts with the teacher model under the production task.

Runs LIMA's exact production extraction (system message + user template +
JSON Schema from extraction_task.py) with llama.cpp schema-constrained
decoding ON — the same condition every eval run uses.

Input: JSONL with at least {"id": ..., "text": ...}.
Output: input record + {"label": {...}, "teacher": model} per line.
Resumable: appends to --out, skips ids already labeled.

Usage:
    python3 label_teacher.py --input corpus/synthetic_memos.jsonl --out corpus/labeled_synthetic.jsonl
"""

import argparse
import json
from pathlib import Path

import extraction_task
import llm

TEACHER_MODEL = "qwen3-coder-30b"
TEMPERATURE = 0.2

# bump when the prompt/schema/teacher changes; resume regenerates non-matching rows
LABEL_VERSION = 1


def label(text: str) -> dict:
    raw = llm.chat(
        [
            {"role": "system", "content": extraction_task.SYSTEM_MESSAGE},
            {"role": "user", "content": extraction_task.USER_TEMPLATE.format(transcript=text)},
        ],
        model=TEACHER_MODEL,
        temperature=TEMPERATURE,
        response_schema=extraction_task.SCHEMA,
    )
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=0, help="label at most N records (0 = all)")
    args = parser.parse_args()

    with args.input.open() as f:
        records = [json.loads(line) for line in f if line.strip()]
    if args.limit:
        records = records[: args.limit]

    done = set()
    if args.out.exists():
        with args.out.open() as f:
            done = {
                r["id"]
                for r in (json.loads(line) for line in f if line.strip())
                if r.get("label_version") == LABEL_VERSION
            }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a") as f:
        for n, record in enumerate(records, 1):
            if record["id"] in done:
                continue
            try:
                result = label(record["text"])
            except Exception as e:
                print(f"[{n}/{len(records)}] {record['id']} FAILED: {e}", flush=True)
                continue
            f.write(json.dumps({**record, "label": result, "teacher": TEACHER_MODEL,
                                "label_version": LABEL_VERSION},
                               ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{n}/{len(records)}] {record['id']} ok", flush=True)


if __name__ == "__main__":
    main()
