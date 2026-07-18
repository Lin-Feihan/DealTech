# Milestone 1 business workflow: deterministic Gate A evidence repair

## Business boundary

This milestone implements only the first executable slice of the independent
buyer-side loop:

`Input / Mandate → Research Contract → Block A: Strategic Thesis → Strategic Thesis Gate`

When Gate A fails for missing evidence, the implemented loop is:

`Gap Diagnosis → Memory Update → Loop Controller → Re-plan → targeted return → Gate A`

Block A keeps these acquisition concepts explicit:

- Transaction Context
- Buyer Strategic Need
- Strategic Rationale
- Target Attractiveness
- Target Capability & Business Quality
- Industry / Competitive Position
- Strategic Fit

## Deterministic Gate A rule

Gate A evaluates five named criteria. The first four require an explicit business
statement. The fifth requires a Strategic Fit claim with an available supporting
Evidence record, a linked Source, and a `Certified` PCE precheck:

`Target Capability & Business Quality evidence supports Strategic Fit`

Failure creates an `EVIDENCE_MISSING` research gap whose only return target is
**Target Capability & Business Quality**. The re-planner is not allowed to rerun
unrelated Block A modules.

## PCE and Gate A are different decisions

PCE asks whether a claim is deliverable inside its registered evidence boundary.
Gate A asks whether the strategic-thesis business criteria are satisfied. Each has
its own status and both are written into each gate-iteration artifact.

The adapter calls the existing `dealtech_certification.pce.run_pce` function. The
existing PCE claim interface holds one evidence/source link, while loop memory is
append-only and permits multiple evidence links. The adapter therefore retains all
lineage in the new Claim and selects the latest available supporting link for one
PCE invocation.

The existing ER/BRB function is not called in this milestone. It iterates existing
evidence rows and applies evidence-risk and certification-boundary checks; it does
not evaluate Block A module completeness, and the first iteration deliberately has
no admissible evidence row. Treating that function as Gate A would merge two
different decision boundaries. The existing certification package is unchanged.

## Memory and stop rule

Memory appends Sources and Evidence. It never overwrites a prior record. Each
Iteration Record snapshots the question, module executed, lineage, PCE status, Gate
status, gaps, and change made.

The synthetic case has a two-iteration budget. Its successful repair now ends in
the explicit `COMPLETED_STRATEGIC_THESIS` terminal state. A Gate A pass is only a
strategic-thesis result; it is not a full-deal recommendation.
