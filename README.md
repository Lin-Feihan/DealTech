# Certified Deep Research Agents for AI-Native DealTech

## Overview

**Certified Deep Research Agents for AI-Native DealTech** explores how AI agents can support complex transaction research beyond one-step report generation.

The project focuses on M&A-related research tasks where outputs must be supported by evidence, intermediate artifacts, risk checks, and human-reviewable research traces.

The core idea is simple:

> AI agents should not only generate final reports. They should leave behind a certified research trail.

---

## Scope

This repository is organized around four deep research agents:

```text
Certified Deep Research Agents for AI-Native DealTech
├── Shell Company Screening Agent
├── SPAC Target Screening Agent
├── Acquisition Strategy Agent
└── Merger Strategy Agent
```

These agents cover three transaction research scenarios:

| Scenario | Research Focus |
|---|---|
| Shell-related transactions | Screening listed shell companies or SPAC acquisition targets |
| Acquisition transactions | Supporting buyer-side and seller-side acquisition analysis |
| Merger transactions | Assessing strategic rationale, synergy, governance, and integration feasibility |

---

## Why This Matters

Transaction research is evidence-intensive and judgment-heavy. It often requires:

- retrieving information from filings, annual reports, exchange disclosures, company websites, market data, and news;
- comparing candidates across financial, strategic, regulatory, and ownership dimensions;
- identifying risks, missing evidence, and judgment uncertainty;
- producing outputs that can be reviewed, audited, and corrected.

Traditional AI outputs are often difficult to verify because the reasoning path is hidden. This project treats the research process itself as the key asset.

---

## Core Workflow

The system follows a workflow-first structure:

```text
Mandate
→ Research Execution
→ Certified Research Trace
→ Certification Gate
→ Final Deliverable
```

### 1. Mandate

Defines the transaction background, user requirements, research scope, screening criteria, and risk preferences.

### 2. Research Execution

The agent performs structured research, such as candidate pool construction, source retrieval, hard filtering, due diligence, risk analysis, financial calculation, and report drafting.

### 3. Certified Research Trace

The agent preserves the intermediate artifacts behind the final output, including:

```text
- candidate pool
- screening table
- hard filter results
- due diligence evidence
- risk matrix
- claim-to-evidence map
- calculation records
- human review notes
- run logs
```

### 4. Certification Gate

Before final delivery, the research trace is checked for evidence quality, completeness, reproducibility, risk coverage, and human-review readiness.

### 5. Final Deliverable

Only certified research traces should be converted into final reports, investment memos, presentation materials, or due diligence packages.

---

## Certification Logic: PCE

The project uses a **Proposal → Certification → Execution** logic.

```text
Proposal      = the agent generates research results and supporting traces
Certification = an independent PCE layer checks the trace against Policy π
Execution     = only certified or caveated claims can enter the final deliverable
```

The principle is:

> Generation does not equal permission.

A generated report is not automatically ready for use. It must first pass a certification process.

In this repository, **Policy π** refers to the claim-level certification policy used by the PCE layer. It is not the same as the generator prompt. The generator proposes research outputs, while Policy π decides whether each claim is deliverable.

Conceptually:

```text
π(claim, source, evidence, ER/BRB result, calculation record, human-review flag)
→ certification status
```

The certification status can be:

```text
Certified
Certified with Caveat
Needs Human Review
Not Certified
Internal Trace Only
```

The PCE layer checks whether a claim has a registered source, specific evidence, sufficient source quality, replayable calculations when needed, preserved ER/BRB risk flags, and visible human-review boundaries.

Therefore, the system separates two roles:

```text
Generator Agent   = produces claims, evidence tables, calculations, and research traces
Certifying Layer  = applies Policy π and certifies, caveats, blocks, or escalates claims
```

At the current prototype stage, the certifier is implemented mainly as an independent PCE certification module or workflow rather than a fully separate LLM agent. However, it is separated from the generator in responsibility and logic. Future versions can package this PCE layer as a standalone certifying agent.

---

## Decision Logic: ER/BRB

The project also explores an internal decision layer based on **Evidential Reasoning / Belief Rule Base**.

Instead of forcing every candidate into a single score, ER/BRB represents judgment as explainable decision states:

