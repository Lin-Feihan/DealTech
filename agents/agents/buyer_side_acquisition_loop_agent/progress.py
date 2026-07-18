from __future__ import annotations

from .models import (
    Claim,
    Evidence,
    EvidenceSnapshot,
    EvidenceStatus,
    GateResult,
    NoProgressAssessment,
    PCEStatus,
    ResearchAttempt,
    Source,
)


def _admissible_source_ids(sources: list[Source]) -> list[str]:
    completed = {"completed", "complete", "replayed", "source_replay_completed"}
    return [
        source.source_id
        for source in sources
        if source.pce_eligible
        and source.source_replay_status.strip().lower() in completed
        and bool(source.url_or_file.strip())
    ]


def build_evidence_snapshot(
    *,
    iteration: int,
    sources: list[Source],
    evidence: list[Evidence],
    claim: Claim,
    gate_result: GateResult,
) -> EvidenceSnapshot:
    return EvidenceSnapshot(
        snapshot_id=f"SNAPSHOT-A-{iteration:02d}",
        iteration=iteration,
        source_ids=[item.source_id for item in sources],
        admissible_source_ids=_admissible_source_ids(sources),
        evidence_ids=[item.evidence_id for item in evidence],
        supporting_evidence_ids=[
            item.evidence_id
            for item in evidence
            if item.status == EvidenceStatus.AVAILABLE and item.supports_claim
        ],
        claim_evidence_ids=list(claim.evidence_ids),
        pce_status=gate_result.pce_status,
        gate_status=gate_result.status,
        passed_gate_criteria=sum(1 for passed in gate_result.criteria.values() if passed),
    )


def assess_no_progress(
    *,
    case_id: str,
    previous: EvidenceSnapshot,
    current: EvidenceSnapshot,
    attempt: ResearchAttempt,
    prior_attempts: list[ResearchAttempt],
) -> NoProgressAssessment:
    new_source_ids = sorted(set(current.source_ids) - set(previous.source_ids))
    new_admissible_source_ids = sorted(
        set(current.admissible_source_ids) - set(previous.admissible_source_ids)
    )
    new_evidence_ids = sorted(set(current.evidence_ids) - set(previous.evidence_ids))
    deliverable = {PCEStatus.CERTIFIED, PCEStatus.CERTIFIED_WITH_CAVEAT}
    pce_improved = current.pce_status in deliverable and previous.pce_status not in deliverable
    gate_criteria_improved = current.passed_gate_criteria > previous.passed_gate_criteria
    identical_action_repeated = any(
        prior.action_key == attempt.action_key for prior in prior_attempts
    )
    material_progress = bool(
        new_admissible_source_ids or pce_improved or gate_criteria_improved
    )

    reasons: list[str] = []
    if not new_source_ids:
        reasons.append("No new Source was registered.")
    if not new_admissible_source_ids:
        reasons.append("No new admissible Source was registered.")
    if not new_evidence_ids:
        reasons.append("No new Evidence was registered.")
    elif not material_progress:
        reasons.append("New evidence did not add admissible support for the Claim.")
    if not pce_improved:
        reasons.append("The Claim's PCE deliverability did not improve.")
    if not gate_criteria_improved:
        reasons.append("No Strategic Thesis Gate criterion improved.")
    if identical_action_repeated:
        reasons.append("An identical unsuccessful research action was repeated.")
    if material_progress:
        reasons.append("At least one material evidence or gate signal improved.")

    return NoProgressAssessment(
        assessment_id=f"NO-PROGRESS-{current.iteration:02d}",
        case_id=case_id,
        current_iteration=current.iteration,
        compared_to_iteration=previous.iteration,
        new_source_ids=new_source_ids,
        new_admissible_source_ids=new_admissible_source_ids,
        new_evidence_ids=new_evidence_ids,
        pce_improved=pce_improved,
        gate_criteria_improved=gate_criteria_improved,
        identical_action_repeated=identical_action_repeated,
        material_progress=material_progress,
        reasons=reasons,
    )
