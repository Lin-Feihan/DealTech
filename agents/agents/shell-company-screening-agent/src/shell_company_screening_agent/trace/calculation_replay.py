from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

WEIGHTS = {
    "synergy_score": 0.30,
    "value_creation_score": 0.30,
    "transaction_feasibility_score": 0.25,
    "risk_control_score": 0.15,
}
SCORE_RE = re.compile(
    r"(synergy_score|value_creation_score|transaction_feasibility_score|risk_control_score)=(-?[0-9]+(?:[.][0-9]+)?)"
)


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def parse_inputs(text: str) -> dict[str, float]:
    return {k: float(v) for k, v in SCORE_RE.findall(text or '')}


def replay_trace_calculations(example_dir: Path) -> dict:
    trace = example_dir / 'trace'
    calc_rows, calc_fields = read_csv(trace / 'financial_calculation_sheet.csv')
    claim_rows, claim_fields = read_csv(trace / 'claim_to_evidence_map.csv')
    audit_rows, audit_fields = read_csv(example_dir / 'pce_audit' / 'pce_audit_current_run.csv')

    replayed_claims: set[str] = set()
    failures: list[dict[str, str]] = []

    for row in calc_rows:
        if row.get('calculation_required') != 'Yes':
            continue
        if row.get('metric_name') != 'weighted_total_score':
            failures.append({'calc_id': row.get('calc_id', ''), 'reason': 'unsupported_metric'})
            continue
        values = parse_inputs(row.get('input_1', ''))
        missing = [k for k in WEIGHTS if k not in values]
        if missing:
            failures.append({'calc_id': row.get('calc_id', ''), 'reason': 'missing_inputs:' + ','.join(missing)})
            continue
        expected = round(sum(values[k] * w for k, w in WEIGHTS.items()), 2)
        try:
            output = round(float(row.get('output_value') or 'nan'), 2)
        except Exception:
            failures.append({'calc_id': row.get('calc_id', ''), 'reason': 'invalid_output'})
            continue
        if abs(expected - output) <= 0.011:
            row['calculation_replayed'] = 'Yes'
            if row.get('linked_claim_id'):
                replayed_claims.add(row['linked_claim_id'])
        else:
            failures.append({'calc_id': row.get('calc_id', ''), 'reason': f'mismatch computed={expected} output={output}'})

    for rows in [claim_rows, audit_rows]:
        for row in rows:
            if row.get('claim_id') in replayed_claims:
                row['calculation_replayed'] = 'Yes'
                if row.get('certification_status') not in {'Needs Human Review', 'Not Certified'}:
                    row['certification_status'] = 'Certified'

    if calc_fields:
        write_csv(trace / 'financial_calculation_sheet.csv', calc_rows, calc_fields)
    if claim_fields:
        write_csv(trace / 'claim_to_evidence_map.csv', claim_rows, claim_fields)
    if audit_fields:
        write_csv(example_dir / 'pce_audit' / 'pce_audit_current_run.csv', audit_rows, audit_fields)

    result = {
        'replayed_claim_count': len(replayed_claims),
        'failure_count': len(failures),
        'failures': failures[:20],
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
    out = example_dir / 'run_records/run_replay_trace_calculations/replay_result.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result
