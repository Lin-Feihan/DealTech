# Contributing

## Add a new market

Create `src/shell_company_screening_agent/data_sources/<market>/` and `configs/markets/<market>/` with source hierarchy, field mapping, announcement types and market-specific filter rules.

## Add a new case

Create `examples/<case_id>/` with mandate, case config, input, trace, PCE audit and delivery folders.

## Add ER/BRB rules

Add rules under `configs/decisioning/` and implementation under `src/shell_company_screening_agent/decisioning/er_brb/`.

## Add PCE rules

Add rules under `configs/pce/` and corresponding checks under `src/shell_company_screening_agent/pce/`.

## Add a data-source adapter

Implement the adapter under `data_sources/`, map it to common schemas, and keep source reliability explicit.

## Add a delivery template

Add reporting code under `src/shell_company_screening_agent/reporting/` and ensure PCE gating prevents unsupported claims from entering final delivery.
