# Benchmarks

Measured numbers from real hardware, for sizing decisions. Everything here was
measured empirically — no vendor claims, no estimates. Test rig: **RTX 4090 24GB**,
Arch Linux, NVIDIA proprietary driver, GPU shared with desktop/gaming (idle-to-zero
VRAM is a hard requirement).

- [LLM serving layer (2026-07)](#llm-serving-layer-202607) — llama-swap + llama.cpp vs Ollama
- [Whisper transcription models (2026-07)](#whisper-transcription-models-202607) — size/accuracy/VRAM sweep

---

## LLM serving layer (2026-07)

**Question:** which serving layer runs LIMA's LLM steps — `llama-swap` +
`llama.cpp` `llama-server`, or Ollama? Primary workload: n8n agent workflows
calling an OpenAI-compatible API with tool calling (n8n's OpenAI node streams by
default). Decided by a two-day empirical spike, not on paper.

**Versions tested:** llama.cpp b9859 (CUDA), llama-swap v234, Ollama 0.31.1,
n8n 1.123.5 (re-verified on 2.28.5). Models: `Qwen3-8B` and
`Qwen3-Coder-30B-A3B-Instruct`, both Q4_K_M GGUF (unsloth) on llama.cpp and the
matching `qwen3:8b` / `qwen3-coder:30b` on Ollama. 16K context everywhere.

### Results

| Check | llama-swap + llama.cpp | Ollama 0.31.1 |
|---|---|---|
| Streaming + tools accepted | PASS (spec-correct streamed `tool_calls` deltas) | PASS (single-delta tool calls) |
| Multi-round tool chain, 8B (raw API) | PASS, textbook sequence, 4.9s warm | misfired 3/3 — speculative parallel calls with hallucinated args; recovered but dirty |
| Multi-round tool chain, 30B (raw API) | PASS, 5.6s incl. cold load | PASS, 12.5s incl. cold load |
| n8n AI Agent 2-tool chain, 8B | PASS, agent node 2.25s warm | PASS with repeated tool calls, ~30s |
| n8n AI Agent 2-tool chain, 30B | PASS, ~11s cold / near-instant warm | PASS clean, ~13s cold |
| n8n voice-memo workflow (structured output) | success, 7.8–10.6s end-to-end | success, 7.9–8.6s end-to-end |
| Cold start (model load → answer) | **2.3s** (8B, 5GB) / **~4s** (30B, 18.6GB) | ~5.1s to first token (8B) |
| Generation speed (8B) | 149 tok/s | comparable, but chains ~2× slower (see below) |
| VRAM @ 30B + 16K ctx | 20.3GB | 20.3GB |
| Idle → zero VRAM | PASS (per-model `ttl`, process exit) | PASS (`keep_alive` expiry) |
| Manual instant-unload | `POST /api/models/unload` | `ollama stop <model>` |

### Key findings

1. **llama.cpp's historical "cannot use tools with stream" rejection is gone.**
   Verified at the raw API level and through n8n's stream-by-default OpenAI node
   on both n8n 1.123.5 and 2.28.5.
2. **Ollama's weakness is multi-round agent chains with *thinking* models.** Its
   qwen3 chat template (which diverges from the upstream Jinja template llama.cpp
   uses) produced speculative parallel tool calls with placeholder/hallucinated
   arguments in every 8B trial. The identical weights through llama.cpp chained
   perfectly every time. Non-thinking `qwen3-coder` was clean on both backends.
3. **`/no_think` is ignored on Ollama's OpenAI-compat route** — reasoning streams
   in a nonstandard `reasoning` delta field on every round, roughly doubling
   chain wall-clock with thinking models.
4. **On single-completion structured output the backends are equals.** The gap is
   specifically agentic tool loops.
5. **One backend at a time on 24GB.** With a big model resident on one backend,
   the other OOMs at spawn. Not a daily-use issue (you run one), but it bites
   during side-by-side testing.

### Verdict

**llama-swap + llama.cpp llama-server** is LIMA's recommended local serving
layer on NVIDIA hardware. Model guidance: `qwen3-coder-30b` (Q4_K_M) as the
daily agent model, a dense 27B-class as the quality lane, `qwen3-8b` as the fast
fallback — and avoid *thinking* models for tool-loop workflows regardless of
backend. `gpt-oss-20b` (the old default) has documented tool-calling problems on
every backend and is not recommended for agent workflows.

Post-verdict audition: `Qwen3.6-27B` dense Q4_K_M passed the same tool chain
cleanly — 14.7s cold / 8.4s warm, 19.4GB @ 16K. Dense decode is slower per token
than the 30B MoE's 3B active parameters; that's the speed/quality trade.

### Operational notes

- Model swap on request, TTL unload, and a manual unload endpoint make llama-swap
  fit a gaming-shared GPU: VRAM returns to desktop baseline within seconds of TTL
  expiry (measured: 20.3GB → ~1.2GB).
- GGUF downloads: a plain single-connection `curl` from Hugging Face capped at
  5–10 MB/s on a 500 Mbps line (long-RTT TCP). `HF_XET_HIGH_PERFORMANCE=1` with
  `hf download` sustained **61.5 MB/s (line-saturated)** for 16.8GB. Use it.

---

## Whisper transcription models (2026-07)

**Question:** which faster-whisper model should the native CUDA server
(`services/whisper-server/`) run? Measured with a 37-second synthetic voice memo
(espeak-ng TTS — deliberately hard, robotic audio) via
`/v1/audio/transcriptions`. VRAM is the server process's steady residency after
transcription (includes ~300MB CUDA context).

### float16 (default `COMPUTE_TYPE`)

| Model | Disk | VRAM | Warm transcribe (37s audio) | Hard-word test¹ |
|---|---|---|---|---|
| base | 142M | 662 MiB | ~1.0s | ✗ |
| small | 464M | 1,110 MiB | 0.7s | ✗ |
| medium | 1.5G | 2,358 MiB | 1.0s | ✗ |
| large-v3 | 2.9G | 4,182 MiB | 1.3s | ✓ |
| large-v3-turbo | 1.6G | 2,518 MiB | 0.6s | ✗ |

### int8_float16 (load-time quantization, same model files)

| Model | VRAM | vs fp16 | Hard-word test¹ |
|---|---|---|---|
| large-v3 | 2,230 MiB | −47% | ✓ |
| large-v3-turbo | 1,462 MiB | −42% | ✗ |
| medium | 1,334 MiB | −43% | ✗ |

¹ Whether the model transcribed "Tuesday **sync**" correctly (everything smaller
wrote "sink") on the robotic test audio. One word on one file — a signal, not a
benchmark — but representative of the proper-noun/jargon errors that poison
downstream note extraction.

### Key findings

1. **Speed never differentiates** — every model transcribes 37s of audio in
   about a second warm. Choose on accuracy vs VRAM only.
2. **Only large-v3 survived the hard-word test, and it survives int8.** At
   `int8_float16` it needs 2.2GB — half of fp16 — with no observed quality loss.
3. **Budget the LLM and Whisper together, and unload deterministically.** Next
   to a 30B-class LLM (20.3GB @ 16K) plus desktop compositor overhead, large-v3
   fp16 (4.2GB) does not fit on 24GB, and even large-v3-int8 (2.2GB) is marginal.
   `base`/`small` always fit. The fix is a **`POST /unload` endpoint** on the
   native server (`server_cuda.py`): the memo workflow calls it between the
   transcription step and the LLM step, so whisper releases its VRAM before the
   LLM loads. Measured on this rig, in sequence on the one 24GB card: transcribe
   (large-v3 int8 → 2,230 MiB resident) → `/unload` (process falls to 396 MiB,
   bare CUDA context — the model weights are actually freed, not just
   dereferenced) → qwen3-coder-30b loads (19.6GB) → total 21,967 MiB, fits.
   A **pure idle-unload timer would not fix this** — the LLM step runs seconds
   after transcription, inside any reasonable idle window, so the timer never
   fires between them. `WHISPER_IDLE_TIMEOUT` exists as a secondary safety net
   for ad-hoc callers outside the pipeline; the explicit endpoint is what makes
   the coexistence deterministic.
4. **Model/precision overrides must be make command-line variables:**
   `make whisper-native WHISPER_MODEL=large-v3 COMPUTE_TYPE=int8_float16`.
   The env-prefix form (`WHISPER_MODEL=x make whisper-native`) is silently
   overridden — the Makefile's `-include .env` + `export` makes `.env` values
   shadow the calling environment.
5. Models auto-download to `~/.cache/huggingface/hub/` on first load
   (`large-v3-turbo` resolves to the `mobiuslabsgmbh` CT2 conversion).
