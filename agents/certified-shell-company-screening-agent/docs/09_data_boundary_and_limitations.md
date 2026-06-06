# Data Boundary and Limitations

This repository is a research workflow prototype and technical demonstration. It is not investment, legal, tax, regulatory, financial-advisory, or transaction advice.

## Current Data Boundary

The Tuntun HK example includes trace artifacts imported from an original working bundle and validated by the clean-repo pipeline. The current demo does not claim full live regeneration of all HK market-data, announcement, PDF-body parsing, or risk-review artifacts.

The run manifest explicitly distinguishes:

- `pipeline_generated`
- `pipeline_validated`
- `imported_from_original_bundle`
- `not_reproducible_currently`
- `needs_human_review`

## Certification Boundary

PCE is conservative by design:

- Evidence gaps are downgraded.
- Metadata-only or title-level evidence is not treated as final-certifiable.
- Upstream human-review flags propagate into PCE.
- Final delivery must cite explicit certified `CLM-*` claims.

A blocked delivery gate is a valid and expected result when the current evidence boundary does not support final certification.
