# PCE Case Result — SPAC Target Acquisition

Case: `case_001_soren_spac_target_acquisition`

Overall status: **Needs Human Review**

|claim_id|claim_text|source_id|evidence_id|PCE_status|reason|human_review_required|
|---|---|---|---|---|---|---|
|CLM-SPAC-101|Aledade is a real source-replayed healthcare candidate identity/business-description row.|SRC-SPAC-101|EVI-SPAC-101|Certified|PCE executed; claim is certified within the current registered evidence boundary.|no|
|CLM-SPAC-102|Cityblock Health is a real source-replayed healthcare candidate identity/business-description row.|SRC-SPAC-102|EVI-SPAC-102|Certified|PCE executed; claim is certified within the current registered evidence boundary.|no|
|CLM-SPAC-103|DispatchHealth is a real source-replayed healthcare candidate identity/business-description row.|SRC-SPAC-103|EVI-SPAC-103|Certified|PCE executed; claim is certified within the current registered evidence boundary.|no|
|CLM-SPAC-104|Lyra Health is a real source-replayed healthcare candidate identity/business-description row.|SRC-SPAC-104|EVI-SPAC-104|Certified|PCE executed; claim is certified within the current registered evidence boundary.|no|
|CLM-SPAC-105|SEC ticker lookup supports a caveated screening note that the real candidate rows were not matched to public tickers in the sampled lookup.|SRC-SPAC-105|EVI-SPAC-105|Certified with Caveat|human_review_required flag is visible and blocks pure Certified status|yes|
|CLM-SPAC-001|The imported Soren report reconstructed a prior healthcare SPAC target shortlist.|SRC-SPAC-001|EVI-SPAC-001|Needs Human Review|source is not PCE eligible; imported artifact cannot serve as primary evidence by itself; human_review_required flag is visible and blocks pure Certified status|yes|
|CLM-SPAC-002|The legacy candidate background and company identity claims require source replay.|SRC-SPAC-002|EVI-SPAC-003|Needs Human Review|source is not PCE eligible; source replay pending; human_review_required flag is visible and blocks pure Certified status|yes|
|CLM-SPAC-003|An authenticated Apify run discovered candidate records for this case.|SRC-SPAC-004|EVI-SPAC-007|Needs Human Review|source is not PCE eligible; source replay pending; human_review_required flag is visible and blocks pure Certified status|yes|
|CLM-SPAC-004|Revenue, EBITDA, or deal value support SPAC deal-size fit.|SRC-SPAC-005|EVI-SPAC-009|Needs Human Review|calculation replay required before certification; human_review_required flag is visible and blocks pure Certified status|yes|
|CLM-SPAC-005|Modeled/hypothetical old-report names are excluded from the real candidate universe.|SRC-SPAC-005|EVI-SPAC-004|Certified with Caveat|human_review_required flag is visible and blocks pure Certified status|yes|
|CLM-SPAC-006|The mandate is a first-pass U.S. private healthcare SPAC target screen.|SRC-SPAC-006|EVI-SPAC-008|Certified with Caveat|PCE executed; claim can be delivered only with caveat under the current evidence boundary.|no|
|CLM-SPAC-007|ER/BRB screening is a business screen, not final certification.|SRC-SPAC-005|EVI-SPAC-010|Certified with Caveat|human_review_required flag is visible and blocks pure Certified status|yes|
|CLM-SPAC-008|Soren should pursue any retained candidate as an acquisition target.|SRC-SPAC-005|EVI-SPAC-009|Needs Human Review|calculation replay required before certification; human_review_required flag is visible and blocks pure Certified status|yes|
