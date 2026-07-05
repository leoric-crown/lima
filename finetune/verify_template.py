#!/usr/bin/env python3
"""Verify the training-time chat template matches llama.cpp's serving render.

M2 trains with the HF tokenizer's chat template; M3 deploys a GGUF served by
llama.cpp --jinja. If those two renders differ on the production message shape
(system + user, generation prompt), the tuned model is trained and served on
different prompts and every M3 number is suspect. This script renders LIMA's
exact production messages both ways and diffs the strings.

Usage:
    # terminal 1 (or backgrounded): a llama-server on the GGUF under test
    llama-server -m <gguf> --jinja --port 9393 -ngl 0
    # terminal 2
    uv run verify_template.py --gguf-url http://localhost:9393 \
        [--hf-model Qwen/Qwen3-4B-Instruct-2507]
"""

import argparse
import difflib
import sys

import requests
from transformers import AutoTokenizer

sys.path.insert(0, ".")
import extraction_task  # noqa: E402

SAMPLE_TRANSCRIPT = (
    "so um quick note before I forget, need to send the deck to Laura by "
    "Thursday and uh also check whether the GPU box can take a second drive"
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hf-model", default="Qwen/Qwen3-4B-Instruct-2507")
    parser.add_argument("--gguf-url", default="http://localhost:9393")
    args = parser.parse_args()

    messages = [
        {"role": "system", "content": extraction_task.SYSTEM_MESSAGE},
        {"role": "user",
         "content": extraction_task.USER_TEMPLATE.format(transcript=SAMPLE_TRANSCRIPT)},
    ]

    tok = AutoTokenizer.from_pretrained(args.hf_model)
    hf_render = tok.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True)

    resp = requests.post(f"{args.gguf_url}/apply-template",
                         json={"messages": messages}, timeout=30)
    resp.raise_for_status()
    gguf_render = resp.json()["prompt"]

    if hf_render == gguf_render:
        print(f"MATCH: HF '{args.hf_model}' template == GGUF serving template "
              f"({len(hf_render)} chars) on the production message shape.")
        return 0

    print("MISMATCH between HF training template and GGUF serving template:\n")
    for line in difflib.unified_diff(
            hf_render.splitlines(keepends=True),
            gguf_render.splitlines(keepends=True),
            fromfile="hf_tokenizer", tofile="gguf_jinja"):
        print(line, end="")
    return 1


if __name__ == "__main__":
    sys.exit(main())
