from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig', newline='') as f:
        return [{k: (v or '').strip() for k, v in row.items()} for row in csv.DictReader(f)]


def _count(path: Path) -> int:
    return len(_read_csv(path))


def _truthy(value: str) -> bool:
    return str(value or '').strip().lower() in {'yes', 'true', 'y', '1', 'human review required', 'needs_review'}


def _shell_trace_paths(case_dir: Path) -> dict[str, Path]:
    trace = case_dir / 'supporting_files' / 'trace'
    pce = case_dir / 'supporting_files' / 'pce_audit'
    return {
        'candidate_universe_table': trace / 'candidate_universe_table.csv',
        'hard_filter_table': trace / 'hard_filter_table.csv',
        'dd_evidence_table': trace / 'dd_evidence_table.csv',
        'er_brb_scoring_table': trace / 'er_brb_scoring_table.csv',
        'risk_matrix': trace / 'risk_matrix.csv',
        'financial_calculation_sheet': trace / 'financial_calculation_sheet.csv',
        'claim_to_evidence_map': trace / 'claim_to_evidence_map.csv',
        'pce_audit_current_run': pce / 'pce_audit_current_run.csv',
    }


def _count_true(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if _truthy(row.get(field, '')))


def _case_paths(case_dir: Path, names: list[str]) -> dict[str, Path]:
    return {name: case_dir / 'supporting_files' / name for name in names}


