# Buyer-side Acquisition Loop Agent v0.1.0-rc1

This independent buyer-side agent runs a complete recorded acquisition workflow:

```text
Case Intake → Mandate → Research Contract
→ Block A (A1–A7) → Gate A
→ Block B (B1–B5) → calculation replay → Gate B
→ Block C (C1–C5) → Gate C → Decision State
→ Final Acquisition Strategy Report → Final Delivery Verification
```

Gate failures enter one targeted loop: Gap Diagnosis → Memory Update → Loop Controller → Re-plan → return only to the affected module and its dependencies. The recorded public demo executes all 17 M&A modules and the three existing repair patterns under one case ID and run ID.

Provider execution, PCE, ER/BRB, business Gates and the Loop Controller have separate authority. Providers propose research objects. PCE controls Claim delivery. ER/BRB records evidence-row reliability and risk signals. Gates apply acquisition business criteria. The Loop Controller selects the permitted repair path. None of these grants final transaction approval.

## Start here

From the repository root:

```bash
python -m pip install -e ".[test]"
buyer-side-acquisition-loop --case agents/agents/buyer-side-acquisition-loop-agent/06_examples/recorded_full_pipeline_case/case.yaml --check-case
buyer-side-acquisition-loop --case agents/agents/buyer-side-acquisition-loop-agent/06_examples/recorded_full_pipeline_case/case.yaml --module FULL_PIPELINE
```

Resume an interrupted full run after validating its manifest and hashes:

```bash
buyer-side-acquisition-loop --resume-run agents/agents/buyer-side-acquisition-loop-agent/06_examples/recorded_full_pipeline_case/run_output
```

Initialize a supported Human Review case, then apply its structured response once to the paused workspace:

```bash
buyer-side-acquisition-loop --case agents/agents/buyer-side-acquisition-loop-agent/06_examples/synthetic_human_only_information_case/case.yaml
buyer-side-acquisition-loop --case agents/agents/buyer-side-acquisition-loop-agent/06_examples/synthetic_human_only_information_case/case.yaml --human-review-response agents/agents/buyer-side-acquisition-loop-agent/06_examples/synthetic_human_only_information_case/valid_human_review_response.json
```

Human Review history is append-only, so a previously accepted `response_id` cannot be applied again.

The equivalent module entry point is `python -m buyer_side_acquisition_loop_agent`. Individual recorded Block A/B/C fixtures remain runnable with `--module BLOCK_A`, `BLOCK_B` or `BLOCK_C`.

## Provider and attachment boundaries

`recorded` mode is deterministic and makes no research network request. `openai_live` provider code is implemented and requires the optional SDK, environment configuration, explicit case and attachment permissions, valid budgets and `--enable-live`. It has **not** received a paid end-to-end validation and is not enabled in CI.

Supported attachment extensions are `.pdf`, `.txt`, `.md`, `.html`, `.csv` and `.xlsx`. Non-macro, unencrypted `.xlsx` extraction is restricted to the explicit local Block B boundary. Confidential files may be processed locally only when authorized and may remain forbidden from provider upload.

## Outputs and authority

The full local trace contains stage research, Source–Evidence–Claim lineage, counterevidence, calculations/replays, Gate histories, loop records, PCE, ER/BRB and Human Review items. The curated public sample contains only the report, run summary, Gate results, Decision State, delivery verification, manifest and cross-block consistency result.

The machine Decision State is decision support, not final human approval. Delivery permission means the caveated report passed delivery controls; it does not approve price, financing, risk acceptance or the transaction.

See `QUICKSTART.md`, `ARCHITECTURE.md`, `CASE_INPUT_GUIDE.md`, `EVIDENCE_AND_CERTIFICATION.md`, `HUMAN_REVIEW_GUIDE.md` and `KNOWN_LIMITATIONS.md` for concise operational guidance.
