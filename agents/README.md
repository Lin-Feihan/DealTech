# Certified Deep Research Agents for AI-Native DealTech

This repository contains **certified deep research agents for AI-native DealTech**.

Each business agent follows its own M&A workflow but shares the same ER/BRB screening and PCE certification discipline.

The goal is **not polished report generation**, but separating evidence-backed claims from claims requiring human review.

## Agent maturity table

| Agent | Maturity / status |
|---|---|
| Shell Company Screening Agent | gold-standard complete case; `Certified with Caveat` |
| SPAC Target Acquisition Agent | upgraded screening workflow; status depends on source replay |
| Acquisition Strategy Agent | buyer-side / target-side partial certification; valuation/fairness/recommendation require human review |
| Merger Strategy Agent | framework only / not modified in this task |

## Import wrapper note

Directories using underscores such as `agents/spac_target_acquisition_agent/` and `agents/acquisition_strategy_agent/` are Python import wrappers for the runnable package layout. Case-specific files remain under the hyphenated agent directories in `07_case_studies/`.

## Repository layout

```text
Certified-Deep-Research-Agents-for-AI-Native-DealTech/
├── README.md
├── requirements.txt
├── pyproject.toml
├── run_agent.py
├── repository_status.md
├── dealtech_certification/              # shared runnable certification engine
├── agents/
│   ├── shell-company-screening-agent/   # Shell / TonTon gold-standard case assets
│   ├── spac-target-acquisition-agent/   # SPAC / Soren migrated case overlay
│   ├── acquisition-strategy-agent/      # buyer-side and target-side runnable views
│   └── merger-strategy-agent/           # flowchart-integrated framework output
├── examples/sample_outputs/             # command outputs captured from real runs
└── tests/                               # root tests; agent tests live under agents/*/tests
```

## Install

```bash
pip install -r requirements.txt
```

## Unified runner

```bash
python run_agent.py --agent shell-company-screening --case case_001_tonton_shell_company_screening
python run_agent.py --agent spac-target-acquisition --case case_001_soren_spac_target_acquisition
python run_agent.py --agent acquisition-strategy --case case_001_acquisition_strategy --view buyer_side
python run_agent.py --agent acquisition-strategy --case case_001_acquisition_strategy --view target_side
python run_agent.py --agent merger-strategy
```

Each runnable case/view generates or updates:

- `certification_result.json`
- `ER_BRB_case_result.md`
- `PCE_case_result.md`
- `ER_BRB_result.md` compatibility copy
- `PCE_result.md` compatibility copy
- `final_output.md`

## Test

`pyproject.toml` configures default pytest discovery to cover both:

```text
tests/
agents/*/tests/
```

Run:

```bash
pytest -q
```

Latest verification in this workspace: **78 passed**.

## What the code actually does

For each runnable case/view, the workflow performs:

1. Load `source_registry.md` / `.csv`.
2. Load `evidence_table.md` / `.csv`.
3. Load `claim_to_evidence_map.csv` / `.md`, or derive a claim map from evidence where appropriate.
4. Execute ER/BRB with unified fields: `claim_id`, `claim_text`, `evidence_id`, `source_id`, `evidence_reliability`, `business_risk`, `regulatory_risk`, `reputational_risk`, `certification_status`, `human_review_required`, `reason`.
5. Execute claim-level PCE with source existence, source PCE eligibility, imported-artifact detection, LLM-summary rejection, source-replay-pending checks, evidence existence, calculation replay requirements, human-review flags, and final-output caveat checks.
6. Write generated output files, plus a scoped shell-claim audit sample when supporting trace files are available.

## Current agent status

| Agent | Case/View | Actual status |
|---|---|---|
| Shell Company Screening | TonTon / Tuntun | Gold-standard runnable case; `Certified with Caveat` |
| SPAC Target Acquisition | Soren | Migrated case with certification overlay; `Needs Human Review` |
| Acquisition Strategy | Buyer-side | Runnable buyer-side view; `Needs Human Review / Source replay pending` |
| Acquisition Strategy | Target-side | Runnable target-side view; `Needs Human Review / Source replay pending` |
| Merger Strategy | Framework | Business workflow integrated from provided flowchart; real case input pending |

## Shell / TonTon gold-standard case

The Shell / TonTon case now reads real supporting workflow files, including:

- `candidate_universe_table.csv`
- `hard_filter_table.csv`
- `dd_evidence_table.csv`
- `er_brb_scoring_table.csv`
- `risk_matrix.csv`
- `financial_calculation_sheet.csv`
- `claim_to_evidence_map.csv`
- `pce_audit_current_run.csv`

The command output includes business workflow statistics such as candidate universe count, hard-filter pass/fail count, DD evidence record count, risk matrix item count, calculation sheet row count, PCE audit row count, human-review count, and final certification status.

## SPAC / Soren case

The SPAC / Soren case runs the overlay workflow and remains honest:

- No authenticated Apify run was executed in this version.
- Imported artifact is not primary evidence by itself.
- Overall status: `Needs Human Review`.

A connector design stub is included at `agents/spac-target-acquisition-agent/src/apify_connector.py` for future authenticated Apify integration.

## Acquisition Strategy buyer-side / target-side

The two views run separately and do not mix claims or outputs.

Buyer-side focus:

- strategic rationale
- target attractiveness
- synergy assessment
- valuation / pricing
- integration risk
- go / no-go recommendation

Target-side focus:

- offer attractiveness
- standalone case
- strategic alternatives
- fairness assessment
- deal certainty
- accept / reject / negotiate recommendation

Valuation, pricing, fairness, and recommendation claims remain Human Review Required until source replay and calculation replay are complete.

## Merger Strategy framework

The Merger Strategy Agent has the provided flowchart integrated into:

- `workflow_overview.md`
- `workflow_steps.md`
- `decision_points.md`
- `workflow_diagram.md`
- `workflow_diagram.mmd`
- `src/workflow.py`

Current status: **Business workflow integrated from provided flowchart; ER/BRB and PCE framework ready; real case input pending.**

No merger case facts, valuation, synergies, antitrust conclusions, or final recommendations are fabricated.
