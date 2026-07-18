from __future__ import annotations

from dataclasses import replace

from .gate_a import RETURN_TARGET
from .models import Claim, GateResult, GateStatus, GapStatus, GapType, ResearchGap


def diagnose_gate_a_gap(
    gate_result: GateResult,
    claim: Claim,
    *,
    gap_type: GapType = GapType.EVIDENCE_MISSING,
    previous_gap: ResearchGap | None = None,
) -> ResearchGap:
    if gate_result.status != GateStatus.FAIL_RESEARCH_GAP:
        raise ValueError("Gap diagnosis requires a failed gate result")
    version = previous_gap.version + 1 if previous_gap else 1
    if gap_type == GapType.HUMAN_ONLY_INFORMATION:
        description = (
            "The Strategic Fit claim depends on confidential target information that "
            "public or automated research cannot reasonably verify."
        )
        required_action = (
            "Pause automated research and obtain the specified information from an "
            "authorized human reviewer."
        )
    else:
        description = (
            "The Strategic Fit claim is not supported by admissible evidence for the "
            "target's capability and business quality."
        )
        required_action = (
            "Research one bounded question and append a replayable Source and Evidence "
            "record linked to the existing claim."
        )
    return ResearchGap(
        gap_id=f"GAP-A-{gate_result.iteration:02d}-V{version}",
        gap_type=gap_type,
        originating_gate=gate_result.gate_name,
        failed_criterion=gate_result.failed_criterion,
        affected_claim_id=claim.claim_id,
        description=description,
        required_action=required_action,
        return_target=RETURN_TARGET,
        version=version,
        previous_gap_id=previous_gap.gap_id if previous_gap else "",
        created_iteration=gate_result.iteration,
    )


def resolve_gap(gap: ResearchGap, iteration: int) -> ResearchGap:
    return replace(
        gap,
        gap_id=f"GAP-A-{iteration:02d}-V{gap.version + 1}",
        status=GapStatus.RESOLVED,
        version=gap.version + 1,
        previous_gap_id=gap.gap_id,
        created_iteration=iteration,
    )
