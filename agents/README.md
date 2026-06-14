# Certified Deep Research Agents for AI-Native DealTech

This repository contains certified deep research agents for AI-native DealTech.

Each business agent follows its own M&A workflow but shares the same ER/BRB screening and PCE certification discipline. The goal is not polished report generation, but separating evidence-backed claims from claims requiring human review.

## Agent Maturity

| Agent | Current maturity | Certification status |
|---|---|---|
| Shell Company Screening Agent | Gold-standard complete case | `Certified with Caveat` |
| SPAC Target Acquisition Agent | Partially source-replayed screening case | `Needs Human Review` |
| Acquisition Strategy Agent | Buyer-side / target-side partial certification | `Needs Human Review` |
| Merger Strategy Agent | Framework only | Real case input pending |

## Repository Layout

```text
README.md
LICENSE
requirements.txt
pyproject.toml
run_agent.py
limitations.md
agents/
  shell-company-screening-agent/      # canonical business folder
  spac-target-acquisition-agent/      # canonical business folder
  acquisition-strategy-agent/         # canonical business folder
  merger-strategy-agent/              # canonical business folder
  shell_company_screening_agent/      # Python import compatibility wrapper
  spac_target_acquisition_agent/      # Python import compatibility wrapper
  acquisition_strategy_agent/         # Python import compatibility wrapper
  merger_strategy_agent/              # Python import compatibility wrapper
dealtech_certification/               # shared runnable certification engine
docs/                                 # reviewer-facing project docs
examples/                             # sample inputs, outputs, ER/BRB tables, PCE results
shared/                               # shared schemas, templates, and certification policies
tests/                                # root integration and certification tests
```

Hyphen folders are canonical business agent folders; underscore folders are Python import compatibility wrappers.

## What Is Preserved

Each canonical business agent keeps the materials needed for reviewer inspection and runnable certification:

- business workflow, prompts, source registries, schemas, ER/BRB rules, PCE rules, logs, source/evidence/claim maps, and case studies
- case outputs including `research_trace.md`, `ER_BRB_result.md`, `PCE_result.md`, `final_output.md`, `final_delivery_certificate.md`, `scoped_claim_audit_result.md`, and `certification_result.json`
- supporting files for the Shell, SPAC, and Acquisition Strategy cases, including PCE audits, ER/BRB scoring, risk matrices, calculation sheets, and trace tables

## Install

```bash
pip install -r requirements.txt
```

## Run Agents

```bash
python run_agent.py --agent shell-company-screening --case case_001_tonton_shell_company_screening
python run_agent.py --agent spac-target-acquisition --case case_001_soren_spac_target_acquisition
python run_agent.py --agent acquisition-strategy --case case_001_acquisition_strategy --view buyer_side
python run_agent.py --agent acquisition-strategy --case case_001_acquisition_strategy --view target_side
python run_agent.py --agent merger-strategy
```

Each runnable case/view writes or refreshes:

- `certification_result.json`
- `ER_BRB_case_result.md` and `ER_BRB_result.md`
- `PCE_case_result.md` and `PCE_result.md`
- `final_output.md`

## Test

```bash
pytest -q
```

Latest verification for this clean repository version: `78 passed`.

## Certification Discipline

The shared engine performs claim-level review across source existence, source PCE eligibility, imported-artifact handling, source-replay status, evidence existence, calculation replay, human-review flags, and final-output caveats.

Important boundaries:

- imported artifacts are not primary evidence by themselves
- source-replay-pending claims cannot become cleanly certified
- secondary public reporting can support caveated factual claims, not deal economics or recommendation claims
- valuation, fairness, synergy, EPS, go/no-go, and accept/reject/negotiate claims remain blocked or human-review-required unless proper source replay and calculation replay are complete

## Current Agent Status

| Agent | Case/View | Actual status |
|---|---|---|
| Shell Company Screening | TonTon / Tuntun shell-company screening | Gold-standard runnable case; `Certified with Caveat` |
| SPAC Target Acquisition | Soren SPAC target acquisition | Partially source-replayed screening structure; `Needs Human Review` |
| Acquisition Strategy | Apple → DarwinAI buyer-side view | Partial caveated certification; `Needs Human Review` |
| Acquisition Strategy | Apple → DarwinAI target-side view | Partial caveated certification; `Needs Human Review` |
| Merger Strategy | Framework-only merger workflow | Framework only; no case facts certified |

## Reviewer Docs

Useful reviewer-facing docs live under `docs/`, including:

- `docs/01_project_overview.md`
- `docs/02_system_architecture.md`
- `docs/05_ER_BRB_framework.md`
- `docs/06_PCE_framework.md`
- `docs/07_case_study_standard.md`
- `docs/08_limitations_and_human_review.md`
- `docs/agent_completion_gap_report.md`

See `limitations.md` for the repository-level certification boundary and human-review constraints.
