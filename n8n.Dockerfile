# LIMA - Custom n8n image with ffmpeg for audio processing
# Build: docker build -f n8n.Dockerfile -t lima-n8n .
#
# Note: Using :latest for ease of updates.
# See VERSIONS.md for tested versions and pinning instructions.

FROM docker.n8n.io/n8nio/n8n:latest

USER root

# Install ffmpeg for audio splitting/manipulation
RUN apk add --no-cache ffmpeg

# Verify installation
RUN ffmpeg -version

USER node
