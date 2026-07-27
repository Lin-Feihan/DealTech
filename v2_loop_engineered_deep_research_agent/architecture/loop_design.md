# Loop Design

## Design Goal

Loop engineering turns a one-shot agent into a controlled research system. The system does not trust first-pass generation. It repeatedly plans, researches, verifies, diagnoses gaps, and revises until a governance condition is met.

## Loop Layers

### 1. Research Loop

Purpose: collect evidence and create candidate claims.

```text
research question -> search/read/extract/compute -> candidate claims -> evidence repository -> research gaps
```

The research loop is local to each work package. It should not write final recommendations directly.

### 2. Certification Loop

Purpose: decide whether candidate claims can be used.

```text
candidate claims + evidence + sources + calculations
-> verifier
-> certification status
-> research gaps or certified evidence
```

This loop is the core of the V2 system.

### 3. Deal Analysis Loop

Purpose: build transaction judgment from certified evidence.

```text
certified evidence -> analytical claims -> investment thesis -> thesis certification
```

The key idea is that analytical conclusions are also claims. They must be checked against upstream evidence.

### 4. Report Generation Loop

Purpose: produce a report whose material statements are traceable.

```text
certified thesis -> report draft -> report manifest -> report certification -> final report
```

A report paragraph or table without traceable claim support must be revised, caveated, or removed.

## Loop State

Recommended states:

```text
planned
researching
evidence_collected
verification_failed
gap_research_required
certified
certified_with_caveat
human_review_required
not_certified
internal_trace_only
terminated_quality_met
terminated_budget_exhausted
terminated_iteration_exhausted
terminated_human_review_required
```

## Stop Conditions

### Quality Gate

- all material decision questions covered
- no critical uncertified claims remain in final recommendation
- source quality threshold met
- calculations replayable where calculations are material
- conflicts resolved or disclosed
- human-review items isolated from final recommendation

### Resource Gate

- maximum iterations reached
- time budget exhausted
- cost budget exhausted
- source access blocked

### Escalation Gate

- material legal, regulatory, or valuation judgment exceeds automated confidence
- source conflict cannot be resolved
- user-provided data conflicts with source-backed data
- valuation depends on unsupported assumptions
- recommendation depends on non-certified evidence

## Controller Behavior

The Loop Controller should not simply ask for more research. It should prioritize gaps by decision impact.

Recommended priority order:

1. gaps that affect final recommendation
2. gaps that affect valuation or price ceiling
3. gaps that affect deal structure or financing
4. gaps that affect synergy or returns
5. gaps that affect risk caveats
6. gaps that affect report completeness but not decision outcome

## Output Principle

The system may produce restricted output when quality is incomplete, but it must label limitations clearly.

Examples:

- `Certified Report`
- `Certified with Caveat Report`
- `Restricted Output - Human Review Required`
- `Research Gap Memo Only`
