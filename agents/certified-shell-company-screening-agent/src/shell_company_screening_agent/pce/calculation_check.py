def calculation_ok(row: dict) -> bool:
    return row.get('calculation_required') != 'Yes' or row.get('calculation_replayed') == 'Yes'
