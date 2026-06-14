from __future__ import annotations

import json
from pathlib import Path
from .models import SourceRecord, EvidenceRecord


def _table(headers: list[str], rows: list[list[object]]) -> str:
    out = ['|' + '|'.join(headers) + '|', '|' + '|'.join(['---'] * len(headers)) + '|']
    for row in rows:
        out.append('|' + '|'.join(str(c).replace('\n', ' ') for c in row) + '|')
    return '\n'.join(out) + '\n'


def _csv(headers: list[str], rows: list[list[object]]) -> str:
    out = [','.join(headers)]
    for row in rows:
        cells = []
        for cell in row:
            text = str(cell).replace('"', '""')
            if any(ch in text for ch in [',', '"', '\n']):
                text = f'"{text}"'
            cells.append(text)
        out.append(','.join(cells))
    return '\n'.join(out) + '\n'


def write_outputs(output_dir: Path, agent_name: str, case_id: str, view: str | None, sources: list[SourceRecord], evidence: list[EvidenceRecord], er_results: list[dict], pce_result: dict, business_metrics: dict | None = None) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    certification = {
        'agent': agent_name,
        'case_id': case_id,
        'view': view,
        'overall_status': pce_result['overall_status'],
        'sources_loaded': len(sources),
        'evidence_records_loaded': len(evidence),
        'claims_checked': len(pce_result['claim_results']),
        'er_brb_completed': True,
        'pce_completed': True,
        'human_review_required': pce_result['summary']['human_review_required_claims'] > 0,
        'reason': _overall_reason(pce_result['overall_status']),
        'business_metrics': business_metrics or {},
        'claim_results': pce_result['claim_results'],
    }
    p = output_dir / 'certification_result.json'
    p.write_text(json.dumps(certification, ensure_ascii=False, indent=2), encoding='utf-8')
    files.append(p)

    er_md = (
        f"# ER/BRB Case Result — {agent_name}\n\n"
        f"Case: `{case_id}`" + (f" / View: `{view}`" if view else '') + "\n\n" +
        _table(
            ['claim_id', 'claim_text', 'evidence_id', 'source_id', 'evidence_reliability', 'business_risk', 'regulatory_risk', 'reputational_risk', 'certification_status', 'human_review_required', 'reason'],
            [[r['claim_id'], r.get('claim_text', ''), r['evidence_id'], r['source_id'], r['evidence_reliability'], r['business_risk'], r['regulatory_risk'], r['reputational_risk'], r['certification_status'], 'yes' if r['human_review_required'] else 'no', r['reason']] for r in er_results]
        )
    )
    p = output_dir / 'ER_BRB_case_result.md'
    p.write_text(er_md, encoding='utf-8')
    files.append(p)
    compat_er = output_dir / 'ER_BRB_result.md'
    compat_er.write_text(er_md, encoding='utf-8')
    files.append(compat_er)

    pce_md = (
        f"# PCE Case Result — {agent_name}\n\n"
        f"Case: `{case_id}`" + (f" / View: `{view}`" if view else '') +
        f"\n\nOverall status: **{pce_result['overall_status']}**\n\n" +
        _table(
            ['claim_id', 'claim_text', 'source_id', 'evidence_id', 'PCE_status', 'reason', 'human_review_required'],
            [[r['claim_id'], r.get('claim_text', ''), r['source_id'], r['evidence_id'], r['PCE_status'], r['reason'], 'yes' if r.get('human_review_required') else 'no'] for r in pce_result['claim_results']]
        )
    )
    scoped_sample = pce_result.get('scoped_claim_sample') or {}
    if scoped_sample.get('rows'):
        scope = scoped_sample.get('sampling_scope', '')
        total = scoped_sample.get('total_scope_rows', 0)
        size = scoped_sample.get('sample_size', len(scoped_sample.get('rows', [])))
        pce_md += (
            "\n## Scoped sampled business claims\n\n"
            f"Sampling rule: {scoped_sample.get('scope_rule', '')}\n\n"
            f"Scoped rows available in `{scope}`: {total}. Sample shown here: {min(total, size)} rows.\n\n"
        )
        pce_md += _table(
            ['claim_id', 'company_name', 'stage', 'source_id', 'evidence_id', 'delivery_scope', 'certification_status', 'human_review_required'],
            [[
                row.get('claim_id', ''),
                row.get('company_name', ''),
                row.get('stage', ''),
                row.get('source_id', ''),
                row.get('evidence_id', ''),
                row.get('delivery_scope', ''),
                row.get('certification_status', ''),
                row.get('human_review_required', ''),
            ] for row in scoped_sample.get('rows', [])]
        )
    p = output_dir / 'PCE_case_result.md'
    p.write_text(pce_md, encoding='utf-8')
    files.append(p)
    compat = output_dir / 'PCE_result.md'
    compat.write_text(pce_md, encoding='utf-8')
    files.append(compat)

    if scoped_sample.get('rows'):
        scoped_headers = ['claim_id', 'claim_text', 'company_name', 'stage', 'source_id', 'evidence_id', 'delivery_scope', 'certification_status', 'human_review_required', 'source_link_or_file', 'reviewer_note']
        scoped_rows = [[
            row.get('claim_id', ''),
            row.get('claim_text', ''),
            row.get('company_name', ''),
            row.get('stage', ''),
            row.get('source_id', ''),
            row.get('evidence_id', ''),
            row.get('delivery_scope', ''),
            row.get('certification_status', ''),
            row.get('human_review_required', ''),
            row.get('source_link_or_file', ''),
            row.get('reviewer_note', ''),
        ] for row in scoped_sample.get('rows', [])]
        sample_csv = output_dir / 'scoped_claim_audit_sample.csv'
        sample_csv.write_text(_csv(scoped_headers, scoped_rows), encoding='utf-8')
        files.append(sample_csv)
        sample_md = output_dir / 'scoped_claim_audit_result.md'
        sample_md.write_text(
            "# Scoped Claim Audit Result\n\n"
            f"Sampling rule: {scoped_sample.get('scope_rule', '')}\n\n"
            f"Source files: {', '.join(scoped_sample.get('source_files', []))}\n\n"
            + _table(scoped_headers, scoped_rows),
            encoding='utf-8'
        )
        files.append(sample_md)

    p = output_dir / 'final_output.md'
    p.write_text(_final_output(agent_name, case_id, view, certification), encoding='utf-8')
    files.append(p)
    return files


