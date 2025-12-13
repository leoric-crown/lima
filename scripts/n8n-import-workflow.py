#!/usr/bin/env python3
"""
Import a workflow JSON file to n8n via REST API.

Usage:
    uv run python scripts/n8n-import-workflow.py <workflow.json> [--url URL]

Requires:
    N8N_API_KEY in .env file or environment variable (create in n8n UI: Settings → API)

Examples:
    uv run python scripts/n8n-import-workflow.py my-workflow.json
    uv run python scripts/n8n-import-workflow.py my-workflow.json --url http://localhost:5678
"""

import argparse
import json
import os
from pathlib import Path
import platform
import socket
import sys
import urllib.request
import urllib.error


def load_dotenv(env_path: Path | None = None) -> dict[str, str]:
    """Load .env file into environment. Returns loaded vars."""
    if env_path is None:
        # Search for .env in current dir and parents
        search_dir = Path.cwd()
        while search_dir != search_dir.parent:
            candidate = search_dir / ".env"
            if candidate.is_file():
                env_path = candidate
                break
            search_dir = search_dir.parent

    if env_path is None or not env_path.is_file():
        return {}

    loaded = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse KEY=value (handle optional quotes)
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Remove surrounding quotes if present
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                # Only set if not already in environment
                if key and key not in os.environ:
                    os.environ[key] = value
                    loaded[key] = value
    return loaded


def get_host_ip() -> str | None:
    """Get the host's local IP address that Docker containers can reach."""
    try:
        # Connect to an external address to determine the local IP
        # (doesn't actually send data, just determines routing)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def list_workflows(n8n_url: str, api_key: str) -> list[dict]:
    """List all workflows from n8n API."""
    url = f"{n8n_url.rstrip('/')}/api/v1/workflows"
    req = urllib.request.Request(
        url,
        headers={"X-N8N-API-KEY": api_key},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("data", [])
    except urllib.error.HTTPError:
        return []
    except urllib.error.URLError:
        return []


def find_duplicate(name: str, n8n_url: str, api_key: str) -> dict | None:
    """Check if a workflow with the same name already exists. Returns the existing workflow or None."""
    workflows = list_workflows(n8n_url, api_key)
    for wf in workflows:
        if wf.get("name") == name:
            return wf
    return None


def apply_replacements(
    workflow_data: dict,
    native_whisper_port: str | None = None,
    host_ip: str | None = None,
) -> tuple[dict, list[str]]:
    """Apply URL replacements to workflow JSON.

    1. If native_whisper_port is set, replace :9001 with the configured port (all platforms)
    2. If host_ip is set, replace host.docker.internal with actual IP (Linux only)

    Returns (modified_data, list_of_replacements).
    """
    json_str = json.dumps(workflow_data)
    replacements = []

    # Step 1: Replace native whisper port (all platforms)
    # Be specific to avoid false positives on other :9001 occurrences
    if native_whisper_port and "host.docker.internal:9001" in json_str:
        old = "host.docker.internal:9001"
        new = f"host.docker.internal:{native_whisper_port}"
        count = json_str.count(old)
        json_str = json_str.replace(old, new)
        replacements.append(f"{count}x port 9001 → {native_whisper_port}")

    # Step 2: Replace host.docker.internal with actual IP (Linux only)
    if host_ip and "host.docker.internal" in json_str:
        count = json_str.count("host.docker.internal")
        json_str = json_str.replace("host.docker.internal", host_ip)
        replacements.append(f"{count}x host.docker.internal → {host_ip}")

    if replacements:
        return json.loads(json_str), replacements
    return workflow_data, []


def import_workflow(
    workflow_file: str,
    n8n_url: str,
    api_key: str,
    host_ip: str | None = None,
    native_whisper_port: str | None = None,
) -> tuple[dict, list[str]]:
    """Import a workflow JSON file to n8n.

    Returns (api_response, list_of_replacements).
    """
    # Read and parse workflow file
    with open(workflow_file, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    # Extract only API-accepted fields
    payload = {
        "name": workflow.get("name", "Unnamed Workflow"),
        "nodes": workflow.get("nodes", []),
        "connections": workflow.get("connections", {}),
        "settings": workflow.get("settings", {}),
    }

    # Apply URL replacements (port on all platforms, host on Linux)
    replacements = []
    if native_whisper_port or host_ip:
        payload, replacements = apply_replacements(payload, native_whisper_port, host_ip)

    # Prepare request
    url = f"{n8n_url.rstrip('/')}/api/v1/workflows"
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-N8N-API-KEY": api_key,
        },
        method="POST",
    )

    # Make request
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8")), replacements
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            error_json = json.loads(error_body)
            raise RuntimeError(f"API error: {error_json.get('message', error_body)}")
        except json.JSONDecodeError:
            raise RuntimeError(f"HTTP {e.code}: {error_body}")


