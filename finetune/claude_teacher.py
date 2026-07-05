#!/usr/bin/env python3
"""Claude-as-teacher experiment: audition, label, and assemble splits.

Runs LIMA's exact production extraction task (extraction_task.py) against
Claude models over the Batch API (50% price) with structured outputs playing
the role llama.cpp's constrained decoding plays locally. Condition notes vs
the local teacher: no temperature control (API default; local teacher used
0.2) and thinking explicitly disabled on every request so Opus and Sonnet
run the same non-thinking condition.

Crash-safe: submitted batch ids are recorded in .batch_state.json, so
re-running any mode reattaches to in-flight batches instead of resubmitting
(and re-paying). Batches also survive on the server for 29 days — a dead
terminal never loses work. To adopt a batch submitted before this state file
existed: --attach model=msgbatch_xxx.

Modes:
  audition  Run candidate teacher(s) over the held-out eval slices (batches
            for all models submitted up front, polled together) and write a
            benchmark-shaped report that scripts/judge_extraction.py can
            grade against the cached blind reference. Decides whether a
            frontier teacher beats the local 30B (0.78 hallucinated/memo)
            before any money is spent on full labeling.
  label     Label a corpus input file (synthetic memos / real train pool)
            with the chosen teacher. Resumable: re-running collects only
            missing ids.
  splits    Build train/val for the new teacher by joining its normalized
            labels onto the EXISTING train.jsonl/val.jsonl membership — the
            split, inputs, and eval slices stay identical to the local-teacher
            corpus; only the labels change.

Usage:
    uv run claude_teacher.py audition --models claude-opus-4-8,claude-sonnet-5
    uv run claude_teacher.py audition --attach claude-opus-4-8=msgbatch_xxx
    uv run claude_teacher.py label --model claude-sonnet-5 \
        --input corpus/synthetic_memos.jsonl --out corpus/labeled_synthetic_claude.jsonl
    uv run claude_teacher.py splits --labeled-real corpus/labeled_real_claude.jsonl \
        --labeled-synthetic corpus/labeled_synthetic_claude.jsonl --out-dir corpus/claude
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
CORPUS = HERE / "corpus"
SCRIPTS = HERE.parent / "scripts"
RESULTS_DIR = SCRIPTS / "benchmark_results"
STATE_PATH = HERE / ".batch_state.json"
sys.path.insert(0, str(SCRIPTS))

import extraction_task  # noqa: E402
import normalize_labels  # noqa: E402
from benchmark_extraction import SLICES, code_grade, load_jsonl  # noqa: E402

MAX_TOKENS = 2048
LABEL_VERSION = "claude-api-1"
POLL_SECONDS = 30


def get_client():
    import anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        env_file = HERE / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                key, _, value = line.partition("=")
                if key.strip() == "ANTHROPIC_API_KEY" and value.strip():
                    os.environ["ANTHROPIC_API_KEY"] = value.strip()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("no ANTHROPIC_API_KEY in environment or finetune/.env")
    return anthropic.Anthropic()


def request_params(model: str, text: str) -> dict:
    return {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": extraction_task.SYSTEM_MESSAGE,
        "messages": [{
            "role": "user",
            "content": extraction_task.USER_TEMPLATE.format(transcript=text),
        }],
        "thinking": {"type": "disabled"},
        "output_config": {
            "format": {"type": "json_schema", "schema": extraction_task.SCHEMA},
        },
    }


def load_state() -> dict:
    return json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}


def save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, indent=1))


def ensure_batch(client, key: str, model: str, records: list[dict]) -> dict:
    """Submit a batch for records, or reattach to one already in flight."""
    state = load_state()
    if key in state:
        entry = state[key]
        try:
            client.messages.batches.retrieve(entry["batch_id"])
            print(f"  reattached to batch {entry['batch_id']} ({key})")
            return entry
        except Exception as e:
            print(f"  stale batch state for {key} ({e}); resubmitting")

    custom_to_id = {f"rec-{i:04d}": r["id"] for i, r in enumerate(records)}
    batch = client.messages.batches.create(requests=[
        {"custom_id": cid,
         "params": request_params(model, rec["text"])}
        for (cid, _), rec in zip(custom_to_id.items(), records)
    ])
    entry = {"batch_id": batch.id, "model": model, "custom_to_id": custom_to_id}
    state[key] = entry
    save_state(state)
    print(f"  batch {batch.id} submitted ({len(records)} requests, {model})")
    return entry


def wait_all(client, entries: dict[str, dict]):
    """Poll every batch until all have ended; one status line per poll."""
    pending = dict(entries)
    while pending:
        parts, done = [], []
        for key, entry in pending.items():
            batch = client.messages.batches.retrieve(entry["batch_id"])
            c = batch.request_counts
            parts.append(f"{entry['model']}: {batch.processing_status} "
                         f"ok={c.succeeded} err={c.errored} proc={c.processing}")
            if batch.processing_status == "ended":
                done.append(key)
        print("  " + " | ".join(parts), flush=True)
        for key in done:
            pending.pop(key)
        if pending:
            time.sleep(POLL_SECONDS)


def collect_batch(client, key: str, entry: dict) -> dict[str, dict]:
    """Fetch results for an ended batch, then clear its state entry."""
    custom_to_id = entry["custom_to_id"]
    outputs: dict[str, dict] = {}
    for result in client.messages.batches.results(entry["batch_id"]):
        rec_id = custom_to_id[result.custom_id]
        if result.result.type != "succeeded":
            outputs[rec_id] = {"error": result.result.type}
            continue
        message = result.result.message
        if message.stop_reason == "refusal":
            outputs[rec_id] = {"error": "refusal"}
            continue
        text = next((b.text for b in message.content if b.type == "text"), "")
        try:
            outputs[rec_id] = {"output": json.loads(text),
                               "usage": {
                                   "input_tokens": message.usage.input_tokens,
                                   "output_tokens": message.usage.output_tokens,
                               }}
        except json.JSONDecodeError:
            outputs[rec_id] = {"error": f"unparseable ({message.stop_reason})"}
    failed = [rid for rid, o in outputs.items() if "error" in o]
    if failed:
        print(f"  WARNING: {len(failed)} failed rows: {failed[:5]}")
    state = load_state()
    state.pop(key, None)
    save_state(state)
    return outputs


def parse_attach(attach: list[str], state_keys: dict[str, str],
                 records_by_key: dict[str, list[dict]]):
    """Seed .batch_state.json with externally submitted batches."""
    if not attach:
        return
    state = load_state()
    for spec in attach:
        model, _, batch_id = spec.partition("=")
        key = state_keys.get(model)
        if key is None:
            raise SystemExit(f"--attach model {model!r} is not in --models")
        records = records_by_key[key]
        state[key] = {
            "batch_id": batch_id,
            "model": model,
            "custom_to_id": {f"rec-{i:04d}": r["id"] for i, r in enumerate(records)},
        }
        print(f"  attached {batch_id} as {key}")
    save_state(state)


def cmd_audition(client, args):
    slices = {name: load_jsonl(path) for name, path in SLICES.items()}
    all_records = [r for recs in slices.values() for r in recs]
    print("eval slices:", {k: len(v) for k, v in slices.items()})

    models = [m.strip() for m in args.models.split(",")]
    state_keys = {m: f"audition:{m}" for m in models}
    parse_attach(args.attach, state_keys,
                 {key: all_records for key in state_keys.values()})

    # submit everything up front, then poll together
    entries = {state_keys[m]: ensure_batch(client, state_keys[m], m, all_records)
               for m in models}
    wait_all(client, entries)

    conditions = []
    for model in models:
        key = state_keys[model]
        outputs = collect_batch(client, key, entries[key])

        results = {}
        for slice_name, records in slices.items():
            rows = []
            for rec in records:
                out = outputs.get(rec["id"], {"error": "missing"})
                row = {"id": rec["id"], **out}
                if "output" in row:
                    row["grade"] = code_grade(row["output"])
                rows.append(row)
            results[slice_name] = rows

        ok = [r for rows in results.values() for r in rows if "output" in r]
        grade_rates = {}
        if ok:
            for check in next(iter(ok))["grade"]:
                vals = [r["grade"][check] for r in ok if r["grade"][check] is not None]
                grade_rates[check] = round(sum(vals) / len(vals), 3) if vals else None
        conditions.append({
            "model": model,
            "serving": "anthropic-batch-api/structured-outputs",
            "records_ok": len(ok),
            "records_failed": sum(len(r) for r in results.values()) - len(ok),
            "grade_rates": grade_rates,
            "slices": results,
        })

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task": "lima-extraction-v0.3.1",
        "temperature": None,
        "constrained_decoding": "structured-outputs-api",
        "note": "teacher audition over the API; thinking disabled; no temperature control",
        "conditions": conditions,
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"extraction_api_{stamp}.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(f"\nreport -> {out}")
    print(f"judge with: cd {SCRIPTS} && uv run judge_extraction.py {out}")
    for c in conditions:
        print(f"  {c['model']}: ok={c['records_ok']} failed={c['records_failed']} "
              f"grades={c['grade_rates']}")


def cmd_label(client, args):
    records = load_jsonl(args.input)
    done = set()
    if args.out.exists():
        done = {r["id"] for r in load_jsonl(args.out)
                if r.get("label_version") == LABEL_VERSION}
    todo = [r for r in records if r["id"] not in done]
    print(f"{len(records)} records, {len(done)} already labeled, {len(todo)} to label")
    if not todo:
        return

    key = f"label:{args.model}:{args.out.name}"
    parse_attach(args.attach, {args.model: key}, {key: todo})
    entry = ensure_batch(client, key, args.model, todo)
    wait_all(client, {key: entry})
    outputs = collect_batch(client, key, entry)

    labeled = 0
    with args.out.open("a") as f:
        for rec in todo:
            out = outputs.get(rec["id"], {})
            if "output" not in out:
                continue
            f.write(json.dumps({**rec, "label": out["output"], "teacher": args.model,
                                "label_version": LABEL_VERSION},
                               ensure_ascii=False) + "\n")
            labeled += 1
    print(f"wrote {labeled} labels -> {args.out} (re-run to retry failures)")


def cmd_splits(client, args):  # client unused; signature uniform
    new_labels = {}
    for path in (args.labeled_real, args.labeled_synthetic):
        for r in load_jsonl(path):
            label = r["label"]
            if label["title"] != normalize_labels.FALLBACK_TITLE:
                label = {**label, "tags": normalize_labels.normalize_tags(label["tags"])}
            new_labels[r["id"]] = (label, r["teacher"])

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name in ("train.jsonl", "val.jsonl"):
        rows = load_jsonl(CORPUS / name)
        missing = [r["id"] for r in rows if r["id"] not in new_labels]
        if missing:
            raise SystemExit(f"{name}: {len(missing)} ids lack new-teacher labels "
                             f"(e.g. {missing[:5]}) — finish labeling first")
        out = args.out_dir / name
        with out.open("w") as f:
            for r in rows:
                label, teacher = new_labels[r["id"]]
                f.write(json.dumps({**r, "label": label, "teacher": teacher,
                                    "label_version": LABEL_VERSION},
                                   ensure_ascii=False) + "\n")
        print(f"{name}: {len(rows)} rows (same membership as corpus/{name}) -> {out}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)

    p = sub.add_parser("audition")
    p.add_argument("--models", default="claude-opus-4-8,claude-sonnet-5")
    p.add_argument("--attach", action="append", default=[],
                   metavar="MODEL=BATCH_ID",
                   help="adopt an already-submitted batch instead of resubmitting")

    p = sub.add_parser("label")
    p.add_argument("--model", required=True)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--attach", action="append", default=[],
                   metavar="MODEL=BATCH_ID")

    p = sub.add_parser("splits")
    p.add_argument("--labeled-real", required=True, type=Path)
    p.add_argument("--labeled-synthetic", required=True, type=Path)
    p.add_argument("--out-dir", type=Path, default=CORPUS / "claude")

    args = parser.parse_args()
    client = get_client() if args.mode != "splits" else None
    {"audition": cmd_audition, "label": cmd_label, "splits": cmd_splits}[args.mode](client, args)


if __name__ == "__main__":
    main()
