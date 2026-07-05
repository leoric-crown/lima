#!/usr/bin/env python3
"""Stage the STT-Voice-Notes-Evals held-out eval slice.

Source: https://huggingface.co/datasets/danielrosehill/STT-Voice-Notes-Evals
(Apache 2.0, DOI 10.57967/hf/6317). The memos are SCRIPTED readings, not
spontaneous speech — so we use the bundled raw STT outputs (real transcription
noise: punctuation loss, name mangling) as eval INPUTS, not the clean ground
truths. The ground truth text rides along as reference for the LLM judge.

This slice is eval-only. It must never be labeled for training.

Usage:
    git clone https://huggingface.co/datasets/danielrosehill/STT-Voice-Notes-Evals /tmp/stt
    python3 build_stt_eval.py --src /tmp/stt
"""

import argparse
import json
from pathlib import Path

OUT = Path(__file__).parent / "corpus" / "eval" / "eval_stt_voice_notes.jsonl"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True, type=Path)
    args = parser.parse_args()

    ground_truth = {p.stem: p.read_text().strip() for p in (args.src / "texts").glob("*.txt")}

    rows = []
    # layout: transcriptions/<provider>/<model>/raw/*.txt
    for raw_dir in sorted((args.src / "transcriptions").glob("*/*/raw")):
        system = f"{raw_dir.parent.parent.name}/{raw_dir.parent.name}"
        for txt in sorted(raw_dir.glob("*.txt")):
            memo = txt.stem
            if memo not in ground_truth:
                continue
            text = txt.read_text().strip()
            rows.append({
                "id": f"stt-{system}-{memo}",
                "memo": memo,
                "stt_system": system,
                "words": len(text.split()),
                "text": text,
                "ground_truth": ground_truth[memo],
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    systems = sorted({r["stt_system"] for r in rows})
    print(f"{len(rows)} eval rows ({len(ground_truth)} memos x {len(systems)} systems) -> {OUT}")
    print("systems:", systems)


if __name__ == "__main__":
    main()
