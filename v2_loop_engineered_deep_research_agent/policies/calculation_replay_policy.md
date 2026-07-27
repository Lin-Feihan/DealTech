# Calculation Replay Policy

## Purpose

M&A reports often depend on calculations: valuation, synergy value, returns, leverage, EPS, ROIC, and price bridges. V2 requires material calculations to be replayable.

## Replayable Calculation Record

A calculation record should include:

- calculation_id
- linked claim_id
- formula
- input values
- source or evidence ID for each input
- unit
- currency
- period/date
- FX rate if used
- assumptions
- output value
- sensitivity variables
- reviewer notes

## Required For

Calculation replay is required for:

- valuation ranges
- maximum acceptable price
- minimum acceptable price
- synergy value
- risk-adjusted synergy value
- IRR
- MOIC
- NPV
- payback period
- EPS accretion/dilution
- ROIC versus WACC
- leverage and interest coverage
- sources and uses
- probability-weighted shareholder value

## Buyer-Side Price Formula

For buyer-side acquisition strategy:

```text
maximum_acceptable_price
= standalone_value
+ buyer_shareable_synergy_value
- integration_cost
- transaction_cost
- risk_discount
- value_buffer_required_by_buyer_minimum_return
```

## Seller-Side Price Formula

For target/seller-side acquisition strategy:

```text
minimum_acceptable_price
= standalone_risk_adjusted_value
+ reasonable_control_premium
+ target_shareholder_share_of_synergies
- stock_consideration_discount
- closing_risk_discount
- regulatory_or_time_value_discount
+ competitive_bidding_or_strategic_scarcity_premium
```

## Probability-Weighted Value

```text
probability_weighted_value
= sum(each_scenario_value * each_scenario_probability)
```

## Certification Impact

A calculation claim can be Certified only if:

- the formula is shown
- all material inputs are identified
- units and periods are consistent
- source or assumption status is clear
- output can be recomputed

A calculation should be Certified with Caveat if:

- formula is replayable but input assumptions are not source-backed
- source data is reliable but dated
- sensitivity materially affects conclusion

A calculation should be Needs Human Review if:

- valuation conclusion depends on unsupported assumptions
- assumptions require expert judgment
- conflicting data materially changes conclusion

A calculation should be Not Certified if:

- formula is absent
- inputs are missing
- units or periods are inconsistent
- output cannot be reproduced
