# Repository Status — v1.0 Professional Runnable Repository

Default test command: `pytest -q` is configured in `pyproject.toml` to cover both root tests and agent tests: `tests/` and `agents/*/tests/`.

Latest local verification: `python3 -m pytest -q` — **78 passed**. The local shell does not expose the `pytest` console script on `PATH`, but the repository configuration is ready for the standard `pytest -q` command in a normal installed environment.

| Agent | Case/View | Runnable | Business Workflow Integrated | Data Loaded | ER/BRB Executed | PCE Executed | Output Generated | Certification Status | Remaining Limitation |
|---|---|---|---|---|---|---|---|---|---|
| Shell Company Screening | TonTon / Tuntun | Yes | Yes | Yes | Yes | Yes | Yes | Certified with Caveat | Human review remains for caveated claims; some trace rows are metadata-level or imported-package evidence. |
| SPAC Target Acquisition | Soren | Yes | Yes | Yes | Yes | Yes | Yes | Needs Human Review | Imported artifact; no authenticated Apify run; source replay pending. |
| Acquisition Strategy | Buyer-side | Yes | Yes | Yes | Yes | Yes | Yes | Needs Human Review | Valuation / pricing / recommendation claims require source replay and calculation replay. |
| Acquisition Strategy | Target-side | Yes | Yes | Yes | Yes | Yes | Yes | Needs Human Review | Fairness / board-response / recommendation claims require source replay and calculation replay. |
| Merger Strategy | Framework | Yes | Yes, from provided flowchart | No real case | Framework only | Framework only | Framework output | Case pending | Real case input pending. |

## Generated output locations

Each runnable case/view writes or updates these files in its case directory:

- `certification_result.json`
- `ER_BRB_case_result.md`
- `PCE_case_result.md`
- `ER_BRB_result.md` compatibility copy
- `PCE_result.md` compatibility copy
- `final_output.md`

For Shell / TonTon, the generated case directory also includes scoped sampled claim-audit artifacts:

- `scoped_claim_audit_sample.csv`
- `scoped_claim_audit_result.md`

Merger Strategy writes framework-only output under `agents/merger-strategy-agent/07_case_studies/_framework_only_run/`.

## Shell / TonTon gold-standard workflow metrics

The Shell / TonTon run now loads the real supporting trace files and reports business workflow metrics, including candidate universe count, hard-filter pass/fail count, DD evidence row count, risk matrix row count, calculation sheet row count, PCE audit row count, human-review count, and final certification status. It also appends a scoped external-delivery business-claim sample from `supporting_files/trace/claim_to_evidence_map.csv` joined to `supporting_files/pce_audit/pce_audit_current_run.csv`, while preserving the overall status `Certified with Caveat`.

## Honesty constraints preserved

- No agent is described as fully certified.
- Shell remains `Certified with Caveat`, not pure `Certified`.
- SPAC remains `Needs Human Review` and explicitly states: no authenticated Apify run was executed, and imported artifacts are not primary evidence by themselves.
- Acquisition buyer-side and target-side run separately and remain `Needs Human Review / Source replay pending`.
- Merger Strategy has the business workflow integrated from the provided flowchart, but no real case-run is claimed.
