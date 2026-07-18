# v0.1.0-rc1 release inventory

## Intended GitHub change set

Include these root release files:

- `.gitignore`
- `README.md`
- `AGENTS.md`
- `pyproject.toml`
- `.github/workflows/buyer-side-acquisition-loop-agent.yml`
- `scripts/prepare_buyer_side_agent_sample.py`
- `scripts/verify_buyer_side_agent_release.py`

Include the complete importable new-agent package:

- `agents/agents/buyer_side_acquisition_loop_agent/`

Include these public asset groups under `agents/agents/buyer-side-acquisition-loop-agent/`:

- `.env.example` and `requirements-live.txt`
- `README.md`, `QUICKSTART.md`, `ARCHITECTURE.md`, `CASE_INPUT_GUIDE.md`, `EVIDENCE_AND_CERTIFICATION.md`, `HUMAN_REVIEW_GUIDE.md` and `KNOWN_LIMITATIONS.md`
- `RELEASE_CHECKLIST.md` and `RELEASE_INVENTORY.md`
- `01_business_workflow/`
- `03_prompts/`
- `04_schemas/`
- `tests/`
- public recorded, synthetic and live-case templates under `06_examples/`, excluding every `run_output/`
- the nine curated artifacts in `06_examples/recorded_full_pipeline_case/sample_output/`
- only the blank `06_examples/teacher_case_template/case.yaml` and `06_examples/teacher_case_template/attachment_manifest.json` teacher-case templates

The recorded Block B fixture `06_examples/recorded_block_b_case/attachments/target_financials.xlsx` is an intentional 4,135-byte binary required to verify bounded local XLSX ingestion.

## Curated public sample

`06_examples/recorded_full_pipeline_case/sample_output/` contains exactly:

- `final_acquisition_strategy_report.md`
- `run_summary.json`
- `gate_a_result.json`
- `gate_b_result.json`
- `gate_c_result.json`
- `decision_state.json`
- `final_delivery_verification.json`
- `run_manifest.json`
- `cross_block_consistency_result.json`

The manifest documents that full research traces are intentionally not published. All sample paths are repository-relative and all eight JSON files parse.

## Explicit exclusions

Exclude:

- `.codex/` and all other local editor or Codex state
- `agents/docs/acquisition-loop-upgrade/`
- local `PRE_RELEASE_AUDIT.md` and `pre_release_audit.json` working notes
- every unrestricted `**/run_output/`
- every `**/raw_live_provider_responses/` and `**/local_confidential_attachments/`
- `.env`, `.env.*` other than the named public `.env.example`, API keys and credentials
- virtual environments, editable-install metadata, caches, bytecode, temporary files and test scratch directories
- confidential user attachments, raw live-provider output and teacher-case facts or data
- local absolute paths
- generated legacy test changes

The following protected legacy paths are unchanged and are not part of this release change set:

- `agents/agents/acquisition-strategy-agent/`
- `agents/agents/acquisition_strategy_agent/`
- `agents/dealtech_certification/`
- `.codex/`

## Pending owner decisions

- No `LICENSE` file is present. Apache-2.0 is recommended, but explicit repository-owner approval is required before adding it.
- Paid live validation has not been performed.
- CI is `LOCALLY VALIDATED, NOT YET RUN ON GITHUB ACTIONS`.
