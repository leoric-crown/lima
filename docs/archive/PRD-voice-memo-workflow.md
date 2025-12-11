# PRD: LIMA Voice Memo Workflow

## Overview

A demonstration n8n workflow that processes voice memos into structured, Obsidian-compatible markdown notes with extracted insights.

**Privacy:** Voice memos often contain personal or sensitive content. LIMA ensures they never leave your device.

**Purpose:** Demo and inspiration for local-first voice-to-knowledge systems, not production automation.

**Target Users:** Developers, BAs, PMs, and power users who want to tinker with local AI solutions for capturing and organizing spoken thoughts.

**Current Version:** v0.2.0 - See [Changelog](#changelog) for version history.

---

## Goals

1. **Demonstrate end-to-end local processing:** Audio → Transcript → Insights → Markdown
2. **Obsidian compatibility:** Output files work seamlessly when Obsidian points at `data/notes/`
3. **Remote access:** Webhook trigger accessible from any device via Tailscale
4. **Readable, hackable workflow:** Simple enough to understand and modify
5. **Zero cloud dependencies:** All processing happens locally

## Non-Goals

- Production-grade reliability (retry logic, monitoring, alerting)
- Multi-user support
- Real-time streaming transcription
- Complex chunking/parallel processing for long files
- Embeddings or RAG pipeline (future enhancement)
- Speaker diarization (single-speaker voice memos don't need it)

---

## User Flow

```
1. User records a voice memo on their phone/laptop (1-5 minutes typical)
2. User sends audio to the n8n webhook:
   - iOS: Shortcuts app with "Get Contents of URL" action
   - Android: Tasker or HTTP Shortcuts app
   - Desktop: curl, web form, or file drop
3. Workflow:
   a. Receives audio via webhook
   b. Sends audio to local Whisper endpoint
   c. Receives transcript
   d. Sends transcript to local LLM with extraction prompt
   e. Formats output as Obsidian-friendly markdown
   f. Writes file to data/notes/
4. User opens Obsidian (pointed at data/notes/) and sees the new note
```

**Key insight:** By the time you open Obsidian, your voice memo is already a structured note.

---

## Workflow Architecture (v0.2.0)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              n8n Workflow v0.2.0                                     │
├──────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  TRIGGERS (either/or)                                                                │
│  ┌──────────────┐     ┌──────────────┐                                               │
│  │   Webhook    │     │ Local File   │                                               │
│  │   Trigger    │     │   Trigger    │                                               │
│  │ POST /memo   │     │ /data/voice- │                                               │
│  │ + audio file │     │ memos/*.mp3  │                                               │
│  └──────┬───────┘     └──────┬───────┘                                               │
│         │                    │                                                       │
│         ▼                    │                                                       │
│  ┌──────────────┐            │                                                       │
│  │ Save to Disk │────────────┘                                                       │
│  │ (webhook/)   │                                                                    │
│  └──────┬───────┘                                                                    │
│         │                                                                            │
│         ▼                                                                            │
│  ┌──────────────┐    ┌─────────────────┐    ┌──────────────────────────┐             │
│  │  Set Data    │───▶│    ffprobe      │───▶│   Read Voice Memo        │             │
│  │  (normalize) │    │  (duration)     │    │   (binary data)          │             │
│  └──────────────┘    └─────────────────┘    └────────────┬─────────────┘             │
│                                                          │                           │
│                                                          ▼                           │
│  ┌──────────────┐    ┌─────────────────┐    ┌──────────────────────────┐             │
│  │   Crypto     │───▶│ Detect Input    │───▶│   Route by Type          │             │
│  │  (hash file) │    │   Type          │    │   (audio/unsupported)    │             │
│  └──────────────┘    └─────────────────┘    └────────────┬─────────────┘             │
│                                                          │                           │
│                                              ┌───────────┴───────────┐               │
│                                              ▼                       ▼               │
│                                       [audio branch]          [error branch]         │
│                                                                                      │
│  ┌──────────────┐    ┌─────────────────┐    ┌──────────────────────────┐             │
│  │Install Model │    │    Whisper      │───▶│   Extract Insights       │             │
│  │ (parallel)   │    │  Transcription  │    │   (AI Agent + LLM)       │             │
│  └──────────────┘    └─────────────────┘    └────────────┬─────────────┘             │
│                                                          │                           │
│                                                          ▼                           │
│  ┌──────────────┐    ┌─────────────────┐    ┌──────────────────────────┐             │
│  │   Respond    │◀───│  Archive Audio  │◀───│   Write Note             │             │
│  │   Success    │    │  (mv to archive)│    │   /data/notes/*.md       │             │
│  └──────────────┘    └─────────────────┘    └──────────────────────────┘             │
│                                                          ▲                           │
│                                              ┌───────────┴───────────┐               │
│                                              │  Delete Old Hash      │               │
│                                              │  (idempotent update)  │               │
│                                              └───────────────────────┘               │
│                                                          ▲                           │
│                                              ┌───────────┴───────────┐               │
│                                              │  Format Markdown      │               │
│                                              │  (Code node)          │               │
│                                              └───────────────────────┘               │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘

External Services (running on host):
┌─────────────────┐    ┌─────────────────┐
│ Whisper/Speaches│    │   LM Studio     │
│ :8000 (internal)│    │   :1234         │
│                 │    │                 │
│ Audio → Text    │    │ Text → JSON     │
└─────────────────┘    └─────────────────┘

Remote Access:
┌─────────────────┐
│   Tailscale     │
│                 │
│ Phone/Laptop ──▶│──▶ n8n webhook
│ anywhere        │    (via tailnet)
└─────────────────┘
```

### Data Flow (v0.2.0)

| Step | Node | Input | Output |
|------|------|-------|--------|
| 1 | Webhook OR Local File Trigger | POST with audio file OR file event | Binary data + metadata |
| 2 | Save to Disk (webhook only) | Binary from webhook | File path in `/data/voice-memos/webhook/` |
| 3 | Set Data | File path | Normalized path + webhook flag |
| 4 | ffprobe | File path | Duration in seconds |
| 5 | Read Voice Memo | File path | Binary audio data |
| 6 | Crypto | Binary audio | SHA256 hash (first 8 chars for filename) |
| 7 | Detect Input Type | Binary + metadata | `{ inputType: "audio", mimeType, ... }` |
| 8 | Route by Input Type | Input type | Audio branch OR error branch |
| 9 | Install Whisper Model (parallel) | Model ID | Success (idempotent) |
| 10 | Whisper Transcription | Binary audio | `{ "text": "Full transcript..." }` |
| 11 | Extract Insights (AI Agent) | Transcript + prompt | `{ "title": "...", "summary": "...", ... }` |
| 12 | Format Full Markdown | LLM JSON + transcript | `{ filename, filepath, archivePath, markdown }` |
| 13 | Delete Old Hash Files | File hash | Removes previous versions with same hash |
| 14 | Write Note | Markdown binary | File written to `/data/notes/` |
| 15 | Archive Audio | Source path, archive path | Original moved to `/data/audio-archive/` |
| 16 | Respond to Webhook | Success message | `{ "status": "ok", "note": "...", "title": "..." }` |

The webhook response confirms completion and returns the filename, useful for mobile clients to show a notification.

---

## Technical Components

### Trigger: Webhook

Use the **Webhook** node to receive audio from any device:

| Setting | Value |
|---------|-------|
| HTTP Method | POST |
| Path | `memo` |
| Authentication | None (secured by Tailscale) or Header Auth |
| Response Mode | Last Node |

The webhook URL will be: `http://<n8n-host>:5678/webhook/memo`

With Tailscale: `http://<tailscale-hostname>:5678/webhook/memo`

**Binary Data Handling:**
- n8n automatically parses multipart/form-data
- Audio file available as `$binary.data` or `$binary.file` depending on form field name

### Model Installation (Idempotent)

Ensure the Whisper model is installed before transcription:

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://whisper:8000/v1/models/Systran%2Ffaster-whisper-base` |
| Timeout | 300000ms (5 min for first download) |

This is idempotent - returns success whether model is already installed or newly downloaded.

### Transcription

Use the **HTTP Request** node with multipart/form-data:

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://whisper:8000/v1/audio/transcriptions` |
| Body Content Type | Form-Data |
| Timeout | 300000ms |

**Form-Data Parameters:**

| Name | Type | Value |
|------|------|-------|
| `file` | n8n Binary File | `={{ $binary.data }}` (from webhook) |
| `model` | Text | `Systran/faster-whisper-base` |
| `response_format` | Text | `json` |

**Output:** JSON with `text` field containing full transcript.

### Insight Extraction (LLM)

Use the **OpenAI Chat Model** node with LM Studio's OpenAI-compatible API.

#### LM Studio Setup
1. Start LM Studio and load a model (e.g., `qwen2.5-7b-instruct`)
2. Go to **Developer** tab → Start server (default port: 1234)
3. Server exposes OpenAI-compatible endpoints at `http://localhost:1234/v1`

#### LM Studio Recommended Settings

For reliable n8n integration, enable these settings in LM Studio (**Developer** tab):

| Setting | Value | Why |
|---------|-------|-----|
| Just-in-Time Model Loading | ON | Loads model on first request (no manual loading needed) |
| Auto unload unused JIT loaded models | ON | Frees memory when idle |
| Max idle TTL | 5 minutes | Balance between responsiveness and memory usage |
| Only Keep Last JIT Loaded Model | ON | Prevents memory issues with multiple models |

These settings ensure the model loads automatically when n8n sends a request and unloads when idle, preventing memory exhaustion during long-running workflows.

#### n8n Credential Configuration
Create an **OpenAI API** credential with:

| Setting | Value |
|---------|-------|
| API Key | `lm-studio` (any non-empty string works) |
| Base URL | `http://host.docker.internal:1234/v1` (from Docker) |

### Output Format
- **Location:** `data/notes/YYYY-MM-DD-<title-slug>-<hash>.md`
- **Format:** Obsidian-compatible markdown with YAML frontmatter

---

## Output Specification

### Filename (v0.2.0)
```
YYYY-MM-DD-<title-slug>-<hash>.md
```
Example: `2024-01-15-api-integration-idea-a1b2c3d4.md`

Components:
1. **Date:** ISO date of processing
2. **Slug:** LLM-generated title (sanitized, max 50 chars)
3. **Hash:** First 8 characters of file's SHA256 hash (enables idempotent updates)

#### Slug Generation (Code Node)

```javascript
const llmResponse = $json;

// Extract title from LLM response
const rawTitle = llmResponse.title || 'voice-memo';

// Sanitize: lowercase, replace non-alphanumeric with hyphens, trim
const slug = rawTitle
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, '-')
  .replace(/^-+|-+$/g, '')
  .substring(0, 50);

// Generate date prefix
const date = new Date().toISOString().split('T')[0];

return {
  filename: `${date}-${slug}.md`,
  title: llmResponse.title || rawTitle,
  slug,
  date,
  ...llmResponse
};
```

### Markdown Structure (v0.2.0)

```markdown
---
title: "API Integration Idea"
date: 2024-01-15T10:30:00.000Z
type: voice-memo
duration: 127.5
original_filename: "voice-memo-2024-01-15.m4a"
audio_archive: "[[audio-archive/2024-01-15-api-integration-idea-a1b2c3d4.m4a]]"
tags:
  - memo
  - api
  - architecture
status: processed
---

# API Integration Idea

**Date:** January 15, 2024 at 10:30 AM
**Type:** Voice Memo

---

## Summary

Brief 2-3 sentence summary of the memo content.

## Key Points

- Main point 1
- Main point 2
- Main point 3

## Action Items

- [ ] Task to follow up on
- [ ] Another task

## Questions & Follow-ups

- Question to research?
- Topic needing more thought?

---

## Raw Transcript

<details>
<summary>Click to expand full transcript</summary>

Full transcript text here...

</details>
```

### YAML Frontmatter Fields (v0.2.0)

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Memo title (LLM-generated) |
| `date` | ISO 8601 | Processing date/time |
| `type` | string | Always `voice-memo` |
| `duration` | string | Audio duration in seconds (from ffprobe) |
| `original_filename` | string | Original uploaded filename |
| `audio_archive` | string | Obsidian wikilink to archived audio file |
| `tags` | list | Always includes `memo`, plus extracted topics |
| `status` | string | `processed` |

### Markdown Generation (Code Node)

```javascript
const data = $json;
const transcript = $('Whisper Transcription').first().json.text;

// Build YAML frontmatter
const tags = ['memo', ...(data.key_topics || [])].map(t => `  - ${t}`).join('\n');
const frontmatter = `---
title: ${data.title}
date: ${new Date().toISOString()}
type: memo
tags:
${tags}
status: processed
---`;

// Build key points list
const keyPoints = (data.key_points || [])
  .map(p => `- ${p}`)
  .join('\n') || '- No key points identified';

// Build action items with checkboxes
const actionItems = (data.action_items || [])
  .map(item => `- [ ] ${item}`)
  .join('\n') || '- No action items identified';

// Build questions list
const questions = (data.questions || [])
  .map(q => `- ${q}`)
  .join('\n') || '- No questions identified';

// Assemble full markdown
const markdown = `${frontmatter}

# ${data.title}

**Date:** ${data.date}
**Type:** Voice Memo

---

## Summary

${data.summary || 'No summary available.'}

## Key Points

${keyPoints}

## Action Items

${actionItems}

## Questions & Follow-ups

${questions}

---

## Raw Transcript

<details>
<summary>Click to expand full transcript</summary>

${transcript}

</details>
`;

return {
  filename: data.filename,
  content: markdown
};
```

---

## LLM Prompt

### System Message
```
You are a personal assistant that processes voice memo transcripts. You extract structured information and return valid JSON.

IMPORTANT: Return ONLY raw JSON. Do not wrap in markdown code blocks. Do not include any text before or after the JSON.
```

### User Message Template
```
Analyze this voice memo transcript and extract structured information.

TRANSCRIPT:
{{ $json.text }}

Return a JSON object with these fields:

{
  "title": "Brief descriptive title for the memo (5-8 words)",
  "summary": "2-3 sentence summary of what was discussed",
  "key_points": ["Main points or ideas mentioned"],
  "action_items": ["Tasks or things to do that were mentioned"],
  "questions": ["Questions raised or topics needing follow-up"],
  "key_topics": ["2-5 short tags for categorization"]
}

Guidelines:
- Be concise but capture important details
- Title should capture the main topic or purpose
- key_points are the important ideas or information
- action_items are concrete tasks (things to do)
- questions are open items needing research or thought
- key_topics should be 2-5 short tags suitable for categorization
- Return ONLY the JSON object, no markdown formatting
```

---

## Remote Access with Tailscale

Tailscale creates a secure private network (tailnet) that lets you access your home services from anywhere without exposing them to the public internet.

### Why Tailscale?

| Traditional Approach | Tailscale Approach |
|---------------------|-------------------|
| Port forwarding on router | No router config needed |
| Dynamic DNS for changing IP | Stable hostname (e.g., `macbook.tail1234.ts.net`) |
| SSL certificates | Built-in encryption (WireGuard) |
| Firewall rules | Access limited to your devices |
| VPN server setup | Zero server setup |

### Setup Overview

1. **Install Tailscale** on your server (Mac/Linux running LIMA)
2. **Install Tailscale** on your phone/laptop
3. **Both devices join your tailnet** (authenticated via Google/GitHub/etc.)
4. **Access n8n** via Tailscale hostname: `http://macbook:5678/webhook/memo`

### iOS Shortcut Example

Create a Shortcut that:
1. Records audio (or receives shared audio)
2. Uses "Get Contents of URL" action:
   - URL: `http://<tailscale-hostname>:5678/webhook/memo`
   - Method: POST
   - Request Body: File (the audio)
3. Shows notification with result

This lets you record a voice memo and tap "Share → LIMA" to process it.

---

## Error Handling

**Minimal for demo purposes:**

1. **Whisper fails:** Return error via webhook response
2. **LLM fails:** Save transcript-only note with `status: transcribed`
3. **File write fails:** Return error via webhook response

No retry logic, no dead letter queue, no alerting.

---

## Configuration

### Environment Variables (already in .env)
- `WHISPER_PORT` - Whisper service port (default: 9000 external, 8000 internal)

### n8n Credentials (configured in UI)

#### LM Studio Credential
Create an **OpenAI API** credential named "LM Studio Local":

| Field | Value |
|-------|-------|
| API Key | `lm-studio` (placeholder, not validated) |
| Base URL | `http://host.docker.internal:1234/v1` |

### LM Studio Requirements
- LM Studio installed and running on the host machine
- A model loaded (recommended: `qwen2.5-7b-instruct` or `llama-3.1-8b-instruct`)
- Developer server started on port 1234

### Workflow Variables
- Whisper endpoint URL: `http://whisper:8000/v1/audio/transcriptions`
- Model install URL: `http://whisper:8000/v1/models/Systran%2Ffaster-whisper-base`
- Output directory: `/data/notes/`

---

## Future Enhancements

1. **Web recording UI:** Simple page to record directly in browser
2. ~~**File deduplication:** Track processed files in Postgres~~ ✅ Done in v0.2.0 (hash-based)
3. **Embeddings:** Generate vectors for semantic search (pgvector ready)
4. **Categories:** Auto-categorize memos (idea, task, reminder, analysis)
5. **Obsidian plugin:** Custom view for memo dashboard
6. **Apple Watch:** Direct recording from watch
7. **Multi-modal support:** Process images, videos, PDFs (v0.2.0 has detection, not processing)

---

## Success Criteria

1. ✅ User can send audio via webhook and receive structured note
2. ✅ User can drop audio file and have it auto-processed
3. ✅ Output markdown opens correctly in Obsidian
4. ✅ Tags appear in Obsidian's tag pane
5. ✅ Checkboxes are interactive
6. ✅ Transcript is preserved but collapsed
7. ✅ Workflow is readable and modifiable by developers
8. ✅ Remote access works via Tailscale
9. ✅ Re-processing same file updates existing note (idempotent)
10. ✅ Original audio preserved in archive with Obsidian link

---

## Decisions

1. **Dual triggers** - Webhook for remote, file watcher for local convenience
2. **Short memos focus** - 1-5 minutes typical, no chunking needed
3. **No diarization** - Single-speaker memos don't need it
4. **Tailscale for remote** - Secure without public exposure
5. **File-only for v1** - Markdown files are the single source of truth
6. **Hash-based idempotency** - Same file content = same output filename (v0.2.0)
7. **Archive originals** - Keep audio files linked from notes for playback (v0.2.0)

---

## Changelog

### v0.2.0 - File Lifecycle Management

**New Features:**
- **Dual triggers:** Webhook + Local File Trigger (watch `/data/voice-memos/`)
- **Hash-based deduplication:** Same audio file produces same output filename
- **Audio archiving:** Original files moved to `/data/audio-archive/` after processing
- **Duration metadata:** ffprobe extracts audio length into frontmatter
- **Obsidian audio links:** `[[audio-archive/...]]` wikilinks in frontmatter
- **Input type detection:** Extensible architecture for future image/video/PDF support
- **Idempotent reprocessing:** Re-dropping same file updates the note (deletes old hash match first)

**Breaking Changes:**
- Filename format changed: `YYYY-MM-DD-slug-hash.md` (was `YYYY-MM-DD-slug.md`)
- New frontmatter fields: `duration`, `original_filename`, `audio_archive`

**Architecture Changes:**
- Added Crypto node for file hashing
- Added ffprobe Execute Command node for duration
- Added "Delete Old Hash" node for idempotent updates
- Added "Archive Audio" node for file lifecycle

### v0.1.0 - Initial Release

- Webhook trigger for remote audio upload
- Whisper transcription via local Speaches container
- LLM insight extraction (title, summary, key points, action items, questions, tags)
- Obsidian-compatible markdown output with YAML frontmatter
- Collapsible raw transcript section
