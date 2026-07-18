# Buyer-side Acquisition Agent Engineering Contract

- Treat `agents/agents/acquisition-strategy-agent/`, `agents/agents/acquisition_strategy_agent/`, `agents/dealtech_certification/`, `agents/docs/acquisition-loop-upgrade/` and `.codex/` as protected legacy or local-state paths. Do not modify them without explicit user approval.
- New business implementation belongs in `agents/agents/buyer_side_acquisition_loop_agent/`; prompts, schemas, examples, tests and product documentation belong in `agents/agents/buyer-side-acquisition-loop-agent/`.
- Preserve the 17 named M&A modules, three Gates, Mandate thresholds, Source–Evidence–Claim lineage, counterevidence, calculation replay, PCE, ER/BRB and Human Review boundaries. Do not turn PCE or ER/BRB into a business Gate.
- Gate histories are append-only. Cross-block bundles require matching case/run IDs, relative artifact references and SHA-256 integrity checks.
- Run focused deterministic tests first. Final release verification must include all new-agent tests, affected acquisition tests and the repository suite. Never make paid/live requests in CI.
- Commit source, prompts, schemas, tests, recorded fixtures and curated `sample_output/`. Exclude unrestricted `run_output/`, credentials, raw live responses and confidential local attachments.
- See `agents/agents/buyer-side-acquisition-loop-agent/ARCHITECTURE.md`, `EVIDENCE_AND_CERTIFICATION.md`, `HUMAN_REVIEW_GUIDE.md` and `RELEASE_CHECKLIST.md` for details.
