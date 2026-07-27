# US SPAC Target Acquisition Agent - Source And Curation Note

This note replaces the earlier v1 all-files map. The public agent repository is intentionally curated: it keeps the highest-value Soren workflow, prompt set, case report, source anchors, selected evidence tables, and demo link notes, while excluding raw notes, local demo packages, scripts, run logs, and intermediate working material.

## Source Lineage

- Main early source: `US_SPAC_Target_Acquisition_Agent_v1/`
- Historical delivery zips: `outputs/US_SPAC_Target_Acquisition_Agent_v1_*.zip`
- Demo lineage: `soren-spac-target-screening-demo/`, represented in this package by `03_case_studies/soren_v1_final/demo_README.md` only.

## Public Repository Shape

```text
01_business_workflow/
02_prompts/
03_case_studies/soren_v1_final/
```

No production agent-core folder is retained for this agent because the high-value public artifact is the screening workflow/prompt/case package, not a runnable production codebase.

## Retained Material

- `01_business_workflow/METHODOLOGY_AND_FILE_MAP.md` keeps the Soren methodology and workflow map.
- `01_business_workflow/flowcharts/` keeps the workflow diagram assets.
- `02_prompts/` keeps the seven SPAC target acquisition prompts.
- `03_case_studies/soren_v1_final/input/original_user_input/original_user_prompt.md` keeps the original user mandate.
- `03_case_studies/soren_v1_final/input/derived_mandate/` keeps the structured mandate derived from the original prompt and SEC source anchor.
- `03_case_studies/soren_v1_final/input/sec_sources/soren_sec_links.csv` keeps the SEC source anchor.
- `03_case_studies/soren_v1_final/reports/` keeps the final public-facing report in available formats.
- `03_case_studies/soren_v1_final/evidence_tables/` keeps only selected tables needed to understand the final screening report and its limitations.
- `03_case_studies/soren_v1_final/demo_README.md` keeps the public demo link and technical path without bundling local demo source/build packages.

## Excluded From The Formal Repository

- Raw notes and scratch target-universe files.
- Intermediate working tables, scripts, agent configs, and one-off working outputs.
- Run logs and evidence-capture logs.
- Duplicate local demo folders and deliverable demo source packages.
- Placeholder citation ledgers or unclear-provenance tables that do not materially support the retained final report.

## Interpretation

This package preserves screening-priority and next-diligence logic. It is not a final investment recommendation, valuation opinion, or outreach-readiness claim. SPAC materials remain screening-level and human-review-required where public source replay is incomplete.
