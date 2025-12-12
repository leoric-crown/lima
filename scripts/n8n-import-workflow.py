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


def import_workflow(workflow_file: str, n8n_url: str, api_key: str) -> dict:
    """Import a workflow JSON file to n8n."""
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
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            error_json = json.loads(error_body)
            raise RuntimeError(f"API error: {error_json.get('message', error_body)}")
        except json.JSONDecodeError:
            raise RuntimeError(f"HTTP {e.code}: {error_body}")


def main():
    parser = argparse.ArgumentParser(
        description="Import a workflow JSON file to n8n via REST API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/n8n-import-workflow.py my-workflow.json
  uv run python scripts/n8n-import-workflow.py my-workflow.json --url http://n8n.local:5678

Environment variables (loaded from .env automatically):
  N8N_API_KEY  - Required. Create in n8n UI: Settings → API
  N8N_URL      - Optional. Default: http://localhost:5678
        """,
    )
    parser.add_argument("workflow_file", help="Path to workflow JSON file")
    parser.add_argument(
        "--url",
        default=os.environ.get("N8N_URL", "http://localhost:5678"),
        help="n8n URL (default: $N8N_URL or http://localhost:5678)",
    )

    args = parser.parse_args()

    # Load .env file (searches current dir and parents)
    load_dotenv()

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

    print(f"Importing: {workflow_name}")
    print(f"From: {args.workflow_file}")
    print(f"To: {args.url}")
    print()

    # Import workflow
    try:
        result = import_workflow(args.workflow_file, args.url, api_key)
        workflow_id = result.get("id", "unknown")
        print("✓ Imported successfully!")
        print(f"  Workflow ID: {workflow_id}")
        print(f"  URL: {args.url}/workflow/{workflow_id}")
        print()
        print("⚠️  Workflow is INACTIVE. Activate in the n8n UI.")
    except Exception as e:
        print(f"❌ Import failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
