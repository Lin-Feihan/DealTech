from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class TransactionBoundary:
    market: str
    use_case: str
    delivery_boundary: str
    requires_human_review: bool = True
