# Where Is My Data?

LIMA stores everything locally in the `data/` directory. This guide explains file locations, how to view your notes in Obsidian, and backup strategies.

## File Locations

```
data/
├── voice-memos/          # Input: Drop audio files here
│   └── webhook/          # Webhook uploads land here
├── notes/                # Output: Generated markdown notes
└── audio-archive/        # Processed original recordings
```

### Input: `data/voice-memos/`

Drop audio files here for automatic processing. Supported formats include MP3, WAV, M4A, FLAC, and most common audio formats.

The `webhook/` subdirectory receives files uploaded via the Voice Recorder UI or HTTP webhook. These are processed but not re-watched (prevents loops).

### Output: `data/notes/`

Generated markdown notes with YAML frontmatter:

```markdown
---
date: 2025-01-15
tags: [voice-memo, meeting]
source: ../audio-archive/2025-01-15-project-sync-abc123.mp3
---

# Project Sync Meeting

## Summary
...
```

### Archive: `data/audio-archive/`

After processing, original audio files are moved here and linked from the note's `source` field. This keeps `voice-memos/` clean while preserving originals.

---

## Viewing Notes in Obsidian

The `data/` folder is structured as an [Obsidian](https://obsidian.md/) vault.

### Setup

1. Download Obsidian from [obsidian.md](https://obsidian.md/)
2. Click "Open folder as vault"
3. Select the `data/` directory inside your LIMA installation

### Benefits

- **Graph view:** See connections between notes
- **Quick search:** Find notes by content or tags
- **Wikilinks:** Notes can reference each other with `[[note-name]]`
- **Mobile sync:** Use Obsidian Sync or Syncthing to access notes on your phone

---

## Backup Recommendations

### What to Back Up

| Directory | Priority | Notes |
|-----------|----------|-------|
| `data/notes/` | **High** | Your generated knowledge |
| `data/audio-archive/` | Medium | Original recordings (large files) |
| `.env` | **High** | Your configuration and secrets |
| `data/voice-memos/` | Low | Temporary input folder |

### Simple Backup Strategy

```bash
# Back up notes and config
cp -r data/notes/ ~/backup/lima-notes/
cp .env ~/backup/lima-env-backup

# Or use rsync for incremental backups
rsync -av data/notes/ ~/backup/lima-notes/
```

### Cloud Sync Options

- **Obsidian Sync:** Built-in, paid service
- **Syncthing:** Free, peer-to-peer sync between devices
- **Git:** Version control your notes (add `data/audio-archive/` to `.gitignore`)
- **Dropbox/iCloud/OneDrive:** Sync the `data/notes/` folder

---

## What's Safe to Delete

| Directory | Safe to Delete? | Notes |
|-----------|-----------------|-------|
| `data/voice-memos/*.mp3` | Yes, after processing | Moved to archive anyway |
| `data/audio-archive/` | Yes, if you don't need originals | Notes remain, but `source` links break |
| `data/notes/` | **No** | This is your knowledge base |
| Docker volumes | **Careful** | Contains n8n workflows and database |

### Cleaning Up Audio Archive

If disk space is tight, you can delete old audio files:

```bash
# Delete audio files older than 30 days
find data/audio-archive/ -type f -mtime +30 -delete
```

Note: This breaks the `source` links in your notes, but the text content remains.

---

## Database & n8n Data

LIMA uses PostgreSQL for all n8n data. The database runs in Docker and stores data in a Docker volume.

### What's Stored in PostgreSQL

- **Workflows:** All your automation definitions
- **Credentials:** API keys, passwords (encrypted with `N8N_ENCRYPTION_KEY`)
- **Execution history:** Logs of past workflow runs
- **Future:** Embeddings for semantic search over notes

### Critical: Protect Your Encryption Key

> **`N8N_ENCRYPTION_KEY` is irreplaceable.** All credentials stored in n8n are encrypted with this key. If you lose it, you lose access to all saved credentials (API keys, passwords, etc.) and must recreate them manually.

**Back up your `.env` file** - especially the encryption key. Store it securely (password manager, encrypted backup).

### Access the Database

```bash
docker compose exec postgres psql -U postgres -d lima
```

### Database Backup

The PostgreSQL data lives in a Docker volume. To back up:

```bash
# Export database
docker compose exec postgres pg_dump -U postgres lima > lima-backup.sql

# Restore (if needed)
docker compose exec -T postgres psql -U postgres lima < lima-backup.sql
```

---

## Next Steps

- [Getting Started](getting-started.md) - Initial setup
- [Recipes](recipes.md) - Use case examples
