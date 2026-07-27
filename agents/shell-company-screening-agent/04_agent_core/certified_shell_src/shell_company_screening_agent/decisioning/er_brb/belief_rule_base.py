from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class BeliefRule:
    rule_id: str
    stage: str
    signal: str
    weight: float
    rationale: str

class BeliefRuleBase:
    def __init__(self, rules: Iterable[BeliefRule]):
        self.rules = list(rules)

    def rules_for_stage(self, stage: str) -> list[BeliefRule]:
        return [r for r in self.rules if r.stage == stage]
