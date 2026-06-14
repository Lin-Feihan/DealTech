# Input Setting — Merger Strategy Agent

Status: **Business workflow integrated from provided flowchart; ER/BRB and PCE framework ready; real case input pending.**

Expected future input fields:

| Field | Required | Description |
|---|---:|---|
| buyer_name | Yes | Acquiring / merging party |
| target_name | Yes | Target / counterparty |
| transaction_type | Yes | Merger, acquisition, merger-of-equals, stock-for-stock, cash deal, etc. |
| sector | Yes | Industry / subsector |
| geography | Yes | Relevant jurisdictions |
| transaction_timing | Yes | Announced, rumored, exploratory, signed, pending close |
| user_objective | Yes | Strategic fit, financial sense, go/no-go, board memo, diligence memo |
| available_sources | Yes | SEC filings, company corpus, reports, model, data room documents, etc. |
| financial_model | Conditional | Required for valuation, walkaway price, accretion/dilution, ROIC/WACC, scenario analysis |

The current runner must not fabricate any of these fields.
