# Report Generation Loop

## Purpose

The report generation loop produces a final M&A report only after evidence and thesis certification have established what can be safely used.

## Inputs

- mandate
- certified evidence
- caveated evidence
- certified investment thesis
- report output contract
- report-writer policy
- claim-evidence graph
- human review items
- authoritative `case_analysis.json`
- replayed model results

## Actions

1. Load the analysis-authored `case_analysis.json`; verify current-case input sovereignty plus every chapter basis/model reference.
2. Validate case-grounded method selection, replay supported typed calculations, and run quality control on evidence timing, assumptions, alternatives, scenario policy, research-gap decision effects and recommendation coherence.
3. Preserve the original contract: section 1 Executive Summary through section 15 Final Recommendation. Select tables only when they compare options, replay a calculation, allocate risk or expose a decision-changing assumption.
4. Pass validated chapter content and calculated outputs to a passive renderer that formats but does not invent judgments, conditions, diligence actions, red lines or workstreams.
5. Keep raw claim IDs, evidence IDs, source IDs, and certification mechanics out of the main report body.
6. Link every chapter and model output to its analysis basis in the report manifest.
7. Create report manifest.
8. Run report certification.
9. Revise, caveat, restrict, or remove unsupported content.
10. Produce final report and manifest.

## Report Certification Checks

- every key section has claim support
- every material table has source or calculation support
- caveated claims are visibly caveated
- no Not Certified claim supports final recommendation
- Needs Human Review items are not hidden
- recommendation status matches evidence status
- main report does not expose internal audit markers such as raw claim IDs, evidence IDs, source IDs, PCE labels, or ER/BRB labels
- main report does not explain the runtime, structured-object schema, recommendation gate, or certification workflow
- main report reads as section-specific acquisition analysis rather than a repeated process template
- audit trace remains available in separate package files

## Outputs

- final report
- report manifest
- claim-evidence graph
- certification results
- human review queue
- research gap memo if needed
- analysis package
- authoritative case analysis
- recommendation decision
- analysis quality-control result

## Restricted Output

If certification is incomplete, the report must be labeled clearly:

```text
Restricted Output - Human Review Required
```

Restricted output may summarize evidence and gaps, but it must not overstate a final recommendation.

## Executable Scope

`../runtime/runner.py` writes `analysis_package.json`, `recommendation_decision.json`, `report_manifest.json`, `research_gaps.json`, `human_review_items.json`, `analysis_quality_control.json`, and `final_report.md`. The renderer rejects the report if quality control fails or internal audit markers leak into the business-facing body.
