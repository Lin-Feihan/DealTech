# Milestone 3 Business Asset Coverage Matrix

This is the migration trace for the independent **Buyer-side Acquisition Loop Agent**. The four notes in `agents/docs/acquisition-loop-upgrade/` were the primary map and remain unchanged. Legacy V0 code and case artifacts are read-only references. No real-company demonstration fact or conclusion is used.

Labels: **KEEP EXACT** retains the professional term or control boundary; **KEEP SEMANTICS, REFACTOR STRUCTURE** retains meaning in a new structured contract; **EXTEND FOR LOOP CONTROL** adds gaps, closure tests and targeted return; **HUMAN REVIEW REQUIRED** reserves judgement or approval for an authorized person.

## Acquisition business modules

| Exact concept | Primary legacy source / section | Treatment | New prompt and implementation | Block / Gate | Verification |
|---|---|---|---|---|---|
| Transaction Context | `acquisition-strategy-agent/docs/business_workflow.md` — input/context; `schemas/transaction_context.schema.json` | KEEP SEMANTICS, REFACTOR STRUCTURE | `A1_TRANSACTION_CONTEXT`; contract/result A1 | A / Gate A | registry + end-to-end |
| Buyer Strategic Need | business workflow — buyer need; `buyer_profile.schema.json` | KEEP EXACT; KEEP SEMANTICS, REFACTOR STRUCTURE | `A2_BUYER_STRATEGIC_NEED`; target-independent need and alternatives | A / Gate A | distinct from target/rationale |
| Strategic Rationale | business workflow; `strategic_rationale.schema.json` | KEEP EXACT; KEEP SEMANTICS, REFACTOR STRUCTURE | `A3_STRATEGIC_RATIONALE`; acquire/build/partner/defer comparison | A / Gate A | distinct from need and fit |
| Target Attractiveness | `docs/workflow_steps.md` — target assessment; `target_profile.schema.json` | KEEP SEMANTICS, REFACTOR STRUCTURE | `A4_TARGET_ATTRACTIVENESS`; scarcity, durability and alternatives | A / Gate A | comparator/counterevidence fields |
| Target Capability & Business Quality | workflow steps; target schema | KEEP EXACT; KEEP SEMANTICS, REFACTOR STRUCTURE | `A5_TARGET_CAPABILITY_BUSINESS_QUALITY`; capability separated from customer/economic/scalability quality | A / Gate A | material unknown retained |
| Industry / Competitive Position | business workflow — industry/competition | KEEP SEMANTICS, REFACTOR STRUCTURE | `A6_INDUSTRY_COMPETITIVE_POSITION`; market definition, rivalry, barriers, substitutes, position | A / Gate A | adverse competition retained |
| Strategic Fit | `docs/decision_points.md`; strategic rationale schema | KEEP EXACT; KEEP SEMANTICS, REFACTOR STRUCTURE | `A7_STRATEGIC_FIT`; buyer-need-to-capability links | A / Gate A | fit does not prove synergy/value |
| Standalone Financial Analysis | business workflow/workflow steps; `acquisition_calculation.schema.json` | KEEP SEMANTICS, REFACTOR STRUCTURE | `B1_STANDALONE_FINANCIAL_ANALYSIS`; historical, normalization, forecast, cash conversion | B / Gate B | sourced inputs and multiples replay |
| Synergy Assessment / Synergy Mechanism & Value Creation | business workflow — synergy; calculation schema | KEEP EXACT; KEEP SEMANTICS, REFACTOR STRUCTURE | `B2_SYNERGY_VALUE_CREATION`; revenue/cost/capex/WC, timing, probability, cost, dis-synergy, owner | B / Gate B | net and probability-adjusted replay |
| Valuation | workflow steps; calculation schema | KEEP EXACT; KEEP SEMANTICS, REFACTOR STRUCTURE | `B3_VALUATION_PRICE_DISCIPLINE`; EV, equity value, multiples, premium, net debt | B / Gate B | Decimal + independent replay |
| Purchase Price Discipline | decision points; calculation schema | KEEP EXACT; EXTEND FOR LOOP CONTROL | same B3 prompt; mandate maximum, total consideration, walk-away | B / Gate B | `RENEGOTIATE_PRICE` boundary test |
| Deal Structure | business workflow — deal structure | KEEP EXACT; KEEP SEMANTICS, REFACTOR STRUCTURE | `B4_DEAL_STRUCTURE_FINANCING`; consideration, funding, covenants, tax/legal dependencies | B / Gate B | structured result |
| Financing Impact | business workflow; calculation schema | KEEP EXACT; KEEP SEMANTICS, REFACTOR STRUCTURE | same B4 prompt; leverage and liquidity | B / Gate B | replay + thresholds |
| Returns Analysis | workflow steps; calculation schema | KEEP EXACT; KEEP SEMANTICS, REFACTOR STRUCTURE | `B5_RETURNS_ANALYSIS`; invested capital, ROIC, payback, IRR | B / Gate B | replay + no invented hurdles |
| Due Diligence | business workflow; decision points | KEEP EXACT; EXTEND FOR LOOP CONTROL; HUMAN REVIEW REQUIRED | `C1_DUE_DILIGENCE`; workstreams, findings, red flags, unknowns, owners, conditions | C / Gate C | open item retained |
| Regulatory Risk | workflow/decision points; `er_brb_scoring.schema.json` | KEEP EXACT; HUMAN REVIEW REQUIRED | `C2_REGULATORY_RISK`; jurisdiction, filing, harm, timing, remedies | C / Gate C | qualified counsel condition |
| Integration Risk | business workflow; `integration_risk.schema.json` | KEEP EXACT; KEEP SEMANTICS, REFACTOR STRUCTURE | `C3_INTEGRATION_RISK`; people, culture, technology, customer, operating model, value-at-risk | C / Gate C | counterevidence + retention condition |
| Downside Risk | decision rules; calculation schema | KEEP SEMANTICS, REFACTOR STRUCTURE | `C4_DOWNSIDE_RISK`; scenarios, breaches, mitigation, walk-away | C / Gate C | no unverified upside offset |
| Go / No-Go, conditional recommendation, Decision State | decision points; `final_delivery_certificate.schema.json` | KEEP EXACT; HUMAN REVIEW REQUIRED | `C5_DECISION_STATE`; PROCEED / PROCEED_WITH_CONDITIONS / RENEGOTIATE / PAUSE / NO_GO / HUMAN_REVIEW | C / Gate C | support state is not approval |

