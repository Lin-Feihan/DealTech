# ER/BRB Rules

ER/BRB means Evidential Reasoning / Belief Rule Base. It converts source-backed evidence into a decision status while preserving business, regulatory, and reputational risk.

## Required ER/BRB case-result fields

`claim_id`, `claim_text`, `evidence_id`, `source_id`, `evidence_reliability`, `business_risk`, `regulatory_risk`, `reputational_risk`, `certification_status`, `human_review_required`, `reason`.

## Decision rules

1. Tier 1 / Tier 2 evidence can support stronger belief only when extraction and claim mapping are explicit.
2. Tier 3 evidence can support a caveated claim but usually cannot certify a material transaction recommendation alone.
3. Tier 4 evidence is background only.
4. LLM-generated summaries are `Not Evidence` and cannot be used in ER/BRB support.
5. Imported artifacts are not primary evidence by themselves.
6. Source mapping pending, secondary-source-only support, metadata-level evidence, or calculation not replayed cannot be marked clean certified.
7. Any high business, regulatory, or reputational risk must appear in the ER/BRB row and PCE result.
