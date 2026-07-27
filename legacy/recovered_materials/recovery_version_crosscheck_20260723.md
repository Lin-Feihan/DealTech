# DealTech Agent Version Crosscheck - 2026-07-23

Purpose: evidence-based核对每个 agent 的 prompt、business workflow、case study、code、demo 哪一版最可信，避免重建时遗漏或做成不像真实 agent 仓库。

Important: memory semantic index was unavailable during this check, so this table is based on local filesystem, git history, README/status/migration files, and rescue inventories.

## Shell Company Screening Agent

- Recommended canonical rebuild path: `agents/shell-company-screening-agent/`
- Best primary version to use: `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/shell-company-screening-agent/ plus certified-shell-company-screening-agent/`
- Current interpretation: Most mature case: TonTon/Tuntun, Certified with Caveat. Full trace exists locally. Early prompt files are partly skeletal but legacy prompt and later certified prompts exist.

### Earlier / supporting versions
- `HK_Shell_Screening_Agent_v0.1` — exists: yes; files: 715
- `deliverables/HK_Shell_Screening_Agent_FULL_WORKFLOW_v0.4` — exists: yes; files: 198
- `certified-shell-company-screening-agent` — exists: yes; files: 179

### Prompt sources
- `HK_Shell_Screening_Agent_v0.1/01_prompts` — exists: yes; files: 6
- `certified-shell-company-screening-agent/prompts` — exists: yes; files: 5
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/shell-company-screening-agent/03_prompts` — exists: yes; files: 6

### Business workflow sources
- `HK_Shell_Screening_Agent_v0.1/README.md` — exists: yes; files: 1
- `deliverables/HK_Shell_Screening_Agent_FULL_WORKFLOW_v0.4/00_START_HERE/01_FULL_WORKFLOW_OVERVIEW.md` — exists: yes; files: 1
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/shell-company-screening-agent/01_business_workflow` — exists: yes; files: 5

### Case study / output sources
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/shell-company-screening-agent/07_case_studies/case_001_tonton_shell_company_screening` — exists: yes; files: 42
- `certified-shell-company-screening-agent/examples/tuntun_hk` — exists: yes; files: 40
- `HK_Shell_Screening_Agent_v0.1/05_final` — exists: yes; files: 69

### Code sources
- `certified-shell-company-screening-agent/src/shell_company_screening_agent` — exists: yes; files: 66
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/shell-company-screening-agent/src` — exists: yes; files: 74

### Demo sources
- `shell-screening-demo` — exists: yes; files: 9
- `shell-demo-deploy` — exists: yes; files: 4
- `deliverables/shell-screening-demo-share` — exists: yes; files: 2
- `HK_Shell_Screening_Agent_v0.1/05_final/preview` — exists: yes; files: 2

### Rebuild decision
- Keep main canonical files in the agent folder, and copy any older/noncanonical material into `legacy/recovered_materials/` with source path preserved.
- Add this agent to `docs/prompt_inventory.md`, `docs/case_inventory.md`, and `docs/demo_inventory.md` before any push.

## SPAC Target Acquisition Agent

- Recommended canonical rebuild path: `agents/spac-target-acquisition-agent/`
- Best primary version to use: `US_SPAC_Target_Acquisition_Agent_v1 plus Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/spac-target-acquisition-agent/`
- Current interpretation: Soren case is runnable overlay in unified repo but remains Needs Human Review; no authenticated Apify live run. Early SPAC prompts are substantial and should be restored visibly.

### Earlier / supporting versions
- `US_SPAC_Target_Acquisition_Agent_v1` — exists: yes; files: 60
- `soren-spac-target-screening-demo` — exists: yes; files: 63
- `deliverables/soren-spac-target-screening-demo` — exists: yes; files: 16

### Prompt sources
- `US_SPAC_Target_Acquisition_Agent_v1/01_prompts` — exists: yes; files: 7
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/spac-target-acquisition-agent/03_prompts` — exists: yes; files: 1

### Business workflow sources
- `US_SPAC_Target_Acquisition_Agent_v1/README.md` — exists: yes; files: 1
- `US_SPAC_Target_Acquisition_Agent_v1/METHODOLOGY_AND_FILE_MAP.md` — exists: yes; files: 1
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/spac-target-acquisition-agent/01_business_workflow` — exists: yes; files: 5

