# Buyer-Side Acquisition Strategy Agent

A source-bounded Deep Research Agent for buyer-side acquisition strategy analysis.

The Agent coordinates external research, evidence normalization, claim-to-evidence mapping, certification, repair routing, buyer-side analysis, report gating, audit packaging, and final report generation.

It is part of the broader **Loop-Engineered Deep Research Agent** framework.

---

## Overview

Buyer-side acquisition research requires more than generating a narrative report. It also requires:

- identifiable and reviewable sources;
- traceable claims and evidence;
- controlled use of historical and post-decision information;
- reproducible financial calculations;
- explicit treatment of missing or conflicting evidence;
- clear human-review boundaries;
- auditable report generation.

This Agent therefore separates research, verification, analysis, and delivery.

```text
External Research
        ↓
Evidence Processing
        ↓
Claim Certification
        ↓
Repair and Human Review
        ↓
Buyer-Side Analysis
        ↓
Report Gate
        ↓
Final Report and Audit Package
```

External tools may perform research, but they do not directly control the final report. Retrieved information must pass through the Agent's evidence and certification pipeline before it can be used downstream.

---

## Key Capabilities

- Structured acquisition mandate intake
- Case seed and research-plan generation
- External Deep Research handoff
- Retrieved-source normalization
- Raw evidence extraction
- Evidence repository construction
- Claim-to-evidence graph construction
- Citation and temporal verification
- Numeric verification
- Claim-level certification and caveats
- Research-gap detection
- Targeted repair loops
- Human-review routing
- Evidence-bounded buyer-side analysis
- Gate-controlled report generation
- Machine-readable audit packaging

---

## Workflow

The runtime follows an M1-M8 workflow:

```text
M1   Mandate Intake and Research Planning
 ↓
M2   External Research and Source Retrieval
 ↓
M3   Evidence Repository Construction
 ↓
M4   Claim-Evidence Graph Construction
 ↓
M5   Certification and Research-Gap Detection
 ↓
M6   Buyer-Side Acquisition Analysis
 ↓
M7   Report Rendering Gate
 ↓
M8 Final Report Rendering
```

The main artifact chain is:

```text
mandate.json
→ research_plan.json
→ case_seed.json
→ research_request.json
→ retrieved_sources_manifest.json
→ raw_evidence.json
→ evidence_repository.json
→ claim_evidence_graph.json
→ certification_result.json
→ research_gaps.json
→ repair_plan.json
→ analysis_package.json
→ report_manifest.json
→ audit_package.json
→ final_report.md
```

`final_report.md` is generated only when the applicable report gate allows it.

---

## Quick Start

Use the unified entrypoint for normal case execution:

```text
runtime/run_agent.py
```

Users should not manually run each M1-M7.1 stage for a standard case.

### 1. Start a Case

```bash
python loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/runtime/run_agent.py start \
  --case loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/examples/synthetic_acquisition_mandate.json \
  --output-dir outputs/runs/synthetic_buyer_acquisition
```

The Agent creates the initial planning artifacts and normally stops with:

```text
status: awaiting_external_research
```

The run directory will contain a structured research request for the external research executor.

### 2. Complete External Research

OpenClaw, another Deep Research system, or a human-assisted research process reads:

```text
research_request.json
```

The external executor performs source-bounded research and saves a structured response:

```text
deep_research_response.json
```

External research should provide identifiable sources, evidence items, candidate claims, claim-evidence links, source gaps, and relevant limitations.

### 3. Resume the Agent

```bash
python loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/runtime/run_agent.py resume \
  --run-dir outputs/runs/synthetic_buyer_acquisition \
  --research-response <deep_research_response.json>
```

The Agent then resumes evidence processing, certification, repair routing, analysis, and report generation.

---

## Case Input

The preferred real-world input is a case package containing both a mandate and a case seed:

