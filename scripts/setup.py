#!/usr/bin/env python3
"""
LIMA Setup Script - Interactive first-time setup.

Usage:
    uv run python scripts/setup.py
    # or via Makefile:
    make setup
"""

import getpass
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def load_dotenv() -> dict[str, str]:
    """Load .env file into environment."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return {}

    loaded = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = value
                    loaded[key] = value
    return loaded


def update_env_file(key: str, value: str) -> None:
    """Add or update a key in .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    lines = []
    found = False

    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith(f"{key}="):
                    lines.append(f"{key}={value}\n")
                    found = True
                else:
                    lines.append(line)

    if not found:
        lines.append(f"{key}={value}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    os.environ[key] = value


def run(cmd: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a shell command."""
    return subprocess.run(
        cmd,
        shell=True,
        check=check,
        capture_output=capture,
        text=True,
        cwd=Path(__file__).parent.parent,
    )


def check_n8n_ready(url: str) -> bool:
    """Check if n8n is responding."""
    try:
        req = urllib.request.Request(f"{url}/healthz", method="GET")
        with urllib.request.urlopen(req, timeout=5):
            return True
    except Exception:
        return False


def check_api_key(url: str, api_key: str) -> bool:
    """Check if API key is valid."""
    if not api_key:
        return False
    try:
        req = urllib.request.Request(
            f"{url}/api/v1/workflows",
            headers={"X-N8N-API-KEY": api_key},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            # Only 2xx status codes mean the key is valid
            return 200 <= resp.status < 300
    except Exception:
        return False


def prompt(message: str, default: str = "") -> str:
    """Prompt user for input with optional default."""
    if default:
        result = input(f"{message} [{default}]: ").strip()
        return result if result else default
    return input(f"{message}: ").strip()


def confirm(message: str, default: bool = True) -> bool:
    """Prompt for yes/no confirmation."""
    suffix = "[Y/n]" if default else "[y/N]"
    result = input(f"{message} {suffix} ").strip().lower()
    if not result:
        return default
    return result in ("y", "yes")


def print_header(text: str) -> None:
    """Print a section header."""
    print()
    print("=" * 60)
    print(f"  {text}")
    print("=" * 60)
    print()


def print_step(num: int, text: str) -> None:
    """Print a step indicator."""
    print(f"\n[{num}/5] {text}")
    print("-" * 40)


def main():
    print_header("LIMA Setup")
    print("This script will set up LIMA for first-time use.")
    print("It will: build images, start services, and import workflows.")
    print()

    if not confirm("Continue with setup?"):
        print("Aborted.")
        sys.exit(0)

    # Load existing .env
    load_dotenv()

    # Check .env exists
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        print()
        print("ERROR: .env file not found!")
        print("Please copy .env.example to .env and configure it first:")
        print("  cp .env.example .env")
        print("  # Edit .env with secure passwords")
        sys.exit(1)

    n8n_port = os.environ.get("N8N_PORT", "5678")
    n8n_url = f"http://localhost:{n8n_port}"

    # Step 1: Build and pull images
    print_step(1, "Building and pulling Docker images")
    print("This may take a few minutes on first run...")
    run("docker compose build --pull")
    run("docker compose pull")
    print("✓ Images ready")

    # Step 2: Start services
    print_step(2, "Starting services")
    # Create data directories
    for d in ["data/voice-memos/webhook", "data/audio-archive", "data/notes"]:
        Path(d).mkdir(parents=True, exist_ok=True)
    run("docker compose up -d")

    print("Waiting for n8n to start (max 30s)", end="", flush=True)
    for _ in range(15):
        if check_n8n_ready(n8n_url):
            print(" ✓")
            break
        print(".", end="", flush=True)
        time.sleep(2)
    else:
        print(" TIMEOUT")
        print()
        print("ERROR: n8n did not start within 30 seconds.")
        print("Last 30 lines of n8n logs:")
        print("-" * 40)
        logs = run("docker compose logs n8n --tail 30", check=False, capture=True)
        print(logs.stdout or logs.stderr or "(no logs available)")
        print("-" * 40)
        sys.exit(1)

    print(f"✓ n8n is running at {n8n_url}")

    # Step 3: Get API key
    print_step(3, "Configure n8n API key")

    api_key = os.environ.get("N8N_API_KEY", "")
    if api_key and check_api_key(n8n_url, api_key):
        print(f"✓ API key already configured and valid")
    else:
        print(f"Please create an API key in n8n:")
        print(f"  1. Open {n8n_url}")
        print(f"  2. Create your admin account (first time only)")
        print(f"  3. Go to Settings → API → Create API Key")
        print()

        while True:
            api_key = getpass.getpass("Paste your API key (hidden): ").strip()
            if not api_key:
                print("API key is required.")
                continue

            # Show masked preview for confirmation
            if len(api_key) > 8:
                masked = f"{api_key[:4]}...{api_key[-4:]}"
            else:
                masked = "***"
            print(f"   Key: {masked}")

            if check_api_key(n8n_url, api_key):
                update_env_file("N8N_API_KEY", api_key)
                print("✓ API key saved to .env")
                break
            else:
                print("Invalid API key or cannot connect. Please try again.")

    # Step 4: Configure LLM port
    print_step(4, "Configure Local LLM")

    print("Which local LLM server are you using?")
    print("  1. LM Studio (port 1234) - default")
    print("  2. Ollama (port 11434)")
    print("  3. Other (custom port)")
    print()

    choice = prompt("Enter choice", "1")

    if choice == "2":
        update_env_file("LOCAL_LLM_PORT", "11434")
        print("✓ Set LOCAL_LLM_PORT=11434 for Ollama")
    elif choice == "3":
        port = prompt("Enter your LLM server port")
        if port and port != "1234":
            update_env_file("LOCAL_LLM_PORT", port)
            print(f"✓ Set LOCAL_LLM_PORT={port}")
    else:
        print("✓ Using default port 1234 (LM Studio)")

    # Configure LLM model
    print()
    print("Which LLM model will you use? (must support tool calling)")
    print("  Default: openai/gpt-oss-20b")
    print("  Make sure the model is downloaded in your LLM server.")
    print()

    model = prompt("Enter model name", "openai/gpt-oss-20b")
    if model and model != "openai/gpt-oss-20b":  # Only save if different from workflow default
        update_env_file("LLM_MODEL", model)
        print(f"✓ Set LLM_MODEL={model}")
    else:
        print("✓ Using default model")

    # Check for native whisper
    print()
    if confirm("Are you using the native GPU whisper server?", default=False):
        port = prompt("Enter native whisper port", "9001")
        update_env_file("NATIVE_WHISPER_PORT", port)
        print(f"✓ Set NATIVE_WHISPER_PORT={port}")

    # Step 5: Seed workflows
    print_step(5, "Importing workflows and credentials")

    # Re-load env to pick up changes
    load_dotenv()

    result = run("uv run python scripts/seed.py", check=False)
    if result.returncode != 0:
        print("WARNING: Seed may have had issues. Check output above.")

    # Done!
    print_header("Setup Complete!")

    caddy_port = os.environ.get("CADDY_PORT", "8888")

    print("Next steps:")
    print(f"  1. Start your local LLM server (LM Studio or Ollama)")
    print(f"  2. Activate a workflow at {n8n_url}/home/workflows")
    print(f"  3. Open the Voice Recorder at http://localhost:{caddy_port}/lima/recorder/")
    print()
    print("Useful commands:")
    print("  docker compose logs -f  - View service logs")
    print("  make status             - Check service health")
    print("  make down               - Stop all services")
    print()


if __name__ == "__main__":
    main()
