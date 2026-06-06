# Delivery Protocol

Final delivery is controlled by `final_delivery_gate.py`.

External final delivery may cite only material claims that:

1. appear explicitly in delivery markdown as `CLM-*` references;
2. exist in `trace/claim_to_evidence_map.csv`;
3. exist in `pce_audit/pce_audit_current_run.csv`;
4. have status `Certified` or `Certified with Caveat`; and
5. are scoped for external final delivery.

The following statuses cannot enter external final delivery:

- `Needs Human Review`
- `Internal Trace Only`
- `Not Certified`

Each run updates:

- `examples/tuntun_hk/delivery/readiness_result.json`
- `examples/tuntun_hk/delivery/final_delivery_gate.md`
- `examples/tuntun_hk/run_records/<run_id>/delivery_gate_summary.json`

If delivery files contain no explicit `CLM-*` material claim references, final delivery is blocked. This prevents narrative output from bypassing claim-level PCE.
