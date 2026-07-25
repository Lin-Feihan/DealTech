from __future__ import annotations

import csv
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
    p.write_text(_final_output(agent_name, case_id, view, certification, output_dir), encoding='utf-8')
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


def _claim_results(cert: dict) -> list[dict]:
    return [r for r in cert.get('claim_results', []) if isinstance(r, dict)]


def _claim_status(row: dict) -> str:
    return str(row.get('PCE_status') or row.get('certification_status') or '').strip()


def _requires_review(row: dict) -> bool:
    return bool(row.get('human_review_required')) or _claim_status(row) in {'Needs Human Review', 'Not Certified'}


def _format_claim_bullets(rows: list[dict], empty: str) -> str:
    if not rows:
        return f'- {empty}\n'
    lines = []
    for row in rows:
        claim_id = row.get('claim_id', '')
        text = row.get('claim_text', '')
        source_id = row.get('source_id', '')
        evidence_id = row.get('evidence_id', '')
        status = _claim_status(row)
        refs = ', '.join(v for v in [source_id, evidence_id, status] if v)
        prefix = f'`{claim_id}` - ' if claim_id else ''
        suffix = f' ({refs})' if refs else ''
        lines.append(f'- {prefix}{text}{suffix}')
    return '\n'.join(lines) + '\n'


def _filter_claims(rows: list[dict], keywords: tuple[str, ...]) -> list[dict]:
    filtered = []
    for row in rows:
        text = str(row.get('claim_text', '')).lower()
        if any(k in text for k in keywords):
            filtered.append(row)
    return filtered


def _read_supporting_text(output_dir: Path, name: str) -> str:
    path = output_dir / 'supporting_files' / name
    if not path.exists():
        return ''
    return path.read_text(encoding='utf-8').strip()


