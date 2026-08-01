# Buyer-Side Acquisition Strategy Agent

This directory contains the Buyer-Side Acquisition Strategy Agent.

The Agent implements a source-bounded M1-M7.1 closed-loop runtime for buyer-side acquisition strategy research. It is gate-controlled and provider-agnostic: external tools may retrieve or research sources, but the Agent controls normalization, evidence repository construction, claim-evidence certification, repair planning, buyer-side analysis, report gating, audit packaging, and final report rendering.

Current external Deep Research direction:

- OpenClaw / GPT-5.5 or human-assisted research can act as an external Deep Research executor by saving a structured `deep_research_response.json` package.
- OpenAI Deep Research API support remains future-ready, but it is not required for current runs and is fail-closed unless explicitly configured.
- The runtime is not production-ready and still has known limitations, including prototype-specific planning, claim mapping, numeric verification, and analysis behavior that must be generalized later.

Current artifact chain:

```text
mandate.json
-> research_plan.json
-> case_seed.json
-> source_discovery_plan.json
-> retrieved_sources_manifest.json
-> raw_evidence.json
-> evidence_repository.json
-> claim_evidence_graph.json
-> certification_result.json
-> research_gaps.json
-> repair_plan.json
-> targeted_source_discovery_plan.json / repair_attempt_log.json when repair is needed
-> analysis_package.json
-> report_manifest.json
-> final_report.md only if gate allows
```

## Unified Agent Entrypoint

Use `runtime/run_agent.py` for normal case execution. Users should not manually run M1-M7.1 for a standard Agent run.

Start a case:

```bash
python loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/runtime/run_agent.py start \
  --case loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/examples/synthetic_acquisition_mandate.json \
  --output-dir outputs/runs/synthetic_buyer_acquisition_m1
```

The Agent writes `research_request.json` and stops with:

```text
status: awaiting_external_research
```

OpenClaw, GPT-5.5, or a human external research executor then reads `research_request.json`, performs source-bounded research outside the runtime, and saves a structured `deep_research_response.json`. The Agent does not remotely control OpenClaw.

Resume after external research:

```bash
python loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/runtime/run_agent.py resume \
  --run-dir outputs/runs/synthetic_buyer_acquisition_m1 \
  --research-response <deep_research_response.json>
```

The unified entrypoint returns exactly one of these statuses:

```text
awaiting_external_research
report_generated
blocked_by_missing_evidence
human_review_required
failed
```

Each run writes `outputs/runs/<case_id>/run_state.json`. `run_state.json` records `case_id`, `status`, `current_stage`, `completed_stages`, `iteration`, `max_repair_iterations`, `next_action`, and `last_error`. If M5 finds evidence or numeric gaps, the Agent writes `repair_request.json`, returns `awaiting_external_research`, and on resume reruns the necessary M2/M3/M4/M5 path. The repair loop is capped at two iterations; unresolved gaps after that return `blocked_by_missing_evidence`.

Run artifacts belong under `outputs/runs/<case_id>/` and are intentionally ignored by git except `outputs/runs/.gitkeep`.

## Current Scope

Implemented scope:

- mandate intake
- fail-closed mandate validation
- deterministic research-plan generation
- case seed loading and source discovery planning
- manual retrieved-source ingestion
- external Deep Research package ingestion
- raw evidence extraction
- evidence repository construction
- claim evidence graph construction
- loop certification and repair planning
- evidence-bounded deal analysis package generation
- report rendering gate
- gate-controlled report rendering when allowed
- unit tests for M1-M7.1 runtime behavior

Current exclusions and fail-closed boundaries:

- no built-in search engine
- no configured live OpenAI Deep Research API run required
- no custom SEC EDGAR, patent, or clinical-trials providers implemented
- no fake source repair
- no production-ready professional M&A recommendation engine
- no legacy runtime changes

## Run

The unified Agent entrypoint above is the preferred way to run a case. The older milestone runners remain available for debugging individual stages.

```bash
python3 loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/runtime/run_m1.py \
  --mandate loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/examples/minimal_mandate.json \
  --output-dir loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/outputs/demo_run
```

Expected outputs:

```text
loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/outputs/demo_run/
├── mandate.json
└── research_plan.json
```

Later M2-M7.1 stages have dedicated runners under `runtime/`. They remain artifact-gated; running M1 does not run a new case through the full loop.

## Test

```bash
python3 -m unittest discover -s loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/tests
```

## M2 Source Retrieval Boundary

Buyer-Side Acquisition Strategy Agent is a provider-agnostic M&A Deep Research orchestration runtime. It is not itself a search engine, SEC EDGAR client, patent client, clinical-trials client, GPT-like Deep Research system, or live web-search product.

M2 has one authoritative bridge into raw evidence:

```text
case_seed + research_plan -> source_discovery_plan.json -> retrieved_sources_manifest.json -> raw_evidence.json
```

