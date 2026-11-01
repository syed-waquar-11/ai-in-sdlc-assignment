# Measurement plan before on-call rotation

Use the 30 complete days before the rotation begins, timestamps in UTC, and
retain the raw export and query version. The rotation start date and access to
the production deployment, incident and review systems are not supplied.
Do not treat the invented `ops/` evidence as observations of a real service.

## Requested baselines

| Measure | Definition and exact source | Current status |
|---|---|---|
| Lead time for changes | Median time from each included change's Git committer timestamp to its first successful **production** deployment. Join deployed commit SHAs from GitHub REST `GET /repos/{owner}/{repo}/deployments?environment=production&per_page=100` and `GET /repos/{owner}/{repo}/deployments/{deployment_id}/statuses` to commits in `GET /repos/{owner}/{repo}/compare/{previous_sha}...{sha}`. Use the `success` status timestamp, deduplicate commits deployed more than once, and document excluded rollbacks and missing records. Paginate every endpoint. | **Real baseline unavailable:** no real production deployment status history is supplied. One fictional author-date-to-deployment example is calculated below; it is not the complete 30-day baseline. |
| Change failure rate | Number of production deployments linked to at least one incident requiring remediation, divided by total production deployments in the period. Join successful production deployment IDs/SHAs and timestamps from the GitHub deployment endpoints above to the incident system's incident IDs, causally linked deployment IDs, timestamps and remediation status. Count a deployment only once even if it causes multiple incidents; apply the same defined observation window to each deployment. | **Real baseline unavailable:** no complete production deployment and linked-incident history is supplied. The fictional 1/3 estimate below relies on unverified assumptions. A failed CI build is not a failed production change. |
| Review turnaround | Median time from a PR becoming ready for review to its first submitted non-author, non-bot review. Use `GET /repos/{owner}/{repo}/pulls?state=all&per_page=100`, `GET /repos/{owner}/{repo}/issues/{number}/timeline?per_page=100` for `ready_for_review` when created as a draft, and `GET /repos/{owner}/{repo}/pulls/{number}/reviews?per_page=100` for `submitted_at`, author and state. For a PR created ready, use its creation time. Exclude PRs with no qualifying review from the median and report their count separately. Paginate all endpoints. | **Not calculable for the original repository:** its public PR list was empty when checked. The assignment PR in the fork was created for this exercise and is not a pre-rotation baseline. |

The REST paths are source specifications, not claims that production uses
GitHub deployment records. If production deployment or incident records live
elsewhere, substitute that system's actual export and document the join.

## One captured fictional lead-time example

The `INC-2041` scenario includes a commit and its deployment:

- `ops/incidents/INC-2041/deploy-diff.patch` records commit `7c41ab9` with
  an **author date** of 2026-01-13 17:22:08 UTC.
- `ops/incidents/INC-2041/app-logs.txt` identifies the same commit at the
  start of release `2.14.0`, whose deployment swap completed at
  2026-01-14 09:58:41 UTC.
- The elapsed time from that author date to deployment completion is
  **16 hours, 36 minutes, 33 seconds**.

This is one measurement from fictional evidence, not a real production
observation or a representative 30-day median. The patch's author date is
not necessarily the commit's committer timestamp or the start of all work in
the release. It is an explicitly defined example, not a substitute for the
baseline definition in the table.

Reproduce the example from the repository root:

