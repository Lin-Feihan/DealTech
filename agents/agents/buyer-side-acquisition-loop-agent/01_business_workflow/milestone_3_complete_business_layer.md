# Milestone 3 — Complete Buyer-side Acquisition Business Layer

Milestone 3 adds the full deterministic business path while preserving Milestones 1 and 2:

`Input / Mandate → Research Contract → A1–A7 → Gate A → B1–B5 → Gate B → C1–C5 → Gate C → structured Decision State`

Any non-advancing gate calls one shared path:

`Gap Diagnosis → append-only Memory Update → Loop Controller → targeted Re-plan → affected Block A, B or C module`

The synthetic case executes 17 modules, loads 35 acquisition-specific prompts, replays 15 Decimal calculations and produces `PROCEED_WITH_CONDITIONS`. This is not final Go / No-Go approval.

## Boundaries

- **Acquisition business logic** owns module contracts/results, gates, mandate thresholds and Decision State.
- **Deep Research execution** is a `ResearchProvider`; the current provider reads registered fixtures only—no web or LLM.
- **Loop Engineering** owns diagnosis, append-only history, controller action and targeted return; it cannot change business criteria.
- **Calculation Engine** owns registered formulas, input checks and independent replay; it cannot choose assumptions.
- **PCE** is a read-only-adapted delivery control, not a business gate.
- **ER/BRB** is a read-only-adapted evidence-row rule signal, not a business gate or probabilistic belief engine.
- **Human Review** retains legal, regulatory, tax, accounting, price, risk and final approval authority.

## Outputs

- `00_input`: mandate, Research Contract, plan, questions and contracts.
- `01_research`: sources, evidence, claims, assumptions, unknowns, counterevidence and provider responses.
- `02_block_a` / `03_gate_a`: Strategic Thesis and Gate A.
- `04_block_b` / `05_gate_b`: economics, calculations, replays, gaps and Gate B.
- `06_block_c` / `07_gate_c`: risks, Gate C and Decision State.
- `08_controls`: PCE, ER/BRB, prompts, human review and loop events.
- `09_loop`: iteration, loop and terminal states.

No final narrative report is generated. Live LLM/web research, PDF/Excel ingestion, a database, interactive review resume, external actions and the final Acquisition Strategy Report remain deferred.
