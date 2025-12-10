# PRD: LIMA Meeting Processing Workflow

## Overview

A demonstration n8n workflow that processes meeting audio files into structured, Obsidian-compatible markdown notes with extracted insights.

**Purpose:** Demo and inspiration for local-first meeting intelligence, not production automation.

**Target Users:** Developers and power users who want to tinker with local AI solutions for meeting documentation.

---

## Goals

1. **Demonstrate end-to-end local processing:** Audio → Transcript → Insights → Markdown
2. **Obsidian compatibility:** Output files work seamlessly when Obsidian points at `data/notes/`
3. **Readable, hackable workflow:** Simple enough to understand and modify
4. **Zero cloud dependencies:** All processing happens locally

## Non-Goals

- Production-grade reliability (retry logic, monitoring, alerting)
- Multi-user support
- Real-time streaming transcription
- Complex chunking/parallel processing for long files
- Embeddings or RAG pipeline
- Automated file watching (manual trigger only for v1)

---

## User Flow

```
1. User drops audio file (.mp3, .m4a, .wav, .flac) into data/audio/
2. User opens n8n and manually triggers the workflow
3. User selects/confirms the audio file to process
4. Workflow:
   a. Sends audio to local Whisper endpoint
   b. Receives transcript
   c. Sends transcript to local LLM with extraction prompt
   d. Formats output as Obsidian-friendly markdown
   e. Writes file to data/notes/
5. User opens Obsidian (pointed at data/notes/) and sees the new note
```

---

## Technical Components

### Trigger
- **Manual trigger** with file path input
- User provides: audio file path (relative to `/data/audio/`)

### Transcription
- **Endpoint:** `http://whisper:9000/v1/audio/transcriptions` (Docker) or `http://host.docker.internal:9002/v1/audio/transcriptions` (native)
- **Input:** Audio file (multipart form upload)
- **Output:** JSON with `text` field containing full transcript

### Insight Extraction
- **Endpoint:** Configured in n8n credentials (Ollama, LMStudio, or any OpenAI-compatible endpoint)
- **Model:** User's choice (configured in n8n)
- **Prompt:** Structured extraction prompt (see below)
- **Output:** JSON with extracted sections

### Output Format
- **Location:** `data/notes/YYYY-MM-DD-<title-slug>.md`
- **Format:** Obsidian-compatible markdown with YAML frontmatter

---

## Output Specification

### Filename
```
YYYY-MM-DD-<title-slug>.md
```
Example: `2024-01-15-weekly-standup.md`

Title slug derived from:
1. LLM-generated title (preferred)
2. Fallback: audio filename without extension

### Markdown Structure

```markdown
---
title: Weekly Standup
date: 2024-01-15T10:30:00
audio_file: weekly-standup.mp3
duration: 42:53
tags:
  - meeting
  - standup
status: processed
---

# Weekly Standup

**Date:** 2024-01-15 10:30 AM
**Duration:** 43 minutes
**Participants:** (if detected)

---

## Summary

Brief 2-3 sentence summary of the meeting.

## Key Decisions

- Decision 1
- Decision 2

## Action Items

- [ ] Task description @owner (if detected)
- [ ] Another task
- [ ] Third task

## Risks & Blockers

- Risk or blocker 1
- Risk or blocker 2

## Open Questions

- Unanswered question 1?
- Topic needing follow-up?

## Discussion Notes

Key discussion points organized by topic.

---

## Raw Transcript

<details>
<summary>Click to expand full transcript</summary>

Full transcript text here...

</details>
```

### YAML Frontmatter Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Meeting title (LLM-generated or filename) |
| `date` | ISO 8601 | Meeting date/time |
| `audio_file` | string | Source audio filename |
| `duration` | string | Estimated duration (if available) |
| `tags` | list | Always includes `meeting`, plus extracted topics |
| `status` | string | `processed` |

### Obsidian Compatibility Features

1. **Tags:** Use `#tag` format in frontmatter for Obsidian tag pane
2. **Checkboxes:** `- [ ]` format for native checkbox support
3. **Collapsible sections:** `<details>` for raw transcript
4. **Clean headers:** Standard markdown headers for outline view

### Optional: Wiki-Links for Graph View

To make Obsidian's graph view useful, the LLM can optionally generate:
- Links to project pages: `[[Project Alpha]]`
- Links to people: `[[John Smith]]`
- Links to related meetings: `[[2024-01-08-weekly-standup]]`

This is optional and can be added in v2.

---

## LLM Prompt

```
You are a meeting analyst. Analyze this meeting transcript and extract structured information.

TRANSCRIPT:
{transcript}

Respond in JSON format with these fields:

{
  "title": "Brief descriptive title for the meeting",
  "summary": "2-3 sentence summary of what was discussed",
  "decisions": ["List of decisions made"],
  "action_items": [
    {"task": "Description", "owner": "Name or null"}
  ],
  "risks": ["Risks or blockers mentioned"],
  "open_questions": ["Unanswered questions or topics needing follow-up"],
  "key_topics": ["Main topics discussed (for tags)"],
  "discussion_notes": "Organized notes on key discussion points"
}

Guidelines:
- Be concise but capture important details
- For action items, include owner if clearly assigned
- Only include sections with actual content (omit empty arrays)
- key_topics should be 2-5 short tags suitable for categorization
```

---

## Error Handling

**Minimal for demo purposes:**

1. **Whisper fails:** Show error message, stop workflow
2. **LLM fails:** Save transcript-only note with `status: transcribed`
3. **File write fails:** Show error in n8n execution log

No retry logic, no dead letter queue, no alerting.

---

## Configuration

### Environment Variables (already in .env)
- `WHISPER_PORT` - Whisper service port (default: 9000)

### n8n Credentials (configured in UI)
- OpenAI-compatible credential for LLM endpoint
  - Base URL: `http://host.docker.internal:11434/v1` (Ollama)
  - Or LMStudio, local vLLM, etc.

### Workflow Variables
- Whisper endpoint URL (hardcoded or environment)
- Output directory: `/data/notes/`

---

## Future Enhancements (Out of Scope for v1)

1. **Scheduled polling:** Watch `data/audio/` for new files
2. **File deduplication:** Track processed files in Postgres
3. **Chunking:** Split long recordings for parallel processing
4. **Embeddings:** Generate vectors for semantic search
5. **Speaker diarization:** Identify who said what
6. **Wiki-link generation:** Auto-link to projects/people
7. **Obsidian plugin:** Custom view for meeting dashboard

---

## Success Criteria

1. User can process an audio file with one click
2. Output markdown opens correctly in Obsidian
3. Tags appear in Obsidian's tag pane
4. Checkboxes are interactive
5. Transcript is preserved but collapsed
6. Workflow is readable and modifiable by developers

---

## Decisions

1. **One file per run** - Keep it simple, user triggers per audio file
2. **LLM prompt in repo** - Store prompt as a file in `workflows/prompts/` for version control; users can edit directly but we maintain the canonical version
3. **File-only for v1** - No Postgres writes. Markdown files are the single source of truth. Postgres + pgvector available for future semantic search features.
