#!/usr/bin/env python3
"""
Prepare credential JSON for import, replacing host.docker.internal on Linux.

Outputs credential JSON to stdout (pipe to docker exec for import).
"""

import os
import platform
import socket
import sys
from pathlib import Path


def get_host_ip() -> str | None:
    """Get the host's local IP address that Docker containers can reach."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: prepare-credential.py <credential.json>", file=sys.stderr)
        sys.exit(1)

    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"File not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    # Read credential file
    content = input_file.read_text()

    # Replace LLM port if configured (e.g., Ollama uses 11434 instead of LM Studio's 1234)
    # Be specific to avoid false positives on other :1234 occurrences
    local_llm_port = os.environ.get("LOCAL_LLM_PORT")
    if local_llm_port and "host.docker.internal:1234" in content:
        content = content.replace("host.docker.internal:1234", f"host.docker.internal:{local_llm_port}")
        print(f"Replaced port 1234 → {local_llm_port}", file=sys.stderr)

    # On Linux, replace host.docker.internal with actual host IP
    if platform.system() == "Linux" and "host.docker.internal" in content:
        host_ip = get_host_ip()
        if host_ip:
            content = content.replace("host.docker.internal", host_ip)
            print(f"Replaced host.docker.internal → {host_ip}", file=sys.stderr)

    # Output content to stdout (for piping to docker)
    print(content)


if __name__ == "__main__":
    main()
