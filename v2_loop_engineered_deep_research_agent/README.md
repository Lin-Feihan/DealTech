# V2 Loop-Engineered Certified Deep Research Agent

This folder defines the V2 architecture for turning the V1 DealTech agents into a controlled deep-research runtime for M&A work.

The main idea is simple:

> A deal research agent should not only write a report. It should plan the research, collect evidence, certify claims, expose gaps, and then write a professional report from the certified research record.

V2 is designed for transaction research where unsupported claims can be costly: acquisition strategy, target assessment, shell-company screening, SPAC target screening, restructuring analysis, and future merger strategy work.

## Current Status

This package now includes an **executable minimum post-certification runtime** for the buyer-side Acquisition Strategy Agent.

For the clean map of what belongs to the V2 agent bundle, start with `AGENT_BASELINE_MAP.md`. It identifies the preserved buyer-side prompt/workflow baseline, the V2 loop and certification control layer, the current runtime boundary, and the files that should not be removed during future optimization.

It currently includes:

- the V2 system architecture;
- shared schemas for mandates, research plans, claims, evidence, certifications, and report manifests;
- shared governance policies for source quality, calculation replay, Policy π, and human review;
- runtime workflow documents for the research, certification, deal analysis, and report-generation loops;
- the first V2 agent bundle: `acquisition_strategy_agent.buyer_side.v2`;
- a case-agnostic standard-library Python runner that validates an analysis-authored case package, routes case-applicable DCF or rNPV adapters, replays typed models, and produces a 15-section report plus traceable manifest;
- synthetic portability and fail-closed tests that do not add a V2 case study.

It does **not** yet include:

- a fully automated web/search runtime;
- a live financial data connector;
- a committed V2 case study;
- an automated claim-certification runner.

The implemented runtime deliberately begins after claim certification. It does not pretend that source retrieval, evidence graph construction, or Policy π claim certification are already automated.

## Why V2 Exists

The V1 agent baseline preserves valuable agent assets: workflows, prompts, structured specs, demos, case reports, and certification artifacts. Those assets are useful, but many early agents still resemble a one-pass pattern:

```text
user request -> model research -> final report
```

That pattern is not strong enough for serious transaction work. M&A research needs source control, evidence coverage, calculation replay, conflict detection, uncertainty disclosure, human-review boundaries, and a clear distinction between what was generated and what is safe to deliver.

V2 separates the work into controlled layers:

```text
User Mandate
-> Mandate Parser
-> Research Planner
-> Deep Research Agent
-> Evidence Repository
-> Claim-Evidence Graph
-> Loop Certification
-> Deal Analysis
-> Thesis Certification
-> Professional Report Generation
-> Report Certification
-> Final Report + Audit Package
```

The result is a research system that is **claim-centric**, not report-centric. The report is the presentation layer. The durable asset is the certified research record behind it.

## Architecture At A Glance

```text
                            User Mandate
                                 |
                                 v
                         Mandate Parser
                                 |
                                 v
                        Research Planner
                                 |
                                 v
                          Research Loop
        search / read / extract / compute / identify gaps
                                 |
                                 v
       Evidence Repository + Candidate Claims + Calculations
                                 |
                                 v
                       Claim-Evidence Graph
                                 |
                                 v
                       Certification Loop
      source quality / evidence sufficiency / calculation replay
      conflict checks / human-review triggers / Policy π status
                                 |
                                 v
             Certified Evidence or Prioritized Research Gaps
                                 |
                                 v
                        Deal Analysis Loop
        strategic thesis / valuation thesis / risk thesis
                                 |
                                 v
                       Thesis Certification
                                 |
                                 v
                    Report Generation Loop
        professional report body + separate audit package
                                 |
                                 v
                       Report Certification
                                 |
                                 v
             Final Report + Manifest + Human Review Items
```

## The Four Loops

### 1. Research Loop

The research loop collects sources, extracts evidence, creates candidate claims, records calculations, and logs gaps. It does not decide final recommendations.

```text
research question -> source retrieval -> evidence extraction -> candidate claims -> research gaps
```

### 2. Certification Loop

The certification loop decides whether candidate claims can be used downstream.

Each claim receives one of the following statuses:

- `Certified`
- `Certified with Caveat`
- `Needs Human Review`
- `Not Certified`
- `Internal Trace Only`

