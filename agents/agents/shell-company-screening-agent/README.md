# Shell Company Screening Agent

## 1. Business Problem

Screen listed-company restructuring, shell-platform, asset-injection, and control-transaction candidates with evidence-linked public-market research.

## 2. User Input

Market, mandate, target profile, transaction boundary, exclusion rules, evidence sources, and reviewer constraints.

## 3. Business Workflow

Mandate normalization → universe construction → hard filters → deep diligence evidence table → ER/BRB scoring → PCE claim review → final delivery with caveats.

See `01_business_workflow/business_workflow.md` for the detailed staged workflow.

## 4. Data Sources & Evidence Layer

HK/public-company source registry, trace CSVs, imported package artifacts, and case delivery files. Imported artifacts remain caveated.

Required source registry fields: `source_id`, `source_name`, `source_type`, `url_or_file`, `used_for`, `reliability_tier`, `PCE_eligible`, `limitations`.

Required evidence table fields: `evidence_id`, `claim_id`, `source_id`, `extracted_fact`, `evidence_type`, `confidence`, `limitations`, `human_review_required`, `PCE_status`.

## 5. ER/BRB Layer

Case-run ER/BRB rows evaluate claim, evidence, source reliability, risk, status, and human-review requirement.

ER/BRB case result rows must include claim, evidence, source, reliability, business risk, regulatory risk, reputational risk, certification status, human-review flag, and reason.

## 6. PCE Layer

Case-run PCE result is Certified with Caveat, not pure Certified.

PCE checks final-output claims claim-by-claim. It must not hide human-review flags or convert imported artifacts into primary evidence.

## 7. Case Studies

TonTon / Tuntun HK case integrated under `07_case_studies/case_001_tonton_shell_company_screening/`.

## 8. Current Certification Status

Certified with Caveat.

## 9. Current Limitations

Some claims still require human review, source-level caution, metadata-level evidence handling, and imported-artifact caveats.

## 10. How to Run

Run the lightweight smoke entrypoint from the repository root:

```bash
python agents/shell-company-screening-agent/src/main.py
```

Run this agent's tests:

```bash
python -m pytest agents/shell-company-screening-agent/tests -q
```

Run all repository tests:

```bash
python -m pytest -q
```
