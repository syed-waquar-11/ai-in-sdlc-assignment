# Review evaluation method

## Scope and isolation

- Cases: the ten supplied files and `case-11.diff` and `case-12.diff`.
- Model: `gpt-6-luna` in a new Copilot CLI process for each case.
- Baseline: three independent passes using prompt v1.
- Comparison: one pass using prompt v2; only the prompt changes.
- Each reviewer receives the case diff and prompt, not the answer keys or
  application source. The CLI starts outside the repository with custom
  instructions and built-in MCPs disabled, and its available-tools list
  restricted to a nonexistent tool name. Model/system instructions still
  exist; this is not a completely instruction-free model invocation.
- Raw reviewer responses and execution metadata are retained privately and are
  not included in this public submission. The paths in `results.csv` identify
  those private artifacts. The scoring keys are separate and must not be added
  to the review prompt.

## Prompt v1

> Review this diff for defects. For each finding give the file, the line, what
> goes wrong, and how confident you are. If you find nothing, say so
> explicitly rather than listing general observations.

## Prompt v2

Prompt v1 followed by:

> Systematically consider correctness, concurrency, authorization, error
> handling, and sensitive-data exposure. Report concrete defects supported by
> the diff; clearly identify any uncertainty caused by missing context.

## Execution incident

The first baseline review received its diff. The initial automated runner then
used the Windows `copilot.cmd` wrapper with multiline arguments; the subsequent
responses said the diff had not been supplied. Those attempts were stopped,
preserved privately under `invalid-wrapper`, and excluded from scoring. Their
individual outputs are not included in this public submission. The exact cause
of argument loss was not independently isolated beyond that runner setup.

The corrected runner invokes the Copilot Node loader directly with one prompt
argument containing the complete diff. A test review of case 02 identified
its interpolated SQL, demonstrating that this invocation received relevant
case content. All sessions still require individual output review: a zero
process exit code alone is not proof that a diff was reviewed.