## Evidence, certification, loop and reporting controls

| Asset | Exact legacy source | Treatment | New boundary / implementation | Verification |
|---|---|---|---|---|
| Source tiers and source policy | `docs/source_policy.md`; `dealtech_certification/shared/source_tier.md` | KEEP EXACT | `GLOBAL_EVIDENCE`; Source replay/admissibility fields | no LLM summary; imported-only, secondary-only and pending sources cannot be pure Certified |
| Evidence quality and claim mapping | source policy; `shared/claim_mapping.md` | KEEP EXACT; EXTEND FOR LOOP CONTROL | Source → Evidence → Claim lineage plus Research Gap | missing evidence and counterevidence tests |
| Claim verification / PCE | `docs/PCE_workflow.md`; `dealtech_certification/pce.py`; `pce_audit.schema.json` | KEEP EXACT delivery boundary; read-only adapter | `PCE_EVALUATOR`; `business_certification.run_business_certification` | PCE controls delivery, never Gate A/B/C |
| ER/BRB | `docs/ER_BRB_rules.md`; `dealtech_certification/er_brb.py`; scoring schema | KEEP EXACT current rule semantics; read-only adapter | `ER_BRB_EVALUATOR` | keyword/rule rows are not represented as belief aggregation |
| Calculation replay | PCE workflow; calculation/PCE schemas | KEEP EXACT; EXTEND FOR LOOP CONTROL | `GLOBAL_CALCULATION`; `calculations.py` | Decimal inputs, unit/currency checks, independent replay; failed replay blocks Gate B |
| Counterevidence | system prompt, source policy, claim mapping | KEEP EXACT | every module contract/result includes adverse evidence | linked counterevidence persists |
| Assumptions / explicit unknowns | input policy, workflow, report limitations | KEEP EXACT; EXTEND FOR LOOP CONTROL | AssumptionRecord / UnknownRecord | assumption cannot become fact; unknown has impact and closure test |
| Human review | `shared/human_review.md`; PCE rules; final certificate schema | KEEP EXACT; HUMAN REVIEW REQUIRED | `GLOBAL_HUMAN_REVIEW`; open review items | no invented reviewer, legal sign-off, price or committee approval |
| Report structure | acquisition README/workflow/final certificate | KEEP SEMANTICS, REFACTOR STRUCTURE | structured output directories; `GLOBAL_DELIVERY` | final narrative report explicitly deferred |
| Unified failure loop | audit map plus Milestones 1–2 | EXTEND FOR LOOP CONTROL | four `LOOP_*` prompts; `business_loop.enter_unified_loop` | every non-advancing A/B/C gate creates Diagnosis → Memory → Controller → targeted Re-plan |

## Gate vocabularies

- Gate A: `PASS`, `CONDITIONAL_PASS`, `FAIL_RESEARCH_GAP`, `FAIL_MANDATE_GAP`, `HUMAN_REVIEW_REQUIRED`, `FATAL_STRATEGIC_MISMATCH`.
- Gate B: `PASS`, `CONDITIONAL_PASS`, `FAIL_RESEARCH_GAP`, `FAIL_CALCULATION_GAP`, `FAIL_MANDATE_GAP`, `HUMAN_REVIEW_REQUIRED`, `RENEGOTIATE_PRICE`, `RENEGOTIATE`, `FATAL_VALUE_DESTRUCTION`.
- Gate C: `PASS`, `CONDITIONAL_PASS`, `FAIL_RESEARCH_GAP`, `HUMAN_REVIEW_REQUIRED`, `RENEGOTIATE`, `PAUSE`, `NO_GO`, `FATAL_RISK`.

The enum contains the union; each evaluator may select only statuses meaningful to its gate. PCE statuses remain separate.

## Legacy exclusions

Real-company demonstration cases, generated evidence tables, reports and conclusions are not contracts, prompts, defaults or tests. The deterministic fixture uses only `Synthetic Buyer` and `Synthetic Target` and labels every source as synthetic.
