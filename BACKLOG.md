# LIMA Backlog

Issues and improvements for future versions.

> See also: [v0.3.0 Proposals](docs/v0.3.0-proposals.md) for detailed implementation plans.

## v0.3.0 Candidates

### Voice Recorder UI (FLAGSHIP)
**Vision:** A beautiful web interface served by n8n that captures audio, shows live processing, and displays results.
**Experience:**
```
Open URL → Tap record → Watch transcription appear → See insights extracted → Done
```
**Why this changes everything:**
- Zero friction — no file management, just click and talk
- Self-contained — one URL does everything (n8n serves UI AND processes audio)
- Mobile-first — works from phone browser via Tailscale
- Full-stack showcase — proves n8n can be a complete application platform
**Implementation:**
- n8n webhook serves HTML with MediaRecorder API
- Status polling shows live progress (transcribing → extracting → complete)
- Markdown preview with Obsidian deep links
- Recent notes panel

### Conversational Memory Query
**Vision:** Ask your notes questions via voice and get AI-generated answers with citations.
**Example:** "What did I discuss with Sarah about the budget?" → Returns answer with [[wikilinks]] to source notes.
**Implementation:**
- Generate embeddings for all existing notes (pgvector already installed!)
- Auto-index new notes as they're created
- Question detection → semantic search → RAG synthesis
- Output with Obsidian wikilinks to sources
**Why:** Turns LIMA from a capture tool into a queryable second brain.

### Context-Aware Routing
**Vision:** Single inbox, intelligent routing to specialized workflows.
**Example routes:**
- "I just met with..." → Meeting Notes (participants, action items)
- "Idea for a feature..." → Idea Capture (related notes, tags)
- "Remember to..." → Quick Todo (checkbox format)
- "Question: What did..." → Memory Query (semantic search)
**Implementation:**
- Quick LLM classification (~100ms with local model)
- n8n Switch node routes to sub-workflows
- User-configurable routing rules via JSON

### LLM Context Overflow Handling
**Problem:** Long transcripts can exceed LLM context window, causing failures.
**Current behavior:** Workflow fails at "Extract Insights" node.
**Proposed solution:**
- Detect transcript length before LLM call
- Split into chunks with 30% overlap (preserve context)
- Summarize each chunk independently
- Synthesize chunk summaries into final output
- Streaming insights for long meetings (push partial results)

### Error Handling & Failed File Management
**Problem:** When processing fails (LLM output validation, context overflow, etc.), source files remain in `voice-memos/` with no indication of failure.
**Current behavior:** File just sits there; user has to check n8n executions to see what happened.
**Proposed solution:**
- Move failed files to `voice-memos/failed/`
- Create `{filename}.error.json` sidecar with:
  ```json
  {
    "error": "LLM context overflow",
    "timestamp": "2024-12-10T10:30:00Z",
    "transcript_length": 15420,
    "retry_suggestion": "Use hierarchical summarization"
  }
  ```
- Graceful degradation: Whisper base → tiny → manual review queue
- Optional webhook notification on failure

## v0.4.0+ Ideas

### Multi-Agent Research Pipeline
Specialized agents working in concert for richer insights:
- **Research Analyst Agent**: Identifies new topics, retrieves context from prior meetings
- **Action Item Manager Agent**: Extracts tasks, checks for conflicts, suggests reassignments
- **Risk/Opportunity Agent**: Flags risks, identifies opportunities, suggests escalation
- **Coordinator Agent**: Synthesizes outputs into coherent document

### Home Assistant Integration
Voice memos that trigger smart home actions:
- "Remind me to water the plants when I get home"
- Extract intent → Create Home Assistant automation via webhook
- Link to Obsidian note with context

### Live Processing Dashboard
Real-time web UI showing workflow progress:
- Live transcript streaming as Whisper processes
- AI extraction progress indicators
- Recent notes list with click-to-open
- Stats: memos processed, words transcribed, action items extracted

### Multi-speaker Diarization
- Use pyannote-audio via Execute Command node
- Output speaker-labeled VTT file
- Per-speaker insight extraction
- "What did Sarah specifically commit to?"

### Configurable LLM Prompts
- Allow customization of extraction prompts via environment variables or config file
- Different prompt templates for different memo types (meetings, ideas, interviews)
- User-defined custom fields in output

### Improved Media Type Detection
**Problem:** WebM files are detected as audio because browser MediaRecorder sends audio-only as `video/webm`. Current workaround treats all `video/webm` as audio, which could mishandle actual video files.
**Current behavior:** `video/webm` → always treated as audio → sent to Whisper (works because Whisper extracts audio track anyway)
**Proposed solution:**
- Use ffprobe to detect actual streams: `ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0`
- Check if file has video stream with frames vs audio-only
- Route accordingly: audio-only → transcription, video with audio → transcription, video without audio → error/skip
- File size heuristic as fallback (audio-only webm from browser is typically <1MB)

### Audio Quality Detection
- Warn if audio quality is poor (low bitrate, high noise)
- Suggest re-recording or manual review
- Auto-enhance with ffmpeg filters

### Batch Processing
- Process multiple files in queue
- Rate limiting for API-based LLMs
- Priority queue for urgent memos

### Hybrid Search
Combine semantic + keyword search for better retrieval:
- Dense vectors for conceptual similarity
- Sparse keywords (tsvector) for exact matches
- Fused relevance scoring
