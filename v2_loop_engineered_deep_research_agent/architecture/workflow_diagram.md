# Workflow Diagram

## High-Level Flow

```text
User Mandate
  |
  v
Mandate Parser
  |
  v
Research Planner
  |
  v
Deep Research Agent
  |
  v
Evidence Repository <-> Claim-Evidence Graph
  |
  v
Loop Certification / Verifier
  |
  +-- Not Certified / Gap Found --> Loop Controller --> Research Planner
  |
  +-- Needs Human Review --------> Human Review Queue
  |
  +-- Certified / Caveated ------> Certified Evidence
                                      |
                                      v
                                  Deal Analyst
                                      |
                                      v
                               Investment Thesis
                                      |
                                      v
                              Thesis Certification
                                      |
                                      +-- Gap Found --> Loop Controller
                                      |
                                      v
                              IC Report Generator
                                      |
                                      v
                              Report Certification
                                      |
                                      v
             Final M&A Report + Claim-Evidence Graph + Report Manifest
```

## Buyer-Side Acquisition Strategy Flow

The buyer-side V2 pilot maps the V1 buyer acquisition workflow into loopable modules:

```text
B1  Transaction Background And Deal Logic
B2  Buyer Strategic Objectives
B3  Target Business Quality
B4  Industry And Competitive Position
B5  Strategic Fit
B6  Standalone Financial Analysis
B7  Valuation And Acceptable Purchase Price
B8  Synergies And Value Creation
B9  Deal Structure
B10 Financing And Capital Structure Impact
B11 Returns Analysis
B12 Due Diligence Priorities
B13 Regulatory Integration And Downside Risks
B14 Final Decision Recommendation
```

Each module produces candidate claims and research gaps before it contributes to the final report.

## Certification Status Flow

```text
Candidate Claim
  |
  v
Verifier
  |
  +-- Certified -------------> usable in final report
  +-- Certified with Caveat -> usable with visible caveat
  +-- Needs Human Review ----> blocked from final recommendation unless reviewed
  +-- Not Certified ---------> cannot enter final report
  +-- Internal Trace Only ---> retained for audit, not reportable
```

## Governance Flow

```text
Quality Standard Met
  -> proceed

Research Gap Detected
  -> reprioritize and run another research loop

Budget / Iteration Exhausted
  -> stop automatic execution and produce restricted output

Beyond Automated Judgment
  -> escalate to human review
```
