# LIMA extraction distillation — corpus & pipeline

Distills LIMA's structured-extraction task (voice memo transcript → 6-field
JSON note) from the production teacher model (`qwen3-coder-30b`) into a small
student, with an eval harness measuring retained content quality. The task
definition — system message, user template, JSON Schema — is imported verbatim
from the live n8n workflow via `extraction_task.py`, the single source of
truth for every pipeline stage.

## Pipeline map

```mermaid
flowchart LR
    subgraph SRC["Sources (all license-clean, zero private data)"]
        QM["QMSum bundle<br>232 AMI/ICSI meetings<br>CC BY 4.0 / MIT"]
        SEED["seeds.py matrix<br>14 personas x 20 topics<br>x length x mood x setting"]
        STT["STT-Voice-Notes-Evals<br>16 memos x 4 STT engines<br>Apache 2.0"]
    end

    QM -- "carve_qmsum.py<br>merge turns, 150-600w" --> RC["real_chunks.jsonl<br>1,202 chunks"]
    RC -- "make_splits.py real<br>(meeting-level manifest)" --> POOL["train_pool_real.jsonl<br>170 chunks, max 3/meeting"]
    RC -- "11 meetings reserved" --> EVR["eval_real.jsonl<br>31 chunks"]

    SEED -- "generate_synthetic.py<br>2-stage: content -> disfluency<br>(teacher, length-gated)" --> SM["synthetic_memos.jsonl<br>268 memos"]

    POOL --> LBL["label_teacher.py<br>teacher @ temp 0.2<br>constrained decoding ON"]
    SM --> LBL
    LBL --> LR["labeled_real.jsonl"]
    LBL --> LS["labeled_synthetic.jsonl"]

    LR --> FIN["make_splits.py final<br>+ hard leak check"]
    LS --> FIN
    FIN --> TR["train.jsonl — 389"]
    FIN --> VA["val.jsonl — 43"]
    FIN -- "teacher-failed artifacts" --> EVB["eval_boundary_garbled.jsonl — 6"]

    STT -- "build_stt_eval.py<br>noisy STT outputs as inputs" --> EVS["eval_stt_voice_notes.jsonl<br>64 rows"]

    style TR fill:#2d6a4f,color:#fff
    style VA fill:#2d6a4f,color:#fff
    style EVR fill:#7b2d26,color:#fff
    style EVS fill:#7b2d26,color:#fff
    style EVB fill:#7b2d26,color:#fff
```

Green = training surface. Red = held-out eval, never trained on.

## Corpus recipe (built 2026-07-04/05)

**Train 389 / val 43 pairs**, split by transcript/meeting (real) and by cell
id (synthetic), never by row. Assembled by `make_splits.py`; the manifest
(`corpus/split_manifest.json`) reserves whole AMI/ICSI meetings for eval and
`make_splits.py final` hard-fails if a labeled train row comes from one.

- **~60% synthetic** — two-stage teacher generation: fluent first-person memo
  from a persona × topic × length × mood × setting seed matrix (temp 0.9),
  then a disfluency-injection rewrite (temp 0.7) with a hard length gate.
  `seeds.py` + `generate_synthetic.py`.
- **~40% real spontaneous speech** — monologue-ish chunks carved from AMI and
  ICSI meeting transcripts (via the QMSum bundle): same-speaker turns merged
  across ≤1 short backchannel, 150–600 words, real disfluencies preserved,
  markup stripped. Parliamentary "Committee" transcripts excluded (prepared
  speech, wrong register). `carve_qmsum.py`.
- **Labels** — teacher runs the exact production task at temp 0.2 with
  llama.cpp schema-constrained decoding ON (the same condition every eval
  uses). `label_teacher.py`. Records carry `gen_version`/`label_version`;
  resume skips only rows produced by current code.

## Eval slices (`corpus/eval/` + `corpus/eval_real.jsonl`) — never trained on

- `eval_real.jsonl` — 31 chunks from 11 reserved AMI/ICSI meetings: genuinely
  spontaneous, disfluent held-out speech.
- `eval/eval_stt_voice_notes.jsonl` — 64 rows: 16 scripted voice-memo readings
  × 4 real STT systems' raw outputs (STT-Voice-Notes-Evals). The memos are
  scripted, not spontaneous — so the noisy STT outputs are the eval inputs and
  the clean scripts ride along as judge reference.
- `eval/eval_boundary_garbled.jsonl` — 6 STT-failure-artifact probes
  (verbatim loops, polite-phrase hallucinations, contentless prose). Routed
  here because the teacher itself fails them: it converts "Thanks for
  watching!" spam into a structured note instead of the fallback. Known
  teacher weakness, kept as an eval dimension.

## Measurement architecture (harness lives in `../scripts/`)

