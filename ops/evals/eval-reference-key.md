# Provisional scoring key for the ten supplied cases

This key is for scoring, not reviewer input. It was independently derived
from the diffs and repository evidence; the exercise does not supply an
official answer key. Interpretations and limitations are recorded below.

| Case | Classification | Ground truth used for scoring |
|---|---|---|
| 01 | Defect | Nullable `Ids` is iterated without a null check, causing an unhandled null-reference failure for a missing or null list. |
| 02 | Defect | Both customer and status are interpolated into SQL; attacker-controlled values can change the query. |
| 03 | Defect | The changed rounding produces different invoice totals. For amount 10.01 and discount 12.35%, the original produces 8.77 and the change produces 8.78. |
| 04 | Clean | The repository field and its shown uses are consistently renamed; a rename alone does not change behavior. |
| 05 | Defect | The new delete endpoint has no admin role restriction. In the actual application `InvoicesController` has no class-level role restriction and deletion is admin-only. |
| 06 | Clean | These are tests of rejection, approval metadata and a missing invoice, not production behavior changes. Whether the diff applies to the actual checkout is separate from the intended case. |
| 07 | Defect, assumption-dependent | Logging the full invoice and user session can expose invoice/customer and identity information in logs. The exact sensitivity and log-access policy are not specified; score this classification separately in sensitivity analysis. The current `UserSession` contains username and role, not a bearer token. |
| 08 | Defect | Replacing a concurrent dictionary with an unprotected dictionary and check-then-add is unsafe under concurrent requests. |
| 09 | Defect, context-dependent | Logging out and back in does not reset invoices: `AuthController.Logout` removes the session while `InMemoryInvoiceRepository` is registered as a singleton in `Program.cs`. The diff alone does not establish this, and reviewers do not receive that context. |
| 10 | Defect | The catch-all reports success for unexpected failures, masking errors and returning HTTP 200. |

Classification of 07 depends on an assumed logging policy; classification of
09 requires repository context deliberately withheld from the reviewer.
Do not treat this provisional key as an official solution. Review unexpected
findings individually and disclose these limitations when reporting rates.
