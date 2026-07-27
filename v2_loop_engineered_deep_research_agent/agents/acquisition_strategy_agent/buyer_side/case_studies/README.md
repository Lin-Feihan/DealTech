# Case Studies

No V2 case study is included in this initial architecture commit.

A future case study should be added only after the buyer-side agent bundle is reviewed and accepted.

The first V2 case study should use a new user-provided transaction case, not the prior Apple / DarwinAI V1 demo.

Recommended future structure:

```text
case_studies/
└── <case_id>/
    ├── input/
    │   └── mandate.json
    ├── planning/
    │   └── research_plan.json
    ├── loop_runs/
    │   ├── loop_state.json
    │   ├── research_gaps.json
    │   └── iteration_log.md
    ├── evidence/
    │   ├── evidence_repository.json
    │   └── claim_evidence_graph.json
    ├── certification/
    │   └── certification_results.json
    ├── analysis/
    │   └── investment_thesis.json
    └── output/
        ├── report_manifest.json
        └── final_report.md
```
