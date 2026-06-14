# PCE Rules

PCE means Post-Claim Evaluation. It checks each final-output claim against upstream evidence, source registry, ER/BRB result, calculation replay, risk escalation, and final caveat visibility.

## Required PCE checks for every final-output claim

| check_id | Check |
|---|---|
| PCE-CHECK-01 | claim has a stable `claim_id` |
| PCE-CHECK-02 | claim maps to at least one `source_id` |
| PCE-CHECK-03 | mapped source is PCE_eligible for the claim type |
| PCE-CHECK-04 | evidence comes from primary / reliable source when the claim is material |
| PCE-CHECK-05 | evidence is not merely an imported artifact |
| PCE-CHECK-06 | evidence is not only metadata-level evidence |
| PCE-CHECK-07 | calculation-dependent claim has calculation replay |
| PCE-CHECK-08 | business / regulatory / reputational risk escalation is visible |
| PCE-CHECK-09 | `human_review_required` is not hidden or overwritten |
| PCE-CHECK-10 | final output preserves caveats instead of presenting unsupported certainty |

## Status vocabulary

- `Certified`: only when all required checks pass and no human-review flag remains.
- `Certified with Caveat`: core workflow and evidence trace are present, but limited claims require caution or human review.
- `Human Review Required`: source replay, primary evidence, risk review, or calculation replay is incomplete.
- `Not Certified pending source replay`: source mapping is missing or imported artifacts are the main support.
- `Internal Trace Only`: framework or connector design evidence; not a case-level certification.

If any claim in a case has `human_review_required = yes`, imported-artifact-only support, source mapping pending, metadata-level evidence, or calculation not replayed, the case result must not be written as pure `Certified`.
