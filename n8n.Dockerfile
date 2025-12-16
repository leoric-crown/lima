# LIMA - Custom n8n image with ffmpeg for audio processing
# Build: docker build -f n8n.Dockerfile -t lima-n8n .
#
# Note: Pinned to 1.123.5 due to n8n 2.0 breaking workflow imports.
# See VERSIONS.md for tested versions and BACKLOG.md for upgrade plans.

FROM docker.n8n.io/n8nio/n8n:1.123.5

USER root

# Install ffmpeg for audio splitting/manipulation
RUN apk add --no-cache ffmpeg

# Verify installation
RUN ffmpeg -version

USER node
