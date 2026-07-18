# Milestone 2 business workflow: robust termination and human review

## Scope

Milestone 2 extends only the deterministic Block A loop. It preserves the original
repair-success behavior and adds safe outcomes when research cannot repair the
Strategic Fit evidence gap.

## Failure scenarios

### Repeated evidence failure

Each attempt is appended with its own action ID, Source IDs, Evidence IDs, and
outcome. PCE-ineligible material does not certify the Claim. Every failed Gate A
result and every Research Gap version remains available for replay.

### No progress

The controller compares consecutive evidence snapshots. It records:

- newly registered Sources;
- newly admissible Sources;
- newly registered Evidence;
- PCE deliverability improvement;
- Strategic Thesis Gate criterion improvement; and
- repeated action keys.

Material progress requires an admissible-source, deliverability, or Gate-criterion
improvement. Low-quality volume alone does not qualify. Consecutive failures
increment `no_progress_count`; the configured limit produces
`STOPPED_NO_PROGRESS`.

### Iteration-budget exhaustion

The Mandate and Research Contract define the same maximum iteration count. When the
last permitted iteration still fails Gate A, the controller records
`STOP_ITERATION_BUDGET`, does not schedule another iteration, and produces
`STOPPED_ITERATION_BUDGET`.

### Human-only information

Confidential customer concentration is the controlled example. Gap Diagnosis uses
`HUMAN_ONLY_INFORMATION`, and the controller records `ESCALATE_HUMAN_REVIEW`
instead of retrying public research. The open `HumanReviewItem` names the reviewer,
exact question, required materials, related Claim, and related Gap. The runtime
pauses at `AWAITING_HUMAN_REVIEW`.

## Append-only memory boundary

Memory persists every Gate A result, PCE result, Research Gap version, Research
Attempt, Evidence Snapshot, No-Progress Assessment, Controller Decision, Re-plan,
Human Review Item, Iteration Record, and Terminal Decision. A new record never
replaces an older failed record.

## Decision separation

- **PCE status** controls claim deliverability inside the registered evidence
  boundary.
- **Gate A status** controls Strategic Thesis completeness.
- **Controller Decision** selects retry, alternate method, escalation, stop, advance,
  or technical failure.
- **Terminal State** explains why the current runtime ended or paused.

None of these objects is a full-deal recommendation.
