# LIMA - Custom n8n image with ffmpeg for audio processing
# Build: docker build -f n8n.Dockerfile -t lima-n8n .
#
# n8n images are Docker Hardened Images (no package manager), so ffmpeg/ffprobe
# are copied in as static binaries instead of installed via apk.
# See VERSIONS.md for tested versions.

FROM mwader/static-ffmpeg:8.1.2 AS ffmpeg

FROM docker.n8n.io/n8nio/n8n:2.29.3

COPY --from=ffmpeg /ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg /ffprobe /usr/local/bin/ffprobe

# Verify installation
RUN ffmpeg -version && ffprobe -version

USER node
