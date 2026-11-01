# Review evaluation results

The evaluation used `gpt-6-luna`, 12 cases and a fresh CLI process for each
review. See `method.md` for the prompts, isolation, and an execution error
that invalidated earlier attempts. `results.csv` contains the 48 scored rows.
Its response paths identify original outputs retained privately; the individual
responses and metadata are not included in this public submission.

## Results for all 12 cases

The provisional key classifies 9 cases as defective and 3 as clean. Caught and
missed rates use the 9 defective cases as their denominator; false-alarm
rates use the 3 clean cases. A review is scored once per case, even if it
reports multiple findings.

| Run | Prompt | Caught | Missed | False alarms |
|---|---|---:|---:|---:|
| 1 | v1 | 9/9 (100%) | 0/9 (0%) | 0/3 (0%) |
| 2 | v1 | 9/9 (100%) | 0/9 (0%) | 1/3 (33.3%) |
| 3 | v1 | 9/9 (100%) | 0/9 (0%) | 1/3 (33.3%) |
| 4 | v2 | 8/9 (88.9%) | 1/9 (11.1%) | 0/3 (0%) |

Across the three v1 runs, 27/27 defective-case reviews were scored caught
and 2/9 clean-case reviews were scored false alarms. These are counts of
case-review outcomes, not 27 independent defects: the same cases are
repeated across runs.

## Comparison and confidence

The changed prompt produced no scored false alarms in its one run, but missed
case 09, which all three baseline runs identified. **There is no convincing
overall improvement in this sample.** The changed prompt was run only once,
the cases are few and repeated, and scoring relies on a provisional key. No
statistical significance or production performance is established.

Interpret the differences with these important limitations:

- Case 04 was treated as clean because no named-argument caller was found in
  the checkout. The two v1 findings correctly describe a *potential* public
  constructor source-compatibility break and explicitly acknowledge that no
  such caller is shown. Counting those conditional findings as false alarms
  is debatable; if they are not counted, v1 also has zero false alarms.
- Case 07 is counted as a defect because full invoice and user logging could
  disclose sensitive information. The actual data classification and log
  access policy are not specified.
- Case 09's answer requires repository context: logout removes the session,
  not the singleton invoice store. Reviewers received only the diff and
  prompt. The v2 review explicitly said it could not verify the reset claim
  from that limited context; its missed score reflects the evaluation key,
  not an unsupported assertion by the reviewer.
- If cases 04, 07 and 09 are excluded as interpretation- or context-sensitive,
  each run catches 7/7 remaining defective cases with 0/2 false alarms on
  remaining clean cases. This narrower view also shows no measurable
  difference.
- Cases 11 and 12 are constructed examples based on observed repository
  behavior; case 11 is not represented as a historical commit.

The key in `eval-reference-key.md` and the added-case key in
`evaluation-added-case-key.md` should be reviewed by the engineer; they
are not an official answer key.
