# LIMA Backlog

> LIMA exists to show how much fun you can have when you build your own tools.
> This backlog collects the ideas, experiments, and rabbit holes waiting to be explored.

**Philosophy:** We spend all day inside other people's tools. This is your invitation to build your own — and enjoy it.

---

## Current State: v0.3.0

### Voice Recorder UI ✓
**Status:** Basic version complete - browser-based recording with webhook upload works.

**What's working:**
- [x] Browser-based audio recording (MediaRecorder API)
- [x] Webhook upload to LIMA processor
- [x] Multimodal input detection (audio/image/video/PDF)
- [x] Caddy reverse proxy for microphone access

**What's next:**
- [ ] Live processing status polling (currently fire-and-forget)
- [ ] Inline markdown preview of results
- [ ] Recent notes panel
- [ ] File tree view showing processed memos

---

## The Three Paths Forward

Following the three "aha moments" from the talk: **Accessible → Practical → Achievable**

### Path 1: Making It More Accessible

*Polish the UX, make it delightful*

#### File Tree Enhancement (DEMO READY)
**Vision:** Add a file browser to the Voice Recorder UI showing processed notes and archived audio.
**Why:** Makes the UI self-contained - record, process, and browse all in one place.
**Status:** Planned for demo via n8n-mcp live coding session.

#### Live Processing Dashboard
**Vision:** Real-time web UI showing workflow progress as it happens.
**Why:** Transparency builds trust. Watching AI "think" is satisfying.
**Features:**
- Live transcript streaming as Whisper processes
- AI extraction progress indicators
- Recent notes list with click-to-open
- Stats: memos processed, words transcribed, action items extracted

#### Retro Mode (For Fun)
**Vision:** Output notes styled like typewriter paper, terminal green text, or dot-matrix printer.
**Why:** Because we're allowed to build things purely because they delight us.

---

### Path 2: Making It More Practical

*Robustness, reliability, real-world use cases*

#### Context-Aware Routing
**Vision:** Single inbox, intelligent routing to specialized workflows.
**Why:** This mirrors how humans mentally triage thoughts; the system becomes a cognitive extension, not just a pipeline.

**Example routes:**
- "I just met with..." → Meeting Notes (participants, action items)
- "Idea for a feature..." → Idea Capture (related notes, tags)
- "Remember to..." → Quick Todo (checkbox format)
- "Question: What did..." → Memory Query (semantic search)

**Implementation:**
- Quick LLM classification (~100ms with local model)
- n8n Switch node routes to sub-workflows
- User-configurable routing rules via JSON

#### LLM Context Overflow Handling
**Problem:** Long transcripts can exceed LLM context window, causing failures.
**Why this matters:** Silent failures erode trust, especially for important meetings.

**Proposed solution:**
- Detect transcript length before LLM call
- Split into chunks with 30% overlap (preserve context)
- Summarize each chunk independently
- Synthesize chunk summaries into final output
- Streaming insights for long meetings (push partial results)

#### Error Handling & Failed File Management
**Problem:** When processing fails, source files remain in `voice-memos/` with no indication of failure.
**Why this matters:** Essential for trust — especially when models fail silently.

**Proposed solution:**
- Move failed files to `voice-memos/failed/`
- Create `{filename}.error.json` sidecar with error details and retry suggestions
- Graceful degradation: Whisper base → tiny → manual review queue
- Optional webhook notification on failure

#### Video-to-Audio Extraction
**Problem:** Meeting recordings often come as MP4/video files, but we only need the audio track for transcription.
**Why this matters:** Video files are 10-20x larger than audio-only. Storing both wastes disk space and slows uploads.

**Proposed solution:**
- Detect video files (MP4, MOV, MKV, WebM with video track)
- Extract audio track via ffmpeg before transcription
- Optionally archive video or delete after extraction
- Example: `ffmpeg -i input.mp4 -vn -acodec libmp3lame -q:a 2 output.mp3`

**Benefits:**
- 328MB MP4 → 13MB MP3 (25x smaller)
- Faster webhook uploads
- n8n container already has ffmpeg installed

