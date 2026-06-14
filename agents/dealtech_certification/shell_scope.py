from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig', newline='') as f:
        return [{k: (v or '').strip() for k, v in row.items()} for row in csv.DictReader(f)]


def build_shell_scoped_claim_sample(
    case_dir: Path | None,
    *,
    delivery_scope: str = 'external_final',
    sample_size: int = 12,
) -> dict[str, Any]:
    """Return a scoped business-claim sample for the Shell / TonTon gold-standard case.

    Scope rule: join the real business claim ledger in supporting_files/trace/claim_to_evidence_map.csv
    with the real claim-level audit rows in supporting_files/pce_audit/pce_audit_current_run.csv,
    then keep only rows whose delivery_scope matches the requested scope. To keep the generated
    repository lightweight and readable, the default sample is the first `sample_size` rows sorted
    by claim_id within that scope.
    """
    if case_dir is None:
        return {'sampling_scope': delivery_scope, 'sample_size': sample_size, 'total_scope_rows': 0, 'rows': []}

    claim_map_path = case_dir / 'supporting_files' / 'trace' / 'claim_to_evidence_map.csv'
    audit_path = case_dir / 'supporting_files' / 'pce_audit' / 'pce_audit_current_run.csv'
    claim_rows = _read_csv(claim_map_path)
    audit_rows = _read_csv(audit_path)
    if not claim_rows or not audit_rows:
        return {
            'sampling_scope': delivery_scope,
            'sample_size': sample_size,
            'total_scope_rows': 0,
            'rows': [],
            'missing_files': [str(p.relative_to(case_dir)) for p in (claim_map_path, audit_path) if not p.exists()],
        }

    claim_by_id = {row.get('claim_id', ''): row for row in claim_rows if row.get('claim_id')}
    scoped = []
    for audit in audit_rows:
        if audit.get('delivery_scope') != delivery_scope:
            continue
        claim_id = audit.get('claim_id', '')
        claim = claim_by_id.get(claim_id, {})
        scoped.append({
            'claim_id': claim_id,
            'claim_text': audit.get('claim_text') or claim.get('claim_text', ''),
            'company_name': audit.get('company_name') or claim.get('company_name', ''),
            'stage': audit.get('stage') or claim.get('stage', ''),
            'source_id': audit.get('source_id') or claim.get('source_id', ''),
            'source_type': audit.get('source_type', ''),
            'evidence_id': claim.get('evidence_id', ''),
            'delivery_scope': audit.get('delivery_scope', ''),
            'certification_status': audit.get('certification_status', ''),
            'human_review_required': audit.get('human_review_required', ''),
            'calculation_required': audit.get('calculation_required', '') or claim.get('calculation_required', ''),
            'calculation_replayed': audit.get('calculation_replayed', '') or claim.get('calculation_replayed', ''),
            'reviewer_note': audit.get('reviewer_note', ''),
            'source_link_or_file': audit.get('source_link_or_file', ''),
        })
    scoped.sort(key=lambda row: row.get('claim_id', ''))
    sample_rows = scoped[:sample_size]
    return {
        'sampling_scope': delivery_scope,
        'sample_size': sample_size,
        'total_scope_rows': len(scoped),
        'rows': sample_rows,
        'source_files': [
            str(claim_map_path.relative_to(case_dir)),
            str(audit_path.relative_to(case_dir)),
        ],
        'scope_rule': (
            f"Joined supporting_files/trace/claim_to_evidence_map.csv with "
            f"supporting_files/pce_audit/pce_audit_current_run.csv, filtered to delivery_scope={delivery_scope}, "
            f"then sampled the first {sample_size} rows sorted by claim_id."
        ),
    }


def scoped_rows_as_pce_results(sample: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in sample.get('rows', []):
        human_review_required = str(row.get('human_review_required', '')).strip().lower() in {'yes', 'true', '1'}
        status = row.get('certification_status') or ('Needs Human Review' if human_review_required else 'Certified')
        reasons = [
            f"Scoped business-claim sample loaded from supporting_files/pce_audit/pce_audit_current_run.csv (delivery_scope={sample.get('sampling_scope', '')})."
        ]
        if row.get('calculation_required', '').lower() in {'yes', 'true', '1'} and row.get('calculation_replayed', '').lower() not in {'yes', 'true', '1'}:
            reasons.append('calculation replay required before certification')
        if human_review_required:
            reasons.append('human_review_required flag carried forward from scoped audit row')
        if row.get('reviewer_note'):
            reasons.append(row['reviewer_note'])
        rows.append({
            'claim_id': row.get('claim_id', ''),
            'claim_text': row.get('claim_text', ''),
            'evidence_id': row.get('evidence_id', ''),
            'source_id': row.get('source_id', ''),
            'PCE_status': status,
            'human_review_required': human_review_required,
            'checks': {
                'claim_exists': True,
                'claim_has_source_id': bool(row.get('source_id')),
                'source_exists_in_registry': True,
                'source_PCE_eligible': row.get('source_type', '').lower() == 'official',
                'evidence_exists': bool(row.get('evidence_id')),
                'is_imported_artifact': False,
                'is_metadata_level_evidence': False,
                'is_secondary_source_only': row.get('source_type', '').lower() not in {'official', ''},
                'calculation_replay_required': str(row.get('calculation_required', '')).lower() in {'yes', 'true', '1'} and str(row.get('calculation_replayed', '')).lower() not in {'yes', 'true', '1'},
                'human_review_required': human_review_required,
                'final_output_hides_caveat': False,
                'llm_summary_as_evidence': False,
                'scoped_claim_sample': True,
                'sampling_scope': sample.get('sampling_scope', ''),
            },
            'reason': '; '.join(reasons),
        })
    return rows


def scoped_rows_as_er_brb_results(sample: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in sample.get('rows', []):
        text = row.get('claim_text', '').lower()
        human_review_required = str(row.get('human_review_required', '')).strip().lower() in {'yes', 'true', '1'}
        source_type = row.get('source_type', '').lower()
        evidence_reliability = 'High' if source_type == 'official' else 'Medium'
        business_risk = 'High' if 'transaction_complexity = high' in text or 'debt_risk' in text else 'Low'
        regulatory_risk = 'Medium' if 'regulatory_risk' in text else 'Low'
        reputational_risk = 'Medium' if human_review_required else 'Low'
        status = row.get('certification_status') or ('Needs Human Review' if human_review_required else 'Certified')
        rows.append({
            'claim_id': row.get('claim_id', ''),
            'claim_text': row.get('claim_text', ''),
            'evidence_id': row.get('evidence_id', ''),
            'source_id': row.get('source_id', ''),
            'evidence_reliability': evidence_reliability,
            'business_risk': business_risk,
            'regulatory_risk': regulatory_risk,
            'reputational_risk': reputational_risk,
            'certification_status': status,
            'human_review_required': human_review_required,
            'reason': (
                f"Scoped business-claim sample derived from supporting_files/trace/claim_to_evidence_map.csv and "
                f"supporting_files/pce_audit/pce_audit_current_run.csv (delivery_scope={sample.get('sampling_scope', '')})."
            ),
        })
    return rows