`retrieved_sources_manifest.json` is the only bridge between external retrieval tools and `raw_evidence.json`. `case_seed`, mandate notes, source leads, and local case briefs may guide source discovery, but they are not evidence and must not be extracted directly into raw evidence.

Current provider status:

- `manual_retrieved_sources_provider`: implemented. This is the only reliable current provider. It requires an explicit `--retrieved-sources-manifest` whose sources point to locally retrieved authoritative files.
- `authoritative_url_retrieval_provider`: implemented only for explicit authoritative URLs when URL fetching succeeds. It does not search, infer URLs, or hardcode sources.
- `web_search_provider`: fail-closed stub.
- `sec_edgar_provider`: fail-closed stub.
- `patent_provider`: fail-closed stub.
- `clinical_trials_provider`: fail-closed stub.
- `deep_research_provider`: implemented for structured external Deep Research package ingestion through `replay_deep_research_response`. It does not call a search engine or require `OPENAI_API_KEY`. The OpenAI Deep Research API path remains a future-ready provider scaffold and still fails closed when API key, model configuration, or structured provider output is unavailable.

Every unavailable provider fails closed with:

```text
Provider not configured; no retrieval performed; case_seed cannot be used as evidence.
```

GPT, Claude, Deep Research, search APIs, SEC EDGAR APIs, patent APIs, and clinical-trials APIs are external providers. Their outputs can generate source leads or retrieved source manifests, but `raw_evidence.json` must be extracted from original sources listed in `retrieved_sources_manifest.json`, not from a provider's narrative answer.

### Deep Research Provider

Buyer-Side Acquisition Strategy Agent does not implement its own Deep Research engine. For current runs, OpenClaw / GPT-5.5 or human-assisted research can act as the external Deep Research executor and save a structured `deep_research_response.json` package. Buyer-Side Acquisition Strategy Agent then ingests that package in replay mode.

Deep Research performs multi-source discovery and evidence collection outside the runtime. It does not produce the final acquisition report. The expected output is a structured research package with `sources`, `evidence_items`, `candidate_claims`, `claim_evidence_links`, `source_gaps`, and uncertainties or limitations when applicable. Buyer-Side Acquisition Strategy Agent then validates and normalizes the structured external output into `retrieved_sources_manifest.json` and `raw_evidence.json` with preserved source provenance, source tier, timing labels, permitted use, candidate claims, claim-evidence links, source gaps, and fail-closed rejection of source-less or non-authoritative provider claims.

Downstream M3-M7.1 are unchanged: repository building, claim graph construction, verification, repair loop, evidence-bounded analysis, report gating, and gate-controlled rendering still happen inside Buyer-Side Acquisition Strategy Agent after normalized M2 artifacts exist.

OpenAI Deep Research API support is future-ready but not required for current runs. External package replay does not call OpenAI, does not require OpenAI billing, and does not require `OPENAI_API_KEY`.

External research packages should be saved as:

```text
loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/external_research_packages/<case_id>/deep_research_response.json
```

Ingestion command:

```bash
python3 loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/runtime/run_m2_deep_research.py \
  --mandate <mandate.json> \
  --research-plan <research_plan.json> \
  --case-seed <case_seed.json> \
  --source-discovery-plan <source_discovery_plan.json> \
  --output-dir <output_dir> \
  --mode replay_deep_research_response \
  --replay-response <external_deep_research_response.json>
```

Replay mode writes only `retrieved_sources_manifest.json` and `raw_evidence.json`. It preserves external `candidate_claims` and `claim_evidence_links` for downstream ingestion, but candidate claims are not certified claims. It does not generate `final_report.md`, `recommendation_decision.json`, or any M3-M7 downstream artifacts, and it does not bypass the M3-M7 gate logic.

Fixture-backed extraction exists only under `tests/fixtures/` for contract tests. Fixture output is not certified evidence, analysis, or a final report.

### M2.1 Temporal Source Classification

M2 labels source timing; it does not decide sufficiency or certify claims. Each `retrieved_sources[]` entry carries `source_date_or_period`, `source_time_relation_to_decision_date`, and `permitted_use`. Each raw evidence item inherits `evidence_time_relation_to_decision_date` and `permitted_use` from its source and adds `hindsight_leakage_warning`.

Post-decision or retrospective evidence may support retrospective outcome validation, outcome tracking, source leads, or gap tracking. It must not be silently treated as ex-ante buyer decision evidence. Missing source needs remain `failed_source_needs`; they are not evidence.

## M3 Evidence Repository Boundary

M3 transforms:

```text
raw_evidence.json -> evidence_repository.json
```

M3 remains source-bounded. It normalizes, deduplicates, classifies, and gap-tracks evidence for later claim-graph construction, but it does not generate `claim_evidence_graph.json`, `certification_result.json`, or `final_report.md`.

M3 responsibilities:

