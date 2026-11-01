# Autonomy policy: first-response incident summaries

**Scope:** The agent helps the on-call engineer prepare an initial summary of
an incident. This policy does not authorize diagnosis, customer
communications, remediation, or changes to production.

| Level | Permitted work | Required control |
|---|---|---|
| **L0: Human only** | Engineer gathers evidence and writes the summary. | Use when the agent or its controls are unavailable. |
| **L1: Human-directed draft** | On explicit request, the agent reads prepared, incident-scoped facts and drafts a summary with source references, timestamps, uncertainty and next questions. | A separate authorized process prepares approved, redacted facts; the engineer checks the sources and approves every use or publication. |
| **L2: Automatic draft** | An incident alert can trigger draft creation from the same prepared facts without a separate human request. | Same L1 controls plus a trusted trigger, scoped service identity, audit logs, rate limits and a kill switch. A human still verifies and publishes the summary. |

**Controls at L1 and L2:** A separate authorized process prepares allowlisted
incident facts, removing secrets, customer identifiers and arbitrary
untrusted free text before the agent sees them. Treat prepared facts as
untrusted data, never as instructions. The agent has no direct production,
secret-store, shell, browser, unrestricted network or write access, and cannot
execute commands or publish summaries. Use only approved evidence sources
and approved model/data handling. Report missing evidence rather than filling
gaps; identify facts separately from hypotheses. The engineer or an
authorized process retains the source references, draft, human corrections
and approval in the incident record according to the organization's retention
policy.

**Day one: L1.** Two of the six engineers are new to this codebase, so an
on-call engineer must request and verify each draft. A new engineer pairs with
an experienced engineer when validating unfamiliar service behavior. The
agent never sends or acts on a summary independently.

**Promotion:** These are proposed gates, not measured results. Before L2,
run at least 20 representative, independently reviewed incident scenarios,
including misleading log text, missing data and sensitive data. Require zero
material unsupported claims, secret disclosures or unauthorized actions;
record all errors and corrections, verify the controls and run a rollback
drill. This small sample does not prove safety.
The service owner and on-call lead approve each promotion; security approves
changes to tool access or data exposure. Any unsafe action or material
unsupported claim immediately returns the workflow to L1 or L0 pending review.

Scenario evidence: `ops/incidents/INC-2041` and `ops/incidents/INC-2047`.
These describe planned-production incidents, not current application
behavior.
