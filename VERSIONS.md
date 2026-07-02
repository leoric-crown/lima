# LIMA - Tested Versions

This file documents the Docker image versions that have been tested and confirmed working with LIMA.

**Last updated:** July 2, 2026

## Production Stack

| Service | Image | Tested Version | Notes |
|---------|-------|----------------|-------|
| PostgreSQL | `pgvector/pgvector:pg17` | 17.7 | Pinned to pg17 |
| n8n | `docker.n8n.io/n8nio/n8n:2.29.3` | 2.29.3 | Pinned; migrated from 1.123.x July 2026 |
| ffmpeg | `mwader/static-ffmpeg:8.1.2` | 8.1.2 | Static binaries copied into n8n image (base is a Docker Hardened Image — no package manager) |
| Caddy | `caddy:2-alpine` | 2.10.2 | Pinned to major version 2 |
| Whisper | `ghcr.io/speaches-ai/speaches:latest-cpu` | (see digest below) | Floating tag |

## Development Stack

| Service | Image | Tested Version | Notes |
|---------|-------|----------------|-------|
| [n8n-mcp](https://github.com/czlonkowski/n8n-mcp) | `ghcr.io/czlonkowski/n8n-mcp:2.62.0` | 2.62.0 | Pinned; node DB built against n8n 2.27.4 — keep aligned with instance version (see note below) |
| [postgres-mcp](https://github.com/crystaldba/postgres-mcp) | `crystaldba/postgres-mcp:latest` | (see digest below) | Floating tag |
| pgAdmin | `dpage/pgadmin4:latest` | (see digest below) | Floating tag |

## Tested Image Digests

For reproducible builds, use these full digests (tested July 2026):

```
ghcr.io/speaches-ai/speaches@sha256:21e3df06d842fb7802ab470dd77c25f0e8c0d22950e8d8c6ae886e851af53ef8
ghcr.io/czlonkowski/n8n-mcp@sha256:b73a497bcb6dd7dd59ae1138f22c0703d95e049864ef7389bd3f960caeb56d57
crystaldba/postgres-mcp@sha256:dbbd346860d29f1543e991f30f3284bf4ab5f096d049ecc3426528f20b1b6e6b
dpage/pgadmin4@sha256:40fa840c5bb7c8463957f1255b01283732c2d8c9396a956d180f8e6c296753b3
```

## Pinning Versions

If you need reproducible builds, replace floating tags with specific versions:

```yaml
# docker-compose.yml
whisper:
  image: ghcr.io/speaches-ai/speaches@sha256:21e3df06d842fb7802ab470dd77c25f0e8c0d22950e8d8c6ae886e851af53ef8

# n8n.Dockerfile
FROM docker.n8n.io/n8nio/n8n:2.29.3
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

Note: `docker.n8n.io` rate-limits aggressively (429). If a build fails to resolve
the base image, pull the same tag from Docker Hub and retag:
`docker pull n8nio/n8n:<ver> && docker tag n8nio/n8n:<ver> docker.n8n.io/n8nio/n8n:<ver>`.

## Compatibility Notes

- **n8n 2.x migration (July 2026)**: migrated 1.123.5 → 1.123.63 → 2.29.3. The 2.0
  default flips that affect LIMA are set explicitly in `docker-compose.yml`
  (`NODES_EXCLUDE=[]`, `N8N_RESTRICT_FILE_ACCESS_TO=/data`,
  `N8N_DEFAULT_BINARY_DATA_MODE=filesystem`, plus task runners and env-access
  blocking which were already enabled). Both memo entry paths (file drop + webhook)
  verified end-to-end after each step. Volume backups taken pre-migration
  (`~/backups/compose-hub/volumes/`, 2026-07-02).
- **n8n images are Docker Hardened Images** (1.123.6x and all 2.x): no `apk`/package
  manager. `n8n.Dockerfile` copies static ffmpeg/ffprobe from `mwader/static-ffmpeg`.
- **Save/Publish split (2.x)**: saving a workflow no longer updates the live version;
  workflows imported via the API land unpublished until published in the UI or via
  `n8n publish:workflow`. Existing active workflows were auto-published by the migration.
- **Python task runner warning (2.x)**: n8n logs "Failed to start Python task runner"
  at boot — benign; LIMA's Code nodes are all JavaScript and the image has no Python.
- **n8n-mcp ↔ n8n version alignment**: n8n-mcp bundles a node database built against
  a specific n8n version (it does not introspect the live instance). Pin an n8n-mcp
  release whose bundled n8n matches the instance; when bumping n8n, bump n8n-mcp too.
  For historical reference: the last n8n-mcp built against n8n 1.123.x was 2.29.5.
- **postgres-mcp credentials**: passed via `PGUSER`/`PGPASSWORD` env vars, not embedded
  in `DATABASE_URI` — passwords containing URL-special characters (`@ : / #`) break
  URI parsing (symptom: "label empty or too long" connection errors).
- **n8n 1.123+**: Requires API key for workflow import (fresh installs don't auto-create owner)
- **pgvector pg17**: Uses IVFFlat indexes for vector similarity search
- **Speaches**: OpenAI-compatible API at `/v1/audio/transcriptions`
