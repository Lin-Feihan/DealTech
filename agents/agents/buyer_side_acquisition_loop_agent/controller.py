from __future__ import annotations

from .models import (
    ControllerDecision,
    ControllerDecisionRecord,
    GateResult,
    GateStatus,
    GapType,
    LoopState,
    NoProgressAssessment,
    ResearchGap,
)


def _record(
    *,
    iteration: int,
    decision: ControllerDecision,
    reason: str,
    gap: ResearchGap,
    next_iteration: int | None,
) -> ControllerDecisionRecord:
    return ControllerDecisionRecord(
        decision_id=f"CTRL-{iteration:02d}-{decision.value}",
        iteration=iteration,
        decision=decision,
        reason=reason,
        return_target=(
            gap.return_target
            if decision
            in {
                ControllerDecision.RETRY_TARGETED_RESEARCH,
                ControllerDecision.USE_ALTERNATE_METHOD,
            }
            else ""
        ),
        next_iteration=next_iteration,
        related_gap_ids=[gap.gap_id],
    )


def initial_controller_decision(
    gap: ResearchGap, loop_state: LoopState
) -> ControllerDecisionRecord:
    if gap.gap_type == GapType.HUMAN_ONLY_INFORMATION:
        return _record(
            iteration=loop_state.current_iteration,
            decision=ControllerDecision.ESCALATE_HUMAN_REVIEW,
            reason=(
                "The required information is confidential or management-controlled; "
                "automated public research must not be repeated."
            ),
            gap=gap,
            next_iteration=None,
        )
    if loop_state.current_iteration >= loop_state.maximum_iterations:
        return _record(
            iteration=loop_state.current_iteration,
            decision=ControllerDecision.STOP_ITERATION_BUDGET,
            reason="The configured iteration budget is already exhausted.",
            gap=gap,
            next_iteration=None,
        )
    return _record(
        iteration=loop_state.current_iteration,
        decision=ControllerDecision.RETRY_TARGETED_RESEARCH,
        reason="One targeted evidence-repair iteration is permitted by the contract.",
        gap=gap,
        next_iteration=loop_state.current_iteration + 1,
    )


def post_iteration_controller_decision(
    *,
    gate_result: GateResult,
    gap: ResearchGap,
    loop_state: LoopState,
    assessment: NoProgressAssessment,
) -> ControllerDecisionRecord:
    if gate_result.status in {GateStatus.PASS, GateStatus.CONDITIONAL_PASS}:
        return _record(
            iteration=loop_state.current_iteration,
            decision=ControllerDecision.ADVANCE,
            reason="Strategic Thesis Gate no longer has an unresolved research gap.",
            gap=gap,
            next_iteration=None,
        )
    if loop_state.no_progress_count >= loop_state.maximum_no_progress_iterations:
        return _record(
            iteration=loop_state.current_iteration,
            decision=ControllerDecision.STOP_NO_PROGRESS,
            reason=(
                "The configured consecutive no-progress limit was reached; another "
                "unsuccessful action is not permitted."
            ),
            gap=gap,
            next_iteration=None,
        )
    if loop_state.current_iteration >= loop_state.maximum_iterations:
        return _record(
            iteration=loop_state.current_iteration,
            decision=ControllerDecision.STOP_ITERATION_BUDGET,
            reason=(
                "Gate A still failed at the maximum iteration; no additional "
                "iteration may begin."
            ),
            gap=gap,
            next_iteration=None,
        )
    if not assessment.material_progress:
        return _record(
            iteration=loop_state.current_iteration,
            decision=ControllerDecision.USE_ALTERNATE_METHOD,
            reason=(
                "The last action made no material improvement; only a distinct "
                "alternate method may be attempted."
            ),
            gap=gap,
            next_iteration=loop_state.current_iteration + 1,
        )
    return _record(
        iteration=loop_state.current_iteration,
        decision=ControllerDecision.RETRY_TARGETED_RESEARCH,
        reason="Material progress occurred but Gate A still requires targeted evidence.",
        gap=gap,
        next_iteration=loop_state.current_iteration + 1,
    )


def technical_failure_decision(
    *, iteration: int, gap: ResearchGap, reason: str
) -> ControllerDecisionRecord:
    return _record(
        iteration=iteration,
        decision=ControllerDecision.FAIL_TECHNICAL,
        reason=reason,
        gap=gap,
        next_iteration=None,
    )
