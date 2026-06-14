# Migration Report

## v1.0 Professional Runnable Repository Upgrade

The repository has been upgraded from a runnable prototype into a **v1.0 professional runnable repository** without replacing the existing directory structure.

### What changed

1. `pyproject.toml` now makes default pytest discovery cover both `tests/` and `agents/*/tests/`.
2. `dealtech_certification/` provides the shared runnable engine for source loading, evidence loading, claim mapping, ER/BRB, PCE, business metrics, and generated output writing.
3. `run_agent.py` is the unified entrypoint for all runnable cases/views.
4. ER/BRB fields are standardized on `evidence_reliability` and include `claim_text` plus `reputational_risk`.
5. PCE produces claim-level rows with `claim_id`, `claim_text`, `source_id`, `evidence_id`, `PCE_status`, `reason`, and `human_review_required`.
6. Runnable cases regenerate `certification_result.json`, `ER_BRB_case_result.md`, `PCE_case_result.md`, compatibility `ER_BRB_result.md` / `PCE_result.md`, and `final_output.md`.
7. `examples/sample_outputs/` was refreshed from actual runner commands.

### Cases that run

- Shell Company Screening / TonTon: runnable; outputs `Certified with Caveat`.
- SPAC Target Acquisition / Soren: runnable; outputs `Needs Human Review`.
- Acquisition Strategy / buyer-side: runnable; outputs `Needs Human Review`.
- Acquisition Strategy / target-side: runnable; outputs `Needs Human Review`.
- Merger Strategy: runnable framework output only; business workflow integrated from provided flowchart; real case input pending.

### Shell / TonTon gold-standard case

Shell / TonTon now loads real supporting business workflow files:

- `candidate_universe_table.csv`
- `hard_filter_table.csv`
- `dd_evidence_table.csv`
- `er_brb_scoring_table.csv`
- `risk_matrix.csv`
- `financial_calculation_sheet.csv`
- `claim_to_evidence_map.csv`
- `pce_audit_current_run.csv`

The command output reports candidate universe count, hard-filter pass/fail count, DD evidence record count, risk matrix item count, calculation sheet row count, PCE audit row count, human-review count, and final certification status.

### SPAC / Soren overlay workflow

The Soren case remains `Needs Human Review` and explicitly preserves the required caveats:

- No authenticated Apify run was executed in this version.
- Imported artifact is not primary evidence by itself.
- Source replay remains pending.

A future connector stub is included at `agents/spac-target-acquisition-agent/src/apify_connector.py`.

### Acquisition Strategy views

Buyer-side and target-side run separately and keep separate input, source, evidence, trace, ER/BRB, PCE, final output, and limitations files.

- Buyer-side emphasizes strategic rationale, target attractiveness, synergy assessment, valuation / pricing, integration risk, and go / no-go recommendation.
- Target-side emphasizes offer attractiveness, standalone case, strategic alternatives, fairness assessment, deal certainty, and accept / reject / negotiate recommendation.

Both remain `Needs Human Review / Source replay pending` for high-risk valuation, pricing, fairness, and recommendation claims.

### Merger Strategy workflow integration

The provided merger strategy flowchart was converted into:

1. Intent capture and clarification.
2. Planning intent.
3. 15-section merger case memo workflow:
   - Transaction Overview
   - Strategic Rationale
   - Stakeholder Assessment
   - Industry & Market
   - Valuation and Walkaway Price
   - Synergies & Value Creation
   - Deal Structure & Financing
   - Pro Forma Financial Impact
   - Governance & Control
   - Deal Diligence Findings
   - Regulatory & Antitrust Risk
   - Integration Plan
   - Risk Analysis
   - Scenario & Sensitivity Analysis
   - Final Recommendation
4. Offline analysis layer: financial model, DCF/projection, valuation, scenario/sensitivity.
5. Online retrieval layer: SEC, company corpus, industry data, market/pricing data, news, equity research.
6. Extended tool-use layer: API search, browser, precedents, contracts, and reports.
7. ER/BRB and PCE framework gates.

The Merger Strategy Agent remains framework-only because no real merger case, source registry, evidence table, or claim-to-evidence map has been provided. No customer, company, transaction, valuation, synergy, antitrust, or recommendation fact has been fabricated.

### Verification

Latest local verification: **78 passed**.
