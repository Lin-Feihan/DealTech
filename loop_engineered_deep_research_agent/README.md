# Loop-Engineered Deep Research Agent

This directory contains Loop-Engineered Deep Research Agents for DealTech.

## Agents

### Buyer-Side Acquisition Strategy Agent

The Buyer-Side Acquisition Strategy Agent is a loop-engineered M&A research agent designed to support buyer-side acquisition analysis. The agent combines Deep Research capabilities with Loop Certification mechanisms to ensure that research outputs are evidence-grounded, traceable, and continuously improved through iterative research loops.

---

## M&A Agentic Workflow

The agent follows an evidence-driven M&A Agentic Workflow:

```text
User Mandate
      ↓
Research Planning
      ↓
External Deep Research
      ↓
Evidence Retrieval
      ↓
Evidence Repository Construction
      ↓
Claim–Evidence Graph Construction
      ↓
Loop Certification
      ↓
 ┌───────────────────────────────┐
 ↓                               ↓
Research Gap Diagnosis       Certified Evidence
      ↓                           ↓
Targeted Research Repair     Deal Analysis
      ↓                           ↓
External Deep Research        Professional Report Writer
                                  ↓
                          Case Library Update
```

---

## Workflow Description

### 1. User Mandate

The agent first converts the user's M&A research request into a structured mandate.

The mandate defines:

- Transaction objective
- Transaction type
- Research scope
- Key questions
- Constraints
- Expected outputs

---

### 2. Research Planning

Based on the User Mandate, the agent generates a structured research plan.

The planning stage defines:

- Research questions to answer
- Required source types
- Mandatory evidence requirements
- Claims requiring certification
- Conditions under which conclusions cannot be produced due to insufficient evidence

---

### 3. External Deep Research

The agent performs external research through iterative information retrieval, document analysis, and evidence discovery.

The research process focuses on:

- Source discovery
- Document retrieval
- Information extraction
- Preliminary evidence identification

External Deep Research provides research inputs for the downstream evidence processing pipeline.

---

### 4. Evidence Retrieval

Retrieved information is transformed into structured raw evidence.

This stage establishes the connection between external research outputs and the internal evidence pipeline.

---

### 5. Evidence Repository Construction

The agent organizes raw evidence into a structured evidence repository.

The repository maintains:

- Evidence normalization
- Evidence deduplication
- Source classification
- Temporal tagging
- Topic classification
- Research gap tracking
- Source provenance

---

### 6. Claim–Evidence Graph Construction

The agent transforms analytical statements into structured claims and links them with evidence.

The graph records:

- Supporting evidence
- Contradictory evidence
- Contextual evidence
- Unresolved evidence gaps

This enables traceable relationships between M&A conclusions and underlying evidence.

---

### 7. Loop Certification

Loop Certification validates the Evidence Repository and Claim–Evidence Graph before allowing downstream analysis.

The certification process evaluates:

- Evidence reliability
- Claim support
- Numeric reproducibility
- Temporal validity
- Severity of research gaps

The verification layer includes:

#### Source / Citation Verifier

Checks:

- Whether claims have source support
- Whether evidence is traceable to original sources
- Whether sources are appropriate for the intended judgment
- Citation completeness

#### Claim–Evidence Support Verifier

Checks:

- Whether claims are actually supported by evidence
- Whether information is only contextual background
- Whether partial support exists
- Whether contradictory evidence exists
- Whether caveats are required

#### Temporal Validity Verifier

Checks:

- Whether evidence timing is valid for the decision context
- Whether post-decision evidence is incorrectly used
- Whether hindsight leakage exists

#### Numeric Verification Verifier

Checks:

- Whether numerical sources are clear
- Whether calculations are reproducible
- Whether units are consistent
- Whether formulas are correct
- Whether derived numerical claims are properly identified

---

### 8. Research Gap Diagnosis & Targeted Research Repair Loop

If research outputs fail certification, the agent identifies unresolved research gaps.

The repair loop:

```text
Research Gap Diagnosis
          ↓
Targeted Research Repair
          ↓
External Deep Research
          ↓
Evidence Update
          ↓
Loop Certification
```

The agent performs targeted additional research until:

- Evidence requirements are satisfied
- Research quality reaches certification standards
- Human review is required
- Execution constraints are reached

---

### 9. Deal Analysis

If research outputs pass certification, the agent performs M&A analysis based on validated evidence.

The analysis includes:

- Strategic Rationale
- Business Quality
- Market Position
- Financial / Valuation Analysis
- Synergy Analysis
- Transaction Structure
- Ownership / Control
- Regulatory Risk
- Due Diligence Findings
- Alternatives Analysis
- Execution Feasibility
- Recommendation Logic

---

### 10. Professional Report Writer

The Professional Report Writer converts certified research outputs and deal analysis into professional deliverables.

Outputs include:

#### `final_report.md`

A human-readable M&A report containing:

- Key findings
- Strategic analysis
- Transaction assessment
- Recommendation logic

#### `audit_package.json`

A machine-readable audit package containing:

- Claims
- Evidence
- Sources
- Caveats
- Certification status
- Gate status

---

### 11. Case Library Update

Completed M&A research cases are stored for future reuse.

The case library records:

- Transaction type
- User mandate
- Research path
- Key evidence
- Certification result
- Final recommendation
- Major risks
- Missing information
- Human review items
- Transaction outcome
- Post-analysis insights
- Reusable lessons

This enables continuous learning and experience accumulation across future M&A research tasks.

---

## Package Layout

```text
loop_engineered_deep_research_agent/
└── buyer_side_acquisition_strategy_agent/
    ├── runtime/
    ├── schemas/
    ├── config/
    ├── tests/
    ├── examples/
    ├── case_seeds/
    └── README.md
```

The package keeps agent runtime code, schemas, configuration, examples, fixtures, and tests together under stable non-versioned paths.
