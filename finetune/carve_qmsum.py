#!/usr/bin/env python3
"""Carve monologue-ish chunks from QMSum's AMI/ICSI meeting transcripts.

Produces the real-speech portion of the extraction-distillation corpus:
long single-speaker stretches of genuinely spontaneous, disfluent speech,
shaped like 1-5 minute voice memos.

Strategy ("B" from the 2026-07-04 carving analysis): merge adjacent
same-speaker turns, skipping at most one intervening turn of <= 10 words
(backchannels like "Yeah.", "Mm-hmm."); keep chunks of 150-600 words,
splitting longer runs. Committee transcripts are excluded — prepared
parliamentary speech, near-zero disfluency, wrong register for voice memos.

Source data: QMSum (Yale-LILY, MIT) bundling AMI + ICSI transcripts
(both CC BY 4.0, https://groups.inf.ed.ac.uk/ami/). See corpus/README.md
for the full attribution block.

Usage:
    python3 carve_qmsum.py --qmsum /path/to/QMSum [--out corpus/real_chunks.jsonl]
"""

import argparse
import json
import random
import re
from pathlib import Path

MIN_WORDS = 150
MAX_WORDS = 600
MAX_INTERJECTION_WORDS = 10
MAX_SKIPPED_TURNS = 1

# {disfmarker}, {vocalsound}, {gap}, {pause}, ... — AMI/ICSI transcription markup
MARKUP_RE = re.compile(r"\{[a-z_ ]+\}")
# spaced punctuation left by the AMI/ICSI tokenization: "word ," -> "word,"
DETOK_RE = re.compile(r"\s+([,.?!;:%])")
# spaced contractions: "we 're" -> "we're", "Jane 's" -> "Jane's"
APOSTROPHE_RE = re.compile(r"\s+'(\w)")


def clean(text: str) -> str:
    text = MARKUP_RE.sub("", text)
    text = DETOK_RE.sub(r"\1", text)
    text = APOSTROPHE_RE.sub(r"'\1", text)
    return re.sub(r"\s+", " ", text).strip()


def word_count(text: str) -> int:
    return len(text.split())


def merge_runs(turns: list[dict]) -> list[dict]:
    """Merge same-speaker runs across short backchannel interjections."""
    runs = []
    i = 0
    while i < len(turns):
        speaker = turns[i]["speaker"]
        parts = [turns[i]["content"]]
        j = i + 1
        while j < len(turns):
            if turns[j]["speaker"] == speaker:
                parts.append(turns[j]["content"])
                j += 1
                continue
            # allow skipping up to MAX_SKIPPED_TURNS short interjections
            skipped = 0
            k = j
            while (
                k < len(turns)
                and turns[k]["speaker"] != speaker
                and skipped < MAX_SKIPPED_TURNS
                and word_count(turns[k]["content"]) <= MAX_INTERJECTION_WORDS
            ):
                skipped += 1
                k += 1
            if k < len(turns) and turns[k]["speaker"] == speaker:
                parts.append(turns[k]["content"])  # interjection text dropped
                j = k + 1
            else:
                break
        runs.append({"speaker": speaker, "text": " ".join(parts)})
        i = j
    return runs


def split_run(text: str) -> list[str]:
    """Split an over-long run into <= MAX_WORDS pieces at sentence-ish bounds.

    Punctuation-poor runs (heavy disfluency = sparse sentence bounds) fall back
    to even word windows — without this, any piece the sentence pass can't
    shrink under MAX_WORDS would later fail the length filter and be silently
    dropped, biasing the corpus against exactly the ugliest STT-like speech.
    """
    words = text.split()
    if len(words) <= MAX_WORDS:
        return [text]
    pieces, current = [], []
    for sentence in re.split(r"(?<=[.?!])\s+", text):
        if current and word_count(" ".join(current)) + word_count(sentence) > MAX_WORDS:
            pieces.append(" ".join(current))
            current = []
        current.append(sentence)
    if current:
        pieces.append(" ".join(current))

    final = []
    for piece in pieces:
        w = piece.split()
        if len(w) <= MAX_WORDS:
            final.append(piece)
        else:
            n_windows = -(-len(w) // MAX_WORDS)
            size = -(-len(w) // n_windows)
            final.extend(" ".join(w[i : i + size]) for i in range(0, len(w), size))
    return final


def carve(qmsum_root: Path) -> list[dict]:
    chunks = []
    for domain, corpus_name in (("Product", "ami"), ("Academic", "icsi")):
        for meeting_file in sorted((qmsum_root / "data" / domain / "all").glob("*.json")):
            meeting = json.loads(meeting_file.read_text())
            turns = [
                {"speaker": t["speaker"], "content": clean(t["content"])}
                for t in meeting["meeting_transcripts"]
            ]
            turns = [t for t in turns if t["content"]]
            for run in merge_runs(turns):
                for piece in split_run(run["text"]):
                    wc = word_count(piece)
                    if MIN_WORDS <= wc <= MAX_WORDS:
                        chunks.append(
                            {
                                "id": f"{corpus_name}-{meeting_file.stem}-{len(chunks):04d}",
                                "source": corpus_name,
                                "meeting": meeting_file.stem,
                                "speaker": run["speaker"],
                                "words": wc,
                                # mid-conversation resumptions start lowercase
                                # ("wasn't it? Okay so..."); lets eval slice by
                                # clipped-start vs clean-start later
                                "starts_clean": piece[0].isupper(),
                                "text": piece,
                            }
                        )
    return chunks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qmsum", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "corpus" / "real_chunks.jsonl")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    chunks = carve(args.qmsum)
    random.Random(args.seed).shuffle(chunks)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    meetings = {c["meeting"] for c in chunks}
    by_source = {}
    for c in chunks:
        by_source[c["source"]] = by_source.get(c["source"], 0) + 1
    print(f"carved {len(chunks)} chunks from {len(meetings)} meetings -> {args.out}")
    print(f"  by source: {by_source}")
    lengths = sorted(c["words"] for c in chunks)
    print(f"  words: min {lengths[0]}, median {lengths[len(lengths)//2]}, max {lengths[-1]}")


if __name__ == "__main__":
    main()
