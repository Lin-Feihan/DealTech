from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Iterable

@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    source_name: str
    source_type: str
    reliability: str

class MarketAdapter(Protocol):
    market_code: str
    def build_universe(self) -> Iterable[dict]: ...
