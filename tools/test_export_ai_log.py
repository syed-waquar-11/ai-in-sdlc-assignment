import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import export_ai_log as exporter


class ExportTests(unittest.TestCase):
    def test_selects_events_and_redacts_without_exporting_reasoning_or_commands(self):
        events = [
            {"type": "session.start", "id": "1", "timestamp": "2026-01-01T00:00:00Z",
             "data": {"sessionId": "session", "selectedModel": "model-1"}},
            {"type": "session.model_change", "id": "2",
             "data": {"previousModel": "model-1", "newModel": "model-2"}},
            {"type": "user.message", "id": "3",
             "data": {"content": "Email me at person@example.com, password=abc",
                      "interactionId": "interaction"}},
            {"type": "assistant.message", "id": "4",
             "data": {"content": "Done", "reasoningText": "private reasoning"}},
            {"type": "tool.execution_start", "id": "5",
             "data": {"toolName": "powershell", "toolCallId": "call",
                      "arguments": {"command": "private command", "description": "Check"}}},
            {"type": "permission.completed", "id": "6",
             "data": {"result": {"kind": "denied-interactively-by-user", "feedback": "No"}}},
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            path.write_text("".join(json.dumps(e) + "\n" for e in events) + '{"partial":',
                            encoding="utf-8")
            with self.assertWarnsRegex(RuntimeWarning, "final event at line 7"):
                records = list(exporter.export_events(path))
        self.assertEqual(len(records), 6)
        self.assertEqual(records[2]["model"], "model-2")
        self.assertEqual(records[2]["details"]["content"],
                         "Email me at <EMAIL>, password=<REDACTED>")
        encoded = json.dumps(records)
        self.assertNotIn("private reasoning", encoded)
        self.assertNotIn("private command", encoded)
        self.assertEqual(records[-1]["details"]["result"]["kind"], "denied-interactively-by-user")

    def test_rejects_malformed_complete_event(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            path.write_text("{bad}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "line 1"):
                list(exporter.export_events(path))

    def test_includes_valid_final_event_without_newline(self):
        event = {"type": "user.message", "data": {"content": "complete final event"}}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            path.write_text(json.dumps(event), encoding="utf-8")
            records = list(exporter.export_events(path))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["details"]["content"], "complete final event")

    def test_redacts_paths_tokens_and_email(self):
        text = r"C:\Users\alice\file and /home/bob/notes ghp_123456789012345 person@example.org"
        result = exporter.redact(text)
        for value in ("alice", "bob", "ghp_123456789012345", "person@example.org"):
            self.assertNotIn(value, result)

    def test_redacts_sensitive_values_in_nested_structured_responses(self):
        response = {
            "PASSWORD": "sample-password",
            "user_password": "sample-user-password",
            "nested": [{"clientSecret": {"value": "sample-client-secret"}},
                       {"access_token": "sample-access-token", "token_count": 2}],
            "Authorization": "sample-authorization",
            "token": None,
            "choice": "approved",
        }
        result = exporter.redact(response)
        self.assertEqual(result["PASSWORD"], "<REDACTED>")
        self.assertEqual(result["user_password"], "<REDACTED>")
        self.assertEqual(result["nested"][0]["clientSecret"], "<REDACTED>")
        self.assertEqual(result["nested"][1]["access_token"], "<REDACTED>")
        self.assertEqual(result["nested"][1]["token_count"], 2)
        self.assertEqual(result["Authorization"], "<REDACTED>")
        self.assertIsNone(result["token"])
        self.assertEqual(result["choice"], "approved")
        for value in ("sample-password", "sample-client-secret", "sample-access-token"):
            self.assertNotIn(value, json.dumps(result))

    def test_patch_paths_and_human_responses(self):
        events = [
            {"type": "tool.execution_start", "data": {
                "toolName": "apply_patch", "arguments":
                    "*** Update File: a.txt\n*** Move to: b.txt\n+secret content"}},
            {"type": "human_response.recorded", "data": {
                "response": {"content": {"choice": "yes"}, "message": "Approve?"}}},
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
            records = list(exporter.export_events(path))
        self.assertEqual(records[0]["details"]["affected_files"], ["a.txt", "b.txt"])
        self.assertEqual(records[1]["details"]["response"]["content"], {"choice": "yes"})
        self.assertNotIn("secret content", json.dumps(records))

    def test_reviews_keep_invalid_attempts_separate_and_require_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evals, cases = root / "evals", root / "cases"
            cases.mkdir()
            (cases / "case-01.diff").write_text("diff", encoding="utf-8")
            for folder in ("raw", "invalid-wrapper"):
                directory = evals / folder
                directory.mkdir(parents=True)
                (directory / "run.json").write_text(json.dumps({
                    "case": "case-01", "model": "gpt-6-luna", "run": 1,
                    "prompt_version": "v1", "exit_code": 0, "output_nonempty": True,
                }), encoding="utf-8")
                (directory / "run.txt").write_text("response", encoding="utf-8")
            with (evals / "results.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["raw_response", "verdict"])
                writer.writeheader()
                writer.writerow({"raw_response": r"raw\run.txt", "verdict": "caught"})
            records = list(exporter.review_records(evals, cases))
            self.assertEqual([r["status"] for r in records], ["scored", "invalid_excluded"])
            self.assertIsNone(records[0]["timestamp"])
            self.assertIsNone(records[0]["session_id"])
            self.assertEqual(records[0]["evidence_origin"],
                             "assignment evaluation artifacts, explicitly included")
            self.assertEqual(records[0]["prompt_evidence"], "ops/evals/method.md")
            self.assertEqual(records[0]["metadata_artifact"], "ops/evals/raw/run.json")
            self.assertEqual(records[0]["response_artifact"], "ops/evals/raw/run.txt")
            self.assertIsNone(records[1]["score"])
            (evals / "raw" / "run.txt").unlink()
            with self.assertRaisesRegex(ValueError, "Missing review"):
                list(exporter.review_records(evals, cases))

    def test_refuses_output_inside_repository(self):
        argv = [
            "export_ai_log.py",
            "--events", "unused-events.jsonl",
            "--output-dir", str(exporter.ROOT / "docs" / "private-output"),
        ]
        errors = io.StringIO()
        with mock.patch.object(sys, "argv", argv), \
             contextlib.redirect_stderr(errors), \
             self.assertRaises(SystemExit) as result:
            exporter.main()
        self.assertEqual(result.exception.code, 2)
        self.assertIn("outside the repository", errors.getvalue())

    def test_atomic_write_preserves_previous_file_if_replace_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "snapshot.jsonl"
            target.write_text("previous", encoding="utf-8")
            with mock.patch.object(Path, "replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    exporter.atomic_write_text(target, "new")
            self.assertEqual(target.read_text(encoding="utf-8"), "previous")
            self.assertEqual(list(root.iterdir()), [target])

    def test_other_session_excludes_assignment_reviews_unless_requested(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "events.jsonl"
            source.write_text(json.dumps({
                "type": "session.start", "data": {"sessionId": "unrelated-session"}
            }) + "\n", encoding="utf-8")
            review = {"record_type": "review_execution", "status": "scored", "session_id": None}
            for include in (False, True):
                output = root / ("included" if include else "excluded")
                argv = ["export_ai_log.py", "--events", str(source), "--output-dir", str(output)]
                if include:
                    argv.append("--include-assignment-reviews")
                with mock.patch.object(sys, "argv", argv), \
                     mock.patch.object(exporter, "review_records", return_value=iter([review])) as reviews, \
                     contextlib.redirect_stdout(io.StringIO()):
                    exporter.main()
                self.assertEqual(reviews.call_count, int(include))
                records = [
                    json.loads(line) for line in
                    (output / "ai-interactions.jsonl").read_text(encoding="utf-8").splitlines()
                ]
                self.assertEqual(sum(r["record_type"] == "review_execution" for r in records),
                                 int(include))
                summary = (output / "ai-interactions-summary.md").read_text(encoding="utf-8")
                self.assertIn("Explicitly included" if include else "not requested", summary)


if __name__ == "__main__":
    unittest.main()
