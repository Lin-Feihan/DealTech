# V2 Agent Baseline Map

This file is the stable reading map for `acquisition_strategy_agent.buyer_side.v2`.

The purpose is to make the V2 agent easy to review without losing the original buyer-side acquisition strategy prompt, the input/output contract, or the loop-engineered deep research architecture.

## Current Truth

V2 has two layers:

1. **Preserved buyer-side deal-research baseline**
   - the original human-readable buyer-side acquisition strategy prompt;
   - the original structured workflow backbone;
   - the 15-section Buyer-side Acquisition Strategy Report contract.

2. **V2 loop and certification control layer**
   - loop policy;
   - certification policy;
   - report-writer policy;
   - schemas for mandate, research plan, claims, evidence, case analysis, report manifest, and recommendation;
   - a post-certification runtime that validates `case_analysis.json`, replays typed models, and writes a professional report plus audit artifacts.

V2 does not replace the baseline. It wraps the baseline with explicit runtime and certification contracts.

## Read These First

| Need | File | Why it matters |
| --- | --- | --- |
| System architecture | `README.md` | High-level V2 architecture, loops, status, and roadmap. |
| Agent overview | `agents/acquisition_strategy_agent/README.md` | What the Acquisition Strategy Agent bundle contains. |
| Baseline source mapping | `agents/acquisition_strategy_agent/buyer_side/source_mapping.md` | Shows the V1 prompt/workflow baseline and what V2 adds. |
| Original buyer-side prompt | `agents/acquisition_strategy_agent/buyer_side/prompt.md` | The preserved natural-language Deep Research prompt and 15-section report logic. |
| Structured workflow | `agents/acquisition_strategy_agent/buyer_side/workflow.json` | Machine-readable workflow derived from the prompt. |
| Output contract | `agents/acquisition_strategy_agent/buyer_side/output_contract.json` | Required outputs, report sections, recommendation rules, and report-layering rules. |
| Runtime sequence | `agents/acquisition_strategy_agent/buyer_side/agent.config.json` | The declared V2 runtime steps and the implemented/unimplemented boundary. |
| Execution runbook | `agents/acquisition_strategy_agent/buyer_side/runbook.md` | End-to-end workflow and current executable stage. |

## Baseline Files That Must Not Be Removed

These files are the buyer-side agent baseline and governance core:

```text
agents/acquisition_strategy_agent/buyer_side/prompt.md
agents/acquisition_strategy_agent/buyer_side/workflow.json
agents/acquisition_strategy_agent/buyer_side/output_contract.json
agents/acquisition_strategy_agent/buyer_side/source_mapping.md
agents/acquisition_strategy_agent/buyer_side/loop_policy.json
agents/acquisition_strategy_agent/buyer_side/certification_policy.json
agents/acquisition_strategy_agent/buyer_side/report_writer_policy.json
agents/acquisition_strategy_agent/buyer_side/runbook.md
agents/acquisition_strategy_agent/buyer_side/agent.config.json
agents/acquisition_strategy_agent/agent.manifest.json
```

If any future optimization changes one of these files, the change should be reviewed as an architecture change, not as a cosmetic cleanup.

## What Is Implemented Now

The current executable stage starts after upstream source retrieval and claim certification.

Implemented:

- load certified/current-case input package;
- require authoritative `supporting_files/case_analysis.json`;
- validate current-case input sovereignty;
- route case-applicable analytical methods;
- replay typed DCF or rNPV models when selected by current-case evidence;
- enforce 15 report sections;
- generate `final_report.md` and audit artifacts;
- reject internal audit-marker leakage in the business-facing report.

Not implemented yet:

- automated web/search retrieval;
- evidence repository construction from raw sources;
- claim-evidence graph construction;
- Policy Pi claim-certification runtime;
- live financial data connectors;
- committed V2 case study.

## Final Output Boundary

The business report and audit package are separate.

Business-facing:

- `final_report.md`

Reviewer/audit-facing:

- `case_analysis.json`
- `analysis_package.json`
- `recommendation_decision.json`
- `report_manifest.json`
- `research_gaps.json`
- `human_review_items.json`
- `analysis_quality_control.json`
- upstream `evidence_repository.json`, `claim_evidence_graph.json`, and `certification_results.json` when those stages are implemented.

Raw claim IDs, evidence IDs, source IDs, PCE/ER-BRB mechanics, and runtime explanations should stay out of the main business report.

## Baseline Guard

Run the baseline guard from this folder:

```bash
python3 tools/verify_v2_agent_baseline.py
```

The guard checks that the critical V2 files exist, JSON files parse, the preserved prompt still carries the Deep Research and 15-section report contract, the output contract still requires the expected artifact set, and the runtime config still declares the current implemented/unimplemented boundary.