### 3. Deal Analysis Loop

The deal analysis loop builds transaction judgment from certified or caveated evidence. Strategic fit, valuation view, financing view, synergy view, risk view, and recommendation logic are treated as analytical claims that must be supported.

### 4. Report Generation Loop

The report generation loop writes a professional M&A report only after the research and thesis layers are certified or caveated.

The main report should read like deal analysis, not like an audit ledger. Raw claim IDs, evidence IDs, source IDs, certification statuses, and machine trace fields belong in the audit package and `report_manifest.json`, not in the business-facing report body.

## Current V2 Pilot

The first V2 pilot is:

```text
acquisition_strategy_agent.buyer_side.v2
```

It upgrades the buyer-side Acquisition Strategy Agent from the V1 agent baseline into a loop-governed specification with an executable analysis-and-report stage.

The pilot uses these V1 materials as its source baseline:

- `../agents/acquisition-strategy-agent/01_business_workflow/flowcharts/buyer-flowchart.jpg`
- `../agents/acquisition-strategy-agent/02_prompts/buyer_acquisition_strategy_prompt.md`
- `../agents/acquisition-strategy-agent/02_prompts/buyer_acquisition_strategy_agent.json`

V2 does not replace V1. V1 remains the preserved rescue materials. V2 wraps selected V1 assets in explicit runtime contracts: schemas, policies, loop controls, certification gates, and output contracts.

## Expected Runtime Inputs And Outputs

The full workflow starts from a user mandate matching `schemas/mandate.schema.json`. The current runner starts later, from a certified case package.

Minimum mandate concepts include:

- buyer name;
- target name;
- transaction type;
- decision questions;
- source requirements;
- output requirements;
- budget and iteration constraints;
- human-review preferences.

The expected final output package is:

- `final_report.md` — professional buyer-side acquisition strategy report with decision-grade transaction analysis;
- `case_analysis.json` — authoritative decision clock, facts, assumptions, analysis-authored chapters, models, alternatives, recommendation, gaps and red lines;
- `analysis_package.json` — validated 15-chapter analysis plus replayed model outputs;
- `recommendation_decision.json` — the analysis-authored decision, price/structure/financing positions, conditions, red lines and next actions;
- `evidence_repository.json` — source-backed evidence records;
- `claim_evidence_graph.json` — claims linked to evidence, sources, calculations, and certification results;
- `certification_results.json` — claim-level certification statuses;
- `report_manifest.json` — report sections mapped back to claims and calculations;
- `research_gaps.json` — unresolved research gaps and their decision impact;
- `human_review_items.json` — issues that require analyst, legal, accounting, valuation, or transaction review;
- `analysis_quality_control.json` — fail-closed checks for analysis provenance, basis references, model coverage, alternative comparison, research-gap effects and audit-layer isolation.

## Report Layering Rule

V2 separates the business report from the audit package.

The main report is for deal teams, investment committees, and strategy reviewers. It should answer why buy, why now, at what price or why price is not certified, how risk is shared, what remains unresolved, and whether the buyer should proceed, proceed with conditions, renegotiate, defer, or walk away.

The audit package is for reviewers, certifiers, maintainers, and future runners. It should preserve raw claim IDs, evidence IDs, source IDs, certification statuses, calculation replay records, and trace metadata.

In short:

```text
final_report.md          = business-facing buyer-side acquisition strategy report
report_manifest.json     = mapping from report sections to certified claims
audit package files      = machine-readable or reviewer-readable trace
```

The report renderer is intentionally passive. Research, counter-thesis testing, cross-module reconciliation, decision thresholds, and business judgments are completed and quality-controlled before report-content synthesis; the renderer only serializes the validated content under the original report contract.

This rule prevents the final report from becoming a dump of internal certification artifacts while still preserving full traceability.

## Folder Structure

