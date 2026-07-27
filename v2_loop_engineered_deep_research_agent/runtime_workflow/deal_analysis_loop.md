# Deal Analysis Loop

## Purpose

The deal analysis loop converts certified evidence into an investment thesis and transaction recommendation.

## Inputs

- certified evidence
- caveated evidence
- claim-evidence graph
- buyer-side workflow modules
- valuation and calculation records
- certified research gaps
- human review items

## Buyer-Side Analysis Areas

- transaction logic
- buyer strategic objectives
- target business quality
- industry and competitive position
- strategic fit
- standalone financial performance
- valuation and maximum acceptable price
- synergies and value creation
- deal structure
- financing and capital structure impact
- returns analysis
- due diligence priorities
- regulatory, integration, and downside risks
- 100-day integration or development plan
- final decision recommendation

## Authoritative Analysis Protocol

The analysis layer writes `case_analysis.json` before rendering. It separates decision-date metadata, facts, assumptions, case-grounded method selection, calculations, alternatives, research gaps and the recommendation. Each visible chapter contains an analysis-authored judgment, natural prose and basis references; the renderer does not turn a method checklist into business prose.

The schemas are `../schemas/case_analysis.schema.json` and `../schemas/section_analysis.schema.json`.

Before report generation, quality control verifies that every model was selected from current-case evidence, declared scenario policies are met, basis/model references resolve, the exact 15-chapter order is preserved, acquisition is compared with at least one real alternative, and research gaps state decision effects. DCF and rNPV are included adapters, not global requirements; additional sectors and transaction types must use their applicable method or fail closed until a replay adapter exists. Evidence-clock checks separate later historical disclosure and hindsight from information usable at the decision date.

## Analytical Claims

The Deal Analyst produces new analytical claims, including:

- strategic thesis
- valuation thesis
- synergy thesis
- financing thesis
- risk thesis
- recommendation thesis

These are not automatically certified. They must link to upstream certified or caveated claims.

## Thesis Certification

The thesis certification gate checks:

- whether analytical claims depend on certified evidence
- whether caveats are visible
- whether valuation formulas are replayable
- whether strategic judgment leaps are disclosed
- whether recommendation claims depend on unresolved human-review items

## Outputs

- investment thesis
- analytical claim set
- thesis certification results
- unresolved decision gaps
- recommended report status
- analysis-authored recommendation, conditions, red lines and next actions
- 15-section analysis package
- analysis quality-control result

## Report Status Recommendation

The Deal Analyst may recommend one of:

- Certified
- Certified with Caveat
- Restricted Output - Human Review Required
- Research Gap Memo Only

## Executable Scope

`../runtime/acquisition_analysis.py` validates authoritative analysis, routes and replays supported typed models, and passively renders the report. It intentionally refuses to create a recommendation from evidence-file presence, certification status, or a prior case.
