# LIMA Backlog

Issues and improvements for future versions.

## v0.3.0 Candidates

### LLM Context Overflow Handling
**Problem:** Long transcripts can exceed LLM context window, causing failures.
**Current behavior:** Workflow fails at "Extract Insights" node.
**Proposed solution:**
- Detect transcript length before LLM call
- If too long, chunk transcript and summarize each chunk
- Then summarize the summaries (hierarchical summarization)
- Or: truncate to last N tokens with warning in output

### Error Handling & Failed File Management
**Problem:** When processing fails (LLM output validation, context overflow, etc.), source files remain in `voice-memos/` with no indication of failure.
**Current behavior:** File just sits there; user has to check n8n executions to see what happened.
**Proposed solutions:**
- Move failed files to `voice-memos/failed/` with error metadata
- Or: prefix with `error_` (e.g., `error_2025-12-10_test-sample.flac`)
- Or: create a `.error.json` sidecar file with failure details
- Lingering files in `voice-memos/` effectively indicate errors, but explicit handling would be clearer

## Future Ideas

### Multi-speaker Diarization
- Identify different speakers in the transcript
- Label sections by speaker

### Configurable LLM Prompts
- Allow customization of extraction prompts via environment variables or config file
- Different prompt templates for different memo types (meetings, ideas, interviews)

### Audio Quality Detection
- Warn if audio quality is poor (low bitrate, high noise)
- Suggest re-recording or manual review

### Progress Webhook
- Send progress updates during long processing
- Useful for UI integration

### Batch Processing
- Process multiple files in queue
- Rate limiting for API-based LLMs
