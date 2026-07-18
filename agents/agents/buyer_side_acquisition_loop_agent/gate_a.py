from __future__ import annotations

from typing import Any

from .models import Claim, GateResult, GateStatus, Mandate, PCEStatus, ResearchContract


EVIDENCE_CRITERION = "Target Capability & Business Quality evidence supports Strategic Fit"
RETURN_TARGET = "Target Capability & Business Quality"


def evaluate_strategic_thesis_gate(
    *,
    mandate: Mandate,
    contract: ResearchContract,
    claim: Claim,
    pce_precheck: dict[str, Any],
    iteration: int,
) -> GateResult:
    if contract.gate_name != "Strategic Thesis Gate":
        raise ValueError("Gate A evaluator received the wrong gate contract")

    pce_status = PCEStatus(pce_precheck["status"])
    criteria = {
        "Buyer Strategic Need is explicit": bool(mandate.buyer_strategic_need.strip()),
        "Strategic Rationale is explicit": bool(mandate.strategic_rationale.strip()),
        "Target Attractiveness is explicit": bool(mandate.target_attractiveness.strip()),
        "Industry / Competitive Position is explicit": bool(
            mandate.industry_competitive_position.strip()
        ),
        EVIDENCE_CRITERION: (
            claim.business_module == "Strategic Fit"
            and pce_status == PCEStatus.CERTIFIED
            and bool(pce_precheck["selected_evidence_id"])
            and bool(pce_precheck["selected_source_id"])
        ),
    }
    failed = next((name for name, passed in criteria.items() if not passed), "")
    if failed:
        return GateResult(
            gate_name=contract.gate_name,
            iteration=iteration,
            status=GateStatus.FAIL_RESEARCH_GAP,
            pce_status=pce_status,
            criteria=criteria,
            reason=(
                "Strategic Thesis Gate failed because the Strategic Fit claim lacks "
                "admissible evidence for Target Capability & Business Quality."
            ),
            failed_criterion=failed,
            return_target=RETURN_TARGET,
        )
    return GateResult(
        gate_name=contract.gate_name,
        iteration=iteration,
        status=GateStatus.PASS,
        pce_status=pce_status,
        criteria=criteria,
        reason=(
            "Strategic Thesis Gate passed after the targeted evidence repair; this is "
            "a Block A gate result, not a full-deal recommendation."
        ),
    )