def main():
    # Load .env early so N8N_PORT/N8N_URL are available for defaults
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Import a workflow JSON file to n8n via REST API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/n8n-import-workflow.py my-workflow.json
  uv run python scripts/n8n-import-workflow.py my-workflow.json --url http://n8n.local:5678

Environment variables (loaded from .env automatically):
  N8N_API_KEY         - Required. Create in n8n UI: Settings → API
  N8N_PORT            - Optional. Default: 5678
  N8N_URL             - Optional. Overrides N8N_PORT if set
  NATIVE_WHISPER_PORT - Optional. Port for native CUDA/MLX whisper server
                        (replaces default port 9001 in workflows)
        """,
    )
    parser.add_argument("workflow_file", help="Path to workflow JSON file")
    # Build default URL from N8N_PORT if set, otherwise use N8N_URL or default
    default_port = os.environ.get("N8N_PORT", "5678")
    default_url = os.environ.get("N8N_URL", f"http://localhost:{default_port}")
    parser.add_argument(
        "--url",
        default=default_url,
        help="n8n URL (default: $N8N_URL or http://localhost:$N8N_PORT)",
    )

    args = parser.parse_args()

    # Check API key
    api_key = os.environ.get("N8N_API_KEY")
    if not api_key:
        print("❌ N8N_API_KEY not set.", file=sys.stderr)
        print("   Create one in n8n UI: Settings → API → Create API Key", file=sys.stderr)
        print("   Then add to .env: N8N_API_KEY=your_key", file=sys.stderr)
        print("   Or export: export N8N_API_KEY=your_key", file=sys.stderr)
        sys.exit(1)

    # Check file exists
    if not os.path.isfile(args.workflow_file):
        print(f"❌ File not found: {args.workflow_file}", file=sys.stderr)
        sys.exit(1)

    # Get workflow name for display
    try:
        with open(args.workflow_file, "r", encoding="utf-8") as f:
            workflow_name = json.load(f).get("name", "Unnamed")
    except (json.JSONDecodeError, OSError) as e:
        print(f"❌ Failed to read workflow file: {e}", file=sys.stderr)
        sys.exit(1)

    # Check for duplicate workflow
    existing = find_duplicate(workflow_name, args.url, api_key)
    if existing:
        existing_id = existing.get("id", "unknown")
        print(f"⚠️ Workflow '{workflow_name}' already exists")
        print(f"   Existing: {args.url}/workflow/{existing_id}")
        try:
            response = input("   Create duplicate? [y/N] ").strip().lower()
            if response not in ("y", "yes"):
                print("   Skipped.")
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            print("\n   Skipped.")
            sys.exit(0)

    # Get replacement settings
    native_whisper_port = os.environ.get("NATIVE_WHISPER_PORT")
    host_ip = None
    if platform.system() == "Linux":
        host_ip = get_host_ip()
        if not host_ip:
            print("⚠️ Warning: Could not detect host IP address", file=sys.stderr)
            print("   host.docker.internal URLs will not be replaced", file=sys.stderr)
            print()

    print(f"Importing: {workflow_name}")
    print(f"From: {args.workflow_file}")
    print(f"To: {args.url}")
    if native_whisper_port:
        print(f"Native Whisper: port {native_whisper_port}")
    if host_ip:
        print(f"Host IP: {host_ip} (Linux: replacing host.docker.internal)")
    print()

    # Import workflow
    try:
        result, replacements = import_workflow(
            args.workflow_file, args.url, api_key, host_ip, native_whisper_port
        )
        workflow_id = result.get("id", "unknown")
        print("✓ Imported successfully!")
        print(f"  Workflow ID: {workflow_id}")
        print(f"  URL: {args.url}/workflow/{workflow_id}")
        for replacement in replacements:
            print(f"  Replaced {replacement}")
        print()
        print("⚠️ Workflow is INACTIVE. Activate in the n8n UI.")
    except urllib.error.URLError as e:
        print(f"❌ Cannot connect to n8n at {args.url}", file=sys.stderr)
        if "Connection refused" in str(e.reason):
            print("   Is n8n running? Try: make up", file=sys.stderr)
        else:
            print(f"   Error: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Import failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
