# Certified Shell Company Screening Agent

A reusable Shell Company Screening Agent framework with configurable market adapters, internal ER/BRB decisioning, certified research trace, and PCE-based final delivery certification.

**This is not a report generator.**
**This is a certified research workflow for shell company screening.**

The repository separates the reusable framework from the current example case:

- Framework: `src/shell_company_screening_agent/`
- Configurable market adapters: `src/shell_company_screening_agent/data_sources/` and `configs/markets/`
- Current market adapter example: HK
- Current case example: `examples/tuntun_hk/`

## Why certified trace matters

Shell-company / listed-platform screening is evidence-heavy. A useful agent cannot jump from raw data directly to a final recommendation. It must preserve staged artifacts, uncertainty, evidence links, calculation replay, risk flags, and human-review gates.

## Workflow

```text
Mandate
 ↓
Market Adapter & Source Hierarchy
 ↓
Universe Construction
 ↓
Extraction & Normalization
 ↓
Hard Filter
 ↓
HF-level ER/BRB Decisioning
 ↓
Filtered Candidate Set
 ↓
Deep Due Diligence
 ↓
DD-level ER/BRB Decisioning
 ↓
Scoring / Ranking / Recommendation Draft
 ↓
Certified Research Trace
 ↓
PCE Certification Gate
 ↓
Certified Final Delivery
```

## Core concepts

| Concept | Meaning |
| --- | --- |
| Framework | Reusable shell company screening workflow and code. |
| Market adapter | Market-specific data/source implementation; HK is only the current adapter. |
| Case example | A concrete run under one market adapter; Tuntun HK is only an example. |
| ER/BRB | Internal decisioning mechanism used in Hard Filter and DD. |
| Certified Research Trace | Persistent staged artifacts that explain how the agent reached its draft conclusions. |
| PCE | Final delivery certification gate. |
| Final Delivery | Delivery materials that may cite only certified claims. |

## ER/BRB vs PCE

ER/BRB is an internal decisioning mechanism.

ER/BRB makes internal decisions.
PCE certifies whether those decisions can enter final delivery.

## Repository structure

```text
certified-shell-company-screening-agent/
├── src/shell_company_screening_agent/
├── configs/
├── prompts/
├── schemas/
├── docs/
├── examples/tuntun_hk/
├── scripts/
├── notebooks/
├── tests/
└── artifacts/
```

## How to run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python scripts/run_tuntun_hk_demo.py
pytest
```

The demo validates imported trace artifacts, replays supported calculations, runs PCE certification checks, updates delivery readiness, and writes a new run record under `examples/tuntun_hk/run_records/`.

## Tuntun HK example

The Tuntun HK case is a complete example under `examples/tuntun_hk/`. It includes imported trace tables from the original bundle and clean-repo validation/certification outputs. It is not the whole project and does not make the framework HK-only.

## Current workflow and certification boundary

```text
case_config.yaml
→ scripts/run_tuntun_hk_demo.py
→ pipeline.py
→ trace validation / supported calculation replay
→ claim_to_evidence_map refresh
→ PCE cross-check
→ final_delivery_gate
→ delivery outputs
→ run_records/<run_id>/
```

Each run writes `examples/tuntun_hk/run_records/<run_id>/trace_manifest.json` and labels artifacts as `pipeline_generated`, `pipeline_validated`, `imported_from_original_bundle`, `not_reproducible_currently`, or `needs_human_review`.

PCE is intentionally not an all-green stamp. Missing evidence, `needs_review`, metadata-only/title-level evidence, unreplayed calculations, and upstream human-review flags are downgraded to `Certified with Caveat`, `Internal Trace Only`, `Needs Human Review`, or `Not Certified` as appropriate.

Final delivery may use only explicit `CLM-*` material claims that exist in both `claim_to_evidence_map.csv` and the PCE audit with status `Certified` or `Certified with Caveat`.

## Adapting to another market

1. Add a market adapter under `src/shell_company_screening_agent/data_sources/<market>/`.
2. Add market config under `configs/markets/<market>/`.
3. Map fields to the common schemas in `schemas/`.
4. Add or adjust hard-filter and ER/BRB rules under `configs/decisioning/`.
5. Add a case under `examples/<case_id>/`.
6. Run trace validation and PCE certification before delivery.

## Data boundary and limitations

Current example artifacts are imported from the original working bundle and validated by this clean repository pipeline. The repository does not claim full live market-data regeneration unless the relevant data-source adapter is run with access to those sources. Claims that cannot be fully certified are marked with caveat, internal-trace-only, or human-review status.

## Disclaimer

This repository is for research workflow prototyping and technical demonstration. It is not investment, legal, tax, regulatory, financial-advisory, or transaction advice.
