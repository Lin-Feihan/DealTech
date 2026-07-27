# Acquisition Strategy Agents

This folder contains two agent specifications built from the provided acquisition strategy flowcharts and aligned with the earlier shell-company screening agent style: planner → intent clarification → iterative tool use → offline/online analysis → structured strategy report.

## Files

- `buyer_acquisition_strategy_agent.json` — Acquisition strategy agent（buyer perspective ）
- `target_acquisition_strategy_agent.json` — Acquisition strategy agent（target perspective ）

## Shared Agent Pattern

Both agents follow the same architecture:

1. User input
2. LLM planning and intent clarification
3. Step-by-step analytical workflow
4. Iterative tool use, including document parsing, filings/public search, financial modeling, valuation, risk screening, and report writing
5. Evidence-backed output report
6. Final recommendation with confidence, assumptions, and data gaps

## Buyer Agent Core Question

Should the buyer pursue the acquisition, at what price, under what structure, with what financing and risk mitigants?

## Target Agent Core Question

Should the target accept, reject, negotiate, run a market check, or pursue alternatives given the offer and standalone value?


## Demo decision

The early one-page dual-perspective prototype is removed from the formal agent directory. The public demo is documented only in `03_case_studies/demo_README.md`, with links to the buyer and seller/target static pages plus technical notes about the static deployment.

No local server, run script, embedded API endpoint, or LAN sharing package is preserved in this canonical folder.
