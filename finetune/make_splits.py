#!/usr/bin/env python3
"""Meeting-level split manifest and corpus assembly. Two stages:

  real   — BEFORE labeling: reserve whole AMI/ICSI meetings for eval, select
           the train-pool chunks (capped per meeting so no single meeting
           dominates), write corpus/split_manifest.json. Chunks from an eval
           meeting can never be labeled for training.
  final  — AFTER labeling: assemble train/val from labeled files, enforcing
           the manifest (hard failure on any train row from an eval meeting),
           routing boundary garbled cells to eval, and holding out val by
           meeting (real) / by cell id (synthetic), never by row.

Usage:
    python3 make_splits.py real
    python3 make_splits.py final --labeled-real corpus/labeled_real.jsonl \
        --labeled-synthetic corpus/labeled_synthetic.jsonl
"""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

CORPUS = Path(__file__).parent / "corpus"
MANIFEST = CORPUS / "split_manifest.json"

EVAL_TARGET_CHUNKS = 30
TRAIN_POOL_SIZE = 170
MAX_PER_MEETING = 3  # caps meeting dominance (largest meeting has 20+ chunks)
VAL_FRACTION = 0.1


def load_jsonl(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def dump_jsonl(rows: list[dict], path: Path):
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def stage_real(seed: int):
    chunks = load_jsonl(CORPUS / "real_chunks.jsonl")
    rng = random.Random(seed)

    by_meeting = defaultdict(list)
    for c in chunks:
        by_meeting[c["meeting"]].append(c)

    # alternate sources so the eval slice isn't single-corpus
    ami = sorted(m for m in by_meeting if by_meeting[m][0]["source"] == "ami")
    icsi = sorted(m for m in by_meeting if by_meeting[m][0]["source"] == "icsi")
    rng.shuffle(ami)
    rng.shuffle(icsi)

    eval_meetings, eval_rows = [], []
    pools = [ami, icsi]
    i = 0
    while len(eval_rows) < EVAL_TARGET_CHUNKS and (ami or icsi):
        pool = pools[i % 2] or pools[(i + 1) % 2]
        meeting = pool.pop()
        eval_meetings.append(meeting)
        take = min(MAX_PER_MEETING, len(by_meeting[meeting]))
        eval_rows.extend(rng.sample(by_meeting[meeting], take))
        i += 1

    train_meetings = sorted(set(by_meeting) - set(eval_meetings))
    candidates = []
    for meeting in train_meetings:
        take = min(MAX_PER_MEETING, len(by_meeting[meeting]))
        candidates.extend(rng.sample(by_meeting[meeting], take))
    train_pool = rng.sample(candidates, min(TRAIN_POOL_SIZE, len(candidates)))

    dump_jsonl(eval_rows, CORPUS / "eval_real.jsonl")
    dump_jsonl(train_pool, CORPUS / "train_pool_real.jsonl")
    MANIFEST.write_text(json.dumps({
        "seed": seed,
        "eval_meetings": sorted(eval_meetings),
        "train_meetings": train_meetings,
        "eval_chunk_ids": [r["id"] for r in eval_rows],
        "train_pool_ids": [r["id"] for r in train_pool],
    }, indent=1))
    print(f"eval: {len(eval_rows)} chunks from {len(eval_meetings)} reserved meetings")
    print(f"train pool: {len(train_pool)} chunks from {len(train_meetings)} meetings")
    print(f"manifest -> {MANIFEST}")


def stage_final(labeled_real: Path, labeled_synthetic: Path, seed: int):
    manifest = json.loads(MANIFEST.read_text())
    eval_meetings = set(manifest["eval_meetings"])
    rng = random.Random(seed)

    real = load_jsonl(labeled_real)
    leaks = [r["id"] for r in real if r["meeting"] in eval_meetings]
    if leaks:
        raise SystemExit(f"LEAK: labeled train rows from eval meetings: {leaks}")
    pool = set(manifest["train_pool_ids"])
    got = {r["id"] for r in real}
    if got != pool:
        raise SystemExit(
            f"MANIFEST MISMATCH: labeled real ids != train pool "
            f"(missing {len(pool - got)}, unexpected {len(got - pool)})")

    synthetic = load_jsonl(labeled_synthetic)
    # eval-routed: declared boundary cells, plus any garbled cell the teacher
    # did NOT give the fallback label (observed: it extracts "notes" from
    # verbatim loops and polite-phrase hallucinations — a real teacher
    # weakness; such rows are eval probes, not clean training signal)
    def eval_routed(r):
        return r.get("boundary") or (
            r.get("garbled") and r["label"]["title"] != "Unclear memo"
        )
    boundary = [r for r in synthetic if eval_routed(r)]
    synthetic = [r for r in synthetic if not eval_routed(r)]

    # val held out by meeting (real) and by cell id (synthetic), never by row
    real_meetings = sorted({r["meeting"] for r in real})
    val_meetings = set(rng.sample(real_meetings, max(1, int(len(real_meetings) * VAL_FRACTION))))
    syn_ids = sorted(r["id"] for r in synthetic)
    val_syn_ids = set(rng.sample(syn_ids, max(1, int(len(syn_ids) * VAL_FRACTION))))

    train = [r for r in real if r["meeting"] not in val_meetings] + \
            [r for r in synthetic if r["id"] not in val_syn_ids]
    val = [r for r in real if r["meeting"] in val_meetings] + \
          [r for r in synthetic if r["id"] in val_syn_ids]
    rng.shuffle(train)

    dump_jsonl(train, CORPUS / "train.jsonl")
    dump_jsonl(val, CORPUS / "val.jsonl")
    boundary_path = CORPUS / "eval" / "eval_boundary_garbled.jsonl"
    if boundary:
        dump_jsonl(boundary, boundary_path)
    elif boundary_path.exists():
        boundary_path.unlink()  # stale from a prior assembly
    print(f"train: {len(train)}  val: {len(val)}  boundary->eval: {len(boundary)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["real", "final"])
    parser.add_argument("--labeled-real", type=Path, default=CORPUS / "labeled_real.jsonl")
    parser.add_argument("--labeled-synthetic", type=Path, default=CORPUS / "labeled_synthetic.jsonl")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.stage == "real":
        stage_real(args.seed)
    else:
        stage_final(args.labeled_real, args.labeled_synthetic, args.seed)


if __name__ == "__main__":
    main()
