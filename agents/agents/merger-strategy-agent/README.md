# Merger Strategy Agent

## 1. Business Problem

Provide a merger-strategy workflow that turns a buyer/target merger question into a structured, evidence-gated merger case memo. The agent is designed for strategic rationale, standalone assessment, valuation / walkaway price, synergies, deal structure, financing, pro forma impact, governance, diligence, regulatory / antitrust risk, integration planning, sensitivity analysis, and final recommendation.

## 2. User Input

Business workflow integrated from the provided flowchart. Real case input is still pending: no buyer, target, transaction facts, source registry, evidence table, or calculation model have been supplied for an actual case run.

## 3. Business Workflow

The provided flowchart has been converted into the files in `01_business_workflow/`:

- `workflow_overview.md`
- `workflow_steps.md`
- `decision_points.md`
- `workflow_diagram.md`
- `workflow_diagram.mmd`

Core flow: user intent → LLM clarification → planning intent → merger strategy agent → offline analysis / online retrieval / extended tool use → 15-section merger case memo → ER/BRB → claim-level PCE → human review / final recommendation.

## 4. Data Sources & Evidence Layer

Framework placeholders only. No real case source registry is claimed.

Required source registry fields: `source_id`, `source_name`, `source_type`, `url_or_file`, `used_for`, `reliability_tier`, `PCE_eligible`, `limitations`.

Required evidence table fields: `evidence_id`, `claim_id`, `source_id`, `extracted_fact`, `evidence_type`, `confidence`, `limitations`, `human_review_required`, `PCE_status`.

## 5. ER/BRB Layer

Framework version only; no case-run ER/BRB result exists.

ER/BRB case result rows must include `claim_id`, `claim_text`, `evidence_id`, `source_id`, `evidence_reliability`, `business_risk`, `regulatory_risk`, `reputational_risk`, `certification_status`, `human_review_required`, and `reason`.

## 6. PCE Layer

Framework version only; no case-run PCE result exists.

PCE checks final-output claims claim-by-claim. It must not hide human-review flags or convert imported artifacts, LLM-generated summaries, or source-replay-pending items into primary evidence.

## 7. Case Studies

Case study status: real case input pending. No case-run is claimed.

## 8. Current Certification Status

Business workflow integrated from provided flowchart; ER/BRB and PCE framework ready; real case input pending.

## 9. Current Limitations

No fabricated case, source, result, customer, company, transaction, valuation, synergy, antitrust, or recommendation fact is included.

## 10. How to Run

Run the framework-only status from the repository root:

```bash
python run_agent.py --agent merger-strategy
```

Run this agent's tests:

```bash
python -m pytest agents/merger-strategy-agent/tests -q
```

Run all repository tests:

```bash
pytest -q
```