#### Improved Media Type Detection
**Problem:** Browsers lie — webm isn't always video. This causes routing issues.
**Current workaround:** Treat all `video/webm` as audio (works because Whisper extracts audio track anyway)

**Proposed solution:**
- Use ffprobe to detect actual streams
- Check if file has video stream with frames vs audio-only
- Route accordingly with proper error handling
- File size heuristic as fallback

#### Audio Quality Detection
**Vision:** Warn if audio quality is poor before transcription attempts.
**Why:** Better to know upfront than waste time on a bad recording.
**Features:**
- Detect low bitrate, high noise, clipping
- Suggest re-recording or manual review
- Auto-enhance with ffmpeg filters when possible

#### Batch Processing
**Vision:** Process multiple files in queue with priority handling.
**Use case:** Backfilling old recordings, bulk imports, emergency catch-up.
**Features:**
- Rate limiting for API-based LLMs
- Priority queue for urgent memos
- Progress tracking across batch

#### Dynamic Prompt Loading from Container Filesystem
**Problem:** LLM prompts are currently embedded in workflow nodes. Iterating on prompts means manually editing in n8n UI or burning LLM tokens via n8n-mcp.
**Vision:** Store prompts as files in `/data/prompts/` and dynamically read them at execution time.
**Why:** Iterate on prompts by editing markdown files - no UI clicks, no LLM token usage, no workflow modifications.

**Implementation steps:**
1. Decompose `docs/insight-extraction-prompt.md` into separate files:
   - `/data/prompts/insight-extraction-system.txt` (system prompt only)
   - `/data/prompts/insight-extraction-user.txt` (user message template)
   - `/data/prompts/insight-extraction-schema.json` (example output for validation)
2. Mount `/data/prompts/` as read-only volume in n8n container (docker-compose.yml)
3. Update LLM node to use n8n's file read expressions:
   - System prompt: `{{ $filesystem.readFile('/data/prompts/insight-extraction-system.txt') }}`
   - User message: `{{ $filesystem.readFile('/data/prompts/insight-extraction-user.txt').replace('TRANSCRIPT_PLACEHOLDER', $json.text) }}`
4. Handle template variables in user message (replace placeholder with actual transcript)
5. Add fallback to embedded prompt if file missing (graceful degradation)

**Benefits:**
- Edit prompts without re-exporting workflows
- Easier A/B testing of different prompt strategies
- Keep prompt engineering separate from workflow engineering
- Version control prompts independently

#### Timezone-Aware Date Handling
**Problem:** LLM outputs recording dates in UTC instead of local timezone. This affects both the content of generated notes and file organization.
**Why this matters:** Memos recorded at "11pm on Tuesday" appear as "Wednesday" if UTC is ahead of local time. This breaks mental models and makes files harder to find.

**Minimal fix:**
- Make date handling timezone-aware throughout the pipeline
- Use local timezone for date formatting in LLM output
- Preserve correct "day of recording" from user's perspective

**Broader enhancements:**
- More granular timestamps in filenames (include hour, not just day)
- Better time-based organization: `2025-12-11/14-30-voice-memo.md` instead of `2025-12-11-voice-memo.md`
- Configurable date format patterns (ISO vs local convention)
- Handle edge cases: DST transitions, multi-timezone teams, recordings that span midnight

**Implementation considerations:**
- Detect timezone from browser when using Voice Recorder UI
- Pass timezone metadata through webhook payload
- Fall back to server timezone or configurable default
- Store timezone in file metadata for audit trail


#### Migrate Recorder UI serving from n8n webhook to Caddy (pure static serving)
  - Purpose: Decouple UI from workflow engine, faster load times
  - Access: http://localhost:8888/recorder
  - Keep n8n workflow for API/Backend logic only

---

### Path 3: Building AI Systems (The Frontier)

*This is where you get your hands dirty with agents, not infrastructure*

#### Conversational Memory Query
**Vision:** Ask your notes questions via voice and get AI-generated answers with citations.
**Why:** This turns LIMA from a voice memo processor into a personal knowledge interface.

**Example:** "What did I discuss with Sarah about the budget?" → Returns answer with [[wikilinks]] to source notes.

