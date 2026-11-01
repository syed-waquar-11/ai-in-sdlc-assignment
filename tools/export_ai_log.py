#!/usr/bin/env python3
"""Export an allowlisted snapshot of a Copilot CLI session for local review."""

import argparse
import collections
import csv
import datetime as dt
import json
import re
import tempfile
import warnings
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVALS_RELATIVE = Path("ops") / "evals"
EVALS = ROOT / EVALS_RELATIVE
CASES = EVALS / "cases"
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
HOME = re.compile(r"(?i)(?:[A-Z]:[\\/](?:Users|Documents and Settings)[\\/]|/home/|/Users/)[^\\/ \r\n\"']+")
TOKEN = re.compile(
    r"(?i)\b(?:gh[pousr]_[A-Za-z0-9_]{10,}|github_pat_[A-Za-z0-9_]{10,}"
    r"|sk-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9._~+/-]+=*)"
)
ASSIGNMENT_SECRET = re.compile(
    r"""(?ix)(["']?(?:password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)["']?\s*[:=]\s*)"""
    r"""(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;}\]]+)"""
)
PATCH_PATH = re.compile(r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+)$", re.M)
EVENT_TYPES = {
    "session.start", "session.model_change", "user.message", "assistant.message",
    "tool.execution_start", "tool.execution_complete", "skill.invoked",
    "human_response.recorded", "permission.requested", "permission.completed",
}


def is_sensitive_key(key):
    if not isinstance(key, str):
        return False
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return normalized in {"token", "authorization", "credential", "credentials"} or normalized.endswith(
        ("password", "passwd", "passphrase", "secret", "apikey",
         "accesstoken", "refreshtoken", "idtoken", "privatekey")
    )


