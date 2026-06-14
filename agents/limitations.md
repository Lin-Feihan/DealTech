# Limitations

- This v1.0 repository runs deterministic local workflows against included case files; it does not claim live external data connectors have been authenticated or rerun.
- Imported artifacts are treated as migration context and never as Tier 1 primary evidence by themselves.
- LLM summaries are not accepted as evidence.
- SPAC / Soren remains `Needs Human Review` because Apify was not authenticated and source replay is pending.
- Acquisition Strategy buyer-side and target-side remain `Needs Human Review` because primary source replay and valuation/calculation validation are pending.
- Merger Strategy is framework-only after workflow integration; it still needs real merger case input, source registry, evidence table, and calculation materials before case-level certification.

## Merger Strategy Workflow Image Integration

The Merger Strategy Agent now reflects the user-provided workflow image, but it remains `Framework only`. A real certified run still requires a concrete merger case, source registry, evidence table, claim-to-evidence map, and calculation replay artifacts.
