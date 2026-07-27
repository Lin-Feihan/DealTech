# Acquisition Strategy Agent V2

## Scope

This folder contains the V2 loop-engineered Acquisition Strategy Agent.

The first implemented perspective is buyer-side acquisition strategy.

## Agent Bundle

```text
buyer_side/
├── agent.config.json
├── source_mapping.md
├── prompt.md
├── workflow.json
├── loop_policy.json
├── certification_policy.json
├── report_writer_policy.json
├── output_contract.json
├── runbook.md
└── case_studies/
    └── README.md
```

## V1 Relationship

The buyer-side V2 bundle uses the V1 buyer-side acquisition strategy prompt and structured workflow as its source baseline, then adds loop policy, certification policy, report-writer policy, and output contracts.

V1 remains preserved at:

```text
agents/acquisition-strategy-agent/
```

## Runtime Status

The V2 bundle now includes an executable, standard-library Python runtime for the post-certification half of the workflow:

```text
certified claims + supporting files
-> 15 structured section-analysis objects
-> recommendation decision gate
-> professional report
-> report manifest + research gaps + human-review items
```

Run it from the repository root:

```bash
python3 v2_loop_engineered_deep_research_agent/runtime/run_agent.py \
  --case-dir /path/to/certified_case \
  --output-dir /path/to/output \
  --json
```

Automated research retrieval, evidence graph construction, and claim certification remain upstream interfaces and are not yet implemented by this runner.

No case study is included yet.