def redact(value):
    """Best-effort filtering, not a guarantee that output is safe to publish."""
    if isinstance(value, str):
        value = HOME.sub("<HOME>", value)
        value = EMAIL.sub("<EMAIL>", value)
        value = TOKEN.sub("<TOKEN>", value)
        return ASSIGNMENT_SECRET.sub(r"\1<REDACTED>", value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {
            key: "<REDACTED>" if is_sensitive_key(key) and item is not None else redact(item)
            for key, item in value.items()
        }
    return value


def selected(data, *names):
    return {name: data[name] for name in names if name in data}


def session_events(path):
    # Take a fixed-size snapshot: the session may be actively appending events.
    with path.open("rb") as stream:
        snapshot = stream.read(path.stat().st_size)
    complete = snapshot.endswith(b"\n")
    lines = snapshot.splitlines()
    for line_no, line in enumerate(lines, 1):
        try:
            yield json.loads(line.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            if not complete and line_no == len(lines):
                warnings.warn(
                    f"Omitting an incomplete or invalid final event at line {line_no}: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )
                break
            raise ValueError(f"Invalid event at line {line_no}: {exc}") from exc


def export_events(path):
    model = None
    session_id = None
    for event in session_events(path):
        kind = event.get("type")
        if kind not in EVENT_TYPES:
            continue
        data = event.get("data") or {}
        if kind == "session.start":
            session_id = data.get("sessionId")
            model = data.get("selectedModel")
        elif kind == "session.model_change":
            model = data.get("newModel")
        elif kind == "assistant.message" and not data.get("content"):
            continue

        record = {
            "record_type": "session_event", "event_type": kind,
            "id": event.get("id"), "timestamp": event.get("timestamp"),
            "parent_id": event.get("parentId"), "session_id": session_id,
            "ai_tool": "GitHub Copilot CLI", "model": data.get("model") or model,
            "agent_type": "main session", "mode": "unknown",
        }
        details = {}
        if kind == "session.start":
            details = selected(data, "producer", "copilotVersion", "selectedModel")
        elif kind == "session.model_change":
            details = selected(data, "previousModel", "newModel", "source")
        elif kind in ("user.message", "assistant.message"):
            details = selected(data, "content", "messageId", "interactionId", "turnId")
        elif kind == "tool.execution_start":
            details = selected(data, "toolCallId", "toolName", "toolTitle", "turnId")
            args = data.get("arguments")
            if isinstance(args, dict):
                details.update(selected(args, "description", "skill", "path"))
                if data.get("toolName") == "mermaid-generate":
                    details.update(selected(args, "name", "folder", "outputFormat"))
            elif isinstance(args, str) and data.get("toolName") == "apply_patch":
                details["affected_files"] = PATCH_PATH.findall(args)
        elif kind == "tool.execution_complete":
            details = selected(data, "toolCallId", "success", "turnId")
            if isinstance(data.get("shellExecution"), dict):
                details["shell_exit_code"] = data["shellExecution"].get("exitCode")
        elif kind == "skill.invoked":
            details = selected(data, "name", "source", "pluginName", "description", "trigger")
        elif kind == "human_response.recorded":
            details = selected(data, "requestId", "toolCallId", "actor")
            response = data.get("response") or {}
            details["response"] = selected(response, "responseKind", "content", "message")
        elif kind == "permission.requested":
            details = selected(data, "requestId", "agentMode")
            request = data.get("permissionRequest") or {}
            details["request"] = selected(request, "kind", "toolCallId", "intention")
        elif kind == "permission.completed":
            details = selected(data, "requestId", "toolCallId", "decisionSource")
            result = data.get("result") or {}
            details["result"] = selected(result, "kind", "feedback", "reason")
        record["details"] = redact(details)
        yield record


def review_records(evals=EVALS, cases=CASES):
    with (evals / "results.csv").open(encoding="utf-8-sig", newline="") as stream:
        scores = {row["raw_response"].replace("\\", "/"): row for row in csv.DictReader(stream)}
    for folder, validity in (("raw", "scored"), ("invalid-wrapper", "invalid_excluded")):
        for metadata_path in sorted((evals / folder).glob("*.json")):
            metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
            response = metadata_path.with_suffix(".txt")
            case = cases / (metadata["case"] + ".diff")
            if not response.is_file() or not case.is_file():
                raise ValueError(f"Missing review response or diff for {metadata_path.name}")
            relative_response = f"{folder}/{response.name}"
            score = scores.get(relative_response)
            if validity == "scored" and score is None:
                raise ValueError(f"No score for {relative_response}")
            yield {
                "record_type": "review_execution", "id": f"{folder}/{metadata_path.stem}",
                "timestamp": None, "session_id": None, "ai_tool": "GitHub Copilot CLI",
                "evidence_origin": "assignment evaluation artifacts, explicitly included",
                "model": metadata.get("model"), "agent_type": "isolated CLI review process",
                "mode": "noninteractive CLI", "status": validity,
                "case": metadata["case"], "run": metadata.get("run"),
                "prompt_version": metadata.get("prompt_version"),
                "prompt_evidence": (EVALS_RELATIVE / "method.md").as_posix(),
                "intended_diff": f"ops/evals/cases/{case.name}",
                "input_limitation": (
                    "Wrapper attempts excluded because multiline diff input was not reliably received."
                    if validity == "invalid_excluded" else
                    "Prompt and diff reconstructed from method and case; exact per-process request not retained."
                ),
                "exit_code": metadata.get("exit_code"),
                "output_nonempty": metadata.get("output_nonempty"),
                "metadata_artifact": (EVALS_RELATIVE / folder / metadata_path.name).as_posix(),
                "response_artifact": (EVALS_RELATIVE / folder / response.name).as_posix(),
                "score": redact(score) if score else None,
            }
    missing = set(scores) - {
        f"raw/{p.with_suffix('.txt').name}" for p in (evals / "raw").glob("*.json")
    }
    if missing:
        raise ValueError(f"Scored reviews missing metadata: {sorted(missing)}")


def render_summary(records, generated, include_assignment_reviews=False):
    events = [r for r in records if r["record_type"] == "session_event"]
    reviews = [r for r in records if r["record_type"] == "review_execution"]
    kinds = collections.Counter(r["event_type"] for r in events)
    tools = collections.Counter(
        r["details"].get("toolName", "unknown") for r in events
        if r["event_type"] == "tool.execution_start"
    )
    models = sorted({r["model"] for r in records if r.get("model")})
    times = [r["timestamp"] for r in events if r.get("timestamp")]
    permissions = collections.Counter(
        r["details"].get("result", {}).get("kind", "unknown")
        for r in events if r["event_type"] == "permission.completed"
    )
    statuses = collections.Counter(r["status"] for r in reviews)
    lines = [
        "# AI interaction log: local snapshot", "",
        f"Generated: {generated}", f"Session: {events[0]['session_id'] if events else 'unknown'}",
        f"Recorded event range: {times[0] if times else 'unknown'} to {times[-1] if times else 'unknown'}",
        f"Models recorded: {', '.join(models) if models else 'unknown'}", "",
        "## Coverage", "",
        f"- {len(events)} selected session events; {kinds['user.message']} user messages, "
        f"{kinds['assistant.message']} visible assistant messages, "
        f"{kinds['human_response.recorded']} structured human responses.",
        (f"- Explicitly included assignment evidence: {statuses['scored']} scored review "
         f"executions and {statuses['invalid_excluded']} invalid wrapper attempts, kept separately."
         if include_assignment_reviews else "- Assignment review evidence was not requested."),
        "- Permission outcomes: " + (", ".join(f"{k}: {v}" for k, v in sorted(permissions.items())) or "none recorded") + ".",
        "- Tools started: " + (", ".join(f"{k}: {v}" for k, v in sorted(tools.items())) or "none recorded") + ".",
        "", "## Reading the evidence", "",
        "- The JSONL retains selected event IDs, timestamps, prompts, visible responses, "
        "human decisions, tool statuses and linked review artifacts.",
        "- Main-session mode is unknown; recorded permission agentMode values are retained "
        "but do not establish an Ask/Plan/Agent/Edit selection.",
        "- If included, review evidence comes from this checkout; its timestamps and session IDs "
        "were not retained, so it is not automatically attributed to the source session. "
        "Scores are provisional and process exit is not proof of correct input.",
        "- Tool completion is not necessarily task success; consult the linked response and "
        "assignment evidence for actual outcomes. Unrecorded manual work cannot be inferred.",
        "- MCP access is not inferred from a tool name; inspect recorded tool events for "
        "evidence. Review processes are not represented as subagents.",
        "- Export is an on-demand snapshot, not continuous monitoring. It excludes tool "
        "output bodies, model reasoning, internal snapshots and most tool arguments.",
        "- Best-effort redaction covers common sensitive fields, tokens, credential assignments, "
        "email addresses and home paths, but can miss sensitive data. Review this log and linked "
        "artifacts before sharing; do not commit or publish it without approval.",
    ]
    if include_assignment_reviews:
        lines.extend([
            "",
            f"Review evaluation method and outcomes: `{(EVALS_RELATIVE / 'method.md').as_posix()}` "
            f"and `{(EVALS_RELATIVE / 'results.md').as_posix()}` in the repository.",
        ])
    lines.append("")
    return "\n".join(lines)


def atomic_write_text(path, content):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".ai-log-",
            suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True, help="Local Copilot events.jsonl")
    parser.add_argument("--output-dir", type=Path, required=True, help="Private output directory")
    parser.add_argument(
        "--include-assignment-reviews", action="store_true",
        help="Also include this checkout's assignment review evidence; association is not inferred",
    )
    parser.add_argument("--overwrite", action="store_true", help="Replace previous export files")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error("Choose an output directory outside the repository to avoid accidental publication.")
    targets = [output / "ai-interactions.jsonl", output / "ai-interactions-summary.md"]
    if not args.overwrite and any(path.exists() for path in targets):
        parser.error("Output already exists; choose another directory or pass --overwrite.")
    if args.events.resolve() in targets:
        parser.error("The source event file must not be an output file.")
    records = list(export_events(args.events))
    if args.include_assignment_reviews:
        records.extend(review_records())
    generated = dt.datetime.now(dt.timezone.utc).isoformat()
    output.mkdir(parents=True, exist_ok=True)
    atomic_write_text(targets[0], "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    atomic_write_text(targets[1], render_summary(records, generated, args.include_assignment_reviews))
    print(f"Wrote {len(records)} records to {targets[0]}")
    print(f"Wrote summary to {targets[1]}")
    print("Private local snapshot only: inspect for sensitive information before sharing.")


if __name__ == "__main__":
    main()
