# SPAC Target Acquisition Agent

## 1. Business Problem

Screen operating companies as potential SPAC business-combination targets while preserving source provenance and diligence blockers.

## 2. User Input

SPAC profile, target sector, geography, size range, listing constraints, public/private source assumptions, and diligence questions.

## 3. Business Workflow

Mandate normalization → candidate universe → target evidence extraction → ER/BRB overlay → PCE claim review → human-review shortlist.

See `01_business_workflow/business_workflow.md` for the detailed staged workflow.

## 4. Data Sources & Evidence Layer

Old Soren report artifact, public-source placeholders, and Apify connector design. No authenticated Apify run was executed in this version.

Required source registry fields: `source_id`, `source_name`, `source_type`, `url_or_file`, `used_for`, `reliability_tier`, `PCE_eligible`, `limitations`.

Required evidence table fields: `evidence_id`, `claim_id`, `source_id`, `extracted_fact`, `evidence_type`, `confidence`, `limitations`, `human_review_required`, `PCE_status`.

## 5. ER/BRB Layer

Case overlay flags imported-artifact and source-replay limitations instead of marking claims cleanly case-level certified.

ER/BRB case result rows must include claim, evidence, source, reliability, business risk, regulatory risk, reputational risk, certification status, human-review flag, and reason.

## 6. PCE Layer

PCE is not all green; source replay pending and Apify-not-run claims are Human Review Required or Not Certified pending source replay.

PCE checks final-output claims claim-by-claim. It must not hide human-review flags or convert imported artifacts into primary evidence.

## 7. Case Studies

Soren case migrated with certified workflow overlay under `07_case_studies/case_001_soren_spac_target_acquisition/`.

Important boundary: this case has been upgraded to a **partially source-replayed screening structure**, but it is **not yet a fully source-replayed complete case**. Aledade, Cityblock Health, DispatchHealth, and Lyra Health have source-replayed identity/business-description rows, but candidate financials, EBITDA, deal value, SPAC readiness, and Apify-authenticated dataset replay remain incomplete.

Rows marked as retained are **provisional validation slots / retained for review**. They are not final recommended targets, outreach targets, or acquisition recommendations.

## 8. Current Certification Status

Needs Human Review.

## 9. Current Limitations

Imported Soren report artifact is not primary evidence by itself; original source mapping, candidate identity replay, candidate financial replay, and live connector execution remain pending.

## 10. How to Run

Run the lightweight smoke entrypoint from the repository root:

```bash
python agents/spac-target-acquisition-agent/src/main.py
```

Run this agent's tests:

```bash
python -m pytest agents/spac-target-acquisition-agent/tests -q
```

Run all repository tests:

```bash
python -m pytest -q
```
