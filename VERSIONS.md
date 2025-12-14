# LIMA - Tested Versions

This file documents the Docker image versions that have been tested and confirmed working with LIMA.

**Last updated:** December 13, 2025

## Production Stack

| Service | Image | Tested Version | Notes |
|---------|-------|----------------|-------|
| PostgreSQL | `pgvector/pgvector:pg17` | 17.7 | Pinned to pg17 |
| n8n | `docker.n8n.io/n8nio/n8n:latest` | 1.123.5 | Built via n8n.Dockerfile |
| ffmpeg | (installed in n8n image) | 6.1.2 | Alpine package |
| Caddy | `caddy:2-alpine` | 2.10.2 | Pinned to major version 2 |
| Whisper | `ghcr.io/speaches-ai/speaches:latest-cpu` | (see digest below) | Floating tag |

## Development Stack

| Service | Image | Tested Version | Notes |
|---------|-------|----------------|-------|
| n8n-mcp | `ghcr.io/czlonkowski/n8n-mcp:latest` | (see digest below) | Floating tag |
| postgres-mcp | `crystaldba/postgres-mcp:latest` | (see digest below) | Floating tag |
| pgAdmin | `dpage/pgadmin4:latest` | (see digest below) | Floating tag |

## Tested Image Digests

For reproducible builds, use these full digests (tested December 2025):

```
ghcr.io/speaches-ai/speaches@sha256:21e3df06d842fb7802ab470dd77c25f0e8c0d22950e8d8c6ae886e851af53ef8
ghcr.io/czlonkowski/n8n-mcp@sha256:488798bcd446c9857ccf9e53d60e7fbbcb6b6d7c841bf3d23e11318c9408fd38
crystaldba/postgres-mcp@sha256:dbbd346860d29f1543e991f30f3284bf4ab5f096d049ecc3426528f20b1b6e6b
dpage/pgadmin4@sha256:8c128407f45f1c582eda69e71da1a393237388469052e3cc1e6ae4a475e12b70
```

## Pinning Versions

If you need reproducible builds, replace floating tags with specific versions:

```yaml
# docker-compose.yml
whisper:
  image: ghcr.io/speaches-ai/speaches@sha256:21e3df06d842fb7802ab470dd77c25f0e8c0d22950e8d8c6ae886e851af53ef8

# n8n.Dockerfile
FROM docker.n8n.io/n8nio/n8n:1.123.5
```

## Updating Images

```bash
# Pull latest images
docker compose pull

# Rebuild n8n with latest base
docker compose build --pull n8n

# Restart services
make down && make up
```

## Compatibility Notes

- **n8n 1.123+**: Requires API key for workflow import (fresh installs don't auto-create owner)
- **pgvector pg17**: Uses IVFFlat indexes for vector similarity search
- **Speaches**: OpenAI-compatible API at `/v1/audio/transcriptions`