def load_business_metrics(agent_slug: str, case_dir: Path | None, pce_result: dict[str, Any]) -> dict[str, Any]:
    """Load agent-specific business workflow metrics from real supporting files.

    These metrics are intentionally separate from certification wrapper counts: they prove
    the workflow touched the business tables (candidate universe, hard filters, DD, risk,
    calculations, claim map, and PCE audit) instead of merely checking that final artifacts exist.
    """
    if agent_slug != 'shell-company-screening' or case_dir is None:
        if case_dir is None:
            return {}
        if agent_slug == 'spac-target-acquisition':
            paths = _case_paths(case_dir, [
                'candidate_universe.csv', 'hard_filter_table.csv', 'retained_candidates.csv',
                'excluded_candidates.csv', 'DD_evidence_table.csv', 'risk_matrix.csv',
                'calculation_sheet.csv', 'ER_BRB_scoring.csv', 'PCE_audit.csv'
            ])
            hard_rows = _read_csv(paths['hard_filter_table.csv'])
            pce_rows = _read_csv(paths['PCE_audit.csv'])
            return {
                'candidate_universe_count': _count(paths['candidate_universe.csv']),
                'hard_filter_pass_count': sum(1 for r in hard_rows if r.get('pass_fail', '').strip().lower() == 'pass'),
                'retained_candidate_count': _count(paths['retained_candidates.csv']),
                'excluded_candidate_count': _count(paths['excluded_candidates.csv']),
                'DD_evidence_count': _count(paths['DD_evidence_table.csv']),
                'risk_count': _count(paths['risk_matrix.csv']),
                'calculation_count': _count(paths['calculation_sheet.csv']),
                'ER_BRB_rows_count': _count(paths['ER_BRB_scoring.csv']),
                'PCE_claims_checked': len(pce_rows),
                'human_review_required_count': _count_true(pce_rows, 'human_review_required'),
                'final_delivery_allowed_count': sum(1 for r in pce_rows if _truthy(r.get('final_delivery_allowed', ''))),
                'overall_status': pce_result.get('overall_status', ''),
                'supporting_files_used': {name: str(path.relative_to(case_dir)) for name, path in paths.items() if path.exists()},
                'missing_supporting_files': [name for name, path in paths.items() if not path.exists()],
            }
        if agent_slug == 'acquisition-strategy':
            is_buyer = case_dir.name == 'buyer_side'
            side_name = 'buyer_side' if is_buyer else 'target_side'
            paths = _case_paths(case_dir, [
                'buyer_side_PCE_audit.csv' if is_buyer else 'target_side_PCE_audit.csv',
                'buyer_side_ER_BRB_scoring.csv' if is_buyer else 'target_side_ER_BRB_scoring.csv',
                'buyer_side_calculation_sheet.csv' if is_buyer else 'target_side_calculation_sheet.csv',
                'strategic_rationale_table.csv' if is_buyer else 'strategic_alternatives_table.csv',
                'integration_risk_matrix.csv' if is_buyer else 'target_side_risk_matrix.csv',
                'offer_attractiveness_matrix.csv' if not is_buyer else 'buyer_profile.md',
                'target_profile.md' if is_buyer else 'target_standalone_case.md',
                'transaction_context.md' if is_buyer else 'target_transaction_context.md',
            ])
            pce_key = 'buyer_side_PCE_audit.csv' if is_buyer else 'target_side_PCE_audit.csv'
            er_key = 'buyer_side_ER_BRB_scoring.csv' if is_buyer else 'target_side_ER_BRB_scoring.csv'
            calc_key = 'buyer_side_calculation_sheet.csv' if is_buyer else 'target_side_calculation_sheet.csv'
            strat_key = 'strategic_rationale_table.csv' if is_buyer else 'strategic_alternatives_table.csv'
            risk_key = 'integration_risk_matrix.csv' if is_buyer else 'target_side_risk_matrix.csv'
            pce_rows = _read_csv(paths[pce_key])
            metrics: dict[str, Any] = {
                'evidence_count': _count(case_dir / 'claim_to_evidence_map.csv'),
                'calculation_count': _count(paths[calc_key]),
                'ER_BRB_rows_count': _count(paths[er_key]),
                'PCE_claims_checked': len(pce_rows),
                'human_review_required_count': _count_true(pce_rows, 'human_review_required'),
                'blocked_claim_count': sum(1 for r in pce_rows if str(r.get('final_delivery_allowed', '')).strip().lower() not in {'true', 'yes', '1'}),
                'final_delivery_allowed_count': sum(1 for r in pce_rows if _truthy(r.get('final_delivery_allowed', ''))),
                'overall_status': pce_result.get('overall_status', ''),
            }
            if is_buyer:
                metrics['strategic_rationale_count'] = _count(paths[strat_key])
                metrics['integration_risk_count'] = _count(paths[risk_key])
            else:
                metrics['strategic_alternative_count'] = _count(paths[strat_key])
                metrics['offer_attractiveness_criteria_count'] = _count(paths['offer_attractiveness_matrix.csv'])
                metrics['risk_count'] = _count(paths[risk_key])
            metrics['supporting_files_used'] = {name: str(path.relative_to(case_dir)) for name, path in paths.items() if path.exists()}
            metrics['missing_supporting_files'] = [name for name, path in paths.items() if not path.exists()]
            metrics['view'] = side_name
            return metrics
        return {}

    paths = _shell_trace_paths(case_dir)
    hard_filter_rows = _read_csv(paths['hard_filter_table'])
    risk_rows = _read_csv(paths['risk_matrix'])
    pce_rows = _read_csv(paths['pce_audit_current_run'])

    pass_values = {'pass', 'include', 'retain', 'passed', 'kept'}
    fail_values = {'fail', 'exclude', 'failed', 'excluded', 'reject'}
    hard_pass = sum(1 for row in hard_filter_rows if row.get('filter_result', '').strip().lower() in pass_values)
    hard_fail = sum(1 for row in hard_filter_rows if row.get('filter_result', '').strip().lower() in fail_values)

    human_review_count = 0
    for rows in (hard_filter_rows, risk_rows, pce_rows):
        for row in rows:
            if _truthy(row.get('human_review_required', '')) or row.get('verification_status', '').lower() == 'needs_review':
                human_review_count += 1

    metrics: dict[str, Any] = {
        'candidate_universe_count': _count(paths['candidate_universe_table']),
        'hard_filter_pass_count': hard_pass,
        'hard_filter_fail_count': hard_fail,
        'DD_evidence_record_count': _count(paths['dd_evidence_table']),
        'ER_BRB_scoring_row_count': _count(paths['er_brb_scoring_table']),
        'risk_matrix_item_count': len(risk_rows),
        'calculation_sheet_row_count': _count(paths['financial_calculation_sheet']),
        'claim_to_evidence_map_row_count': _count(paths['claim_to_evidence_map']),
        'PCE_audit_row_count': len(pce_rows),
        'human_review_count': human_review_count,
        'final_certification_status': pce_result.get('overall_status', ''),
        'supporting_files_used': {name: str(path.relative_to(case_dir)) for name, path in paths.items() if path.exists()},
    }
    metrics['missing_supporting_files'] = [name for name, path in paths.items() if not path.exists()]
    return metrics
