# LIMA Use Cases

Beyond voice memo processing, LIMA's architecture enables various automation scenarios.

## Current: Voice Memo Processing
- Drop audio files or upload via webhook
- Automatic transcription + AI extraction
- Structured markdown notes in Obsidian

## Potential Use Cases

### IoT Voice Control
**Concept:** Control smart home devices via voice memos from anywhere.

**How it works:**
1. Record voice command on phone ("Turn off the bedroom lights")
2. Upload to LIMA webhook (works over Tailscale from anywhere)
3. Whisper transcribes, LLM extracts intent + device
4. n8n triggers Home Assistant / MQTT / device API

**Benefits:**
- Works from anywhere (no local network required with Tailscale)
- Natural language commands ("make it warmer" vs exact temperature)
- Offline-capable LLM means no cloud dependency

### Meeting Notes from Video Calls
- Extract audio from Zoom/Meet recordings
- Generate structured meeting notes with action items
- Auto-tag by project/team

### Podcast/Interview Processing
- Transcribe podcast episodes
- Extract key quotes and timestamps
- Generate show notes

### Lecture/Course Notes
- Record lectures, generate study notes
- Extract key concepts and definitions
- Create flashcard-ready summaries

### Field Notes / Research
- Voice-record observations in the field
- Structured extraction based on research template
- GPS/timestamp metadata integration

### Accessibility
- Voice-to-text note taking for users who can't type
- Audio descriptions to text
- Meeting accessibility for deaf/HoH participants

---

## Architecture Advantages

| Feature | Benefit |
|---------|---------|
| Webhook trigger | Works from any device with HTTP |
| File trigger | Works with local file sync (Syncthing, etc.) |
| Tailscale | Secure remote access without port forwarding |
| Local LLM | Privacy, no API costs, works offline |
| n8n | Easy to extend with new integrations |
