from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class EvidenceSignal:
    source_id: str
    reliability: float
    signal_value: float
    missing: bool = False
    conflict: bool = False


def fuse_evidence(signals: list[EvidenceSignal]) -> tuple[float, float, str]:
    """Return (belief, confidence, rationale) without pretending missing evidence is positive evidence."""
    if not signals:
        return 0.0, 0.0, 'no evidence signals available'
    usable = [s for s in signals if not s.missing]
    if not usable:
        return 0.0, 0.1, 'all evidence signals missing'
    denom = sum(max(s.reliability, 0.0) for s in usable) or 1.0
    belief = sum(s.signal_value * max(s.reliability, 0.0) for s in usable) / denom
    conflict_penalty = 0.2 if any(s.conflict for s in usable) else 0.0
    confidence = max(0.0, min(1.0, denom / len(signals) - conflict_penalty))
    return belief, confidence, 'weighted evidence fusion with missing/conflict penalty'
