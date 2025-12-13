# LIMA Use Cases

Beyond voice memo processing, LIMA's architecture enables various automation scenarios.

> See also: [BACKLOG.md](BACKLOG.md) for the development roadmap and enhancement ideas.

## Current Features (v0.3.0)

### Voice Memo Processing
- Drop audio files in `data/voice-memos/` or upload via webhook
- Automatic transcription via local Whisper
- AI-powered insight extraction (title, summary, action items, tags)
- Structured markdown notes saved to Obsidian vault

### Voice Recorder UI
A browser-based interface that turns LIMA into a complete voice-to-knowledge app.

**Access:** http://localhost:8888/lima/recorder/ (or via Tailscale for remote access)

**Features:**
- Zero friction — no file management, just click and talk
- Mobile-first — works from phone browser via Tailscale
- Live feedback — watch your voice become structured notes
- Multimodal detection — recognizes audio, images, video, PDF uploads

### Multimodal Input Detection
The workflow detects input type and routes accordingly:
- **Audio:** Full transcription + insight extraction pipeline
- **Other formats:** Prepared for future processing (images, video, PDF)

---

## Potential Use Cases

### Personal Knowledge Base
**Concept:** Your voice becomes a searchable second brain.

**Scenarios:**
- Weekly review: "What were my key decisions this week?"
- Project context: "Summarize everything I've said about Project Alpha"
- Pattern recognition: "What topics keep coming up in my memos?"

**Technical foundation:**
- pgvector for semantic embeddings
- RAG pipeline for contextual answers
- Obsidian graph view for visual connections

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

**Advanced scenario:**
```
"Remind me to water the plants when I get home tomorrow"
        ↓
Extract: intent=reminder, trigger=arrive_home, action=water_plants
        ↓
Create Home Assistant automation via n8n webhook
        ↓
Link to Obsidian note with plant care history
```

### Meeting Notes from Video Calls
- Extract audio from Zoom/Meet recordings
- Generate structured meeting notes with action items
- Auto-tag by project/team
- Multi-speaker diarization (future): "What did Sarah commit to?"

### Context-Aware Routing
**Concept:** Single inbox, intelligent routing to specialized workflows.

| What you say | Where it goes | What happens |
|-------------|---------------|--------------|
| "I just met with..." | Meeting Notes | Participants, decisions, action items |
| "Idea for a feature..." | Idea Capture | Related notes search, innovation tags |
| "Remember to..." | Quick Todo | Checkbox format, calendar integration |
| "Question: What did..." | Memory Query | Semantic search + RAG answer |
| "Today I felt..." | Journal Entry | Private, sentiment analysis |

### Podcast/Interview Processing
- Transcribe podcast episodes
- Extract key quotes and timestamps
- Generate show notes
- Speaker attribution with diarization

### Lecture/Course Notes
- Record lectures, generate study notes
- Extract key concepts and definitions
- Create flashcard-ready summaries
- Link to related lectures via semantic search

### Field Notes / Research
- Voice-record observations in the field
- Structured extraction based on research template
- GPS/timestamp metadata integration
- Cross-reference with previous field sessions

### Accessibility
- Voice-to-text note taking for users who can't type
- Audio descriptions to text
- Meeting accessibility for deaf/HoH participants
- Natural language queries for those who struggle with search interfaces

---

## Architecture Advantages

| Feature | Benefit |
|---------|---------|
| Webhook trigger | Works from any device with HTTP |
| File trigger | Works with local file sync (Syncthing, etc.) |
| Tailscale | Secure remote access without port forwarding |
| Local LLM | Privacy, no API costs, works offline |
| pgvector | Semantic search without external vector DB |
| n8n | Easy to extend with new integrations |
| Obsidian vault | Standard markdown, portable, graph view |

## The Local-First Manifesto

LIMA embodies [local-first software principles](https://www.inkandswitch.com/local-first.html):

| Principle | LIMA Implementation |
|-----------|-------------------|
| **Works offline** | All processing local, Tailscale for remote |
| **Data ownership** | PostgreSQL + Obsidian vault, export anytime |
| **No subscription** | One-time hardware investment |
| **Privacy by default** | Your thoughts never leave your machine |
| **Interoperable** | Webhooks, standard formats, ecosystem friendly |

> "Another computer should never prevent you from working." — Ink & Switch

## The Pitch

**"ChatGPT knows everything except your life. LIMA knows nothing except everything YOU'VE ever said."**

**The demo:**
1. Record a voice memo on your phone
2. Watch LIMA process it in real-time (transcription → extraction → save)
3. Open Obsidian and see your structured note appear
4. All locally, no cloud, full privacy
