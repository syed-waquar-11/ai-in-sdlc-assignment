import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "auto_export_ai_log.py"


class AutomaticExportTests(unittest.TestCase):
    def run_hook(self, home, payload, enabled=True):
        environment = os.environ.copy()
        environment["COPILOT_HOME"] = str(home)
        environment.pop("COPILOT_AI_LOG_AUTO", None)
        if enabled:
            environment["COPILOT_AI_LOG_AUTO"] = "1"
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT)],
            input=payload, capture_output=True, text=True, encoding="utf-8",
            timeout=30, env=environment, check=False,
        )

    def test_config_uses_main_agent_stop_and_session_end(self):
        config = json.loads(
            (ROOT / ".github" / "hooks" / "ai-augmentation-log.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["version"], 1)
        self.assertEqual(set(config["hooks"]), {"agentStop", "sessionEnd"})
        for entries in config["hooks"].values():
            self.assertEqual(len(entries), 1)
            self.assertIn("auto_export_ai_log.py", entries[0]["bash"])
            self.assertIn("auto_export_ai_log.py", entries[0]["powershell"])
            self.assertEqual(entries[0]["cwd"], ".")

    def test_disabled_hook_does_not_create_logs_or_parse_input(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            result = self.run_hook(home, "not json", enabled=False)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "{}")
            self.assertEqual(result.stderr, "")
            self.assertEqual(list(home.iterdir()), [])

    def test_both_hook_payloads_refresh_private_session_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            session = home / "session-state" / "sample-session"
            session.mkdir(parents=True)
            events = session / "events.jsonl"
            initial = [
                {"type": "session.start", "data": {"sessionId": "sample-session",
                                                   "selectedModel": "example-model"}},
                {"type": "user.message", "data": {"content": "Contact person@example.com"}},
            ]
            events.write_text("".join(json.dumps(event) + "\n" for event in initial), encoding="utf-8")
            output = session / "files" / "ai-log-auto"
            payloads = [
                {"sessionId": "sample-session", "transcriptPath": "unused", "stopReason": "end_turn"},
                {"sessionId": "sample-session", "reason": "complete"},
            ]
            for index, payload in enumerate(payloads):
                if index:
                    with events.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps({"type": "assistant.message",
                                                 "data": {"content": "Follow-up"}}) + "\n")
                result = self.run_hook(home, json.dumps(payload))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "{}")
                self.assertEqual(result.stderr, "")
                records = [
                    json.loads(line) for line in
                    (output / "ai-interactions.jsonl").read_text(encoding="utf-8").splitlines()
                ]
                self.assertEqual(len(records), 2 + index)
                self.assertEqual(records[1]["details"]["content"], "Contact <EMAIL>")
                self.assertTrue(all(record["record_type"] == "session_event" for record in records))
                summary = (output / "ai-interactions-summary.md").read_text(encoding="utf-8")
                self.assertIn("Assignment review evidence was not requested", summary)

    def test_invalid_input_and_missing_session_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            for payload, expected in (
                ("not json", "Automatic AI log export failed"),
                (json.dumps({"sessionId": "../escape"}), "invalid sessionId"),
                (json.dumps({"sessionId": "missing-session"}), "Native session events are not available"),
            ):
                result = self.run_hook(home, payload)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout.strip(), "{}")
                self.assertIn(expected, result.stderr)
            self.assertEqual(list(home.iterdir()), [])

    def test_incomplete_final_event_produces_a_warning(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            session = home / "session-state" / "sample-session"
            session.mkdir(parents=True)
            (session / "events.jsonl").write_text(
                json.dumps({"type": "session.start", "data": {"sessionId": "sample-session"}})
                + '\n{"partial":', encoding="utf-8"
            )
            result = self.run_hook(home, json.dumps({"sessionId": "sample-session"}))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout.strip(), "{}")
            self.assertIn("incomplete or invalid final event", result.stderr)
            self.assertTrue((session / "files" / "ai-log-auto" / "ai-interactions.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
