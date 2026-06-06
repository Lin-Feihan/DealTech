def blocking_reviews(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get('signoff_blocking') == 'Yes' and r.get('status') != 'completed']
