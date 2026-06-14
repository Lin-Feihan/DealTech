# PCE Framework — Merger Strategy Agent

PCE must check each merger claim for:

- Claim exists.
- Claim has `source_id`.
- Source exists in source registry.
- Source is PCE eligible.
- Evidence exists.
- Evidence is not an imported artifact alone.
- Evidence is not metadata-only.
- Evidence is not secondary-source-only.
- Calculation replay has been performed where required.
- Human-review flags are preserved.
- Final output does not hide caveats.

Until a real merger case source registry, evidence table, and claim map are supplied, PCE status remains framework-only.
