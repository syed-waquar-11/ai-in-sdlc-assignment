# Decision: PayEx submission

**Status:** Proposed and reviewed for the assignment; requires business-owner
review and confirmation of PayEx capabilities. None of the proposed payment
infrastructure exists in the code.

## Context

The planned service handles about 40,000 invoices per month, peaks near 80
approvals per minute, and must retain approval audit information for seven
years. PayEx returns a reference on success, but a 30-second timeout does not
reliably mean a submission failed. Source: assignment PDF, page 1. The
current app uses an in-memory repository and has no PayEx integration:
`backend/src/InvoiceApp.Api/InMemoryInvoiceRepository.cs` and `ops/README.md`.

The material does not establish that PayEx supports idempotency keys, how long
it retains them, or whether payment status can be queried by a client-supplied
reference. Those are open vendor questions, not assumed facts.

## Proposed decision

Use an Azure SQL transactional outbox and a separately operated submission
worker. The approval update, audit record, and durable submission intent must
be committed in one database transaction. A stable key identifies one intended
payment across retries. The worker claims pending records, submits to PayEx,
and records the provider reference and result. Claims must tolerate worker
crashes and concurrent processing, and the same key must be reused on retry.

For the scenario's one intended payment per approved invoice, the database must
enforce a unique payment identity so concurrent approvals cannot create two
payment instructions with different keys. Approval-state concurrency control
and the unique payment identity must be part of the same transactional design.
A retry uses the saved instruction, key and payload; it does not create a new
payment identity. If the business later permits an additional payment for an
invoice, that must be an explicitly authorized new payment, not a retry.

**This does not alone guarantee exactly-once payment.** Before enabling
automatic retries after an ambiguous timeout, confirm that PayEx enforces
idempotency for the key and payload throughout the retry and recovery window,
or provides an authoritative status lookup with finality sufficient to prove
that a prior request cannot still succeed before a replacement is sent. A
simple "not found" response is not enough if the first request can still
complete later.
If neither capability is available, mark the outcome unknown and escalate for
reconciliation; do not blindly retry. An unresolved outcome may require
manual vendor investigation, and automatic eventual delivery cannot be
promised. Contractual semantics, retention, matching rules, failure behavior,
and evidence of provider enforcement need confirmation before production.

Service Bus is available but is not required by this decision. Its use would
need a separate design for reliable handoff and duplicate handling.

## Options and trade-offs

| Option | Benefits | Main objection |
|---|---|---|
| Idempotency key and dedupe table | Simpler synchronous request path; can prevent repeated local attempts and, if PayEx enforces the key, duplicate provider effects. | A crash after approval and before the request can lose the submission unless a durable recovery process exists. A local table cannot deduplicate an effect at PayEx. |
| Transactional outbox and worker | Approval and submission intent commit together; backlog is durable and processing can resume after a crash. | More moving parts and operational work. Re-delivery is possible, so PayEx-side deduplication or authoritative resolution is still necessary. |
| Optimistic submission and nightly reconciliation | Less initial infrastructure and a familiar reconciliation process. | Ambiguous failures and duplicates may remain undetected until reconciliation; recovery can be manual and too slow for payment operations. Reconciliation alone does not guarantee exactly once. |

These are not mutually exclusive features: the proposed outbox also uses
idempotency and reconciliation as safeguards.

## Stress tests

**Preference challenge.** The engineer preferred the idempotency-key and
dedupe-table option for its simpler synchronous flow. The agent's
recommendation did not change: a local table alone does not close the
approval-to-submission crash gap. A synchronous design may be acceptable if
the business explicitly accepts manual recovery and a weaker delivery
guarantee. Adding durable retry and recovery begins to resemble an outbox.

**3 a.m. on the last day of the month.** PayEx times out after a potentially
successful submission while the backlog grows. The on-call engineer needs
alerts for backlog age, failures and unknown outcomes; a runbook should show
the stable key, last attempt and provider response without exposing sensitive
data. Retry only when the verified provider contract makes retry safe;
otherwise quarantine and escalate. Capacity, alert thresholds, response
targets and the vendor escalation route must be defined and tested.

**Build and operating cost.** Outbox requires transactional persistence,
worker deployment, concurrency and recovery tests, dashboards, alerts and
on-call procedures. Ongoing cost includes worker compute, Azure SQL writes
and storage, audit retention, monitoring and support effort. The simpler
option has a lower initial implementation burden but potentially higher
manual recovery cost. No implementation hours, unit prices or resource
measurements were supplied; obtain team estimates and Azure pricing before
recording a budget. A useful model is:

`monthly cost = worker compute + SQL usage/storage + audit/log storage + monitoring + operational effort`

The stated 40,000 monthly invoices and peak of 80 per minute are workload
inputs, not proof that any particular capacity or cost target is met.

## Revisit when

- PayEx cannot guarantee idempotency or authoritative lookup for the complete
  recovery window, or changes its contract.
- Recovery time, backlog age, error rate or operating cost exceeds an agreed
  and measured threshold; thresholds still need to be set.
- The volume, compliance requirements or payment integration changes enough
  to invalidate the design assumptions.

## Where the agent was wrong or useless

- **Incomplete timeout guidance:** The agent initially suggested checking
  payment status after a timeout but did not explain that a "not found"
  response may not be final. The original request might still succeed later,
  so retrying could cause a duplicate payment.
- **Duplicate instructions not addressed initially:** The initial
  recommendation did not explicitly prevent two approval attempts from
  creating two payment instructions with different keys. We added a rule to
  allow only one instruction per intended payment.
- **Provider details and costs remain unknown:** The agent could not verify
  PayEx's idempotency contract or provide a reliable numeric build and
  operating cost from the supplied information. These require vendor
  confirmation and team estimates.
