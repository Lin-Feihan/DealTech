# System Architecture

Each agent uses the same seven-layer pipeline:

1. **Input setting** — mandate, parties, geography, constraints, evaluation objective.
2. **Business workflow** — staged analytical process and hard gates.
3. **Data sources & evidence layer** — source registry, evidence table, source-tier policy.
4. **Research trace** — stage-by-stage trace table connecting workflow outputs to evidence.
5. **ER/BRB** — evidential reasoning and belief-rule-based decisioning.
6. **PCE** — post-claim evaluation of final-output claims against upstream trace.
7. **Final output & human review** — delivery memo plus caveats, blockers, and next diligence.

Agents may differ in market, deal type, and scoring logic, but they must not bypass the source/evidence/certification layers.
