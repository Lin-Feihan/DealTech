# Acquisition Strategy Agent

## 1. Business Problem

Evaluate acquisition strategy from buyer-side and target/seller-side perspectives without mixing the two decision frames.

## 2. User Input

Buyer profile, target profile, transaction context, strategic objectives, financing constraints, valuation assumptions, shareholder/board constraints, and timeline.

## 3. Business Workflow

Shared deal context → buyer-side workflow and target-side workflow → separate evidence tables → separate ER/BRB → separate PCE → separate final outputs.

See `01_business_workflow/business_workflow.md` for the detailed staged workflow.

## 4. Data Sources & Evidence Layer

Imported Apple → DarwinAI reports and pending original source mapping. Original source mapping pending; not PCE-eligible until source replay is completed.

Required source registry fields: `source_id`, `source_name`, `source_type`, `url_or_file`, `used_for`, `reliability_tier`, `PCE_eligible`, `limitations`.

Required evidence table fields: `evidence_id`, `claim_id`, `source_id`, `extracted_fact`, `evidence_type`, `confidence`, `limitations`, `human_review_required`, `PCE_status`.

## 5. ER/BRB Layer

Separate buyer-side and target-side ER/BRB overlays flag valuation, pricing, fairness, board recommendation, accept/reject, and strategic-attractiveness claims for human review unless source replay is complete.

ER/BRB case result rows must include claim, evidence, source, reliability, business risk, regulatory risk, reputational risk, certification status, human-review flag, and reason.

## 6. PCE Layer

Separate buyer-side and target-side PCE results keep Human Review Required where primary sources, calculation replay, or risk review are missing.

PCE checks final-output claims claim-by-claim. It must not hide human-review flags or convert imported artifacts into primary evidence.

## 7. Case Studies

Apple → DarwinAI case migrated with buyer-side and target-side subfolders under `07_case_studies/case_001_acquisition_strategy/`.

## 8. Current Certification Status

Needs Human Review / source replay pending.

## 9. Current Limitations

No claim receives clean case-level certification where source replay, calculation replay, or risk review is pending.

## 10. How to Run

Run the lightweight smoke entrypoint from the repository root:

```bash
python agents/acquisition-strategy-agent/src/main.py
```

Run this agent's tests:

```bash
python -m pytest agents/acquisition-strategy-agent/tests -q
```

Run all repository tests:

```bash
python -m pytest -q
```
