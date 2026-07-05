#!/usr/bin/env python3
"""Merge a QLoRA adapter into full-precision base weights (M3 step 1).

Loads the base model in bf16 (NOT 4-bit — merging into quantized weights
bakes NF4 rounding into the checkpoint), applies the adapter, merges, and
saves an HF checkpoint ready for llama.cpp's convert_hf_to_gguf.py.

Usage:
    uv run merge_adapter.py --adapter runs/qlora-r16-a32-qv/adapter \
        --out runs/qlora-r16-a32-qv/merged
"""

import argparse
import json
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    base = json.loads((args.adapter / "adapter_config.json").read_text())[
        "base_model_name_or_path"]
    print(f"base: {base}")

    model = AutoModelForCausalLM.from_pretrained(
        base, dtype=torch.bfloat16, device_map="cpu")
    model = PeftModel.from_pretrained(model, str(args.adapter))
    model = model.merge_and_unload()
    model.save_pretrained(str(args.out))
    AutoTokenizer.from_pretrained(str(args.adapter)).save_pretrained(str(args.out))
    print(f"merged bf16 checkpoint -> {args.out}")


if __name__ == "__main__":
    main()
