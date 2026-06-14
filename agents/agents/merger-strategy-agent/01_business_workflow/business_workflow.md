# Business Workflow — Merger Strategy Agent

Status: **Business workflow integrated from provided flowchart; case study pending real case input.**

The flowchart defines a merger case framework agent for a user question such as: “I am evaluating a potential merger between [Buyer] and [Target]. Can you analyze whether this deal makes strategic and financial sense?”

## End-to-end flow

1. **User input / intent capture** — buyer, target, deal question, scope, timing, geography, sector, and desired output.
2. **LLM clarification** — ask for missing parties, transaction perimeter, available data, valuation model, and decision context.
3. **Planning intent** — convert the request into a multi-step merger case workflow.
4. **Merger Strategy Agent execution** — run the 15 memo sections below.
5. **Offline analysis layer** — financial model, DCF/projection, valuation, scenario and sensitivity analysis.
6. **Online retrieval layer** — SEC / company corpus, market and pricing data, news, research, and equity research.
7. **Extended tool-use layer** — API search, browser retrieval, precedents, contracts, reports, and other validated corpora.
8. **Merger Case Memo** — produce a structured memo only from mapped claims and evidence.
9. **ER/BRB** — score evidence reliability, business risk, regulatory risk, reputational risk, and review blockers.
10. **PCE** — certify claims only when source replay and calculation replay are adequate; otherwise escalate to human review.

## Fifteen memo modules from the flowchart

1. Transaction Overview.
2. Strategic Rationale.
3. Stakeholder Assessment.
4. Industry & Market.
5. Valuation and Walkaway Price.
6. Synergies & Value Creation.
7. Deal Structure & Financing.
8. Pro Forma Financial Impact.
9. Governance & Control.
10. Deal Diligence Findings.
11. Regulatory & Antitrust Risk.
12. Integration Plan.
13. Risk Analysis.
14. Scenario & Sensitivity Analysis.
15. Final Recommendation.

## Current repository boundary

No real merger case has been run yet. The runnable status is framework output only: business workflow integrated, ER/BRB and PCE framework ready, real case input pending.
