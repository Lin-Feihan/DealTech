# Qualified Candidate Prioritization Prompt

You prioritize only companies that entered the shortlist through the qualification-screening module. Do not rank the full raw universe.

The ranking represents **current SPAC target-screening priority** for Soren Acquisition Corp.: the highest-ranked companies currently screen best and should be researched first. The ranking is not a final investment recommendation, a valuation opinion, or a statement that engagement should begin immediately.

## Two-stage architecture

### Stage 1: qualification screen
Handled separately by the hard-filter module. Only `PRIORITY_SCREEN` and strong `PROVISIONAL_SCREEN` names enter this ranking.

### Stage 2: screening-priority ranking
Rank by Soren-specific SPAC acquisition relevance, not generic company quality.

Use these dimensions:
- `board_conviction_fit` — Can Soren's team understand and underwrite the business more credibly than a generic SPAC?
- `subsector_priority` — Does the company sit in a subsector that screens well for Soren's healthcare SPAC mandate?
- `visible_operating_scale` — Is there public evidence of real platform scale, sites/providers/lives/operations, and possible public-company relevance?
- `ownership_timing_signal` — Is there a publicly visible PE/VC/founder ownership pattern that may support a liquidity or recapitalization discussion? Treat this as inference unless confirmed.
- `financial_frame_confidence` — Can public sources support confirmed public revenue/EBITDA/EV disclosure? If not, penalize confidence and keep the gap explicit.
- `transaction_size_fit` — Use transaction-size fit only where public EV disclosure is actually supported; otherwise keep the fit question open rather than inventing a range.
- `public_market_story` — Would public investors understand a 3–5 year growth story after de-SPAC?
- `public_company_readiness_risk` — Are audited financials, controls, acquisition accounting, management depth, and disclosure burden plausible but unverified?
- `red_flag_adjustment` — Reimbursement, labor, clinical quality, billing, litigation, privacy/security, ownership complexity.
- `spac_transaction_relevance` — Is there a plausible reason a SPAC path could compete with private recap, sponsor-to-sponsor sale, strategic sale, or IPO?

## Output
Return `ranking_rationale.csv` with:
- rank
- company
- subsector
- screening_status
- priority_band, not false precision
- current_screening_view
- visible_supporting_signals
- ranking_rationale
- financial_or_scale_basis
- ownership_timing_basis
- transaction_relevance
- principal_risks
- validation_required
- recommended_next_research

## Style
Use concise professional memo language. Do not use Q&A-style labels in the final report. Distinguish confirmed evidence from inference and penalize unknowns.
