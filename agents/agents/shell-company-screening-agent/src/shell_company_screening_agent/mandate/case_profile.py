from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class CaseProfile:
    case_id: str
    case_name: str
    market_adapter: str
    is_example_case: bool = True
