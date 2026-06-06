def has_evidence(row: dict) -> bool:
    return bool(row.get('source_id') or row.get('evidence_id') or row.get('calc_id') or row.get('risk_id'))
