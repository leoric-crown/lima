#!/usr/bin/env python3
"""QLoRA fine-tune of the LIMA extraction student (M2).

Distills the teacher-labeled corpus into Qwen3-4B-Instruct-2507 under the
EXACT production task: prompts are built from extraction_task.py (system
message + user template, the same single source of truth the teacher labeler
and the benchmark harness import) and rendered with the model's own chat
template. The assistant target is the normalized teacher label as compact
JSON; loss is computed on the completion only — prompt tokens are masked.

Recipe (fixed, one run, no sweep — per M2 scope):
- NF4 4-bit base via bitsandbytes (double quant, bf16 compute)
- LoRA r=16, alpha=32, q_proj/v_proj only, dropout 0.05
- paged 8-bit AdamW, lr 2e-4 cosine, 3 epochs, effective batch 16

Before trusting anything downstream, verify the chat template with
verify_template.py (HF render vs llama.cpp --jinja render of the GGUF).

Usage:
    uv run train_qlora.py                      # defaults: corpus/, runs/
    uv run train_qlora.py --epochs 3 --out runs/qlora-r16-a32-qv
"""

import argparse
import json
import sys
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
    set_seed,
)

sys.path.insert(0, str(Path(__file__).parent))
import extraction_task  # noqa: E402

BASE_MODEL = "Qwen/Qwen3-4B-Instruct-2507"
CORPUS = Path(__file__).parent / "corpus"
MAX_LEN = 4096
SEED = 42


def load_jsonl(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


NEWLINE_ID = 198  # trailing "\n" the template emits after a closed turn


def build_example(tokenizer, record: dict) -> dict:
    """Tokenize one (transcript, label) pair with completion-only loss masking.

    Built the way generation actually sees it: the chat-template prompt render
    (up to and including "<|im_start|>assistant\\n"), then the JSON label
    tokenized on its own, then <|im_end|>. Only the completion tokens carry
    loss. Each example is asserted against the template's own full-conversation
    render (which adds one trailing newline) so the construction can never
    drift from the template.
    """
    messages = [
        {"role": "system", "content": extraction_task.SYSTEM_MESSAGE},
        {"role": "user",
         "content": extraction_task.USER_TEMPLATE.format(transcript=record["text"])},
    ]
    completion = json.dumps(record["label"], ensure_ascii=False)

    prompt_ids = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True).input_ids
    completion_ids = (tokenizer(completion, add_special_tokens=False).input_ids
                      + [tokenizer.eos_token_id])
    full_ids = prompt_ids + completion_ids

    template_ids = tokenizer.apply_chat_template(
        messages + [{"role": "assistant", "content": completion}],
        tokenize=True, add_generation_prompt=False).input_ids
    if template_ids != full_ids + [NEWLINE_ID]:
        raise ValueError(
            f"{record['id']}: constructed tokens diverge from the chat "
            "template render; completion masking would be wrong")

    labels = [-100] * len(prompt_ids) + completion_ids
    return {"input_ids": full_ids, "labels": labels, "id": record["id"]}


class PadCollator:
    """Right-pad input_ids with pad_token, labels with -100."""

    def __init__(self, pad_token_id: int):
        self.pad_token_id = pad_token_id

    def __call__(self, batch: list[dict]) -> dict:
        width = max(len(ex["input_ids"]) for ex in batch)
        input_ids, labels, attention = [], [], []
        for ex in batch:
            pad = width - len(ex["input_ids"])
            input_ids.append(ex["input_ids"] + [self.pad_token_id] * pad)
            labels.append(ex["labels"] + [-100] * pad)
            attention.append([1] * len(ex["input_ids"]) + [0] * pad)
        return {
            "input_ids": torch.tensor(input_ids),
            "labels": torch.tensor(labels),
            "attention_mask": torch.tensor(attention),
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=CORPUS / "train.jsonl")
    parser.add_argument("--val", type=Path, default=CORPUS / "val.jsonl")
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).parent / "runs" / "qlora-r16-a32-qv")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--grad-accum", type=int, default=4)
    args = parser.parse_args()

    set_seed(SEED)
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    train_rows = load_jsonl(args.train)
    val_rows = load_jsonl(args.val)
    train_ds = [build_example(tokenizer, r) for r in train_rows]
    val_ds = [build_example(tokenizer, r) for r in val_rows]

    lengths = sorted(len(ex["input_ids"]) for ex in train_ds + val_ds)
    over = [ex["id"] for ex in train_ds + val_ds if len(ex["input_ids"]) > MAX_LEN]
    if over:
        raise SystemExit(f"{len(over)} examples exceed MAX_LEN={MAX_LEN}: {over[:5]}")
    print(f"train {len(train_ds)} / val {len(val_ds)} examples; "
          f"token lengths min {lengths[0]} / median {lengths[len(lengths) // 2]} "
          f"/ max {lengths[-1]}")

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        ),
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
        device_map={"": 0},
    )
    model = prepare_model_for_kbit_training(
        model, gradient_checkpointing_kwargs={"use_reentrant": False})
    model = get_peft_model(model, LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    ))
    model.print_trainable_parameters()

    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(args.out),
            num_train_epochs=args.epochs,
            per_device_train_batch_size=args.batch_size,
            per_device_eval_batch_size=args.batch_size,
            gradient_accumulation_steps=args.grad_accum,
            learning_rate=args.lr,
            lr_scheduler_type="cosine",
            warmup_ratio=0.03,
            bf16=True,
            gradient_checkpointing=True,
            gradient_checkpointing_kwargs={"use_reentrant": False},
            optim="paged_adamw_8bit",
            logging_steps=5,
            eval_strategy="epoch",
            save_strategy="no",
            report_to=[],
            seed=SEED,
        ),
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=PadCollator(tokenizer.pad_token_id),
        processing_class=tokenizer,
    )

    baseline = trainer.evaluate()
    print(f"val loss before training: {baseline['eval_loss']:.4f}")
    trainer.train()
    final = trainer.evaluate()
    print(f"val loss after training:  {final['eval_loss']:.4f}")

    adapter_dir = args.out / "adapter"
    model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))
    (args.out / "run_meta.json").write_text(json.dumps({
        "base_model": BASE_MODEL,
        "recipe": {"quant": "nf4-double", "r": 16, "alpha": 32,
                   "targets": ["q_proj", "v_proj"], "dropout": 0.05,
                   "lr": args.lr, "epochs": args.epochs,
                   "effective_batch": args.batch_size * args.grad_accum,
                   "loss": "completion-only", "seed": SEED},
        "data": {"train": str(args.train), "n_train": len(train_ds),
                 "val": str(args.val), "n_val": len(val_ds)},
        "val_loss_before": baseline["eval_loss"],
        "val_loss_after": final["eval_loss"],
        "log_history": trainer.state.log_history,
    }, indent=1))
    print(f"adapter -> {adapter_dir}")


if __name__ == "__main__":
    main()