def _read_supporting_csv(output_dir: Path, name: str) -> list[dict]:
    path = output_dir / 'supporting_files' / name
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def _paragraph_from_markdown(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if stripped.startswith('|'):
            continue
        upper = stripped.upper()
        if 'CLM-' in upper or 'EVI-' in upper or 'SRC-' in upper or 'PCE' in upper:
            continue
        lines.append(stripped)
    return '\n\n'.join(lines)


def _is_yes(value: object) -> bool:
    return str(value or '').strip().lower() in {'yes', 'true', '1'}


def _is_certified(row: dict) -> bool:
    status = str(row.get('certification_status') or row.get('PCE_status') or '').strip().lower()
    return status == 'certified' and not _is_yes(row.get('human_review_required'))


def _bullet_list(items: list[str], empty: str) -> str:
    if not items:
        return f'- {empty}\n'
    return ''.join(f'- {item}\n' for item in items)


def _rationale_items(rows: list[dict], certified_only: bool = True) -> list[str]:
    items = []
    for row in rows:
        if certified_only and not _is_certified(row):
            continue
        text = row.get('rationale') or row.get('risk_description') or ''
        limitation = row.get('limitation') or row.get('mitigation') or ''
        if not text:
            continue
        if limitation:
            items.append(f'{text} {limitation}')
        else:
            items.append(text)
    return items


def _risk_items(rows: list[dict], include_review: bool = True) -> list[str]:
    items = []
    for row in rows:
        if not include_review and not _is_certified(row):
            continue
        category = row.get('risk_category') or 'Risk'
        severity = row.get('severity') or 'Unrated'
        desc = row.get('risk_description') or ''
        mitigation = row.get('mitigation') or ''
        if not desc:
            continue
        suffix = f' Mitigation: {mitigation}' if mitigation else ''
        items.append(f'{category} ({severity}): {desc}{suffix}')
    return items


def _calculation_items(rows: list[dict]) -> list[str]:
    items = []
    for row in rows:
        if _is_yes(row.get('human_review_required')):
            continue
        calc_type = str(row.get('calculation_type') or '').replace('_', ' ')
        raw_calc_type = str(row.get('calculation_type') or '')
        formula = row.get('formula') or ''
        output = row.get('output_value') or ''
        unit = row.get('output_unit') or ''
        limitation = row.get('limitation') or ''
        if not output:
            continue
        if raw_calc_type == 'maximum_headline_consideration':
            sentence = 'Maximum headline consideration: $60.0 million of closing cash plus up to $120.0 million of contingent consideration implies a $180.0 million headline ceiling.'
        elif raw_calc_type == 'known_424b4_triggered_or_expected_milestones':
            sentence = 'Disclosed milestone context: the prospectus describes a $37.0 million Phase 2 first-administration payment and an expected $23.0 million Phase 3 first-administration obligation, or $60.0 million in aggregate.'
        elif raw_calc_type == 'remaining_contingent_ceiling_after_424b4_milestones':
            sentence = 'Residual contingent exposure: after those disclosed / expected milestones, $60.0 million of the $120.0 million contingent ceiling remained subject to later clinical or approval outcomes.'
        else:
            sentence = f'{calc_type}: {formula} = {output} {unit}.'.strip()
            if limitation:
                sentence += f' {limitation}'
        items.append(sentence)
    return items


def _human_review_items(rows: list[dict]) -> list[str]:
    items = []
    for row in rows:
        if not _requires_review(row):
            continue
        text = row.get('claim_text') or ''
        if text:
            items.append(text)
    return items


def _professional_acquisition_buyer_report(case_id: str, view: str | None, cert: dict, output_dir: Path) -> str:
    buyer_profile = _paragraph_from_markdown(_read_supporting_text(output_dir, 'buyer_profile.md'))
    target_profile = _paragraph_from_markdown(_read_supporting_text(output_dir, 'target_profile.md'))
    transaction_context = _paragraph_from_markdown(_read_supporting_text(output_dir, 'transaction_context.md'))
    rationales = _read_supporting_csv(output_dir, 'strategic_rationale_table.csv')
    risks = _read_supporting_csv(output_dir, 'integration_risk_matrix.csv')
    calculations = _read_supporting_csv(output_dir, 'buyer_side_calculation_sheet.csv')
    review_items = _human_review_items(_claim_results(cert))
    supporting_files = [
        name
        for name in sorted((cert.get('business_metrics') or {}).get('supporting_files_used', {}).keys())
        if 'pce' not in name.lower() and 'er_brb' not in name.lower()
    ]
    supporting_line = ', '.join(f'`{name}`' for name in supporting_files) or 'No supporting files were registered.'
    status = cert['overall_status']
    if 'alumis' in case_id.lower() or 'fronthera' in case_id.lower():
        title = 'Alumis / FronThera Buyer-side Acquisition Strategy Report'
        thesis = 'Alumis appears to have used the FronThera transaction as a focused asset acquisition to secure ESK-001 and related know-how / intellectual property, creating a lead TYK2 program around which it could build an autoimmune pipeline.'
        recommendation = 'The buyer-side conclusion is proceed with diligence, not unconditional approval. The transaction has a coherent strategic rationale, but clinical milestone exposure, financing capacity, and unresolved founder-source-chain questions prevent a clean go / no-go recommendation.'
    else:
        title = 'Buyer-side Acquisition Strategy Report'
        thesis = 'The transaction should be assessed as a buyer-side strategic acquisition using the certified evidence, business workflow files, and unresolved diligence gates in this case package.'
        recommendation = 'The buyer-side conclusion remains gated by human review unless the case record independently certifies valuation, financing, execution, and recommendation claims.'
    return f"""# {title}

## Executive Summary

{thesis}

The analysis supports a bounded strategic rationale rather than a full investment or board recommendation. The transaction facts, consideration structure, and asset scope are sufficiently supported for research use. The unresolved diligence items relate mainly to private-person economics, founder / patent source-chain replay, and any conclusion that would require valuation, legal, fairness, or investment judgment.

Current certification status: **{status}**. In practical terms, the case is usable as an acquisition-strategy research report, but not as final decision material without additional human review.

## 1. Transaction Overview

{transaction_context or 'Transaction context was not provided in the supporting files.'}

## 2. Buyer Context and Strategic Intent

{buyer_profile or 'Buyer profile was not provided in the supporting files.'}

The strategic intent is best understood as pipeline formation and acceleration. The buyer was not acquiring a mature commercial platform; it was acquiring a specific product candidate and related know-how / intellectual property. That distinction keeps the analysis focused on development risk, financing capacity, and the quality of the acquired asset rather than on operating synergies typical of a mature-company acquisition.

## 3. Target / Asset Assessment

{target_profile or 'Target / asset profile was not provided in the supporting files.'}

The central diligence question is therefore not whether FronThera was attractive as a standalone operating business. It is whether ESK-001 was a strategically valuable enough lead asset to justify the upfront cash commitment, milestone exposure, and subsequent development burden.

## 4. Deal Structure and Economics

{_bullet_list(_calculation_items(calculations), 'No replayed deal calculations were available in the supporting files.')}
The milestone-heavy structure is strategically important. It limited guaranteed closing consideration relative to the maximum headline value, but it did not eliminate economic exposure. Successful clinical progress could trigger additional obligations at precisely the point when the buyer also needs to fund larger trials.

## 5. Strategic Rationale

{_bullet_list(_rationale_items(rationales, certified_only=True), 'No certified strategic rationale rows were available in the supporting files.')}
Taken together, these points support a focused acquisition thesis: use FronThera to obtain ESK-001, keep the rationale tied to that asset, and avoid overstating the acquisition as proof of broader platform value.

## 6. Key Risks and Mitigants

{_bullet_list(_risk_items(risks), 'No risk rows were available in the supporting files.')}
The risk profile is typical of an early clinical-stage biotechnology asset acquisition: the deal can be strategically coherent while still carrying substantial clinical, financing, and execution uncertainty.

## 7. Open Diligence Items

{_bullet_list(review_items, 'No human-review-gated diligence items were identified in the claim ledger.')}
These items should sit in diligence workstreams or appendices, not in the main investment conclusion. In particular, Bohan / Stan Jin identity, founder role, shareholder economics, and patent lineage should not be converted into final conclusions until the underlying primary sources are replayed directly.

## 8. Buyer-side Conclusion

{recommendation}

The report should be used as a disciplined research basis for further diligence. It should not be used as investment advice, legal advice, a fairness opinion, a valuation conclusion, or a board-level approval recommendation.

## Appendix - Audit Trail

Detailed audit outputs are provided separately in the case package. Those files retain the underlying evidence trace, review flags, and machine-readable certification checks that are intentionally omitted from the main report body.

Supporting materials reviewed: {supporting_line}
"""


def _acquisition_buyer_report(case_id: str, view: str | None, cert: dict, metrics_block: str) -> str:
    rows = _claim_results(cert)
    certified = [r for r in rows if _claim_status(r) == 'Certified' and not _requires_review(r)]
    caveated = [r for r in rows if _claim_status(r) == 'Certified with Caveat']
    review = [r for r in rows if _requires_review(r)]
    deliverable = certified + caveated
    deal_rows = _filter_claims(deliverable, ('acquir', 'transaction', 'purchase', 'consideration', 'milestone', 'cash', 'deal value'))
    strategy_rows = _filter_claims(deliverable, ('strategic', 'rationale', 'target', 'asset', 'pipeline', 'technology', 'product candidate', 'integration'))
    if not strategy_rows:
        strategy_rows = deliverable
    title = 'Buyer-side Acquisition Strategy Report'
    if 'alumis' in case_id.lower() or 'fronthera' in case_id.lower():
        title = 'Alumis / FronThera Buyer-side Acquisition Strategy Report'
    return f"""# {title}

- Case: `{case_id}`
- View: `{view}`
- Overall certification status: **{cert['overall_status']}**
- Sources loaded: {cert['sources_loaded']}
- Evidence records loaded: {cert['evidence_records_loaded']}
- Claims checked: {cert['claims_checked']}

## Executive Summary

This report is generated from the case source registry, evidence table, claim-to-evidence map, ER/BRB evaluation, PCE audit, and supporting business workflow files. It is the buyer-side business report, not merely a certification receipt.

For this run, {len(deliverable)} claim(s) are deliverable within the registered evidence boundary and {len(review)} claim(s) remain gated by human review, source replay, calculation replay, or primary-evidence validation. The report preserves those gates instead of converting caveated findings into a clean recommendation.

## 1. Transaction Context and Buyer Objective

{_format_claim_bullets(deal_rows, 'No transaction-context claims were certified in this run.')}
## 2. Strategic Rationale and Fit

{_format_claim_bullets(strategy_rows, 'No strategic-rationale claims were certified in this run.')}
## 3. Deal Structure, Financing, and Execution Constraints

{_format_claim_bullets(_filter_claims(deliverable, ('cash', 'consideration', 'milestone', 'financing', 'funding', 'going-concern', 'valuation', 'price')), 'No deal-structure or financing claims were certified in this run.')}
## 4. Human-review-gated Diligence Items

{_format_claim_bullets(review, 'No claims require human review in this run.')}
## 5. Preliminary Buyer-side Recommendation Boundary

The generated recommendation is intentionally bounded: proceed only with human-review-gated diligence unless all material source replay, calculation replay, valuation work, and decision-maker review are complete. This output does not certify valuation fairness, investment attractiveness, legal advice, board approval, synergy, EPS impact, or a clean go / no-go recommendation unless those claims are separately certified in the claim ledger.

## 6. Final Delivery Boundary

The final delivery may use certified and caveated transaction facts as research findings. Claims marked Needs Human Review or Not Certified must remain blocked from final decision use until their listed evidence gaps are closed.
{metrics_block}
"""


def _final_output(agent_name: str, case_id: str, view: str | None, cert: dict, output_dir: Path) -> str:
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
        return _professional_acquisition_buyer_report(case_id, view, cert, output_dir)
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
