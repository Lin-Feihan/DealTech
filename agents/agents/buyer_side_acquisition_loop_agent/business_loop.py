from __future__ import annotations

from typing import Any

from .business_models import BusinessGateResult, BusinessGateStatus


FATAL = {
    BusinessGateStatus.FATAL_STRATEGIC_MISMATCH,
    BusinessGateStatus.FATAL_VALUE_DESTRUCTION,
    BusinessGateStatus.FATAL_RISK,
    BusinessGateStatus.NO_GO,
}


def enter_unified_loop(gate: BusinessGateResult, iteration: int) -> dict[str, Any]:
    """Create the complete diagnosis→memory→controller→re-plan chain for any failure."""

    if gate.status in {BusinessGateStatus.PASS, BusinessGateStatus.CONDITIONAL_PASS}:
        raise ValueError("A passed gate must not enter the failure loop")
    block_target = {"GATE_A": "Block A", "GATE_B": "Block B", "GATE_C": "Block C"}[gate.gate_id]
    affected = [module for criterion in gate.criteria if criterion.outcome.value == "FAIL" for module in criterion.affected_module_ids]
    if not affected and gate.criteria:
        affected = list(gate.criteria[-1].affected_module_ids)
    gap_type = (
        "CALCULATION_GAP" if gate.status == BusinessGateStatus.FAIL_CALCULATION_GAP
        else "HUMAN_REVIEW_REQUIRED" if gate.status == BusinessGateStatus.HUMAN_REVIEW_REQUIRED
        else "FATAL_BUSINESS_GAP" if gate.status in FATAL
        else "RESEARCH_OR_MANDATE_GAP"
    )
    gaps = [
        {
            "gap_id": f"LOOP-{gate.gate_id}-{iteration:02d}-{index:02d}",
            "gap_type": gap_type,
            "originating_gate": gate.gate_id,
            "failed_criterion_id": criterion_id,
            "return_block": block_target,
            "return_module": affected[min(index - 1, len(affected) - 1)] if affected else "",
            "closure_test": "Re-evaluate the failed criterion with admissible evidence and replayed calculations.",
        }
        for index, criterion_id in enumerate(gate.failed_criterion_ids or ["GATE_LEVEL_FAILURE"], 1)
    ]
    if gate.status in FATAL:
        controller = "STOP_FATAL"
    elif gate.status == BusinessGateStatus.HUMAN_REVIEW_REQUIRED:
        controller = "ESCALATE_HUMAN_REVIEW"
    else:
        controller = "RETRY_TARGETED_STAGE"
    return {
        "gap_diagnosis": gaps,
        "memory_update": {
            "iteration": iteration,
            "gate_id": gate.gate_id,
            "gate_status": gate.status.value,
            "appended_gap_ids": [item["gap_id"] for item in gaps],
            "history_is_append_only": True,
        },
        "loop_controller": {
            "decision": controller,
            "return_block": block_target if controller == "RETRY_TARGETED_STAGE" else "",
            "return_modules": affected if controller == "RETRY_TARGETED_STAGE" else [],
        },
        "replan": {
            "scope": "targeted_only",
            "return_block": block_target,
            "return_modules": affected,
            "required_closure_tests": [item["closure_test"] for item in gaps],
        },
    }
