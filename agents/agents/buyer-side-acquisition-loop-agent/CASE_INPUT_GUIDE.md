# Case input guide

A runnable full case uses `schema_version: release-candidate-1` and requires one `case_id`, one `run_id` and one `as_of_date` across the case, Mandate, Research Contract and cross-block bundles.

The Mandate must name the buyer and target; state transaction type, stage, decision question and Buyer Strategic Need; record strategic objectives, known constraints, currency/unit, maximum equity purchase price, minimum ROIC and IRR, maximum pro forma leverage, minimum closing liquidity, diligence workstreams, jurisdictions, reviewer roles and the agent's authority limit.

The Research Contract must define scope, source policy, unknown policy, calculation/replay policy and delivery policy. Provider permissions, confidentiality and budgets must be explicit. Attachments require an ID, relative path, type, confidentiality, supplier, date, permitted modules, upload permission and extraction limits.

Use `06_examples/teacher_case_template/` as a blank intake form. It is intentionally `NOT_READY`; fill real values and approved template/provider configuration before running. Do not put API keys in the case file. Check it without research using:

```bash
buyer-side-acquisition-loop --case path/to/case.yaml --check-case
```

`READY_WITH_WARNINGS` means execution is technically possible but recorded evidence, confidentiality or review caveats remain. `NOT_READY` lists every missing or invalid field.
