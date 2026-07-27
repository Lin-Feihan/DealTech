# Source Map

This map records which local source folders were used to rebuild each canonical agent folder and what was intentionally retained in the public agent repository. It is curated for public clarity, not a complete recovery log.

## Shell Company Screening Agent

Canonical folder: `agents/shell-company-screening-agent/`

Primary sources:

- `HK_Shell_Screening_Agent_v0.1/`
- `deliverables/HK_Shell_Screening_Agent_FULL_WORKFLOW_v0.4/`
- `certified-shell-company-screening-agent/`
- `shell-screening-demo/` for public demo lineage only

Retained public assets:

- workflow: final v0.4 workflow overview, ER/BRB and PCE positioning, and workflow tables
- prompts: canonical shell screening prompt, certified trace execution prompt, and case-study generation prompt
- code: certified shell source retained as final agent core
- case study: Tuntun/TonTon HK reports, input, certification, and selected evidence tables
- demo: README-only public demo link and technical path notes

Excluded from canonical agent repository:

- raw document caches, early white-box scaffolding, drafts, placeholder audit files, intermediate run outputs, duplicate report builds, local demo source packages, and delivery zips

## SPAC Target Acquisition Agent

Canonical folder: `agents/spac-target-acquisition-agent/`

Primary sources:

- `US_SPAC_Target_Acquisition_Agent_v1/`
- `soren-spac-target-screening-demo/` for public demo lineage only
- historical zip references under `outputs/US_SPAC_Target_Acquisition_Agent_v1_*.zip`

Retained public assets:

- workflow: Soren methodology map and workflow diagram assets
- prompts: seven SPAC target acquisition prompts
- case study: original user mandate, derived mandate, SEC source anchor, Soren final report, and selected evidence tables
- demo: README-only public demo link and technical path notes

Excluded from canonical agent repository:

- raw notes, scratch universes, intermediate folders, agent configs, regeneration scripts, run logs, evidence-capture logs, and local/demo deliverable source packages

## Acquisition Strategy Agent

Canonical folder: `agents/acquisition-strategy-agent/`

Primary sources:

- `acquisition_strategy_agents/`
- public static demo links preserved in `agents/acquisition-strategy-agent/03_case_studies/demo_README.md`

Explicitly excluded from canonical source:

- later buyer-side acquisition loop agent
- FronThera loop/live-sourced run artifacts

Retained public assets:

- prompts/specs: `buyer_acquisition_strategy_prompt.md` and `target_acquisition_strategy_prompt.md` as the human-readable Deep Research prompts; `buyer_acquisition_strategy_agent.json` and `target_acquisition_strategy_agent.json` as the derived structured execution specs
- workflow: buyer and target flowchart images
- case study: Apple-DarwinAI buyer and target reports
- demo: README-only public links and technical notes under the case study folder

## Merger Strategy Agent

Canonical folder: `agents/merger-strategy-agent/`

Current status:

- framework-only placeholder
- no real case study or demo claimed
- no source material fabricated

Pending source confirmation:

- original merger workflow or flowchart
- original prompt set
- original code implementation, if any
- real case study, if any
- demo, if any

## Recovered Materials Layer

Recovered decision logs and rescue inventories are stored under:

- `legacy/recovered_materials/`

This layer is for preservation and audit. It should not be treated as polished canonical agent content without explicit review.
