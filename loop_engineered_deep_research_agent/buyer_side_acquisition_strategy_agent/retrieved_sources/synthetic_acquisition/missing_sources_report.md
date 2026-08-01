# M2 Synthetic Source Partial Coverage Report

Case: AcquirerCo / TargetCo
Runtime scope: Buyer-Side Acquisition Strategy Agent M2 manual_retrieved_sources
Status: PARTIAL COVERAGE - raw evidence may be extracted only from retrieved authoritative sources

## Decision

Create a partial `retrieved_sources_manifest.json` for available synthetic authoritative-source fixtures and record unavailable source categories in `failed_source_needs`.

M2 should fail closed only when there are zero valid authoritative retrieved sources or when the manifest itself is invalid. An incomplete but valid authoritative source set may proceed through M2 raw-evidence extraction with `evidence_coverage_status: partial`.

M2 must not enter M3. This run must not generate `evidence_repository.json`, `claim_evidence_graph.json`, `certification_result.json`, or `final_report.md`.

## Created Location

- Directory: `loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/retrieved_sources/synthetic_acquisition/`
- Manifest: `loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/retrieved_sources/synthetic_acquisition/retrieved_sources_manifest.json`
- Source fixture directory: `loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/tests/fixtures/synthetic_authoritative_sources/`

## Synthetic Candidate Sources Retrieved

These files are local synthetic fixtures standing in for authoritative source owners.

1. Transaction agreement fixture
   - Cached file: `tests/fixtures/synthetic_authoritative_sources/transaction_agreement_excerpt.txt`
   - Observed anchors: `transaction agreement`, `2026-01-15`, `AcquirerCo`, `TargetCo`, `$42 million`, `$18 million`, `ProductX`.

2. Annual report fixture
   - Cached file: `tests/fixtures/synthetic_authoritative_sources/annual_report_excerpt.txt`
   - Observed anchors: AcquirerCo annual reporting, later contingent payment, entity history, retrospective outcome validation.

3. Governance disclosure fixture
   - Cached file: `tests/fixtures/synthetic_authoritative_sources/governance_disclosure_excerpt.txt`
   - Observed anchors: founder role, governance, minority shareholding, cap table gap.

4. Patent database fixture
   - Cached file: `tests/fixtures/synthetic_authoritative_sources/patent_record_excerpt.txt`
   - Observed anchors: ProductX platform intellectual property, inventor records, assignee continuity.

5. Official product page fixture
   - Cached file: `tests/fixtures/synthetic_authoritative_sources/product_pipeline_excerpt.txt`
   - Observed anchors: ProductX product candidate, customer validation, approval, regulatory review.

## Failed Source Needs Still Missing

These missing categories are recorded in the manifest `failed_source_needs` and should remain gaps until supplied by a human or a future retrieval provider.

1. Direct ownership, governance, cap table, or seller economics disclosure
   - Status: missing. Do not infer proceeds from transaction consideration.

2. Complete intellectual property scope and assignment record
   - Status: missing. Available excerpts are fixture leads only.

3. Decision-date clinical, regulatory, approval, or customer validation evidence
   - Status: missing. Retrospective product materials cannot become ex-ante proof without caveat.

4. Direct valuation or financial-support evidence
   - Status: missing. Leave valuation and return analysis as unsupported.

## Runtime Controls

- `evidence_coverage_status`: `partial`
- `case_seed` must not be used as evidence.
- mandate notes must not be used as evidence.
- user narrative notes must not be used.
- test fixtures must be clearly identified as synthetic package fixtures.
- no live search should be faked by the runtime.
- no downstream M3 artifacts should be generated.
