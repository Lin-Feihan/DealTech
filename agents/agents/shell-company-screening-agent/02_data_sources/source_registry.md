# Source Registry — TonTon / Tuntun Shell Company Screening

| source_id | source_name | source_type | url_or_file | used_for | reliability_tier | PCE_eligible | limitations |
|---|---|---|---|---|---|---|---|
| SRC-SHELL-001 | HK public-company trace source inventory | regulatory / official / primary source index | `supporting_files/trace/source_inventory.csv` | source-level audit trail and case trace | Tier 1 / Tier 2 mixed | yes, where extraction rows map to claims | some entries remain metadata-level and require review |
| SRC-SHELL-002 | DD evidence table | case evidence table | `supporting_files/trace/dd_evidence_table.csv` | deep-diligence facts and claim support | Tier 1 / Tier 2 / Tier 3 mixed | yes with caveat | not every row is primary-source level |
| SRC-SHELL-003 | Certified trace package artifacts | imported artifact | `supporting_files/trace/` and `supporting_files/pce_audit/` | migrated trace, ER/BRB, PCE, claim map | Imported Artifact | caveated | imported artifacts are not primary evidence by themselves |
| SRC-SHELL-004 | Final delivery artifact | imported artifact / generated delivery | `supporting_files/delivery/tuntun_hk_case_study.md` | final case narrative | Imported Artifact | no, unless mapped to claim evidence | final narrative must be checked against claim-to-evidence map |
