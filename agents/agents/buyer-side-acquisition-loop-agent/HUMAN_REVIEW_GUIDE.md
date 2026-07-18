# Human Review guide

Human Review is required when information is private or confidential, evidence conflicts materially, a qualified legal/financial/technical judgement is reserved, or the buyer must approve price, financing, risk acceptance or the transaction.

A review item identifies its owning module/Gate, issue, related Claims/Evidence/Gaps/calculations, reviewer role, conditions, decision impact and status. Responses are structured and versioned. Approved information re-enters admission, PCE, affected calculations and the relevant Gate; it does not automatically approve the transaction.

Use `--human-review-response path/to/response.json` with the applicable case/output for the existing review-resume workflow. Outcomes may approve information, approve with conditions, reject it, request more information or exercise explicitly reserved stop authority. The final machine Decision State always remains distinct from authorized human approval.
