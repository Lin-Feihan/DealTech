# Certification Loop

## Purpose

The certification loop verifies candidate claims before they can support downstream deal analysis or final reporting.

## Inputs

- candidate claims
- evidence repository
- claim-evidence graph
- source quality policy
- calculation replay policy
- human review policy
- active research module

## Verifier Checks

1. Coverage: does the research address the required question?
2. Evidence sufficiency: does the evidence directly support the claim?
3. Source reliability: is the source appropriate for the claim type?
4. Calculation replay: can material calculations be recomputed?
5. Conflict detection: do other claims or sources contradict this claim?
6. Human-review boundary: does the claim require expert judgment?

## Outputs

- certification results
- certified claims
- caveated claims
- not certified claims
- internal trace claims
- human review items
- research gaps

## Controller Decisions

```text
Certified -> pass to Certified Evidence
Certified with Caveat -> pass with visible caveat
Needs Human Review -> add to human review queue
Not Certified -> block from report and create research gap
Internal Trace Only -> retain for audit only
```

## Certification Status

The status vocabulary must match Policy π:

- Certified
- Certified with Caveat
- Needs Human Review
- Not Certified
- Internal Trace Only

## Loop Exit

The certification loop exits when all material claims needed for the current stage are Certified, Certified with Caveat, or explicitly escalated.
