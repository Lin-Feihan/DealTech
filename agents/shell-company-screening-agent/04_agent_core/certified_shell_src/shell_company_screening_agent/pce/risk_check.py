def risk_review_ok(row: dict) -> bool:
    return not (row.get('risk_flag') == 'high' and row.get('human_review_required') != 'Yes')
