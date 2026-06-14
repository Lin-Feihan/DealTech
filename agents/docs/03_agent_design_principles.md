# Agent Design Principles

- Separate mandate, workflow, prompts, schemas, evidence, ER/BRB, PCE, and final output.
- Prefer deterministic trace tables over hidden reasoning.
- Never certify a claim solely because it appears in an old demo, LLM answer, or report draft.
- Treat imported artifacts as migration context unless they preserve original source links and extraction details.
- Preserve human-review flags when evidence is weak, secondary-only, metadata-level, or calculation-dependent.
- Agent code should be small, inspectable, and aligned with documents.