### Case study / output sources
- `US_SPAC_Target_Acquisition_Agent_v1/05_final/reports` — exists: yes; files: 5
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/spac-target-acquisition-agent/07_case_studies/case_001_soren_spac_target_acquisition` — exists: yes; files: 25

### Code sources
- `US_SPAC_Target_Acquisition_Agent_v1/03_intermediate/agent_config` — exists: yes; files: 3
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/spac-target-acquisition-agent/src` — exists: yes; files: 9

### Demo sources
- `soren-spac-target-screening-demo` — exists: yes; files: 63
- `deliverables/soren-spac-target-screening-demo` — exists: yes; files: 16

### Rebuild decision
- Keep main canonical files in the agent folder, and copy any older/noncanonical material into `legacy/recovered_materials/` with source path preserved.
- Add this agent to `docs/prompt_inventory.md`, `docs/case_inventory.md`, and `docs/demo_inventory.md` before any push.

## Acquisition Strategy Agent

- Recommended canonical rebuild path: `agents/acquisition-strategy-agent/`
- Best primary version to use: `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/acquisition-strategy-agent/ plus acquisition strategy demos`
- Current interpretation: Apple to DarwinAI buyer-side and target-side cases exist and run in unified repo; status Needs Human Review for valuation/fairness/source replay claims. Prompt layer may be thinner than Shell/SPAC and should be marked for human review if only system_prompt exists.

### Earlier / supporting versions
- `acquisition_strategy_agents` — exists: yes; files: 22
- `acquisition-strategy-agent-portable-demo` — exists: yes; files: 65
- `deliverables/acquisition-strategy-agent-portable` — exists: yes; files: 21

### Prompt sources
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/acquisition-strategy-agent/03_prompts` — exists: yes; files: 1

### Business workflow sources
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/acquisition-strategy-agent/01_business_workflow` — exists: yes; files: 5

### Case study / output sources
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/acquisition-strategy-agent/07_case_studies/case_001_acquisition_strategy` — exists: yes; files: 49
- `acquisition_strategy_agents/reports` — exists: yes; files: 7
- `acquisition-strategy-agent-portable-demo/reports` — exists: yes; files: 7

### Code sources
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/acquisition-strategy-agent/src` — exists: yes; files: 8
- `acquisition_strategy_agents` — exists: yes; files: 22

### Demo sources
- `acquisition_strategy_agents` — exists: yes; files: 22
- `acquisition-strategy-agent-portable-demo` — exists: yes; files: 65
- `deliverables/acquisition-strategy-agent-portable` — exists: yes; files: 21

### Rebuild decision
- Keep main canonical files in the agent folder, and copy any older/noncanonical material into `legacy/recovered_materials/` with source path preserved.
- Add this agent to `docs/prompt_inventory.md`, `docs/case_inventory.md`, and `docs/demo_inventory.md` before any push.

## Buyer-side Acquisition Loop Agent

- Recommended canonical rebuild path: `agents/buyer-side-acquisition-loop-agent/`
- Best primary version to use: `DealTech/buyer-side-acquisition-loop-agent plus importable package DealTech/buyer_side_acquisition_loop_agent`
- Current interpretation: 7/18 rc1 public release inventory exists. 7/23 FronThera live-sourced run completed with final_report.md, claim_evidence_graph.json, run_summary.json. Full local run traces exist but some are intentionally not public-safe.

### Earlier / supporting versions
- `DealTech/agents/agents/buyer-side-acquisition-loop-agent` — exists: yes; files: 451
- `DealTech/local_cases/fronthera_2021` — exists: yes; files: 2309
- `DealTech/runs/fronthera_2021_live_sourced` — exists: yes; files: 3

