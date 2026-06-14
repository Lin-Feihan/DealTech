# PCE Result — Soren SPAC Target Acquisition

Overall status: **Needs Human Review**.

This is a migrated case with certified workflow overlay. It references the old Soren SPAC target screening demo, adds ER/BRB and PCE layers, and includes Apify as an extensible data-source / connector design. **No authenticated Apify run was executed in this version.**

| claim_id | final_output_claim | source_id | evidence_id | source_PCE_eligible | imported_artifact | metadata_level_evidence | calculation_replay_required | human_review_required | final_PCE_status | reason |
|---|---|---|---|---|---|---|---|---|---|---|
| CLM-SPAC-001 | The Soren case has a target shortlist. | SRC-SPAC-001 | EVI-SPAC-001 | no | yes | partial | yes | yes | Human Review Required | Imported artifact; not primary evidence by itself. |
| CLM-SPAC-002 | Public background supports candidate fit. | SRC-SPAC-002 | EVI-SPAC-002 | no | no | partial | possible | yes | Not Certified pending source replay | Original source mapping pending; not PCE-eligible until source replay is completed. |
| CLM-SPAC-003 | Apify can be used as future data connector. | SRC-SPAC-003 | EVI-SPAC-003 | no | no | yes | no | yes | Internal Trace Only | No authenticated Apify run was executed in this version. |
| CLM-SPAC-004 | Old evidence tags support certified migration. | SRC-SPAC-001 | EVI-SPAC-004 | no | yes | partial | no | yes | Human Review Required | Evidence tags do not equal source-level certification. |

PCE is not all green. Claims with source replay gaps, Apify-not-run status, or imported-artifact support remain `Human Review Required` or `Not Certified pending source replay`.
