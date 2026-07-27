# DealTech Rebuild Source Decisions - 2026-07-23

This file records the user's current rebuild rules after the rescue/crosscheck discussion.

## Hard Decisions From User

1. Do not use `Certified-Deep-Research-Agents-for-AI-Native-DealTech/` as a trusted primary source for the rebuild.
   - It may remain in rescue materials/rescue evidence if needed, but it should not drive canonical structure or content.

2. Do not use the buyer-side acquisition loop agent as the requested buyer-side acquisition agent version.
   - Exclude `DealTech/buyer-side-acquisition-loop-agent/` and `DealTech/agents/agents/buyer-side-acquisition-loop-agent/` from the canonical buyer-side acquisition rebuild.
   - These may be rescue materialsd separately as later experimental/loop work.

3. Merger strategy agent should remain framework-only for now.
   - Do not fabricate a real case study or demo.

## Current Primary Source Candidates By Agent

### Shell Company Screening Agent

Primary candidates:
- `HK_Shell_Screening_Agent_v0.1/`
- `deliverables/HK_Shell_Screening_Agent_FULL_WORKFLOW_v0.4/`
- `certified-shell-company-screening-agent/`
- demo sources: `shell-screening-demo/`, `shell-demo-deploy/`, `shell-demo-pkg/`, `deliverables/shell-screening-demo-share/`

Open point:
- Decide whether canonical Shell should be based on full workflow v0.4 or certified-shell cleaned repo, with older v0.1 preserved as white-box lineage.

### SPAC Target Acquisition Agent

Primary candidates:
- `US_SPAC_Target_Acquisition_Agent_v1/`
- output packages under `outputs/US_SPAC_Target_Acquisition_Agent_v1_*.zip`
- demo sources: `soren-spac-target-screening-demo/`, `deliverables/soren-spac-target-screening-demo/`

Open point:
- Decide which SPAC output zip/report is the canonical final Soren version: refined/no-estimates/updated/delivery.

### Acquisition Strategy Agent - Earlier Non-loop Version

Primary candidates:
- `acquisition_strategy_agents/`
- `acquisition-strategy-agent-portable-demo/`
- `deliverables/acquisition-strategy-agent-portable/`
- `deliverables/acquisition-strategy-agent-portable.zip`

Evidence:
- `buyer_acquisition_strategy_agent.json` and `target_acquisition_strategy_agent.json` are real agent specifications, not merely demo data.
- Each JSON includes purpose, input schema, clarification questions, 14-step workflow, output schema, decision logic, guardrails, and agent_id.
- Demo/report assets include Apple-DarwinAI buyer and target reports, HTML/PDF/MD, flowchart images, and local server demo.

Open point:
- Confirm whether this dual-perspective acquisition strategy agent is the intended earlier buyer-side acquisition agent, or whether there was another older buyer-only version outside these folders.

### Merger Strategy Agent

Decision:
- Keep framework-only.

Open point:
- If unified repo is excluded, confirm whether to use current framework files under `DealTech/agents/agents/merger-strategy-agent/` as placeholder framework source, or create only a minimal framework README until original merger flowchart/source is located.

## Rebuild Rule

Canonical repo should be built from non-unified source candidates first. Unified repo material should not be copied into canonical folders unless the user explicitly approves a specific file after comparison.