```json
{
  "mandate": {
    "case_id": "example_case",
    "business_question": "Evaluate the proposed acquisition from the buyer's perspective.",
    "decision_context": "Preliminary buyer-side acquisition review",
    "research_scope": [],
    "output_requirements": []
  },
  "case_seed": {
    "case_id": "example_case",
    "case_parties": [],
    "transaction_leads": [],
    "key_assets_or_topics": [],
    "known_dates": [],
    "known_amounts": [],
    "source_leads": [],
    "uncertainty_warnings": []
  }
}
```

The two parts have different roles:

- `mandate` defines the business question, scope, decision context, and output requirements.
- `case_seed` provides initial case leads and research directions.

A case seed is not evidence. Its contents must be verified against original or authoritative sources before downstream use.

Example inputs are available under:

```text
examples/
case_seeds/
```

---

## External Research Boundary

The Agent is provider-agnostic. It can ingest structured research produced by:

- OpenClaw;
- GPT-based Deep Research systems;
- human-assisted research;
- other external retrieval or research tools.

The Agent does not treat an external narrative answer as automatically verified evidence.

External outputs must preserve:

- source identity;
- source location;
- source date or period;
- source type and quality;
- evidence text or precise summary;
- candidate claim relationships;
- timing relative to the transaction decision date;
- uncertainties and source gaps.

The external research package is normalized before it enters the evidence repository.

---

## Evidence and Certification Principles

The Agent follows several core rules.

### Source-Bounded Analysis

Claims used in analysis must be traceable to identifiable evidence records.

### Case Seeds Are Not Evidence

Mandates, source leads, case briefs, and user-provided summaries may guide research but cannot directly support certified claims.

### Claim-Level Certification

Claims are evaluated individually rather than treated as equally reliable.

Typical statuses include:

```text
certified
certified_with_caveat
requires_numeric_verification
blocked_by_source_gap
failed
```

### Caveat Preservation

A claim certified with a caveat must preserve that caveat in downstream analysis and reporting.

### Temporal Control

Post-decision or retrospective evidence may support hindsight analysis or outcome tracking, but it must not silently be presented as information available to the buyer at the original decision date.

### Numeric Control

Financial conclusions must use explicit, reproducible inputs. Arithmetic verification does not by itself prove that the underlying business definitions or source scope are correct.

### Missing Evidence

Unsupported or unresolved claims are excluded from factual conclusions and routed to:

- research gaps;
- diligence priorities;
- risk disclosures;
- human-review items;
- blocked-claim audit records.

---

## Runtime Statuses

The unified entrypoint returns one of the following statuses:

| Status | Meaning |
|---|---|
| `awaiting_external_research` | Additional external research input is required |
| `report_generated` | The final report was generated |
| `blocked_by_missing_evidence` | Material evidence gaps remain unresolved |
| `human_review_required` | Human judgment is required before delivery |
| `failed` | The runtime stopped because of a validation or execution failure |

Each run also writes:

```text
run_state.json
```

The run state records:

- case ID;
- current status;
- current stage;
- completed stages;
- repair iteration;
- maximum repair iterations;
- next action;
- last error.

---

## Repair Loop

When M5 identifies material source, citation, temporal, or numeric gaps, the Agent may create:

```text
research_gaps.json
repair_plan.json
repair_request.json
targeted_source_discovery_plan.json
repair_attempt_log.json
```

The external research executor can then perform targeted repair research and return an updated structured response.

The repair loop is capped to prevent unlimited research cycles. Unresolved material gaps may lead to:

```text
blocked_by_missing_evidence
```

or:

```text
human_review_required
```

---

## Main Outputs

A complete run may produce the following artifacts:

| Artifact | Purpose |
|---|---|
| `research_plan.json` | Defines the initial research plan |
| `research_request.json` | Instructs the external research executor |
| `retrieved_sources_manifest.json` | Registers retrieved sources |
| `raw_evidence.json` | Stores extracted source-bounded evidence |
| `evidence_repository.json` | Normalizes and organizes evidence |
| `claim_evidence_graph.json` | Maps claims to supporting or conflicting evidence |
| `certification_result.json` | Records claim-level certification results |
| `research_gaps.json` | Lists unresolved evidence gaps |
| `repair_plan.json` | Defines targeted repair actions |
| `analysis_package.json` | Stores structured buyer-side analysis |
| `report_manifest.json` | Controls report eligibility and rendering |
| `audit_package.json` | Preserves report, claim, evidence, source, and caveat traceability |
| `final_report.md` | Human-readable buyer-side acquisition report |
| `run_state.json` | Records runtime state and next action |

