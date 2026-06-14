# Decision Points — Merger Strategy Agent

## Input completeness gate

The workflow cannot certify a case until these inputs exist:

- Buyer and target identity.
- Transaction objective and scope.
- Source registry.
- Evidence table.
- Claim-to-evidence map.
- Financial model or model assumptions.
- Valuation and scenario data.

## Evidence and source gates

- SEC filings and audited financials are preferred for public-company facts.
- Company materials must be mapped to specific claims and caveated where promotional.
- News and equity research are secondary sources unless corroborated.
- Imported artifacts are migration context, not primary evidence.
- LLM summaries cannot be used as evidence.

## High-risk claim gates

The following require primary source replay and/or calculation replay before certification:

- Valuation.
- Walkaway price.
- Synergies.
- Accretion/dilution.
- ROIC / WACC impact.
- Regulatory and antitrust risk.
- Fairness or board recommendation.
- Final go / no-go recommendation.

## Certification gate

- If source replay is missing: `Needs Human Review`.
- If calculation replay is missing: `Needs Human Review`.
- If human-review flags are hidden: block release.
- If no real case evidence exists: `Framework only`.
