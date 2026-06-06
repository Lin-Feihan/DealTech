# Architecture

The project is a reusable certified research workflow for shell company screening. It has four layers:

1. Market adapters and source hierarchy.
2. Screening / DD / ER/BRB decisioning.
3. Certified Research Trace.
4. PCE final delivery certification.

HK is the current example market adapter. Tuntun HK is the current example case.

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