```powershell
@'
import datetime as dt
import email.utils
import re
from pathlib import Path

incident = Path("ops") / "incidents" / "INC-2041"
patch = (incident / "deploy-diff.patch").read_text(encoding="utf-8-sig")
logs = (incident / "app-logs.txt").read_text(encoding="utf-8-sig")
commit = re.search(r"^commit ([0-9a-f]{40})$", patch, re.M)
date = re.search(r"^Date:\s*(.+)$", patch, re.M)
start = re.search(
    r"^\S+\s+INFO\s+\[Deploy\] Starting deployment release=2\.14\.0 commit=([0-9a-f]+)",
    logs, re.M)
end = re.search(
    r"^(\S+)\s+INFO\s+\[Deploy\] Swap completed release=2\.14\.0",
    logs, re.M)
if not all((commit, date, start, end)) or not commit.group(1).startswith(start.group(1)):
    raise ValueError("Commit or matching deployment evidence is missing.")
authored = email.utils.parsedate_to_datetime(date.group(1))
deployed = dt.datetime.fromisoformat(end.group(1).replace("Z", "+00:00"))
print("fictional author-date-to-deployment lead time:", deployed - authored)
'@ | python -
```

## Provisional fictional change-failure example

`ops/incidents/INC-2047/recent-changes.md` lists three fictional releases:
`2.14.3`, `2.15.0` and `2.15.1`. After `2.15.1`, notifications stopped.
The publisher logs and subscription inspection suggest that the release
changed the event name without updating the notification filter.

For this exercise, the engineer chose to count the release with missing
notifications as a failure. **Assuming** `2.15.1` caused the incident, each
listed release was deployed once, and the other two caused no incidents, the
fictional change failure estimate is **1/3 = 33.3%**.

These are assumptions, not verified facts. The incident was still under
investigation, and the pack does not establish a complete deployment and
incident history. The result is a provisional example, not a confirmed
30-day or real-world baseline.

Reproduce the calculation from the repository root:

```powershell
@'
import re
from pathlib import Path

changes = Path("ops") / "incidents" / "INC-2047" / "recent-changes.md"
text = changes.read_text(encoding="utf-8-sig")
releases = re.findall(
    r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|\s*([^|\s]+)\s*\|\s*`[0-9a-f]+`\s*\|",
    text, re.M)
assumed_failed = {"2.15.1"}
if not releases or len(releases) != len(set(releases)) or not assumed_failed.issubset(releases):
    raise ValueError("The expected unique releases are not present.")
print("assumed fictional change failure rate:",
      f"{len(assumed_failed)}/{len(releases)} = {len(assumed_failed) / len(releases):.1%}")
'@ | python -
```

## Additional CI diagnostics

The file `ops/pipeline/run-timings.csv` contains **invented scenario data**:
20 distinct runs from 2026-01-19 to 2026-02-02. Group rows by `run_number`.
The following are useful *CI diagnostics*, but neither is one of the three
requested measures as defined above:

1. **Failed CI runs: 2/20 = 10%.** Both failed runs were PR runs. This is
   not a change failure rate.
2. **Median sum of recorded step durations: 1,875.5 seconds (31m 15.5s).**
   This is not review turnaround or actual end-to-end wall-clock duration;
   the data do not include queue time and failed runs can have fewer steps.

Reproduce the two numbers from the repository root:

```powershell
@'
import collections, csv, statistics
from pathlib import Path

path = Path("ops") / "pipeline" / "run-timings.csv"
runs = {}
with path.open(newline="", encoding="utf-8-sig") as file:
    for row in csv.DictReader(file):
        run = runs.setdefault(row["run_number"],
                              {"conclusion": row["conclusion"], "seconds": 0})
        run["seconds"] += int(row["duration_seconds"])
counts = collections.Counter(run["conclusion"] for run in runs.values())
print("runs:", len(runs), "conclusions:", dict(counts))
print("median step-sum seconds:", statistics.median(
    run["seconds"] for run in runs.values()))
'@ | python -
```

Separately, the original public GitHub repository was observed to have one
completed successful CI run and no pull requests when checked on 2026-11-01.
That single CI run is not evidence that the new architecture test passed;
the test was run separately in WSL.

**Evidence limitation:** The two fictional examples above are a single
lead-time observation and an assumption-based change-failure estimate.
Neither establishes the verified 30-day baseline defined in the table, and
review turnaround remains unavailable. Confirm whether the assignment accepts
the provisional estimate or obtain additional records. Do not relabel the CI
diagnostics as the requested measures.
