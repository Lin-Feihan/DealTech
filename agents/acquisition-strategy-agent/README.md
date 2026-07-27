# Acquisition Strategy Agent

This folder preserves the earlier non-loop Acquisition Strategy Agent. It is based on the dual-perspective buyer/target agent specs and portable demo, not the later buyer-side acquisition loop agent.

## Source Lineage

- Main early agent source: `acquisition_strategy_agents/`
- Public demo reference: `03_case_studies/demo_README.md`

## Contents

- `01_business_workflow/flowcharts/` - buyer and target flowchart images.
- `02_prompts/buyer_acquisition_strategy_prompt.md` - buyer-perspective natural-language Deep Research prompt.
- `02_prompts/buyer_acquisition_strategy_agent.json` - derived buyer-perspective structured agent specification.
- `02_prompts/target_acquisition_strategy_prompt.md` - target/seller-perspective natural-language Deep Research prompt.
- `02_prompts/target_acquisition_strategy_agent.json` - derived target/seller-perspective structured agent specification.
- `03_case_studies/apple_darwinai_reports/` - Apple-DarwinAI buyer and target reports in available formats.
- `03_case_studies/demo_README.md` - public demo links and static/local technical notes.

## Status

Canonical rebuild status: preserved from earlier non-loop source. The buyer and target/seller prompts are retained as the human-readable Deep Research task layers. The buyer and target/seller JSON files have been rewritten from those prompts as machine-readable execution/workflow layers. The later acquisition loop agent is intentionally excluded from this canonical folder.

The earlier one-page dual-perspective prototype and portable demo process package have been removed from the formal agent directory. The public demo is represented only by `03_case_studies/demo_README.md`, which keeps the public links and technical notes without bundling local run artifacts.

## File Counts

- prompt/spec folder count: 4
- case-study folder count: 8
