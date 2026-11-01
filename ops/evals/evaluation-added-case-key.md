# Answer key: added review cases

Do not provide this file to the reviewer during evaluation. The cases are
constructed diffs, not claims about actual past commits or incidents.

## Case 11: defect

`ops/evals/cases/case-11.diff` changes `GetById` from returning a snapshot to
returning the mutable object held in the repository. The `lock` protects the
lookup only; the caller can mutate the returned object after the lock is
released. This changes stored state without `Update` and permits unsynchronized
access to that state. A finding should identify the leaked mutable reference
and its effect, not merely suggest generic locking or immutability.

The proposed final code matches the current implementation in
`backend/src/InvoiceApp.Api/InMemoryInvoiceRepository.cs`. To verify the
behavior on 2026-11-01, a temporary .NET program used the actual repository,
read `INV-1001`, changed its `Status` without calling `Update`, and read it
again. It printed `Mutation persisted without Update: True`. The temporary
program was removed after the check.

The old snapshot implementation in the diff is constructed for the exercise;
it is not evidence that the repository previously used snapshots. A separate
probe attempted 3,000 pairs of simultaneous approvals and observed no double
successes. It therefore did not reproduce that particular race; absence of a
reproduction does not establish that the check-and-update operation is atomic.

## Case 12: clean

`ops/evals/cases/case-12.diff` adds a test for two **sequential** approval
attempts. The existing helper creates a pending invoice, the first approval
records the first approver, and the second must throw because the invoice is
already approved. The subsequent assertions check the first decision.

The test does not claim to cover concurrent approvals or fix the existing
repository's reference leak. Missing concurrent coverage is a limitation of
this test, not a defect introduced by the diff. A false alarm is an asserted
defect in this clean change, not a suggestion to add more coverage.

An equivalent temporary xUnit test ran against the existing
`FakeInvoiceRepository` on 2026-11-01: 1 passed, 0 failed. The temporary test
was then removed; the diff itself was not applied to the application.
