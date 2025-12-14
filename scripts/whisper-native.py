#!/usr/bin/env python3
"""Cross-platform native whisper server manager.

Usage:
    uv run python scripts/whisper-native.py start
    uv run python scripts/whisper-native.py stop
    uv run python scripts/whisper-native.py status
    uv run python scripts/whisper-native.py logs
"""

import argparse
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
WHISPER_DIR = PROJECT_ROOT / "services" / "whisper-server"
LOG_DIR = PROJECT_ROOT / "logs"
PID_FILE = PROJECT_ROOT / ".whisper-native.pid"
LOG_FILE = LOG_DIR / "whisper-native.log"


def load_env():
    """Load .env file if it exists."""
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("\"'")
                    if key in ("NATIVE_WHISPER_HOST", "NATIVE_WHISPER_PORT"):
                        os.environ.setdefault(key, value)


def get_pid() -> Optional[int]:
    """Get PID from file if process is still running."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process is running
        if platform.system() == "Windows":
            # Windows: use tasklist with CSV for reliable parsing
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
            )
            # CSV output: "process.exe","PID","..."  - check if our PID appears
            if result.returncode == 0 and f'"{pid}"' in result.stdout:
                return pid
        else:
            # Unix: send signal 0 to check
            os.kill(pid, 0)
            return pid
    except (ValueError, ProcessLookupError, PermissionError, OSError):
        pass
    # Stale PID file
    PID_FILE.unlink(missing_ok=True)
    return None


def start():
    """Start the native whisper server in background."""
    if pid := get_pid():
        port = os.environ.get("NATIVE_WHISPER_PORT", "9001")
        print(f"Already running (PID: {pid}, port: {port})")
        print(f"  Logs: make whisper-native-logs")
        print(f"  Stop: make whisper-native-stop")
        return 0

    # Ensure logs directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    system = platform.system()
    port = os.environ.get("NATIVE_WHISPER_PORT", "9001")

    # Windows: let PowerShell handle its own backgrounding
    if system == "Windows":
        script = WHISPER_DIR / "run_server.ps1"
        if not script.exists():
            print(f"Error: {script} not found")
            return 1

        print("Starting native whisper server...")

        # Call PowerShell with -Background flag - it handles everything
        cmd = [
            "powershell", "-ExecutionPolicy", "Bypass",
            "-File", str(script),
            "-Background",
            "-LogFile", str(LOG_FILE),
            "-PidFile", str(PID_FILE),
        ]
        result = subprocess.run(cmd, cwd=WHISPER_DIR)

        if result.returncode == 0:
            print(f"  Stop: make whisper-native-stop")
            return 0
        else:
            print(f"Failed to start. Check logs: {LOG_FILE}")
            return 1

    # Unix: use start_new_session to detach
    script = WHISPER_DIR / "run_server.sh"
    if not script.exists():
        print(f"Error: {script} not found")
        return 1

    print("Starting native whisper server...")

    # Open log file for output
    log_handle = open(LOG_FILE, "a")
    log_handle.write(f"\n{'='*60}\n")
    log_handle.write(f"Starting whisper server at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log_handle.write(f"{'='*60}\n")
    log_handle.flush()

    process = subprocess.Popen(
        [str(script)],
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        cwd=WHISPER_DIR,
        start_new_session=True,
    )

    # Save PID
    PID_FILE.write_text(str(process.pid))

    # Wait a moment and verify it started
    time.sleep(2)

    if get_pid():
        print(f"Started (PID: {process.pid}, port: {port})")
        print(f"  Logs: make whisper-native-logs")
        print(f"  Stop: make whisper-native-stop")
        return 0
    else:
        print(f"Failed to start. Check logs: {LOG_FILE}")
        if LOG_FILE.exists():
            print("\n--- Log output ---")
            print(LOG_FILE.read_text()[-2000:])
        return 1


def stop():
    """Stop the native whisper server."""
    pid = get_pid()
    if not pid:
        print("Not running")
        return 0

    print(f"Stopping (PID: {pid})...")

    try:
        if platform.system() == "Windows":
            # Windows: use taskkill to kill process tree
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            # Unix: kill the process group (pid == pgid due to start_new_session=True)
            # This ensures child processes (uvicorn) are also terminated
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass  # Already dead

            # Wait for graceful shutdown
            time.sleep(1)

            # Force kill if still running
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # Already dead

        # Verify termination before removing PID file
        time.sleep(0.5)
        try:
            if platform.system() != "Windows":
                os.kill(pid, 0)  # Check if still exists
                print(f"Warning: Process {pid} may still be running")
                return 1
        except ProcessLookupError:
            pass  # Good, it's dead

        print("Stopped")
        PID_FILE.unlink(missing_ok=True)
        return 0

    except Exception as e:
        print(f"Error stopping: {e}")
        print(f"PID file retained: {PID_FILE}")
        return 1


def status():
    """Check if server is running."""
    if pid := get_pid():
        port = os.environ.get("NATIVE_WHISPER_PORT", "9001")
        print(f"Running (PID: {pid}, port: {port})")
        return 0
    else:
        print("Not running")
        return 1


def logs():
    """Tail the log file."""
    if not LOG_FILE.exists():
        print(f"No log file. Start server first: make whisper-native")
        return 1

    print(f"Tailing {LOG_FILE} (Ctrl+C to stop)\n")

    try:
        with open(LOG_FILE) as f:
            # Show last 10 lines first (like tail default)
            lines = f.readlines()
            for line in lines[-10:]:
                print(line, end="")
            # Then follow new content
            while True:
                line = f.readline()
                if line:
                    print(line, end="")
                else:
                    time.sleep(0.1)
    except KeyboardInterrupt:
        print()
        return 0


def main():
    parser = argparse.ArgumentParser(description="Manage native whisper server")
    parser.add_argument(
        "command",
        choices=["start", "stop", "status", "logs"],
        help="Command to run",
    )
    args = parser.parse_args()

    load_env()

    commands = {
        "start": start,
        "stop": stop,
        "status": status,
        "logs": logs,
    }

    sys.exit(commands[args.command]())


if __name__ == "__main__":
    main()
