from __future__ import annotations

def calibrate_confidence(raw: float, source_reliability: float, missing_rate: float = 0.0) -> float:
    return max(0.0, min(1.0, raw * source_reliability * (1.0 - missing_rate)))
