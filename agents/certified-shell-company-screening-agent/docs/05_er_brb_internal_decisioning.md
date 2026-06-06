# ER/BRB Internal Decisioning

ER/BRB is an internal decisioning mechanism.

It is not a decorative final score table and it is not part of PCE. It is embedded inside the agent at two points:

1. **Hard Filter stage** — handles incomplete evidence, conflicting signals, source reliability differences, missing data, uncertainty and confidence calibration. Outputs: pass, exclude, watchlist, DD escalation, confidence and rationale.
2. **Deep Due Diligence stage** — handles control path, capital structure, compliance, litigation risk, disclosure quality, business fit, asset-injection feasibility and transaction certainty. Outputs: DD-adjusted risk, ranking support, recommendation support, confidence and caveat.

ER/BRB outputs explain confidence-aware internal judgments, not simple weighted scores.

ER/BRB makes internal decisions.
PCE certifies whether those decisions can enter final delivery.
