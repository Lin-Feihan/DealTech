# External Research Packages

This directory is the handoff point for structured Deep Research packages produced outside V3-Lite.

V3-Lite is provider-agnostic. It does not run a search engine in this mode, does not call the OpenAI API, and does not require `OPENAI_API_KEY`. OpenAI Deep Research API support remains a future-ready provider scaffold, but current case runs can use OpenClaw / GPT-5.5 or human-assisted research as the external Deep Research executor.

## Package Layout

Save each external research response under a case-specific directory:

```text
v3_lite_buyer_acquisition_runtime/external_research_packages/<case_id>/deep_research_response.json
```

The JSON file must follow `../schemas/deep_research_response.schema.json` and include:

- `case_id`: must match the mandate, research plan, case seed, and source discovery plan.
- `provider`, `model`, `response_id`, `completed_at`: provenance for the external executor.
- `sources[]`: original cited sources only. Do not list case seeds, mandate notes, Bohan PDF notes, model memory, or provider narrative summaries as authoritative evidence sources.
- `evidence_items[]`: source-bounded evidence only. Every item must reference a known `provider_source_id` from `sources[]`.
- `unresolved_gaps[]`: source needs the external executor could not resolve.
- `provider_notes[]`: non-evidentiary notes about method, scope, or limitations.

## Ingestion Contract

V3-Lite replay mode validates `deep_research_response.json`, rejects source-less evidence, rejects case seed / mandate notes / Bohan PDF / model-memory material as evidence, then writes only:

```text
retrieved_sources_manifest.json
raw_evidence.json
```

It preserves source tier, source timing classification, permitted use, and unresolved gaps as `failed_source_needs`. It does not generate `evidence_repository.json`, `claim_evidence_graph.json`, `certification_result.json`, `analysis_package.json`, `final_report.md`, or `recommendation_decision.json`.

## Ingest Command

```bash
python3 v3_lite_buyer_acquisition_runtime/runtime/run_v3_lite_m2_deep_research.py \
  --mandate <mandate.json> \
  --research-plan <research_plan.json> \
  --case-seed <case_seed.json> \
  --source-discovery-plan <source_discovery_plan.json> \
  --output-dir <output_dir> \
  --mode replay_deep_research_response \
  --replay-response v3_lite_buyer_acquisition_runtime/external_research_packages/<case_id>/deep_research_response.json
```

