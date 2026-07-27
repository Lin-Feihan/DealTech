def top_n(rows: list[dict], score_field: str = "weighted_total_score", n: int = 10) -> list[dict]:
    return sorted(rows, key=lambda r: float(r.get(score_field) or 0), reverse=True)[:n]