def write_framework_only(output_dir: Path, agent_name: str, reason: str) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {
        'agent': agent_name,
        'status': 'Framework only',
        'reason': reason,
        'sources_loaded': 0,
        'evidence_records_loaded': 0,
        'claims_checked': 0,
        'er_brb_completed': False,
        'pce_completed': False,
    }
    p = output_dir / 'framework_status.json'
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    md = output_dir / 'framework_status.md'
    md.write_text(
        f"# {agent_name} — Framework Only\n\n"
        "Status: **Framework only**\n\n"
        f"Reason: {reason}\n\n"
        "No case-run is claimed. No customer, company, or deal facts have been fabricated.\n",
        encoding='utf-8'
    )
    final = output_dir / 'final_output.md'
    final.write_text(md.read_text(encoding='utf-8'), encoding='utf-8')
    return [p, md, final]


def _overall_reason(status: str) -> str:
    if status == 'Certified with Caveat':
        return 'Claim-level evidence exists and PCE ran, but caveats/human-review flags remain visible; not pure Certified.'
    if status == 'Needs Human Review':
        return 'At least one material claim requires source replay, primary evidence validation, calculation replay, or human review.'
    if status == 'Not Certified':
        return 'At least one material claim lacks admissible source/evidence support.'
    return 'All claim-level checks passed without human-review blockers.'