```mermaid
flowchart TD
    subgraph EV["Held-out eval — 101 records"]
        E1["eval_real — 31<br>spontaneous, reserved meetings"]
        E2["eval_stt — 64<br>real STT noise, 4 engines"]
        E3["garbled probes — 6<br>Whisper failure artifacts"]
    end

    subgraph MODELS["Conditions (llama-swap :9292)"]
        T["qwen3-coder-30b<br>teacher, 21.6GB"]
        P["qwen3-8b<br>current prod, 9.3GB"]
        S["qwen3-4b<br>student base, 6.8GB"]
        FT["qwen3-4b + QLoRA<br>(M3, pending)"]
    end

    EV --> BE["benchmark_extraction.py<br>production prompt + schema (extraction_task.py)<br>constrained decoding ON for every condition"]
    MODELS --> BE
    BE --> RES["results JSON<br>outputs + field-discipline grades<br>+ cold-start / VRAM / tok/s"]
    RES --> JU["judge_extraction.py<br>gemma-3-27b — non-Qwen family,<br>scores vs TRANSCRIPT (teacher falsifiable)"]
    JU --> OUT["title/summary quality · action-item recall<br>hallucinated items/memo · fallback accuracy"]

    style FT stroke-dasharray: 5 5
```

## Measured baselines (M1, 2026-07-05)

Full data: `../scripts/benchmark_results/extraction_judged_20260705_033305.json`.

| judge scores, 101 records | 30B teacher | 8B (prod) | 4B student |
|---|---|---|---|
| title / summary quality (1–5) | 4.77 / 4.76 | 4.75 / 4.79 | 4.82 / 4.84 |
| action-item recall | 0.99 | 0.96 | 0.98 |
| **hallucinated items / memo** | **0.41** | 0.83 | **1.59** |
| fallback accuracy (garbled slice) | ~1.0 | — | 0.33 |
| tags kebab-case (code grade) | 0.91 | 0.51 | 0.20 |
| VRAM loaded / cold start / median latency | 21.6GB / 5.5s / 1.1s | 9.3GB / 4.8s / 5.1s | 6.8GB / 2.7s / 1.8s |

The finding that defines M2: **surface quality is flat across model sizes;
the gap is grounding** (4x hallucination rate) **and format discipline**.
Also: the 30B MoE is the *fastest* per memo — the cost axis being right-sized
here is VRAM residency, not speed.

## Milestones

```mermaid
flowchart LR
    M0["M0 — corpus<br>DONE (1e4d579)"] --> M1["M1 — harness + baselines<br>DONE (96c21d8)"]
    M1 --> M2["M2 — QLoRA run<br>NEXT: train_qlora.py<br>(NF4, r=16, alpha=32, q/v,<br>completion-only loss)"]
    M2 --> M3["M3 — deploy + re-benchmark<br>merge -> GGUF -> quantize -> llama-swap<br>compare quantized-tuned vs quantized-base"]

    style M0 fill:#2d6a4f,color:#fff
    style M1 fill:#2d6a4f,color:#fff
    style M2 stroke-dasharray: 5 5
    style M3 stroke-dasharray: 5 5
```

Prereqs already on disk for M2: `corpus/train.jsonl` + `val.jsonl`,
Qwen/Qwen3-4B-Instruct-2507 HF weights (hub cache), llama-swap routes for
`qwen3-4b` and the `gemma-3-27b` judge. Training-time chat template must be
verified against the GGUF's serving template before trusting any M3 number.

## Known limitations (read before citing numbers)

- **Self-distillation caveat**: the synthetic majority is generated AND
  labeled by the same teacher. Retention numbers on synthetic-style eval data
  are inflated by construction; the defensible claims come from the real/noisy
  held-out slices, judged by a different model family. Report them separately.
- **Domain skew in real chunks**: AMI is dominated by its remote-control
  design scenario; ICSI by speech-research meetings. Great disfluency
  coverage, weak personal-memo domain coverage.
- **Scripted STT eval**: the STT-Voice-Notes memos were written then read
  aloud — real STT noise, simulated spontaneity, single speaker/persona.

## Licensing & attribution

- Real chunks contain transcript excerpts from the **AMI Meeting Corpus** and
  the **ICSI Meeting Corpus** (CC BY 4.0,
  <https://groups.inf.ed.ac.uk/ami/>), modified (turn merging, markup
  removal, detokenization), obtained via the **QMSum** dataset (Yale-LILY,
  MIT, Zhong et al., NAACL 2021, <https://github.com/Yale-LILY/QMSum>).
- STT eval slice derives from **STT-Voice-Notes-Evals** by Daniel Rosehill
  (Apache 2.0 per HF metadata, DOI 10.57967/hf/6317,
  <https://huggingface.co/datasets/danielrosehill/STT-Voice-Notes-Evals>).
- Synthetic memos and all labels were generated locally by
  Qwen3-Coder-30B-A3B-Instruct (Q4_K_M) via llama.cpp. No private data
  anywhere in the corpus.

## Rebuild from scratch

```bash
git clone --depth 1 https://github.com/Yale-LILY/QMSum /tmp/QMSum
git clone https://huggingface.co/datasets/danielrosehill/STT-Voice-Notes-Evals /tmp/stt

python3 carve_qmsum.py --qmsum /tmp/QMSum
python3 make_splits.py real
python3 generate_synthetic.py --count 260          # needs llama-swap on :9292
python3 label_teacher.py --input corpus/synthetic_memos.jsonl --out corpus/labeled_synthetic.jsonl
python3 label_teacher.py --input corpus/train_pool_real.jsonl --out corpus/labeled_real.jsonl
python3 make_splits.py final
python3 build_stt_eval.py --src /tmp/stt
```
