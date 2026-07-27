# System Overview

## Objective

The V2 system upgrades DealTech agents from prompt/spec rescue materialss into a loop-engineered research runtime for M&A work.

Its objective is to produce decision-grade transaction research where final recommendations are supported by certified claims, replayable evidence, and explicit human-review boundaries.

## Core Components

### User Mandate

The user mandate defines the transaction context, research scope, evidence requirements, output standard, budget, and human-review preferences.

### Mandate Parser

The parser converts the mandate into structured inputs:

- buyer and target
- transaction type
- decision questions
- report currency and date
- source requirements
- analysis modules
- output requirements
- budget and iteration constraints

### Research Planner

The planner converts the structured mandate into research questions and work packages. For buyer-side acquisition strategy, the V1 14-module workflow becomes the planning backbone.

### Deep Research Agent

The research agent executes one work package at a time. It searches, reads, extracts, computes, and synthesizes, but it does not directly decide what can enter the final report.

Its primary outputs are candidate claims, evidence items, source records, calculation records, and research gaps.

### Evidence Repository

The evidence repository stores source-backed artifacts and extraction records.

It should preserve enough context for later replay:

- source identity
- retrieval date
- source type
- excerpt or data point
- extraction method
- associated claim IDs
- calculation references

### Claim-Evidence Graph

The graph connects claims to evidence, sources, calculations, dependencies, conflicts, and certification results.

This graph is the main auditable research object.

### Loop Certification

Certification is an independent control layer. It evaluates whether candidate claims can be used in downstream analysis.

The certification layer checks:

- research coverage
- evidence sufficiency
- source reliability
- claim-source alignment
- calculation replayability
- conflict detection
- human-review triggers

### Loop Controller

The controller decides what happens after certification:

- proceed to certified evidence
- return to research with prioritized gaps
- produce caveated output
- stop due to budget or iteration limits
- escalate to human review

### Deal Analyst

The analyst consumes certified and caveated evidence to form transaction judgments, including strategic rationale, valuation view, synergy view, financing and return view, risk view, and final recommendation.

### Thesis Certification

Analytical conclusions are also claims. Thesis certification checks whether the investment thesis is supported by upstream certified evidence and whether judgment leaps are disclosed.

### IC Report Generator

The report generator turns certified evidence and certified thesis into a board / investment committee style report.

### Report Certification

The final gate checks that key report paragraphs, tables, and recommendations map back to certified or caveated claims.

## Final Outputs

The expected final outputs are:

- M&A Report
- Claim-Evidence Graph
- Certification Results
- Report Manifest
- Research Gap Log
- Human Review Items

## Non-Goals For This Version

This version does not include:

- a fully automated web/search runtime
- a live financial data connector
- a new case study
- a Python runner
- a new final M&A report

Those should be added after the architecture and buyer-side agent bundle are reviewed.
