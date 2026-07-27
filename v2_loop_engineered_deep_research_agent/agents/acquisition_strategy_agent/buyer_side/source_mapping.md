# Source Mapping

## Purpose

This file maps the V2 buyer-side acquisition strategy agent bundle to its V1 source baseline.

V2 does not replace V1. It wraps the V1 assets in a loop-engineered runtime-ready structure.

## V1 Sources

| V2 Use | V1 Source |
|---|---|
| Business workflow basis | `../../../../agents/acquisition-strategy-agent/01_business_workflow/flowcharts/buyer-flowchart.jpg` |
| Human-readable prompt baseline | `../../../../agents/acquisition-strategy-agent/02_prompts/buyer_acquisition_strategy_prompt.md` |
| Structured workflow baseline | `../../../../agents/acquisition-strategy-agent/02_prompts/buyer_acquisition_strategy_agent.json` |
| Demo context only, not V2 case study | `../../../../agents/acquisition-strategy-agent/03_case_studies/apple_darwinai_reports/` |

## Copied Into V2 Bundle

The following V1 assets are copied into the V2 buyer-side bundle so a future runner can load a self-contained agent package:

| Local V2 File | Source |
|---|---|
| `prompt.md` | V1 buyer natural-language prompt |
| `workflow.json` | V1 buyer structured workflow spec |

## Not Included

The prior Apple / DarwinAI demo report is not included as a V2 case study.

Reason: the user plans to provide a new case for V2 testing after the agent bundle is complete.

## Transformation From V1 To V2

V1 provides:

- research prompt
- workflow modules
- required report sections
- required tables
- guardrails

V2 adds:

- loop state
- research gap prioritization
- claim-evidence graph schema
- certification policy
- calculation replay requirements
- report manifest
- human-review governance
- runtime output contract
