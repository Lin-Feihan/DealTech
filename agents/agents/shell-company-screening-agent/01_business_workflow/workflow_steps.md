# Workflow Steps — Shell Company Screening

1. Normalize mandate and delivery boundary.
2. Load HK-listed candidate universe and source registry.
3. Run hard filters for market-cap, listing, liquidity, shell-likeness, and risk exclusions.
4. Read DD evidence and claim-to-evidence mapping.
5. Execute ER/BRB for source reliability, business risk, regulatory risk, reputational risk, sufficiency, and human review.
6. Execute PCE claim checks and block pure certification when caveats remain.
7. Generate `certification_result.json`, `ER_BRB_case_result.md`, `PCE_case_result.md`, and `final_output.md`.
