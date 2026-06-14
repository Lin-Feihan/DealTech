# Research Trace — Soren SPAC Target Acquisition

This trace upgrades the imported Soren artifact into a source-replayed screening case structure. It does **not** claim live source replay has been completed.

| trace_id | workflow_stage | input_file | output_file | certification_boundary |
|---|---|---|---|---|
| TR-SPAC-001 | Mandate normalization | input_setting.md | supporting_files/candidate_universe.csv | Mandate scope can be caveated; candidates are not certified. |
| TR-SPAC-002 | Candidate universe hygiene | imported Soren report context | supporting_files/candidate_universe.csv; supporting_files/excluded_candidates.csv | Modeled/hypothetical names are excluded from real candidate pool. |
| TR-SPAC-003 | Hard filter | supporting_files/candidate_universe.csv | supporting_files/hard_filter_table.csv | Source replay gaps block Pass decisions. |
| TR-SPAC-004 | Retained for validation | supporting_files/hard_filter_table.csv | supporting_files/retained_candidates.csv | Retained means next DD validation slot, not acquisition recommendation. |
| TR-SPAC-005 | Deep diligence evidence | supporting_files/DD_evidence_table.csv | evidence_table.md | Imported report is context-only and not PCE-eligible evidence. |
| TR-SPAC-006 | Risk review | supporting_files/risk_matrix.csv | ER_BRB_result.md | Regulatory, reimbursement, audit, valuation, and data-quality risks remain visible. |
| TR-SPAC-007 | Calculation replay | supporting_files/calculation_sheet.csv | PCE_result.md | Revenue, EBITDA, and deal value are Unknown unless source replay exists. |
| TR-SPAC-008 | ER/BRB | supporting_files/ER_BRB_scoring.csv | ER_BRB_result.md | ER/BRB screens business risk; it does not certify final claims. |
| TR-SPAC-009 | PCE audit | supporting_files/PCE_audit.csv | scoped_claim_audit_result.md; final_delivery_certificate.md | Final delivery allowed only for process/boundary claims and caveated mandate facts. |
