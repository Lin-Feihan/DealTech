from __future__ import annotations

from dataclasses import dataclass, field

from .models import (
    Claim,
    ControllerDecisionRecord,
    Evidence,
    EvidenceSnapshot,
    GateResult,
    HumanReviewItem,
    IterationRecord,
    NoProgressAssessment,
    ResearchAttempt,
    ResearchGap,
    ResearchQuestion,
    Source,
    TerminalState,
)


@dataclass
class CaseMemory:
    sources: list[Source] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    gate_results: list[GateResult] = field(default_factory=list)
    pce_results: list[dict] = field(default_factory=list)
    research_gaps: list[ResearchGap] = field(default_factory=list)
    research_attempts: list[ResearchAttempt] = field(default_factory=list)
    evidence_snapshots: list[EvidenceSnapshot] = field(default_factory=list)
    no_progress_assessments: list[NoProgressAssessment] = field(default_factory=list)
    controller_decisions: list[ControllerDecisionRecord] = field(default_factory=list)
    replans: list[ResearchQuestion] = field(default_factory=list)
    human_review_items: list[HumanReviewItem] = field(default_factory=list)
    terminal_decisions: list[TerminalState] = field(default_factory=list)
    iteration_records: list[IterationRecord] = field(default_factory=list)

    @staticmethod
    def _assert_unique(item_id: str, existing_ids: list[str], object_name: str) -> None:
        if item_id in existing_ids:
            raise ValueError(f"{object_name} {item_id} already exists; memory is append-only")

    def add_source(self, source: Source) -> None:
        self._assert_unique(source.source_id, [item.source_id for item in self.sources], "Source")
        self.sources.append(source)

    def add_evidence(self, evidence: Evidence) -> None:
        self._assert_unique(
            evidence.evidence_id,
            [item.evidence_id for item in self.evidence],
            "Evidence",
        )
        self.evidence.append(evidence)

    def add_claim(self, claim: Claim) -> None:
        self._assert_unique(claim.claim_id, [item.claim_id for item in self.claims], "Claim")
        self.claims.append(claim)
