# AI augmentation log

This is an evidence-based narrative, not a verbatim transcript.
`ai-augmentation-evidence.jsonl` is a manually curated, non-exhaustive
extract prepared from the private Copilot CLI event export. It contains
paraphrased requests and decisions, outcomes, and source-event references;
it is not an automatically generated transcript. Timestamps on activity
records identify the request or initial decision; later decisions retain their
own timestamps. Paths reflect the current layout, even when source events
refer to earlier locations.
The user confirmed the plain-language summaries of the eight selected
activities and approved sharing the curated files. The full session snapshot
and individual review responses remain private.

The private JSONL snapshot contains recorded prompts and follow-ups, visible
assistant messages, human decisions, selected tool events and linked review
evidence. Its generated summary reports coverage and limitations.

The snapshot is private, outside this repository. It is not automatically
updated: run the exporter again to capture later events. From the repository
root, in PowerShell:

```powershell
$session = '<copilot-session-id>'
$sessionDir = Join-Path $env:USERPROFILE ".copilot\session-state\$session"
$events = Join-Path $sessionDir 'events.jsonl'
$output = Join-Path $sessionDir 'files\ai-log'
python .\tools\export_ai_log.py --events $events --output-dir $output --overwrite
```

Replace `$session` with the local session ID. To attach assignment review
metadata, add `--include-assignment-reviews` only when local copies of the
private scored review responses and metadata are available. Excluded attempts
are included only when their private files are also present. Neither set is
included in this public submission. Review records have no verified session ID;
including them does not establish that they belong to the selected session.
The exporter writes `ai-interactions.jsonl` and `ai-interactions-summary.md` to
the chosen directory. A valid final event is included even without a newline;
an incomplete or invalid final line without a newline is omitted with a warning.
A tool call's successful completion is not proof the underlying task or test
succeeded.

## Optional automatic snapshots

The repository hook in `.github/hooks/ai-augmentation-log.json` refreshes a
private snapshot after each main-agent response and at session end, but only
when explicitly enabled. From the repository root in PowerShell, start a new
Copilot CLI session with:

```powershell
$env:COPILOT_AI_LOG_AUTO = '1'
copilot
```

Trust the repository configuration when prompted. New hook configuration is
loaded when Copilot starts or restarts; it cannot attach retroactively to the
current session. Remove the environment variable after the session to opt out:

```powershell
Remove-Item Env:\COPILOT_AI_LOG_AUTO
```

Automatic output is kept separately under
`%USERPROFILE%\.copilot\session-state\<session-id>\files\ai-log-auto\` by
default; `COPILOT_HOME` changes the Copilot state location. It contains the
JSONL and readable summary. Review-evaluation evidence is **not** included
automatically, and the hook neither publishes data nor changes permissions.
If the native event file is unavailable, the export fails, or the final event
is incomplete, the hook reports a warning instead of claiming success. These
are best-effort snapshots at hook time, not a continuous or complete audit
trail; some final events may require a later manual refresh.

Redaction masks common sensitive fields as well as common text patterns, but is
best effort, not a privacy guarantee. The private JSONL can still contain
sensitive information, and linked review files are not redacted by the
exporter. The curated extract summarizes user requests and decisions without
verbatim quotations, and retains errors and limitations. Source-event IDs let
the user trace selections back to the private export; they do not expose the
full source. Review each artifact before sharing; do not commit or push
session-derived material without explicit approval. The review entries have no
invented execution timestamps or child session IDs; their prompts are reconstructed from
`ops/evals/method.md` and the referenced diff, and invalid wrapper attempts are
clearly separated from scored runs. The mode selected in the interactive UI is
not established by the available events.

| Work | AI contribution and human direction | Evidence and correction |
|---|---|---|
| Architecture | Inspected the approval path, drafted the cited diagrams and structural test. The engineer asked for clarification of the citation labels. | `architecture.md`; `backend/tests/InvoiceApp.Tests/ArchitectureTests.cs`. The agent incorrectly said Mermaid MCP was unavailable; the available tool later rendered the diagrams and exposed a sequence syntax error, which was corrected. |
| Running the test | The engineer identified WSL2 as an option and authorized installing .NET inside WSL. | The test passed once under .NET 8.0.427 with invariant globalization; command and limitations are in `architecture.md`. Fork CI troubleshooting did not establish a successful run. |
| PayEx decision | The engineer first preferred a dedupe-table approach as a challenge, then selected an outbox and worker, and requested a safeguard against duplicate payment instructions. | `payex-decision.md` records trade-offs, the unique-payment safeguard, and the unverified PayEx idempotency contract. |
| Autonomy policy | The engineer selected first-response incident summaries. The agent drafted human-controlled day-one behavior and promotion criteria; the engineer chose human approval for all publication rather than future automatic publication. | `incident-summary-autonomy.md`. |
| Added review cases | The agent investigated a possible concurrency issue. A 3,000-pair probe did not reproduce double approval; a separate probe did demonstrate that a returned invoice can mutate stored state without `Update`. | `ops/evals/evaluation-added-case-key.md`; the probe was temporary and removed. |
| Review evaluation | The engineer chose `gpt-6-luna` and approved fresh-session runs. The agent ran and scored the cases. | `ops/evals/method.md`, `ops/evals/results.csv`, and `ops/evals/results.md`; individual responses remain private. The initial automated runner lost multiline diff input; those attempts were preserved separately and excluded. The engineer approved additional sessions after being told. |
| Risk and measurement | The engineer chose a redesign limiting the summary agent's access to private data. | `agent-risk-audit.md` and `measurement-plan.md` distinguish missing evidence and scenario CI diagnostics from actual production baselines. |
| File layout | The engineer chose to place documentation, evaluation evidence and the exporter in their respective repository areas instead of an assignment-specific folder. | `docs`, `ops/evals`, and `tools`; no publication was authorized by that choice. |
| Log automation | The engineer chose an opt-in hook rather than automatic logging for every session. | `.github/hooks/ai-augmentation-log.json` and `tools/auto_export_ai_log.py`; snapshots remain local and require review before sharing. |

The session used the repository's agent instructions and tools including
PowerShell, file inspection, patching and the Mermaid rendering tool. A separate
local MCP initialization and SVG-render check used
`@peng-shawn/mermaid-mcp-server@0.3.0`; that check
does not establish that the main session's rendering tool was an MCP call.
The isolated review CLI processes were not subagents. The event log cannot
establish every manual action or validation performed outside the session.

The evaluation answer keys remain provisional. The proposed PayEx decision
still requires business-owner review and provider confirmation. The demo
video is not yet recorded.
