# Human Review Policy

## Purpose

Human review is a governance boundary. The V2 system should continue automatic research only while the question remains suitable for automated evidence gathering and structured analysis.

## Human Review Triggers

Human review is required when:

- legal, regulatory, accounting, tax, or fairness judgment exceeds automated confidence
- source conflicts materially affect recommendation
- valuation depends on unsupported or highly subjective assumptions
- management intent, board position, shareholder behavior, or negotiation stance is inferred rather than documented
- data access limitations prevent verification of a material claim
- user-provided information conflicts with public source-backed evidence
- transaction recommendation depends on caveated or uncertified claims
- ethical, confidentiality, or market-sensitive issues arise

## Restricted Output

When human review is required, the system may produce restricted output if allowed by the mandate:

```text
Restricted Output - Human Review Required
```

Restricted output may include:

- known facts
- evidence map
- research gaps
- caveated analysis
- questions for human review
- decision points requiring expert input

Restricted output must not present a final unrestricted recommendation.

## Human Review Queue

Human review items should include:

- item_id
- linked claim_id or module_id
- reason for escalation
- evidence summary
- decision impact
- recommended reviewer type
- required question for reviewer

Recommended reviewer types:

- deal principal
- investment committee member
- legal counsel
- tax advisor
- accounting advisor
- valuation expert
- regulatory counsel
- subject-matter expert

## Return From Human Review

After human review, the system may:

- update assumptions
- certify a caveated claim
- remove a claim
- revise the report
- run additional research
- terminate with no recommendation

Human review decisions should be recorded in the report manifest and claim-evidence graph.
