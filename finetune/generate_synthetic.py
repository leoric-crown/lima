#!/usr/bin/env python3
"""Generate synthetic voice-memo transcripts with the teacher model.

Two-stage pipeline per seed cell (the disfluency-injection pass is separate
from content generation on purpose — single-pass "write a disfluent memo"
collapses into the same few stock phrasings):

  1. content: fluent first-person spoken-register memo from a
     persona x topic x length x mood x setting cell
  2. injection: rewrite with disfluencies at the cell's density level

Garbled memos (production-fallback trainers) are generated single-pass.

Resumable: appends to --out, skips cell ids already present.

Usage:
    python3 generate_synthetic.py --count 260 [--out corpus/synthetic_memos.jsonl]
"""

import argparse
import json
import random
import re
from pathlib import Path

import llm
import seeds

TEACHER_MODEL = "qwen3-coder-30b"

# bump whenever prompts/seeds/logic change: resume skips only rows whose
# gen_version matches, so stale rows from older code get regenerated
GEN_VERSION = 3

CONTENT_SYSTEM = (
    "You write realistic voice memo transcripts used to test a transcription pipeline. "
    "Output only the transcript text — no headings, no quotes, no commentary."
)

CONTENT_TEMPLATE = """Write the transcript of a voice memo recorded by {persona}, {setting}, feeling {mood}.

Topic: {topic}.
Length: roughly {min_words}-{max_words} words. Do NOT exceed {max_words} words.

It must read like natural spoken language: first person, a bit meandering, with concrete specific details (names, numbers, days, places) invented to fit the persona. Plain fluent speech for now — no disfluencies yet. Output ONLY the transcript."""

INJECT_TEMPLATE = """Rewrite this voice memo transcript to sound like genuinely spontaneous speech as captured by speech-to-text. Insert {level_instruction}. Keep every fact and detail intact; do not add or remove content beyond the inserted disfluencies. The rewritten transcript must stay close to the original length — absolutely no longer than {word_cap} words. Output ONLY the rewritten transcript.

TRANSCRIPT:
{text}"""

LOOP_SEED_PROMPT = """Write ONE short plausible spoken sentence (8-15 words) on any mundane everyday topic. Output ONLY the sentence."""


def build_cells(count: int, garbled_count: int, rng: random.Random) -> list[dict]:
    pairs = [(p, t) for p in seeds.PERSONAS for t in seeds.TOPICS]
    rng.shuffle(pairs)
    length_names = [l[0] for l in seeds.LENGTHS]
    length_weights = [l[3] for l in seeds.LENGTHS]
    disf_names = [d[0] for d in seeds.DISFLUENCY_LEVELS]
    disf_weights = [d[1] for d in seeds.DISFLUENCY_LEVELS]

    cells = []
    for i, (persona, topic) in enumerate(pairs[:count]):
        cells.append(
            {
                "id": f"syn-{i:04d}",
                "persona": persona,
                "topic": topic,
                "length": rng.choices(length_names, weights=length_weights)[0],
                "disfluency": rng.choices(disf_names, weights=disf_weights)[0],
                "mood": rng.choice(seeds.MOODS),
                "setting": rng.choice(seeds.SETTINGS),
            }
        )
    for i in range(garbled_count):
        spec = seeds.GARBLED_CELLS[i % len(seeds.GARBLED_CELLS)]
        cell = {"id": f"syn-garbled-{i:02d}", "garbled": True, **spec}
        if spec["mode"] == "polite":
            # composed in code — Whisper hallucinates these strings verbatim
            parts = rng.choices(seeds.POLITE_HALLUCINATIONS, k=rng.randint(3, 6))
            cell["text_prebaked"] = " ".join(parts)
        cells.append(cell)
    return cells


def trim_dangling(text: str) -> str:
    """Drop a trailing unclosed [marker fragment left by max_tokens truncation."""
    return re.sub(r"\[[^\]]*$", "", text).strip()


def generate(cell: dict, rng: random.Random) -> str:
    if cell.get("garbled"):
        if "text_prebaked" in cell:
            return cell["text_prebaked"]
        if cell["mode"] == "loop":
            sentence = llm.chat(
                [{"role": "system", "content": CONTENT_SYSTEM},
                 {"role": "user", "content": LOOP_SEED_PROMPT}],
                model=TEACHER_MODEL, temperature=1.0, max_tokens=60,
            ).strip()
            return " ".join([sentence] * cell["repeats"])
        return trim_dangling(llm.chat(
            [{"role": "system", "content": CONTENT_SYSTEM},
             {"role": "user", "content": cell["prompt"]}],
            model=TEACHER_MODEL, temperature=1.0, max_tokens=200,
        ).strip())

    length = next(l for l in seeds.LENGTHS if l[0] == cell["length"])
    level = next(d for d in seeds.DISFLUENCY_LEVELS if d[0] == cell["disfluency"])
    min_words, max_words = length[1], length[2]

    def content_pass(temperature: float) -> str:
        return llm.chat(
            [{"role": "system", "content": CONTENT_SYSTEM},
             {"role": "user", "content": CONTENT_TEMPLATE.format(
                 persona=cell["persona"], setting=cell["setting"], mood=cell["mood"],
                 topic=cell["topic"], min_words=min_words, max_words=max_words)}],
            model=TEACHER_MODEL, temperature=temperature,
            max_tokens=int(max_words * 2),  # ~1.3 tokens/word + headroom, stops runaways
        ).strip()

    fluent = content_pass(0.9)
    wc = len(fluent.split())
    if not (min_words * 0.5 <= wc <= max_words * 1.3):
        fluent = content_pass(0.7)  # one retry, steadier temperature

    def inject_pass(temperature: float) -> str:
        return llm.chat(
            [{"role": "system", "content": CONTENT_SYSTEM},
             {"role": "user", "content": INJECT_TEMPLATE.format(
                 level_instruction=level[2], text=fluent,
                 word_cap=int(max_words * 1.4))}],
            model=TEACHER_MODEL, temperature=temperature,
            max_tokens=int(max_words * 3),  # injection adds ~10-25% words
        ).strip()

    # final gate on what actually gets labeled: injection can shrink, balloon,
    # or go off-script, and the fluent-draft check can't see that
    result = inject_pass(0.7)
    wc = len(result.split())
    if not (min_words * 0.5 <= wc <= max_words * 1.5):
        result = inject_pass(0.5)
        wc = len(result.split())
        if not (min_words * 0.5 <= wc <= max_words * 1.5):
            raise ValueError(f"length out of band after retry: {wc}w for {cell['length']}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=260)
    parser.add_argument("--garbled", type=int, default=seeds.GARBLED_COUNT)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "corpus" / "synthetic_memos.jsonl")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    cells = build_cells(args.count, args.garbled, rng)

    done = set()
    if args.out.exists():
        with args.out.open() as f:
            done = {
                r["id"]
                for r in (json.loads(line) for line in f if line.strip())
                if r.get("gen_version") == GEN_VERSION
            }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a") as f:
        for n, cell in enumerate(cells, 1):
            if cell["id"] in done:
                continue
            try:
                text = generate(cell, rng)
            except Exception as e:  # keep the batch alive; rerun picks up the gap
                print(f"[{n}/{len(cells)}] {cell['id']} FAILED: {e}", flush=True)
                continue
            meta = {k: v for k, v in cell.items() if k not in ("prompt", "text_prebaked")}
            record = {**meta, "gen_version": GEN_VERSION, "words": len(text.split()), "text": text}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{n}/{len(cells)}] {cell['id']} ok ({record['words']}w)", flush=True)


if __name__ == "__main__":
    main()