def _final_output(agent_name: str, case_id: str, view: str | None, cert: dict) -> str:
    view_line = f"\n- View: `{view}`" if view else ''
    agent_note = ''
    if agent_name == 'SPAC Target Acquisition':
        agent_note = "\n## SPAC / Apify provenance note\n\n- This case uses a partially source-replayed screening structure, not a fully source-replayed complete case.\n- Aledade, Cityblock Health, DispatchHealth, and Lyra Health have source-replayed identity/business-description rows.\n- Candidate financials, EBITDA, deal value, SPAC readiness, and Apify-authenticated dataset replay remain incomplete.\n- Retained candidates are retained for further review only; they are not final recommended SPAC targets.\n- SPAC overall status remains Needs Human Review unless all material source replay and calculation replay are completed.\n- No authenticated Apify run was executed in this version.\n- Imported artifact is not primary evidence by itself.\n"
    elif agent_name == 'Acquisition Strategy':
        if view == 'buyer_side':
            agent_note = "\n## Buyer-side workflow focus\n\nStrategic rationale, target attractiveness, synergy assessment, valuation / pricing, integration risk, and go / no-go recommendation are evaluated separately from target-side claims. Valuation, pricing, and recommendation claims remain Human Review Required until primary source replay and calculation replay are complete.\n"
        elif view == 'target_side':
            agent_note = "\n## Target-side workflow focus\n\nOffer attractiveness, standalone case, strategic alternatives, fairness assessment, deal certainty, and accept / reject / negotiate recommendation are evaluated separately from buyer-side claims. Fairness and board-response claims remain Human Review Required until primary source replay and calculation replay are complete.\n"
    metrics = cert.get('business_metrics') or {}
    metrics_block = ''
    if metrics:
        metric_labels = [
            ('candidate_universe_count', 'Candidate universe count'),
            ('hard_filter_pass_count', 'Hard filter pass count'),
            ('retained_candidate_count', 'Retained candidate count'),
            ('excluded_candidate_count', 'Excluded candidate count'),
            ('DD_evidence_count', 'DD evidence count'),
            ('DD_evidence_record_count', 'DD evidence record count'),
            ('risk_count', 'Risk count'),
            ('risk_matrix_item_count', 'Risk matrix item count'),
            ('calculation_count', 'Calculation count'),
            ('calculation_sheet_row_count', 'Calculation sheet row count'),
            ('ER_BRB_rows_count', 'ER/BRB rows count'),
            ('PCE_claims_checked', 'PCE claims checked'),
            ('PCE_audit_row_count', 'PCE audit row count'),
            ('human_review_required_count', 'Human review required count'),
            ('human_review_count', 'Human review count'),
            ('final_delivery_allowed_count', 'Final delivery allowed count'),
            ('blocked_claim_count', 'Blocked claim count'),
            ('final_certification_status', 'Final certification status'),
            ('overall_status', 'Overall status'),
            ('evidence_count', 'Evidence count'),
            ('strategic_rationale_count', 'Strategic rationale count'),
            ('integration_risk_count', 'Integration risk count'),
            ('strategic_alternative_count', 'Strategic alternative count'),
            ('offer_attractiveness_criteria_count', 'Offer-attractiveness criteria count'),
        ]
        lines = ['\n## Business workflow metrics\n']
        for key, label in metric_labels:
            if key in metrics:
                lines.append(f'- {label}: {metrics[key]}')
        if metrics.get('supporting_files_used'):
            lines.append('- Supporting files loaded: ' + ', '.join(sorted(metrics['supporting_files_used'].keys())))
        if metrics.get('missing_supporting_files'):
            lines.append('- Missing supporting files: ' + ', '.join(metrics['missing_supporting_files']))
        metrics_block = '\n'.join(lines) + '\n'
    if agent_name == 'Acquisition Strategy' and view == 'buyer_side':
        return f"""# Final Output — {agent_name}

- Case: `{case_id}`
- View: `{view}`
- Overall certification status: **{cert['overall_status']}**

## 1. Deliverable findings

- Apple factual background can be delivered only where source-backed.
- DarwinAI transaction occurrence/context can be delivered only with caveats when terms remain undisclosed.

## 2. Caveated strategic rationale

Strategic rationale is presented only as evidence-supported inference, not as fact, valuation, or recommendation.

## 3. Integration risks

Deal terms unknown, valuation unknown, source-quality gaps, and integration execution risk remain visible.

## 4. Claims not certified

Valuation, pricing, synergy, EPS, deal value, and go/no-go recommendation claims are not certified.

## 5. Human review required before decision use

Human review, source replay, and calculation replay are required before decision use, pricing, valuation, fairness, legal, or board-level use.
{metrics_block}
"""
    if agent_name == 'Acquisition Strategy' and view == 'target_side':
        return f"""# Final Output — {agent_name}

- Case: `{case_id}`
- View: `{view}`
- Overall certification status: **{cert['overall_status']}**

## 1. Deliverable target-side framework

- DarwinAI target identity/background can be delivered within the caveated evidence boundary.
- This output is a framework for review, not a fairness or board recommendation.

## 2. Strategic alternatives

Accept Apple acquisition, remain independent, raise private financing, seek another strategic buyer, license technology, or pursue partnership without sale.

## 3. Caveated offer attractiveness

Strategic fit and transaction-occurrence context may be caveated; financial attractiveness and valuation fairness are not certified.

## 4. Claims not certified

Financial fairness, valuation, offer premium, revenue multiple, EBITDA multiple, board response, and accept/reject/negotiate recommendation claims are not certified.

## 5. Human review required before board-level use

Human review, source replay, calculation replay, and fairness review are required before board-level use.
{metrics_block}
"""
    if agent_name == 'SPAC Target Acquisition':
        return f"""# Final Output — {agent_name}

- Case: `{case_id}`{view_line}
- Overall certification status: **{cert['overall_status']}**

## Deliverable findings

- The case now uses a partially source-replayed screening structure with explicit supporting files.
- Modeled / hypothetical names are separated from real candidate screening and are not treated as validated targets.

## Caveated screening state

Four real candidate identity/business-description rows are source-replayed and retained for further review only: Aledade, Cityblock Health, DispatchHealth, and Lyra Health. They are not final recommended SPAC targets and are not certified as hard-filter passes because revenue, EBITDA, deal value, SPAC readiness, Apify-authenticated dataset replay, audit readiness, public-market readiness, and transaction willingness remain Unknown. SPAC overall status remains Needs Human Review unless all material source replay and calculation replay are completed.

## Claims not certified

- Revenue, EBITDA, deal value, valuation, audit readiness, public-market readiness, and final suitability claims.
- Any acquisition recommendation or sponsor-engagement recommendation.

## Human review required before decision use

Human review, source replay, and calculation replay are required before any decision use.
{agent_note}
{metrics_block}
"""
    return f"""# Final Output — {agent_name}

- Case: `{case_id}`{view_line}
- Overall certification status: **{cert['overall_status']}**
- Sources loaded: {cert['sources_loaded']}
- Evidence records loaded: {cert['evidence_records_loaded']}
- Claims checked: {cert['claims_checked']}
- ER/BRB completed: Yes
- PCE completed: Yes

## Certification note

{cert['reason']}

This output is generated from the case `source_registry`, `evidence_table`, `claim_to_evidence_map` / derived claim map, ER/BRB evaluation, and claim-level PCE. Human-review and caveat flags are intentionally preserved and must not be hidden in downstream use.
{agent_note}
{metrics_block}
"""