```text
- Pass
- Need Further Due Diligence
- Exclude
- Insufficient Evidence
```

This is useful for M&A research because many decisions involve incomplete information, conflicting evidence, regulatory uncertainty, and qualitative business judgment.

ER/BRB helps the agent decide:

```text
- whether a candidate can enter the next stage
- which risks require further review
- which evidence is strong, weak, missing, or conflicting
- which conclusions require human escalation
- whether the final recommendation is sufficiently supported
```

---

## Demo Links

| Demo | Link |
|---|---|
| Shell Company Screening Agent | [Open Demo](https://462852416-glitch.github.io/shell-screening-agent-user-test-page/) |
| SPAC Target Acquisition Agent | [Open Demo](https://462852416-glitch.github.io/soren-spac-target-screening-demo/) |
| Acquisition Strategy Agent — Buyer Side | [Open Demo](https://462852416-glitch.github.io/acquisition-strategy-agent-portable-demo/buyer.html) |
| Acquisition Strategy Agent — Target Side | [Open Demo](https://462852416-glitch.github.io/acquisition-strategy-agent-portable-demo/target.html) |

---

## Technical Stack

The broader prototype is designed around the following stack:

```text
- GPT-5.5
- OpenClaw
- Context Engineering
- FastAPI
- Postgres
- Static / Portable Web Frontend
```

OpenClaw handles agent orchestration. Context engineering organizes prompts, inputs, sources, and intermediate files. FastAPI supports backend interfaces. Postgres stores structured states and intermediate results. Static or portable web frontends support demonstration and interaction.

The technical stack above describes the broader design direction and earlier prototypes in this repository. Earlier runnable prototypes remain available as prior implementation assets, while the current loop-engineered research runtime is packaged under `loop_engineered_deep_research_agent/`.

---

## Research Contribution

This project argues that the future moat of AI-native DealTech is not only the model, but the certified research trace behind the model output.

Key contributions include:

```text
1. A workflow-first framework for AI-native transaction research.
2. A certified research trace for evidence preservation and auditability.
3. A PCE certification logic that separates generation from delivery.
4. An ER/BRB decision layer for uncertain business judgment.
5. A multi-agent portfolio covering shell screening, SPAC target screening, acquisition strategy, and merger strategy.
```

---

## Loop-Engineered Deep Research Agent

The current DealTech loop-engineered research runtime is the **Loop-Engineered Deep Research Agent** package.

The package includes the **Buyer-Side Acquisition Strategy Agent**, which builds on the earlier Acquisition Strategy Agent while adding a controlled research and delivery layer: case intake, source-quality control, evidence lineage, claim-evidence certification, repair routing, buyer-side analysis, report gating, audit packaging, and final report rendering.

High-level workflow:

```text
Case Intake
→ Research Planning
→ Source and Evidence Collection
→ Claim and Evidence Mapping
→ Method Selection
→ Deal Analysis
→ Calculation Replay
→ Recommendation Decision
→ Report Generation
→ Certification Review
→ Final Delivery
```

The current package includes:

- the preserved buyer-side acquisition research baseline;
- loop-engineered policies for research, analysis, reporting, certification, and human review;
- structured schemas for mandates, claims, evidence, analysis packages, recommendations, and report manifests;
- a runnable Buyer-Side Acquisition Strategy Agent runtime;
- tests for mandate intake, external research handoff, evidence grounding, certification, repair routing, analysis packaging, report gating, audit packaging, and rendering.

This release should be viewed as the current **Loop-Engineered Deep Research Agent** baseline for DealTech, not yet a fully productionized autonomous transaction system.

| Resource | Link |
|---|---|
| Loop-Engineered Deep Research Agent | [Open Package README](loop_engineered_deep_research_agent/README.md) |
| Buyer-Side Acquisition Strategy Agent | [Open Agent README](loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/README.md) |
| Runtime | [Open Runtime](loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/runtime/) |
| Tests | [Open Tests](loop_engineered_deep_research_agent/buyer_side_acquisition_strategy_agent/tests/) |

---

## Disclaimer

This repository is for academic research, prototype development, and educational demonstration only. It does not constitute investment advice, legal advice, financial advice, or transaction recommendation. Any real-world transaction decision should be reviewed by qualified professionals.
