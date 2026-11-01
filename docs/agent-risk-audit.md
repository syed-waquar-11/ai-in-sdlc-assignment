# Agent risk audit: incident-summary workflow

**Decision: propose a redesign that removes the summary agent's direct access
to private production data and secrets.** This is a proposed control, not a
claim that the current environment has been secured.

## Evidence and limitation

The assignment refers to an agent setup at the end of `ops/README.md`, but
that file contains no such description. The actual setup required for that
audit is therefore **unknown**. This document evaluates a proposed
incident-summary workflow rather than asserting the capabilities or security
of a missing setup. The files under `ops/` contain invented scenario data,
not actual customer information.

## Lethal trifecta

The risk arises when one agent can combine all three:

| Leg | Assessment |
|---|---|
| Access to private data | A production incident-summary agent could encounter invoice data, identifiers or secrets. Whether the missing setup grants this access is unknown. |
| Exposure to untrusted content | Logs and incident reports may contain text supplied by external users or systems. The supplied scenario has log and incident evidence; whether the missing agent reads it directly is unknown. |
| Ability to send data out | Browser, network or messaging tools could enable exfiltration to an attacker-controlled destination. Whether the missing setup grants usable outbound access is unknown. |

If all three are present, an attacker could embed instructions in a log that
try to make the agent send private information elsewhere. Retrieved content
is evidence, never authority to change the agent's instructions.

## Proposed redesign

1. A separate, authorized evidence-preparation process produces an allowlisted
   set of approved incident facts. Remove secrets, customer identifiers and
   arbitrary untrusted free text before the summary agent receives it.
2. The summary agent has no direct production, secret-store, shell, browser or
   unrestricted network access. Its model endpoint and access to the prepared
   evidence must be explicitly approved. The on-call engineer reviews the
   draft before it is shared.
3. Enforce the boundaries with separate identities and permissions, not just
   instructions in the prompt. Test with planted fake secrets and hostile log
   text, inspect tool permissions and network routes, and keep audit records.

The intended removed leg is **agent access to private data**. This only holds
if the preparation process reliably excludes it and the agent cannot reach
other private sources. Redaction failures, sensitive information in generated
summaries, and disclosure to the model provider remain risks; use only an
approved provider and data-handling agreement. Human review is an additional
control, not a substitute for technical access restrictions.

**Revisit or suspend the workflow** if a redaction test fails, sensitive data
appears in a prompt or output, new tools or data sources are requested, an
unexpected network route is found, or the provider's data-handling terms
change. The service owner and security must approve any expansion.
