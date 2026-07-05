#!/usr/bin/env python3
"""Normalize teacher labels to the production tag contract.

Constrained decoding enforces the schema's *structure*, but the field
descriptions ("2-5 lowercase kebab-case tags") are only prompt guidance — the
teacher violates them in ~9% of labels (underscores, spaces, uppercase
acronyms, 6+ tags). Training on those rows would teach the student to fail
the very contract the benchmark measures.

This is a deterministic post-processor — the same one production could apply
— so the student learns the contract, not the teacher's slip-ups. Raw teacher
labels stay untouched on disk; normalized copies are written alongside and
make_splits.py consumes them.

Rules (tags only; other fields untouched):
  lowercase -> [_ and whitespace] -> "-" -> strip non [a-z0-9-] -> collapse
  "-" runs -> dedupe (order-preserving) -> cap at 5.
Fallback rows (title == "Unclear memo") are exempt: their single
"needs-review" tag is the production contract.

Usage:
    python3 normalize_labels.py   # processes both labeled files
"""

import json
import re
from pathlib import Path

CORPUS = Path(__file__).parent / "corpus"
FILES = ["labeled_synthetic.jsonl", "labeled_real.jsonl"]
FALLBACK_TITLE = "Unclear memo"


def normalize_tag(tag: str) -> str:
    tag = tag.strip().lower()
    tag = re.sub(r"[_\s]+", "-", tag)
    tag = re.sub(r"[^a-z0-9-]", "", tag)
    tag = re.sub(r"-{2,}", "-", tag).strip("-")
    return tag


def normalize_tags(tags: list[str]) -> list[str]:
    seen, out = set(), []
    for tag in tags:
        norm = normalize_tag(tag)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out[:5]


def main():
    for name in FILES:
        src = CORPUS / name
        dst = CORPUS / name.replace(".jsonl", "_normalized.jsonl")
        changed = still_short = 0
        rows = []
        with src.open() as f:
            for line in f:
                r = json.loads(line)
                if r["label"]["title"] != FALLBACK_TITLE:
                    norm = normalize_tags(r["label"]["tags"])
                    if norm != r["label"]["tags"]:
                        changed += 1
                        r["label"]["tags"] = norm
                        r["tags_normalized"] = True
                    if len(norm) < 2:
                        still_short += 1
                rows.append(r)
        with dst.open("w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{name}: {len(rows)} rows, {changed} normalized, "
              f"{still_short} still <2 tags (not repaired) -> {dst.name}")


if __name__ == "__main__":
    main()
