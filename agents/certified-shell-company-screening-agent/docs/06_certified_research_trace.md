# Certified Research Trace

Certified Research Trace is the audit object that connects mandate, configs, inputs, trace tables, claim ledger, PCE status, and delivery outputs.

## Current Demo Trace Boundary

The Tuntun HK demo does **not** claim that every historical trace table is regenerated from live sources on each run. The current workflow is:

```text
case_config.yaml
→ scripts/run_tuntun_hk_demo.py
→ pipeline.py
→ trace validation / supported calculation replay
→ claim_to_evidence_map refresh
→ PCE cross-check
→ final_delivery_gate
→ delivery outputs
→ run_records/<run_id>/
```

Each run writes `examples/tuntun_hk/run_records/<run_id>/trace_manifest.json` with these provenance labels:

- `pipeline_generated`
- `pipeline_validated`
- `imported_from_original_bundle`
- `not_reproducible_currently`
- `needs_human_review`

## Current Trace Provenance

Imported but pipeline-validated example tables include:

- `candidate_universe_table.csv`
- `hard_filter_table.csv`
- `dd_evidence_table.csv`
- `er_brb_scoring_table.csv`
- `risk_matrix.csv`
- `financial_calculation_sheet.csv`
- `claim_to_evidence_map.csv`
- `human_review_checklist.csv`

Pipeline-generated or pipeline-refreshed outputs include:

- `pce_audit/pce_audit_current_run.csv`
- `pce_audit/certification_result.json`
- `delivery/readiness_result.json`
- `delivery/final_delivery_gate.md`
- `delivery/final_delivery_certificate.md`
- `run_records/<run_id>/*.json`
- `run_records/<run_id>/warnings.md`

If a trace table is not fully reproducible by the current clean-repo pipeline, it must be marked as imported / validated / not currently reproducible rather than presented as freshly generated.
