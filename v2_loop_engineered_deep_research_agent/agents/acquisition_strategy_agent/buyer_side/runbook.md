# Buyer-Side Acquisition Strategy Agent V2 Runbook

## Purpose

This runbook defines the full V2 workflow and the currently executable post-certification runtime.

The implemented runner begins with certified claim results plus an authoritative, analysis-authored `case_analysis.json`. It replays typed calculations, validates provenance and the 15-chapter contract, writes the professional report, and emits traceable downstream artifacts. Automated research and claim certification remain upstream interfaces.

## Quick Start

From the repository root:

```bash
python3 v2_loop_engineered_deep_research_agent/runtime/run_agent.py \
  --case-dir /path/to/certified_case \
  --output-dir /path/to/output \
  --json
```

The runner uses only the Python standard library.

## Required Inputs

A runner should start with a mandate matching:

```text
../../../schemas/mandate.schema.json
```

Minimum required fields:

- mandate_id
- agent_id = `acquisition_strategy_agent.buyer_side.v2`
- perspective = `buyer`
- buyer_name
- target_name
- decision_questions
- output_requirements
- governance

The current runner also requires the case directory to contain:

```text
certification_results.json
supporting_files/
└── case_analysis.json
```

`certification_result.json` is accepted as a backward-compatible singular filename. The certification object must include `overall_status`. `case_analysis.json` must conform to `../../../schemas/case_analysis.schema.json`; missing analysis fails closed instead of falling back to generated recommendations.

## Execution Sequence

### 1. Parse Mandate

Validate mandate against `mandate.schema.json`.

If buyer or target is missing, ask clarification questions before research.

### 2. Create Research Plan

Use `workflow.json` as the module backbone. Create work packages for B1-B15.

Prioritize modules that affect final recommendation, valuation, deal structure, financing, synergies, and risk.

### 3. Run Research Loop

For each module:

- identify source needs
- retrieve/read sources
- extract evidence
- create candidate claims
- create calculation records where needed
- update evidence repository
- update claim-evidence graph

### 4. Run Certification Loop

Apply `certification_policy.json` plus shared Policy π.

Each candidate claim receives one status:

- Certified
- Certified with Caveat
- Needs Human Review
- Not Certified
- Internal Trace Only

### 5. Route Gaps

If critical claims fail certification, create research gaps and return to the research plan unless stop conditions are met.

### 6. Run Deal Analysis Loop

Use only Certified or Certified with Caveat evidence for analytical claims.

Generate `case_analysis.json` before report writing. It contains the decision clock, facts, assumptions, case-grounded method selection, analysis-authored chapters, replayable models, acquisition-versus-alternative comparison, recommendation, research gaps, conditions, and red lines.

This stage is implemented in `../../../runtime/acquisition_analysis.py`. Research is prioritized by decision leverage. The current mandate and current-case source registry are the only sources of company identity, transaction facts, model inputs, and conclusions. Numerical conclusions preserve inputs, units, timing, scenario, source class, formula, output, and limitations. The method router selects an applicable replay adapter from current-case evidence. The included runtime adapters are DCF for cash-generative operating companies and rNPV for development-stage assets; neither is globally required. Later disclosures of historical facts and post-decision outcomes remain separate from decision-date evidence.

### 7. Certify Thesis

Check that analytical claims link to certified upstream claims. Escalate unsupported recommendation logic.

The recommendation is authored in `case_analysis.json`, supported by facts, assumptions and calculations, and checked for internal consistency. Certification status alone cannot promote, demote or create it.

### 8. Generate Report

Draft the report according to `output_contract.json`.

Apply `report_writer_policy.json` before writing `final_report.md`:

- write the main report as professional acquisition analysis, not as a certification ledger
- translate claim/evidence/certification objects into business-facing statements
- serialize analysis-authored chapters into the original 15-section report's natural prose and appropriate tables
- preserve the original visible numbering exactly: section 1 Executive Summary through section 15 Final Recommendation
- include a 100-day plan only when transaction stage and current-case evidence make it useful; do not create it from renderer defaults
- select tables for decision value and sector relevance; do not preserve empty tables or repeated missing-data rows to meet a count
- keep runtime, schema, certification, and report-generation explanations out of the main report
- keep raw claim IDs, evidence IDs, source IDs, and certification mechanics in `report_manifest.json` and audit package files
- present unsupported or human-review-gated content as diligence questions, not final conclusions
- fail the report gate if internal audit markers leak into the main report body

Before rendering, write `analysis_quality_control.json`. Fail closed when authoritative analysis is missing, method selection is not grounded in current-case basis records, selected models are not replayed, declared scenario policy is unmet, a chapter cites unknown basis/model records, the 15-chapter contract changes, acquisition lacks a real alternative, or research gaps omit decision effects. The renderer serializes validated content and replayed arithmetic only.

### 9. Certify Report

Create `report_manifest.json` linking report sections and tables to claims and calculations.

Remove, caveat, or restrict unsupported content.

### 10. Emit Final Outputs

Expected outputs:

- final_report.md
- case_analysis.json
- analysis_package.json
- recommendation_decision.json
- report_manifest.json
- research_gaps.json
- human_review_items.json
- analysis_quality_control.json

The following remain upstream inputs/artifacts and are not synthesized by the current runner:

- evidence_repository.json
- claim_evidence_graph.json
- certification_results.json

## No Case Study Yet

No case study is committed to this bundle. Runtime portability is tested with temporary synthetic fixtures created during the test run.

## Verification

```bash
python3 -m unittest discover \
  -s v2_loop_engineered_deep_research_agent/runtime/tests \
  -t . \
  -v
```
