"""LIMA's production extraction task — single source of truth.

Mirrors the live n8n workflow "Voice Memo Processor 0.3.1" exactly:
- SYSTEM_MESSAGE: the Extract Insights agent node's system message, verbatim.
- USER_TEMPLATE: the agent node's user prompt shape.
- SCHEMA: the Structured Output Parser node's JSON Schema, verbatim.

Teacher labeling, student fine-tuning, and the extraction benchmark harness
all import from here so no condition can drift from production. If the n8n
workflow's prompt or schema changes, update this file in the same commit.
"""

SYSTEM_MESSAGE = """You are a personal knowledge assistant that transforms voice memo transcripts into structured notes. Voice memos are often stream-of-consciousness with filler words, repetition, and incomplete thoughts. Extract the signal from the noise.

1. Never invent information not in the transcript
2. Ignore filler words, false starts, and repetition
3. **Short ≠ unclear**. Brief memos with clear intent are valid:
   - Shopping lists: "Need to get bread and milk" → action_items: ["Buy bread and milk"]
   - Quick reminders: "Call mom tomorrow" → action_items: ["Call mom tomorrow"]
   - Single tasks: "Research GPU pricing for the server upgrade" → valid memo
4. ONLY use the fallback for truly unintelligible transcripts:
   - Garbled speech: "uh... maybe... I don't know... something about..."
   - Background noise transcribed as words: "[inaudible] [music] [crosstalk]"
   - Incomplete fragments with no clear subject: "and then the... yeah..."

   Fallback format:
   {"title": "Unclear memo", "summary": "Transcript too brief or unclear to extract meaningful content.", "key_points": [], "action_items": [], "questions": [], "tags": ["needs-review"]}"""

USER_TEMPLATE = """Transform this voice memo transcript into a structured note.

TRANSCRIPT:
{transcript}"""

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "A concise, descriptive title for this voice memo (5-10 words)",
        },
        "summary": {
            "type": "string",
            "description": "A 2-3 sentence summary capturing the main topic and conclusion",
        },
        "key_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Important facts, decisions, or observations mentioned",
        },
        "action_items": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Tasks or next steps mentioned (empty array if none)",
        },
        "questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Open questions or things to figure out (empty array if none)",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-5 lowercase kebab-case tags for categorization",
        },
    },
    "required": ["title", "summary", "key_points", "action_items", "questions", "tags"],
    "additionalProperties": False,
}