Run artifacts should be written under:

```text
outputs/runs/<case_id>/
```

Generated run outputs are ignored by Git except for the empty directory placeholder.

---

## Buyer-Side Analysis

M6 produces a structured buyer-side acquisition analysis package covering areas such as:

- transaction logic;
- buyer strategic objectives;
- target business or asset quality;
- industry and competitive position;
- strategic fit;
- standalone financial analysis;
- valuation and acceptable price;
- synergy and value creation;
- deal structure;
- financing and capital structure;
- return analysis;
- due diligence priorities;
- regulatory, integration, and downside risks;
- recommendation readiness.

A section may be marked limited or not assessable when the required evidence is unavailable.

The Agent does not fabricate missing valuation inputs, strategic motives, transaction terms, or financial outcomes.

---

## Report and Audit Layer

The delivery layer separates the human-readable report from the machine-readable trace.

### `final_report.md`

The professional report intended for human readers.

It is generated only when the report gate permits rendering.

### `audit_package.json`

The trace package used to inspect:

- report-section mappings;
- supporting claims;
- supporting evidence records;
- source IDs;
- caveats;
- excluded claims;
- human-review items;
- gate status.

The audit package supports reviewability without forcing detailed technical trace information into the main report.

---

## Project Structure

```text
buyer_side_acquisition_strategy_agent/
├── runtime/                     # Runtime modules and stage runners
├── schemas/                     # JSON schemas
├── config/                      # Analysis and report configuration
├── examples/                    # Example mandates
├── case_seeds/                  # Example case leads
├── external_research_packages/  # External research templates
├── retrieved_sources/           # Synthetic source fixtures
├── tests/                       # Runtime and contract tests
├── state_machine.json           # Workflow state definition
└── README.md
```

The preferred unified entrypoint is:

```text
runtime/run_agent.py
```

Individual stage runners remain available for testing and debugging:

```text
run_m1.py
run_m2.py
run_m2_deep_research.py
run_m3.py
run_m4.py
run_m5.py
run_m5_1.py
run_m6.py
run_m7.py
run_m7_render.py
run_step6a_audit_package.py
```

---

## Testing

Run the complete test suite from the repository root:

```bash
python -m pytest \
  loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/tests \
  -q
```

The tests cover:

- mandate validation;
- research planning;
- external research package ingestion;
- source and evidence processing;
- claim-evidence graph construction;
- citation and temporal checks;
- numeric verification;
- certification and repair routing;
- buyer-side analysis packaging;
- report gating;
- audit packaging;
- final report rendering;
- complete synthetic Agent runs.

---

## Current Limitations

This project is a research prototype rather than a production transaction system.

Current limitations include:

- external research execution is not built into the runtime;
- some provider integrations remain unconfigured or fail-closed;
- generic claim mapping still requires further generalization;
- numeric verification requires stronger formula-driven methods;
- external research packages are validated but not every source is independently re-fetched;
- report and recommendation quality depends on evidence coverage;
- human review remains necessary for material acquisition judgments;
- the runtime is not a substitute for professional financial, legal, tax, technical, or commercial due diligence.

The Agent should be evaluated as an auditable research workflow rather than as an autonomous investment decision-maker.

---

## Design Principle

The central design principle is:

> Generation does not equal permission.

External research may propose claims. The Agent decides which claims can be used, which require caveats, which require repair, and which must remain excluded.

The objective is not to eliminate uncertainty. It is to make uncertainty, evidence quality, and decision boundaries visible and reviewable.

---

## Disclaimer

This project is intended for academic research, prototyping, and educational use.

It does not constitute investment advice, legal advice, financial advice, tax advice, or a transaction recommendation. Any real-world acquisition decision should be reviewed by qualified professionals.
