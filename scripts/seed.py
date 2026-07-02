#!/usr/bin/env python3
"""
Cross-platform seed script for n8n workflows and credentials.

Usage:
    uv run python scripts/seed.py
    # or via Makefile:
    make seed
"""

import json
import os
import platform
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
SEED_DIR = PROJECT_ROOT / "workflows" / "seed"


def load_dotenv():
    """Load .env file into environment."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("\"'")
                if key and key not in os.environ:
                    os.environ[key] = value


def get_host_ip() -> str | None:
    """Get the host's local IP address that Docker containers can reach."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def prepare_credential(file_path: Path, host_ip: str | None, llm_port: str | None) -> str:
    """Prepare credential JSON with replacements."""
    content = file_path.read_text()

    # Replace LLM port if configured
    if llm_port and "host.docker.internal:1234" in content:
        content = content.replace("host.docker.internal:1234", f"host.docker.internal:{llm_port}")
        print(f"  Replaced port 1234 -> {llm_port}")

    # On Linux, replace host.docker.internal with actual host IP
    if host_ip and "host.docker.internal" in content:
        content = content.replace("host.docker.internal", host_ip)
        print(f"  Replaced host.docker.internal -> {host_ip}")

    return content


def get_existing_credential_ids(n8n_url: str, api_key: str) -> set[str] | None:
    """Fetch existing credential IDs via the n8n API (available in n8n 2.x).

    Returns None if the endpoint is unavailable, so callers can fall back to
    importing blindly (pre-2.x behavior).
    """
    req = urllib.request.Request(
        f"{n8n_url.rstrip('/')}/api/v1/credentials",
        headers={"X-N8N-API-KEY": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.load(resp)
        return {c["id"] for c in payload.get("data", []) if c.get("id")}
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return None


def import_credential(
    file_path: Path,
    host_ip: str | None,
    llm_port: str | None,
    existing_ids: set[str] | None,
) -> bool:
    """Import a single credential file.

    The n8n CLI silently OVERWRITES credentials by ID, so skip any credential
    whose ID already exists on the instance — otherwise re-seeding would clobber
    live customizations (e.g. a user-edited base URL).
    """
    name = file_path.stem
    print(f"Importing credential: {name}")

    if existing_ids is not None:
        try:
            file_ids = {c.get("id") for c in json.loads(file_path.read_text()) if c.get("id")}
        except (ValueError, TypeError, AttributeError):
            file_ids = set()
        if file_ids and file_ids <= existing_ids:
            print("  Skipped (already exists)")
            return True

    content = prepare_credential(file_path, host_ip, llm_port)

    # Pipe credential JSON to n8n CLI inside container
    # /dev/stdin works because the command runs inside the Linux container
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "n8n", "n8n", "import:credentials", "--input=/dev/stdin"],
        input=content.encode("utf-8"),
        capture_output=True,
        cwd=PROJECT_ROOT,
    )

    stdout = result.stdout.decode("utf-8", errors="replace").strip()
    stderr = result.stderr.decode("utf-8", errors="replace").strip()

    # n8n import outputs to stdout on success, stderr on error
    output = stdout or stderr

    if result.returncode != 0:
        if "already exists" in output.lower():
            print(f"  Skipped (already exists)")
            return True
        print(f"  Failed (exit {result.returncode}): {output}")
        return False

    # Check for "already exists" in success output too
    if "already exists" in output.lower():
        print(f"  Skipped (already exists)")
    elif output:
        print(f"  OK: {output}")
    else:
        print(f"  OK")
    return True


def import_workflow(file_path: Path, n8n_url: str, api_key: str) -> bool:
    """Import a single workflow file using the existing script."""
    result = subprocess.run(
        ["uv", "run", "python", "scripts/n8n-import-workflow.py", str(file_path), "--url", n8n_url],
        cwd=PROJECT_ROOT,
    )
    return result.returncode == 0


def main():
    load_dotenv()

    api_key = os.environ.get("N8N_API_KEY")
    if not api_key:
        print("N8N_API_KEY not set.")
        print("  1. Create one in n8n UI: Settings -> API -> Create API Key")
        print("  2. Add to .env: N8N_API_KEY=your_key")
        print("  3. Run: make seed")
        sys.exit(1)

    n8n_port = os.environ.get("N8N_PORT", "5678")
    n8n_url = os.environ.get("N8N_URL", f"http://localhost:{n8n_port}")

    print("Importing workflows and credentials from ./workflows/seed/")
    print("(Existing workflows/credentials are skipped automatically)")
    print()

    # Get replacement values
    host_ip = None
    if platform.system() == "Linux":
        host_ip = get_host_ip()
        if host_ip:
            print(f"Linux detected: will replace host.docker.internal -> {host_ip}")

    llm_port = os.environ.get("LOCAL_LLM_PORT")
    if llm_port and llm_port != "1234":
        print(f"Custom LLM port: will replace 1234 -> {llm_port}")

    print()

    # Import credentials
    creds_dir = SEED_DIR / "credentials"
    if creds_dir.exists():
        print("=== Importing credentials ===")
        existing_ids = get_existing_credential_ids(n8n_url, api_key)
        if existing_ids is None:
            print("Note: cannot list existing credentials (n8n < 2.x?);")
            print("      imports will overwrite credentials with matching IDs")
        cred_files = sorted(creds_dir.glob("*.json"))
        for cred_file in cred_files:
            import_credential(cred_file, host_ip, llm_port, existing_ids)
        print()

    # Import workflows
    print("=== Importing workflows ===")
    workflow_files = sorted(SEED_DIR.glob("*.json"))
    failed = 0
    for wf_file in workflow_files:
        if not import_workflow(wf_file, n8n_url, api_key):
            failed += 1

    print()
    if failed > 0:
        print(f"Warning: {failed} workflow(s) failed to import")
    print("Seeding complete!")
    print()
    print(f"Workflows are INACTIVE. Activate at {n8n_url}/home/workflows")
    print()


if __name__ == "__main__":
    main()
