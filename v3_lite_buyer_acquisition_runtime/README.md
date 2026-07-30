# V3-Lite Buyer Acquisition Runtime

This directory is the V3-Lite runtime for the buyer-side Acquisition Strategy Agent.

Milestone 1 only implements:

```text
mandate.json -> research_plan.json
```

It is a deterministic planning runtime. It accepts a structured buyer-side acquisition mandate, validates it, stores the accepted mandate, and emits a structured research plan.

## Current Scope

Included in Milestone 1:

- mandate intake
- fail-closed mandate validation
- deterministic research-plan generation
- local artifact writing for `mandate.json` and `research_plan.json`
- tests for valid and invalid mandate handling

Excluded from Milestone 1:

- web search
- evidence collection
- evidence repository construction
- claim graph construction
- certification
- report generation
- V2 runtime changes

## Run

```bash
python3 v3_lite_buyer_acquisition_runtime/runtime/run_v3_lite.py \
  --mandate v3_lite_buyer_acquisition_runtime/examples/minimal_mandate.json \
  --output-dir v3_lite_buyer_acquisition_runtime/outputs/demo_run
```

Expected outputs:

```text
v3_lite_buyer_acquisition_runtime/outputs/demo_run/
├── mandate.json
└── research_plan.json
```

## Test

```bash
python3 -m unittest v3_lite_buyer_acquisition_runtime.tests.test_mandate_to_research_plan
```

## M2 Source Retrieval Boundary

V3-Lite is a provider-agnostic M&A Deep Research orchestration runtime. It is not itself a search engine, SEC EDGAR client, patent client, clinical-trials client, GPT-like Deep Research system, or live web-search product.

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

V3-Lite does not implement its own Deep Research engine. For current runs, OpenClaw / GPT-5.5 or human-assisted research can act as the external Deep Research executor and save a structured `deep_research_response.json` package. V3-Lite then ingests that package in replay mode.

Deep Research performs multi-source discovery and evidence collection outside the runtime. V3-Lite then validates and normalizes the structured external output into `retrieved_sources_manifest.json` and `raw_evidence.json` with preserved source provenance, source tier, timing labels, permitted use, and fail-closed rejection of source-less or non-authoritative provider claims.

Downstream M3-M7.1 are unchanged: repository building, claim graph construction, verification, repair loop, evidence-bounded analysis, report gating, and gate-controlled rendering still happen inside V3-Lite after normalized M2 artifacts exist.

OpenAI Deep Research API support is future-ready but not required for current runs. External package replay does not call OpenAI, does not require OpenAI billing, and does not require `OPENAI_API_KEY`.

External research packages should be saved as:

```text
v3_lite_buyer_acquisition_runtime/external_research_packages/<case_id>/deep_research_response.json
```

Ingestion command:

```bash
python3 v3_lite_buyer_acquisition_runtime/runtime/run_v3_lite_m2_deep_research.py \
  --mandate <mandate.json> \
  --research-plan <research_plan.json> \
  --case-seed <case_seed.json> \
  --source-discovery-plan <source_discovery_plan.json> \
  --output-dir <output_dir> \
  --mode replay_deep_research_response \
  --replay-response <external_deep_research_response.json>
```

Replay mode writes only `retrieved_sources_manifest.json` and `raw_evidence.json`. It does not generate `final_report.md`, `recommendation_decision.json`, or any M3-M7 downstream artifacts, and it does not bypass the M3-M7 gate logic.

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
- preserve temporal controls and hindsight warnings
- convert `failed_source_needs` into `source_gaps`
- summarize repository quality for the next stage

M3 does not make recommendations, perform valuation, infer unsupported headline values, or repair missing sources on its own.

## M4 Claim Evidence Graph Boundary

M4 transforms:

```text
evidence_repository.json -> claim_evidence_graph.json
```

M4 builds candidate claim nodes, evidence edges, and gap nodes for future certification. It does not certify claims, make Proceed / Walk Away recommendations, perform valuation analysis, or generate `certification_result.json` or `final_report.md`.

M4 responsibilities:

- validate `evidence_repository.json` fail-closed
- map evidence records to uncertified or pending-verification candidate claims
- convert M3 source gaps into graph gap nodes and gap-only claims
- preserve temporal scope, permitted use, and hindsight warnings
- mark derived numeric candidates as requiring later numeric verification

Derived numeric candidates are not source-supported deal values until a later verification stage confirms arithmetic, definitions, and source scope.

## M5 Loop Certification Boundary

M5 transforms:

```text
claim_evidence_graph.json + evidence_repository.json -> certification_result.json -> research_gaps.json -> repair_plan.json
```

M5 verifies candidate claims, classifies certification outcomes, detects research gaps, and produces targeted loop repair instructions. It does not create `final_report.md`, `analysis_package.json`, valuation analysis, investment recommendations, ATL adapters, or report logic changes.

M5 responsibilities:

- validate claim graph and evidence repository inputs fail-closed
- verify citations, temporal scope, and derived numeric candidates
- certify only narrow evidence-backed claims where allowed
- caveat post-decision and retrospective claims so they cannot become ex-ante buyer decision support
- keep gap-only and unsupported claims uncertified
- emit research gaps and repair targets for source retrieval or later verification loops

M5 numeric verification confirms arithmetic only. For example, `$60M + $120M = $180M` can be recorded as a derived relationship, but it is not a direct source quote or final deal-value conclusion unless later source repair supplies direct authoritative support or wording preserves the caveat.

## Future Notes

ATL adapter support is future work. Milestone 1 does not create `atl_manifest`, `agent_card`, `runner_api`, or related platform-wrapper files.

Validate-Trace-Enforce is a future internal mechanism for Loop Certification. Loop Certification remains a future state-machine state and is not implemented in Milestone 1.
