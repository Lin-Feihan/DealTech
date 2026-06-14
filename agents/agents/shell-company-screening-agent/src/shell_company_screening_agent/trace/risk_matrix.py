def risks_by_claim(rows):
    return {r.get("risk_id", ""): r for r in rows}
