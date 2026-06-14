def weighted_score(parts: dict[str, float], weights: dict[str, float]) -> float:
    return sum(float(parts.get(k, 0)) * float(w) for k, w in weights.items())