- validate `raw_evidence.json` fail-closed
- group duplicate raw evidence into canonical evidence records
- preserve candidate claims and claim-evidence links from structured Deep Research packages as `candidate_claims_from_research` and `candidate_claim_evidence_links_from_research`
- preserve temporal controls and hindsight warnings
- convert `failed_source_needs` into `source_gaps`
- summarize repository quality for the next stage

M3 does not make recommendations, perform valuation, infer unsupported headline values, or repair missing sources on its own.

## M4 Claim Evidence Graph Boundary

M4 transforms:

```text
evidence_repository.json -> claim_evidence_graph.json
```

M4 builds candidate claim nodes, evidence edges, and gap nodes for future certification. When `candidate_claims_from_research` is present, M4 uses those real candidate `claim_statement` values and maps them to evidence records through `candidate_claim_evidence_links_from_research`. When no candidate claims are present, M4 keeps the older evidence-record-to-generic-claim fallback for backward compatibility and labels those statements as generic fallback claims. It does not certify claims, make Proceed / Walk Away recommendations, perform valuation analysis, or generate `certification_result.json` or `final_report.md`.

M4 responsibilities:

- validate `evidence_repository.json` fail-closed
- normalize structured Deep Research candidate claims into Claim-Evidence Graph `claim_nodes`
- preserve `created_from_candidate_claim_id` and the real candidate `claim_statement`
- map supporting, partial, contextualizing, contradictory, and requires-verification evidence links into `evidence_edges`
- keep all candidate claims uncertified with `pending_verification`, `failed_precheck`, or `not_applicable` status
- convert M3 source gaps into graph gap nodes and gap-only claims
- preserve temporal scope, permitted use, and hindsight warnings
- mark derived numeric candidates as requiring later numeric verification

Derived numeric candidates are not source-supported deal values until a later verification stage confirms arithmetic, definitions, and source scope.

## M5 Loop Certification Boundary

M5 transforms:

```text
claim_evidence_graph.json + evidence_repository.json -> certification_result.json -> research_gaps.json -> repair_plan.json
```

M5 verifies candidate claims, classifies certification outcomes, detects research gaps, and produces targeted loop repair instructions. M5 decides certification, caveats, repair routing, human review, and report eligibility. It does not create `final_report.md`, `analysis_package.json`, valuation analysis, investment recommendations, ATL adapters, or report logic changes.

M5 responsibilities:

- validate claim graph and evidence repository inputs fail-closed
- verify citations, temporal scope, and derived numeric candidates
- certify only narrow evidence-backed claims where allowed
- caveat post-decision and retrospective claims so they cannot become ex-ante buyer decision support
- keep gap-only and unsupported claims uncertified
- emit research gaps and repair targets for source retrieval or later verification loops

M5 numeric verification confirms arithmetic only. For example, a base consideration amount plus a contingent consideration cap can be recorded as a derived relationship, but it is not a direct source quote or final deal-value conclusion unless later source repair supplies direct authoritative support or wording preserves the caveat.

## M6 Analysis Package Boundary

M6 now produces a professional buyer-side acquisition analysis package with 14 business sections derived into a Buyer-Side Acquisition Strategy Agent-owned buyer-side acquisition framework. Tables are treated as optional analytical exhibits and are not forced when supporting data is missing.

## Professional Report Delivery Layer

The professional report delivery layer separates the clean human-facing report from the machine-readable trace package.

- `final_report.md` is the future clean professional buyer-side acquisition report for human readers.
- `audit_package.json` is the machine-readable trace package for report-section mapping, claims, evidence records, source IDs, caveats, exclusions, human review, and gate status.
- Step 6A defines the report delivery contract and builds `audit_package.json` only.
- Step 6A does not rewrite `report_renderer.py`, does not generate `final_report.md`, and does not generate `recommendation_decision.json`.
- Step 6B will later upgrade `report_renderer.py` into a clean professional assembler that consumes the report contract and audit trace.

## Known Limitations / Next Fixes

1. Remove prototype-specific hard-code from runtime.
2. Generalize canonical facts and claim mapping.
3. Make numeric verifier formula-driven.
4. Strengthen citation verifier from provenance check to semantic claim-evidence alignment.
5. Expand buyer-side M&A analysis package beyond evidence summary.
6. Upgrade report renderer to professional gate-controlled report writer.

Additional current limitations:

- The runtime is a prototype, not production-ready.
- OpenAI Deep Research live API mode is future-ready but not configured for current runs.
- Generic M&A case generalization is not solved.
- External Deep Research ingestion validates structured packages but does not independently re-fetch and verify every source quote.

## Future Notes

ATL adapter support is future work. Buyer-Side Acquisition Strategy Agent does not create `atl_manifest`, `agent_card`, `runner_api`, or related platform-wrapper files.

Validate-Trace-Enforce remains the certification design direction, but the current implementation is still a lightweight prototype and must not be treated as production-grade verification.