### Prompt sources
- `DealTech/buyer-side-acquisition-loop-agent/03_prompts` — exists: yes; files: 8
- `DealTech/agents/agents/buyer-side-acquisition-loop-agent/03_prompts` — exists: yes; files: 8

### Business workflow sources
- `DealTech/buyer-side-acquisition-loop-agent/01_business_workflow` — exists: missing; files: 0
- `DealTech/agents/agents/buyer-side-acquisition-loop-agent/01_business_workflow` — exists: yes; files: 4

### Case study / output sources
- `DealTech/buyer-side-acquisition-loop-agent/06_examples` — exists: yes; files: 6
- `DealTech/local_cases/fronthera_2021` — exists: yes; files: 2309
- `DealTech/runs/fronthera_2021_live_sourced` — exists: yes; files: 3

### Code sources
- `DealTech/buyer_side_acquisition_loop_agent` — exists: yes; files: 107
- `DealTech/agents/agents/buyer_side_acquisition_loop_agent` — exists: yes; files: 92

### Demo sources
- `DealTech/buyer-side-acquisition-loop-agent/06_examples/live_case_mvp` — exists: yes; files: 3

### Rebuild decision
- Keep main canonical files in the agent folder, and copy any older/noncanonical material into `legacy/recovered_materials/` with source path preserved.
- Add this agent to `docs/prompt_inventory.md`, `docs/case_inventory.md`, and `docs/demo_inventory.md` before any push.

## Merger Strategy Agent

- Recommended canonical rebuild path: `agents/merger-strategy-agent/`
- Best primary version to use: `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/merger-strategy-agent/`
- Current interpretation: Framework-only. No real merger case should be claimed. Keep as pending real case / framework demo only unless new materials are found.

### Earlier / supporting versions
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/merger-strategy-agent` — exists: yes; files: 44
- `DealTech/agents/agents/merger-strategy-agent` — exists: yes; files: 44

### Prompt sources
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/merger-strategy-agent/03_prompts` — exists: yes; files: 2

### Business workflow sources
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/merger-strategy-agent/01_business_workflow` — exists: yes; files: 6

### Case study / output sources
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/merger-strategy-agent/07_case_studies/_framework_only_run` — exists: yes; files: 3

### Code sources
- `Certified-Deep-Research-Agents-for-AI-Native-DealTech/agents/merger-strategy-agent/src` — exists: yes; files: 8

### Demo sources
- `[missing / none found yet]`

### Rebuild decision
- Keep main canonical files in the agent folder, and copy any older/noncanonical material into `legacy/recovered_materials/` with source path preserved.
- Add this agent to `docs/prompt_inventory.md`, `docs/case_inventory.md`, and `docs/demo_inventory.md` before any push.

## Cross-agent version anchors

- Early Shell white-box structure: `HK_Shell_Screening_Agent_v0.1/`
- Shell full workflow package: `deliverables/HK_Shell_Screening_Agent_FULL_WORKFLOW_v0.4/`
- Certified shell cleaned lineage: `certified-shell-company-screening-agent/` and deliverable copies
- Early SPAC/Soren package: `US_SPAC_Target_Acquisition_Agent_v1/`
- Unified multi-agent repository: `Certified-Deep-Research-Agents-for-AI-Native-DealTech/`
- Current public GitHub checkout: `DealTech/`
- Buyer-side loop rc1 release: `DealTech/agents/agents/buyer-side-acquisition-loop-agent/RELEASE_INVENTORY.md` and root `DealTech/buyer-side-acquisition-loop-agent/`
- Full rescue package: `rescue_dealtech_20260723/` and `rescue_dealtech_20260723.zip`

## Open questions for manual核对

- Acquisition Strategy has working case/demo/code, but visible prompt set may only be `system_prompt.md`; check whether earlier detailed buyer/target prompts exist in chats or unindexed notes.
- Demo publication targets should be decided: keep GitHub Pages demos in same repo under `demos/`, or separate Pages repos with links from main DealTech.
- Public-safety boundary for FronThera live run traces: final outputs can be public; raw provider traces/local confidential attachments should remain recovered or excluded unless reviewed.
