# External Research Packages

This directory is the handoff point for structured Deep Research packages produced outside Buyer-Side Acquisition Strategy Agent.

Buyer-Side Acquisition Strategy Agent is provider-agnostic. It does not run a search engine in replay mode, does not call the OpenAI API, and does not require `OPENAI_API_KEY`. OpenAI Deep Research API support remains a future-ready provider scaffold, but current case runs can use OpenClaw / GPT-5.5 or human-assisted research as the external Deep Research executor.

## Package Layout

Save each external research response under a case-specific directory:

```text
loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/external_research_packages/<case_id>/deep_research_response.json
```

The JSON file must follow `../schemas/deep_research_response.schema.json`.

## Required Sections

Deep Research output is not a final report. It must be a structured research package for downstream runtime stages.

Required top-level sections:

- `case_id`: must match the mandate, research plan, case seed, and source discovery plan.
- `provider`, `model`, `response_id`, `completed_at`: provenance for the external executor.
- `sources[]`: original cited sources only. Do not list case seeds, mandate notes, user narrative notes, model memory, or provider narrative summaries as authoritative evidence sources.
- `evidence_items[]`: source-bounded evidence only. Every item must reference a known `provider_source_id` from `sources[]`.
- `candidate_claims[]`: candidate claim statements derived from evidence or explicit source gaps. These are not certified claims.
- `claim_evidence_links[]`: typed links from `candidate_claim_id` to `evidence_item_id`, using `supports`, `partially_supports`, `contextualizes`, `contradicts`, or `requires_verification`.
- `source_gaps[]`: source needs the external executor could not resolve.
- `uncertainties_or_limitations[]`: optional but expected when caveats, timing limits, or source limitations matter.
- `provider_notes[]`: non-evidentiary notes about method, scope, or limitations.

Candidate claims are never report-ready on ingestion. M5 verifier decides certification, caveats, repair routing, human review, and report eligibility. M4 only normalizes the candidate claims into a Claim-Evidence Graph.

## Ingestion Contract

Buyer-Side Acquisition Strategy Agent replay mode validates `deep_research_response.json`, rejects source-less evidence, rejects case seed / mandate notes / user narrative notes / model-memory material as evidence, then writes only:

```text
retrieved_sources_manifest.json
raw_evidence.json
```

It preserves source tier, source timing classification, permitted use, candidate claims, claim-evidence links, and source gaps. Source gaps become `failed_source_needs` for M2 repair routing, and candidate claims plus links are preserved into raw evidence for M3 to carry forward as `candidate_claims_from_research` and `candidate_claim_evidence_links_from_research`.

Replay mode does not generate `evidence_repository.json`, `claim_evidence_graph.json`, `certification_result.json`, `analysis_package.json`, `final_report.md`, or `recommendation_decision.json`.

## Ingest Command

```bash
python3 loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/runtime/run_m2_deep_research.py \
  --mandate <mandate.json> \
  --research-plan <research_plan.json> \
  --case-seed <case_seed.json> \
  --source-discovery-plan <source_discovery_plan.json> \
  --output-dir <output_dir> \
  --mode replay_deep_research_response \
  --replay-response loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/external_research_packages/<case_id>/deep_research_response.json
```