**Implementation:**
- Generate embeddings for all existing notes (pgvector already installed!)
- Auto-index new notes as they're created
- Question detection → semantic search → RAG synthesis
- Output with Obsidian wikilinks to sources

**Technical approach:**
- Model: `nomic-embed-text` via Ollama (768 dimensions, fast, local)
- Chunking: 500 tokens with 100 token overlap
- Preserve markdown structure (don't split mid-heading)

#### Multi-Agent Workflow Orchestration

**Vision:** Use n8n's agent nodes to create specialized agents for different tasks, moving beyond single-LLM prompting.

> "The infrastructure is built. The hard part—Docker, Whisper, n8n, database—is done. Now you get to build the interesting AI systems on top. This is where you get your hands dirty with agents, not infrastructure."

**Approach A: Task-Specialized Agents**
- **Summarization Agent**: Dedicated to creating concise summaries with specific format
- **Title & Organization Agent**: Reads your existing notes via filesystem access, decides optimal save location and title based on your organization patterns
- **Action Item Extractor Agent**: Specialized in identifying tasks, deadlines, and assignees
- **Coordinator Agent**: Synthesizes outputs from specialized agents

**Approach B: Research Pipeline**
Specialized agents working in concert for richer insights:
- **Research Analyst Agent**: Identifies new topics, retrieves context from prior meetings
- **Action Item Manager Agent**: Extracts tasks, checks for conflicts, suggests reassignments
- **Risk/Opportunity Agent**: Flags risks, identifies opportunities, suggests escalation
- **Coordinator Agent**: Synthesizes outputs into coherent document

**Implementation ideas:**
- Use n8n's Agent nodes with tool calling
- Give agents file system access to read existing notes and learn your organization patterns
- Chain agents with explicit handoffs (not just one giant prompt)
- Experiment with local models for specific tasks (e.g., tiny model for classification, larger for summarization)

#### Multi-speaker Diarization
**Vision:** Identify who said what in multi-person recordings.
**Why:** "What did Sarah specifically commit to?" becomes answerable.
**Implementation:**
- Use pyannote-audio via Execute Command node
- Output speaker-labeled VTT file
- Per-speaker insight extraction
- Requires speaker enrollment or pre-training

#### Hybrid Search
**Vision:** Combine semantic + keyword search for better retrieval.
**Why:** Dense vectors find conceptual similarity, sparse keywords find exact matches. Together they're powerful.
**Implementation:**
- Dense vectors (embeddings) for conceptual similarity
- Sparse keywords (tsvector) for exact matches
- Fused relevance scoring (RRF or similar)

---

## Integration & Expansion Ideas

### Home Assistant Integration
**Vision:** Voice memos that trigger smart home actions.
**Example:** "Remind me to water the plants when I get home"
**Flow:**
- Extract intent → Create Home Assistant automation via webhook
- Link to Obsidian note with context
- Location-based triggers

### Configurable LLM Prompts
**Vision:** Let users customize extraction behavior without touching code.
**Why:** Different people organize differently. Your tool should adapt to you.
**Implementation:**
- Environment variables or config file for prompts
- Different templates for different memo types (meetings, ideas, interviews)
- User-defined custom fields in output

---

## Development Philosophy

When you own the infrastructure, you're not in a sandbox:
- Need a Python script? Add it.
- Want a cron job? Set it up.
- Need Tailscale for remote access? Install it.
- Want to read files, run commands, add services? The computer is your oyster.

**This backlog isn't a to-do list — it's a playground.**

Pick one thread and pull. See where it takes you. Share what you build.

---

## Related Documentation

- [Audio Processing Guide](docs/audio-processing-guide.md) - ffmpeg patterns and chunking strategies
- [MCP Setup](docs/MCP_SETUP.md) - AI-assisted workflow development with n8n-mcp

**Archived:**
- [v0.3.0 Proposals](docs/archive/v0.3.0-proposals.md) - Original feature brainstorming (now integrated into backlog)
- [PRD: Voice Memo Workflow](docs/archive/PRD-voice-memo-workflow.md) - Original technical specification
