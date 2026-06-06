# Certified Deep Research Agents for AI-Native DealTech

## Overview

**Certified Deep Research Agents for AI-Native DealTech** is a research-oriented prototype that explores how AI agents can support complex transaction research in M&A, shell company screening, SPAC target screening, acquisition strategy, and merger strategy.

The project focuses on a core question:

> How can deep research agents move beyond final report generation and become traceable, auditable, and certifiable research systems for AI-native DealTech?

Instead of treating AI as a one-step writing tool, this project designs agents as structured research workflows. Each agent is expected to generate intermediate artifacts, preserve evidence chains, record risk judgments, support human review, and pass a certification layer before producing final deliverables.

---

## Project Scope

This repository is organized around four certified deep research agents:

```text
Certified Deep Research Agents for AI-Native DealTech
├── Shell Company Screening Agent
├── SPAC Target Screening Agent
├── Acquisition Strategy Agent
└── Merger Strategy Agent
```

These agents cover three typical M&A-related business scenarios:

1. **Shell-related transactions**
   Screening listed shell companies for asset injection, control-path arrangement, business restructuring, or screening private targets for SPAC business combinations.

2. **Acquisition transactions**
   Supporting both buyer-side and seller-side acquisition analysis, including target evaluation, strategic fit, valuation reasonableness, transaction feasibility, and negotiation alternatives.

3. **Merger transactions**
   Assessing whether two companies or business units can create strategic value through combination, synergy realization, governance design, and integration planning.

---

## Core Design Principle

The project follows a workflow-first design principle:

> The value of an AI-native DealTech system is not only the final output, but the certified research trace behind that output.

A final report, shortlist, or transaction memo should not be accepted simply because it is fluent or complete. It should be supported by a structured research process that records:

```text
- user mandate
- research boundary
- source materials
- candidate universe
- screening logic
- due diligence evidence
- risk flags
- calculation records
- claim-to-evidence mapping
- human review status
- final delivery readiness
```

---

## Workflow and Certification Logic

The system is organized around one simple logic:

```text
Research Input
→ Agent Execution
→ Certified Research Trace
→ Certification Gate
→ Final Deliverable
```

### 1. Research Input

The workflow begins with a clearly defined research mandate. This includes the transaction background, user requirements, screening objectives, risk preferences, and research boundaries.

The purpose of this stage is to make sure the agent understands what it is solving, what it should not assume, and what criteria should guide the research process.

### 2. Agent Execution

The agent then performs the research task through a structured workflow. Depending on the agent type, this may include candidate pool construction, source retrieval, hard filtering, due diligence analysis, risk identification, financial calculation, strategic assessment, and report drafting.

This stage is supported by standardized prompts, source materials, agent configuration files, data schemas, and output formats.

### 3. Certified Research Trace

During execution, the agent must preserve a complete research trace rather than only producing a final answer.

The certified research trace may include:

```text
- candidate pool
- screening table
- hard filter results
- due diligence evidence
- risk matrix
- ER/BRB assessment
- claim-to-evidence map
- calculation records
- human review notes
- run logs
```

This trace is the core evidence layer of the system. It allows the research process to be reviewed, audited, corrected, and reproduced.

### 4. Certification Gate

Before any final output is delivered, the research trace must pass a certification gate.

This gate checks whether the research process is complete, evidence-supported, risk-aware, and ready for delivery. It also checks whether key claims are backed by sources, whether calculations can be reproduced, and whether uncertain or high-risk conclusions require human review.

The core principle is:

> Generation does not equal permission.

An agent can generate a shortlist, research memo, or transaction recommendation, but that output should not automatically become a final deliverable.

### 5. Final Deliverable

Only after the research trace passes certification can the system produce final outputs such as screening reports, investment memos, management presentation materials, due diligence packages, or case study summaries.

---

## PCE Framework

The certification logic is implemented through the PCE framework:

```text
Proposal → Certification → Execution
```

### Proposal

The agent proposes a research result. This includes the intermediate evidence, preliminary judgments, risk flags, calculations, and draft recommendations generated during the research process.

### Certification

The certification layer reviews the research trace. It decides whether the result is ready for delivery, needs revision, requires human escalation, or should be rejected.

### Execution

Execution means converting a certified research trace into a final deliverable. In this framework, final delivery is allowed only after the research process has been checked and approved.

In short:

```text
Proposal = the agent generates the research trace.
Certification = the system checks whether the trace is reliable.
Execution = the approved trace becomes the final output.
```

---

## ER/BRB Decision Layer

The project also explores an internal decision layer based on:

```text
Evidential Reasoning / Belief Rule Base
```

This layer is used for uncertain and multi-criteria business judgments. Instead of reducing every candidate to a single weighted score, ER/BRB represents judgment as interpretable decision states.

Examples include:

```text
- Pass
- Need Further Due Diligence
- Exclude
- Insufficient Evidence
```

This is useful in transaction research because many decisions depend on incomplete information, conflicting evidence, regulatory uncertainty, qualitative judgment, and risk tolerance.

In practice, the ER/BRB layer helps the agent answer five questions:

```text
1. Can this candidate enter the next stage?
2. What are the main risk factors?
3. Which evidence is strong, weak, missing, or conflicting?
4. Which conclusions require human review?
5. Is the final recommendation sufficiently supported?
```

For example, in shell company screening, ER/BRB can first support hard-filter decisions, such as whether a listed company should pass, be excluded, or require further due diligence. In later stages, it can help evaluate control-path feasibility, capital structure risk, disclosure quality, regulatory exposure, business compatibility, and transaction feasibility.

The goal is to make the agent’s judgment more transparent, explainable, and auditable.

---

## Technical Architecture

The current prototype is designed around the following technical stack:

```text
- GPT-5.5
- OpenClaw
- Context Engineering
- FastAPI
- Postgres
- Static / Portable Web Frontend
```

OpenClaw is used for agent orchestration and workflow scheduling. Context engineering organizes inputs, source materials, prompts, and intermediate files. FastAPI supports backend service interfaces. Postgres stores structured states and intermediate results. Static or portable web frontends support demo presentation and result interaction.

---

## Research Contribution

This project argues that the future moat of AI-native DealTech is not only the model itself, but the certified research trace behind the model output.

The key contributions include:

```text
1. A workflow-first framework for AI-native transaction research.
2. A certified research trace for evidence preservation and auditability.
3. A PCE workflow that separates generation from delivery authorization.
4. An ER/BRB layer for uncertain, multi-criteria business judgment.
5. A multi-agent portfolio covering shell screening, SPAC target screening, acquisition strategy, and merger strategy.
6. A process-oriented educational framework for understanding complex M&A decisions.
```

---

## Disclaimer

This repository is for academic research, prototype development, and educational demonstration only. It does not constitute investment advice, legal advice, financial advice, or transaction recommendation. Any real-world transaction decision should be reviewed by qualified professionals.