```text
v2_loop_engineered_deep_research_agent/
├── README.md
├── architecture/
│   ├── system_overview.md
│   ├── workflow_diagram.md
│   └── loop_design.md
├── schemas/
│   ├── mandate.schema.json
│   ├── research_plan.schema.json
│   ├── claim.schema.json
│   ├── evidence.schema.json
│   ├── certification.schema.json
│   ├── section_analysis.schema.json
│   ├── analysis_package.schema.json
│   ├── recommendation_decision.schema.json
│   └── report_manifest.schema.json
├── policies/
│   ├── policy_pi.md
│   ├── source_quality_policy.md
│   ├── calculation_replay_policy.md
│   └── human_review_policy.md
├── runtime_workflow/
│   ├── research_loop.md
│   ├── certification_loop.md
│   ├── deal_analysis_loop.md
│   └── report_generation_loop.md
├── runtime/
│   ├── run_agent.py
│   ├── runner.py
│   ├── acquisition_analysis.py
│   └── tests/
│       └── test_runtime.py
└── agents/
    └── acquisition_strategy_agent/
        ├── README.md
        ├── agent.manifest.json
        └── buyer_side/
            ├── agent.config.json
            ├── source_mapping.md
            ├── prompt.md
            ├── workflow.json
            ├── loop_policy.json
            ├── certification_policy.json
            ├── report_writer_policy.json
            ├── output_contract.json
            ├── runbook.md
            └── case_studies/
                └── README.md
```

## How To Read This Folder

If you need the shortest reliable orientation, start here:

1. `AGENT_BASELINE_MAP.md`
2. `agents/acquisition_strategy_agent/buyer_side/source_mapping.md`
3. `agents/acquisition_strategy_agent/buyer_side/prompt.md`
4. `agents/acquisition_strategy_agent/buyer_side/output_contract.json`
5. `agents/acquisition_strategy_agent/buyer_side/runbook.md`

If you are reviewing the system design, start here:

1. `architecture/system_overview.md`
2. `architecture/loop_design.md`
3. `architecture/workflow_diagram.md`

If you are implementing a runner, start here:

1. `runtime/runner.py`
2. `runtime/acquisition_analysis.py`
3. `agents/acquisition_strategy_agent/agent.manifest.json`
4. `agents/acquisition_strategy_agent/buyer_side/agent.config.json`
5. `agents/acquisition_strategy_agent/buyer_side/runbook.md`
6. `schemas/`
7. `runtime_workflow/`

If you are reviewing the buyer-side Acquisition Strategy Agent, start here:

1. `agents/acquisition_strategy_agent/README.md`
2. `agents/acquisition_strategy_agent/buyer_side/source_mapping.md`
3. `agents/acquisition_strategy_agent/buyer_side/prompt.md`
4. `agents/acquisition_strategy_agent/buyer_side/workflow.json`
5. `agents/acquisition_strategy_agent/buyer_side/output_contract.json`
6. `agents/acquisition_strategy_agent/buyer_side/report_writer_policy.json`

## Implementation Roadmap

The minimum executable analysis/report runner is complete. It currently implements:

1. certified-input validation;
2. structured 15-section buyer analysis;
3. deterministic recommendation gates;
4. business-facing report rendering;
5. internal audit-marker leakage rejection;
6. report manifest, research gap, and human-review output;
7. cross-case synthetic tests and input-failure tests.

The next engineering steps are:

1. implement mandate parsing and research-plan execution;
2. add source retrieval and evidence repository adapters;
3. implement the claim-evidence graph and Policy π certification runtime;
4. add a constrained analyst-model adapter that returns schema-valid section analysis rather than free-form Markdown;
5. add thesis certification and input-perturbation tests;
6. add a new user-approved V2 case only after the runtime contracts are accepted.

## Run The Executable Stage

From the repository root:

```bash
python3 v2_loop_engineered_deep_research_agent/runtime/run_agent.py \
  --case-dir /path/to/certified_case \
  --output-dir /path/to/output \
  --json
```

See `agents/acquisition_strategy_agent/buyer_side/runbook.md` for the input contract and test command.

## Verify The Baseline

Run this after any V2 agent cleanup or optimization:

```bash
python3 v2_loop_engineered_deep_research_agent/tools/verify_v2_agent_baseline.py
```

The guard confirms that the key buyer-side prompt, workflow, output contract, loop/certification policies, schemas, runtime boundary, and source mapping are still present and internally consistent.

## Design Boundary

This V2 package should not be treated as investment advice, legal advice, valuation advice, or transaction recommendation. It is an academic and prototype architecture for evidence-grounded, human-reviewable transaction research.

For real transaction use, final outputs must be reviewed by qualified professionals, especially where the result depends on valuation judgment, legal interpretation, accounting treatment, regulatory risk, financing terms, or non-public information.
