# Source Policy

Every claim used by a certified DealTech agent must be mapped to a source row and an evidence row. LLM-generated summaries are not evidence. Imported artifacts are migration context only unless their underlying original sources are recovered and replayed.

## Source tiers

| Tier | Definition | PCE treatment |
|---|---|---|
| Tier 1 | regulatory / official / primary source, including filings, exchange websites, court or regulator records, audited company documents | PCE-eligible when extraction quality and claim mapping are explicit |
| Tier 2 | structured market or commercial source with documented provenance and field definitions | PCE-eligible with provenance caveat |
| Tier 3 | news / company website / secondary source | support evidence only; material claims usually require caveat or corroboration |
| Tier 4 | weak background source, search snippets, generic web material | background only, not sufficient for material certification |
| Not Evidence | LLM-generated summary, unsupported narrative, hidden reasoning, unlinked demo text | never PCE-eligible |
| Imported Artifact | old report, old demo output, migrated markdown, prior package artifact | usable only with caution; not primary evidence by itself |

## Required source registry fields

`source_id`, `source_name`, `source_type`, `url_or_file`, `used_for`, `reliability_tier`, `PCE_eligible`, `limitations`.

## Required evidence table fields

`evidence_id`, `claim_id`, `source_id`, `extracted_fact`, `evidence_type`, `confidence`, `limitations`, `human_review_required`, `PCE_status`.

## Certification restrictions

- Source mapping pending → not PCE-certified.
- Calculation replay pending → human review required.
- Imported artifact → not Tier 1 primary evidence.
- LLM-generated summary → not evidence.
- Metadata-level evidence → Certified with Caveat or Needs Human Review, never pure Certified.
