#!/usr/bin/env python3
"""Refresh a private session snapshot from an opt-in Copilot CLI hook."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")


class HookError(Exception):
    pass


def export_from_hook(raw_input):
    payload = json.loads(raw_input)
    if not isinstance(payload, dict):
        raise ValueError("Hook input must be a JSON object.")
    session_id = payload.get("sessionId")
    if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
        raise ValueError("Hook input has a missing or invalid sessionId.")

    configured_home = os.environ.get("COPILOT_HOME")
    home = Path(configured_home).expanduser() if configured_home else Path.home() / ".copilot"
    state_root = (home / "session-state").resolve()
    session_dir = (state_root / session_id).resolve()
    if session_dir.parent != state_root:
        raise ValueError("Session directory must be directly under the Copilot session-state directory.")

    events = session_dir / "events.jsonl"
    if not events.is_file():
        raise FileNotFoundError(f"Native session events are not available: {events}")
    output = session_dir / "files" / "ai-log-auto"
    command = [
        sys.executable, "-B", str(ROOT / "tools" / "export_ai_log.py"),
        "--events", str(events), "--output-dir", str(output), "--overwrite",
    ]
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=25, env=environment, check=False,
    )
    if result.returncode or result.stderr.strip():
        detail = result.stderr.strip() or f"exporter exited with status {result.returncode}"
        raise HookError(detail)


def main():
    raw_input = sys.stdin.read()
    if os.environ.get("COPILOT_AI_LOG_AUTO") != "1":
        print("{}")
        return 0
    try:
        export_from_hook(raw_input)
    except (HookError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"Automatic AI log export failed: {error}", file=sys.stderr)
        print("{}")
        return 2
    print("{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
