# Quick start

Prerequisites: Python 3.11 or newer. From the repository root:

```bash
python -m venv .venv
python -m pip install -e ".[test]"
```

Validate and run the public recorded case without network research:

```bash
buyer-side-acquisition-loop --case agents/agents/buyer-side-acquisition-loop-agent/06_examples/recorded_full_pipeline_case/case.yaml --check-case
buyer-side-acquisition-loop --case agents/agents/buyer-side-acquisition-loop-agent/06_examples/recorded_full_pipeline_case/case.yaml --module FULL_PIPELINE
```

Resume an interrupted run:

```bash
buyer-side-acquisition-loop --resume-run agents/agents/buyer-side-acquisition-loop-agent/06_examples/recorded_full_pipeline_case/run_output
```

Individual A/B/C cases remain runnable with `--module BLOCK_A`, `BLOCK_B` or `BLOCK_C`. Human Review resumes use `--human-review-response`. Run the release checks with `python scripts/verify_buyer_side_agent_release.py`.

For Human Review, first run the case to create its paused workspace, then apply one structured response:

```bash
buyer-side-acquisition-loop --case agents/agents/buyer-side-acquisition-loop-agent/06_examples/synthetic_human_only_information_case/case.yaml
buyer-side-acquisition-loop --case agents/agents/buyer-side-acquisition-loop-agent/06_examples/synthetic_human_only_information_case/case.yaml --human-review-response agents/agents/buyer-side-acquisition-loop-agent/06_examples/synthetic_human_only_information_case/valid_human_review_response.json
```

Accepted response IDs are append-only and cannot be replayed.

The machine Decision State is decision support, not authorized transaction approval.
