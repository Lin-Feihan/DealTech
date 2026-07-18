from __future__ import annotations

from pathlib import Path
from typing import Any

from .certification_adapter import run_claim_pce_precheck
from .controller import (
    initial_controller_decision,
    post_iteration_controller_decision,
    technical_failure_decision,
)
from .gap_diagnosis import diagnose_gate_a_gap, resolve_gap
from .gate_a import evaluate_strategic_thesis_gate
from .human_review import create_human_review_item
from .memory import CaseMemory
from .models import (
    Claim,
    ControllerDecision,
    Evidence,
    EvidenceStatus,
    GateResult,
    GateStatus,
    GapStatus,
    GapType,
    IterationRecord,
    LoopState,
    LoopStatus,
    Mandate,
    PCEStatus,
    QuestionStatus,
    ResearchAttempt,
    ResearchAttemptStatus,
    ResearchContract,
    ResearchGap,
    ResearchQuestion,
    Source,
    TerminalState,
    TerminalStatus,
)
from .progress import assess_no_progress, build_evidence_snapshot
from .replanner import replan_for_gap
from .storage import load_case, to_primitive, write_json


def _question_from_dict(data: dict[str, Any]) -> ResearchQuestion:
    values = dict(data)
    values["status"] = QuestionStatus(values.get("status", QuestionStatus.PLANNED.value))
    return ResearchQuestion(**values)


def _evidence_from_dict(data: dict[str, Any]) -> Evidence:
    values = dict(data)
    values["status"] = EvidenceStatus(values["status"])
    return Evidence(**values)


def _validate_case_links(mandate: Mandate, contract: ResearchContract, claim: Claim) -> None:
    if mandate.case_id != contract.case_id:
        raise ValueError("Mandate and Research Contract must have the same case_id")
    if mandate.max_iterations != contract.iteration_budget:
        raise ValueError("Mandate and Research Contract iteration budgets must match")
    if claim.business_module != "Strategic Fit":
        raise ValueError("Gate A loop requires one Strategic Fit claim")


def _normalise_research_actions(case_data: dict[str, Any]) -> list[dict[str, Any]]:
    if "research_actions" in case_data:
        return [dict(item) for item in case_data["research_actions"]]
    repair = case_data.get("repair_research_result")
    if not repair:
        return []
    return [
        {
            "action_id": "ATTEMPT-A-02",
            "action_key": "TARGET_CAPABILITY_EVIDENCE_SEARCH",
            "method": "controlled synthetic fixture research",
            "outcome": "One replayable supporting record was found and appended.",
            "source": repair["source"],
            "evidence": repair["evidence"],
        }
    ]


def _source_is_admissible(source: Source) -> bool:
    completed = {"completed", "complete", "replayed", "source_replay_completed"}
    return (
        source.pce_eligible
        and source.source_replay_status.strip().lower() in completed
        and bool(source.url_or_file.strip())
    )


def _execute_research_action(
    *,
    case_id: str,
    action: dict[str, Any],
    question: ResearchQuestion,
    claim: Claim,
    memory: CaseMemory,
) -> ResearchAttempt:
    source = Source(**action["source"]) if action.get("source") else None
    evidence = _evidence_from_dict(action["evidence"]) if action.get("evidence") else None
    if evidence and evidence.claim_id != claim.claim_id:
        raise ValueError("research action Evidence must link to the Strategic Fit claim")
    if evidence and source and evidence.source_id != source.source_id:
        raise ValueError("research action Source-Evidence lineage is invalid")
    if evidence and not source and evidence.source_id not in claim.source_ids:
        raise ValueError("research action Evidence references an unavailable Source")

    source_ids: list[str] = []
    evidence_ids: list[str] = []
    if source:
        memory.add_source(source)
        source_ids.append(source.source_id)
    if evidence:
        memory.add_evidence(evidence)
        claim.add_lineage(evidence)
        evidence_ids.append(evidence.evidence_id)

    if not source and not evidence:
        status = ResearchAttemptStatus.COMPLETED_NO_EVIDENCE
    elif (
        source
        and evidence
        and _source_is_admissible(source)
        and evidence.status == EvidenceStatus.AVAILABLE
        and evidence.supports_claim
    ):
        status = ResearchAttemptStatus.COMPLETED_ADMISSIBLE_EVIDENCE
    else:
        status = ResearchAttemptStatus.COMPLETED_INSUFFICIENT_EVIDENCE

    return ResearchAttempt(
        attempt_id=action["action_id"],
        case_id=case_id,
        iteration=question.iteration,
        action_key=action["action_key"],
        method=action["method"],
        question_id=question.question_id,
        return_target=question.owner_module,
        status=status,
        source_ids_added=source_ids,
        evidence_ids_added=evidence_ids,
        outcome=action["outcome"],
    )


def _latest_gap_states(memory: CaseMemory) -> tuple[list[ResearchGap], list[ResearchGap]]:
    latest: dict[str, ResearchGap] = {}
    for gap in memory.research_gaps:
        latest[gap.gap_family_id] = gap
    open_gaps = [gap for gap in latest.values() if gap.status == GapStatus.OPEN]
    resolved_gaps = [gap for gap in latest.values() if gap.status == GapStatus.RESOLVED]
    return open_gaps, resolved_gaps


def _artifact_references(gate_count: int) -> list[str]:
    names = [
        "run_summary.json",
        "mandate.json",
        "research_contract.json",
        "sources.json",
        "evidence.json",
        "claims.json",
        "research_gap.json",
        "research_gaps.json",
        "gate_a_results.json",
        "pce_results.json",
        "iteration_records.json",
        "loop_state.json",
        "terminal_state.json",
        "controller_decisions.json",
        "no_progress_assessment.json",
        "human_review_items.json",
        "research_attempts.json",
        "resolved_and_open_gaps.json",
        "evidence_snapshots.json",
        "replans.json",
        "terminal_decisions.json",
    ]
    names.extend(f"gate_a_iteration_{iteration}.json" for iteration in range(1, gate_count + 1))
    return names


def _create_terminal_state(
    *,
    status: TerminalStatus,
    mandate: Mandate,
    memory: CaseMemory,
    loop_state: LoopState,
    final_gate: GateResult,
    stopping_reason: str,
) -> TerminalState:
    open_gaps, resolved_gaps = _latest_gap_states(memory)
    unresolved_claims = (
        []
        if final_gate.status in {GateStatus.PASS, GateStatus.CONDITIONAL_PASS}
        else [claim.claim_id for claim in memory.claims]
    )
    terminal = TerminalState(
        status=status,
        case_id=mandate.case_id,
        final_gate_a_status=final_gate.status,
        final_pce_status=final_gate.pce_status,
        open_gaps=[gap.gap_id for gap in open_gaps],
        unresolved_claims=unresolved_claims,
        human_review_items=[item.review_id for item in memory.human_review_items],
        iterations_used=loop_state.completed_iterations,
        no_progress_count=loop_state.no_progress_count,
        stopping_reason=stopping_reason,
        generated_artifact_references=_artifact_references(len(memory.gate_results)),
    )
    loop_state.status = LoopStatus(status.value)
    loop_state.terminal_state = status
    loop_state.stopping_reason = stopping_reason
    loop_state.current_return_target = ""
    loop_state.current_stage = f"Terminal: {status.value}"
    loop_state.final_gate_status = final_gate.status
    loop_state.open_gap_ids = [gap.gap_id for gap in open_gaps]
    loop_state.resolved_gap_ids = [gap.gap_id for gap in resolved_gaps]
    memory.terminal_decisions.append(terminal)
    return terminal


def _write_artifacts(
    *,
    output_dir: Path,
    scenario_name: str,
    mandate: Mandate,
    contract: ResearchContract,
    memory: CaseMemory,
    loop_state: LoopState,
    terminal: TerminalState,
) -> dict[str, Any]:
    open_gaps, resolved_gaps = _latest_gap_states(memory)
    run_summary = {
        "milestone": "Robust Loop Termination and Human Review Escalation",
        "scenario": scenario_name,
        "case_id": mandate.case_id,
        "business_scope": "Block A: Strategic Thesis",
        "gate": "Strategic Thesis Gate",
        "iterations": [
            {
                "iteration": gate.iteration,
                "gate_status": gate.status,
                "pce_status": gate.pce_status,
                "reason": gate.reason,
            }
            for gate in memory.gate_results
        ],
        "controller_decisions": [
            {
                "iteration": item.iteration,
                "decision": item.decision,
                "reason": item.reason,
                "return_target": item.return_target,
            }
            for item in memory.controller_decisions
        ],
        "terminal_state": terminal.status,
        "stopping_reason": terminal.stopping_reason,
        "iterations_used": terminal.iterations_used,
        "iteration_budget": loop_state.maximum_iterations,
        "no_progress_count": terminal.no_progress_count,
        "human_review_required": loop_state.human_review_required,
        "full_deal_recommendation_generated": False,
    }
    artifact_map: dict[str, Any] = {
        "run_summary.json": run_summary,
        "mandate.json": mandate,
        "research_contract.json": contract,
        "sources.json": memory.sources,
        "evidence.json": memory.evidence,
        "claims.json": memory.claims,
        "research_gap.json": memory.research_gaps[0],
        "research_gaps.json": memory.research_gaps,
        "gate_a_results.json": memory.gate_results,
        "pce_results.json": memory.pce_results,
        "iteration_records.json": memory.iteration_records,
        "loop_state.json": loop_state,
        "terminal_state.json": terminal,
        "controller_decisions.json": memory.controller_decisions,
        "no_progress_assessment.json": {
            "assessment_count": len(memory.no_progress_assessments),
            "assessments": memory.no_progress_assessments,
        },
        "human_review_items.json": memory.human_review_items,
        "research_attempts.json": memory.research_attempts,
        "resolved_and_open_gaps.json": {
            "open_gaps": open_gaps,
            "resolved_gaps": resolved_gaps,
        },
        "evidence_snapshots.json": memory.evidence_snapshots,
        "replans.json": memory.replans,
        "terminal_decisions.json": memory.terminal_decisions,
    }
    for index, (gate, pce) in enumerate(
        zip(memory.gate_results, memory.pce_results), start=1
    ):
        artifact_map[f"gate_a_iteration_{index}.json"] = {
            "gate_result": gate,
            "pce_precheck": pce,
        }
    for filename, value in artifact_map.items():
        write_json(output_dir / filename, value)
    return run_summary


def _result(
    *,
    output_path: Path,
    run_summary: dict[str, Any],
    mandate: Mandate,
    contract: ResearchContract,
    memory: CaseMemory,
    loop_state: LoopState,
    terminal: TerminalState,
) -> dict[str, Any]:
    return {
        "output_dir": str(output_path),
        "run_summary": to_primitive(run_summary),
        "mandate": mandate,
        "research_contract": contract,
        "memory": memory,
        "gate_a_iteration_1": memory.gate_results[0],
        "research_gap": memory.research_gaps[0],
        "controller_decision": to_primitive(memory.controller_decisions[0]),
        "gate_a_iteration_2": (
            memory.gate_results[1] if len(memory.gate_results) > 1 else None
        ),
        "loop_state": loop_state,
        "terminal_state": terminal,
    }


def run_case(case_path: str | Path, output_dir: str | Path | None = None) -> dict[str, Any]:
    case_path = Path(case_path).resolve()
    case_data = load_case(case_path)
    if case_data.get("schema_version") == "milestone-3":
        from .business_runtime import run_end_to_end_case

        return run_end_to_end_case(
            case_data,
            case_path,
            Path(output_dir).resolve() if output_dir is not None else None,
        )
    output_path = (
        Path(output_dir).resolve()
        if output_dir is not None
        else case_path.parent.joinpath("run_output").resolve()
    )
    scenario_name = case_data.get("scenario", {}).get("name", "repair_success")

    mandate = Mandate(**case_data["mandate"])
    contract = ResearchContract(**case_data["research_contract"])
    question_1 = _question_from_dict(case_data["initial_research_question"])
    claim = Claim(**case_data["claim"])
    missing_evidence = _evidence_from_dict(case_data["initial_evidence"])
    _validate_case_links(mandate, contract, claim)
    if missing_evidence.claim_id != claim.claim_id:
        raise ValueError("initial evidence marker must link to the Strategic Fit claim")

    gap_type = GapType(
        case_data.get("gap_diagnosis", {}).get(
            "gap_type", GapType.EVIDENCE_MISSING.value
        )
    )
    if gap_type == GapType.HUMAN_ONLY_INFORMATION:
        claim.human_review_required = True

    memory = CaseMemory()
    memory.add_claim(claim)
    memory.add_evidence(missing_evidence)
    claim.add_lineage(missing_evidence)
    question_1.status = QuestionStatus.COMPLETED

    loop_state = LoopState(
        loop_id=f"LOOP-{mandate.case_id}",
        case_id=mandate.case_id,
        current_iteration=1,
        maximum_iterations=contract.iteration_budget,
        status=LoopStatus.RUNNING,
        current_stage=contract.gate_name,
        maximum_no_progress_iterations=contract.maximum_no_progress_iterations,
    )

    initial_attempt_config = case_data.get("initial_research_attempt", {})
    initial_attempt = ResearchAttempt(
        attempt_id=initial_attempt_config.get("action_id", "ATTEMPT-A-01"),
        case_id=mandate.case_id,
        iteration=1,
        action_key=initial_attempt_config.get(
            "action_key", "INITIAL_STRATEGIC_FIT_EVIDENCE_CHECK"
        ),
        method=initial_attempt_config.get(
            "method", "initial mandate and registered-evidence review"
        ),
        question_id=question_1.question_id,
        return_target=question_1.owner_module,
        status=ResearchAttemptStatus.COMPLETED_NO_EVIDENCE,
        source_ids_added=[],
        evidence_ids_added=[],
        outcome=initial_attempt_config.get(
            "outcome", "No admissible evidence was registered at intake."
        ),
    )
    memory.research_attempts.append(initial_attempt)
    loop_state.attempted_research_actions.append(initial_attempt.attempt_id)

    pce_1 = run_claim_pce_precheck(
        case_id=mandate.case_id,
        claim=claim,
        sources=memory.sources,
        evidence=memory.evidence,
    )
    gate_1 = evaluate_strategic_thesis_gate(
        mandate=mandate,
        contract=contract,
        claim=claim,
        pce_precheck=pce_1,
        iteration=1,
    )
    if gate_1.status != GateStatus.FAIL_RESEARCH_GAP:
        raise ValueError("Synthetic termination cases must fail their first Gate A evaluation")
    memory.pce_results.append(pce_1)
    memory.gate_results.append(gate_1)
    loop_state.gate_history.append(gate_1.status)

    latest_gap = diagnose_gate_a_gap(gate_1, claim, gap_type=gap_type)
    memory.research_gaps.append(latest_gap)
    loop_state.open_gap_ids = [latest_gap.gap_id]
    initial_snapshot = build_evidence_snapshot(
        iteration=1,
        sources=memory.sources,
        evidence=memory.evidence,
        claim=claim,
        gate_result=gate_1,
    )
    memory.evidence_snapshots.append(initial_snapshot)

    decision = initial_controller_decision(latest_gap, loop_state)
    memory.controller_decisions.append(decision)
    record_1 = IterationRecord(
        iteration=1,
        research_question_ids=[question_1.question_id],
        modules_executed=[question_1.owner_module],
        source_ids=[],
        evidence_ids=[item.evidence_id for item in memory.evidence],
        claim_evidence_ids=list(claim.evidence_ids),
        pce_status=claim.pce_status,
        gate_status=gate_1.status,
        gap_ids=[latest_gap.gap_id],
        change_summary="Initial Strategic Fit claim remained unsupported by admissible evidence.",
        evidence_snapshot_id=initial_snapshot.snapshot_id,
        controller_decision=decision.decision,
    )
    memory.iteration_records.append(record_1)
    loop_state.completed_iterations = 1

    if decision.decision == ControllerDecision.ESCALATE_HUMAN_REVIEW:
        review = create_human_review_item(
            case_id=mandate.case_id,
            claim=claim,
            gap=latest_gap,
            config=case_data["human_review"],
            iteration=1,
        )
        memory.human_review_items.append(review)
        loop_state.human_review_required = True
        terminal = _create_terminal_state(
            status=TerminalStatus.AWAITING_HUMAN_REVIEW,
            mandate=mandate,
            memory=memory,
            loop_state=loop_state,
            final_gate=gate_1,
            stopping_reason=(
                "Runtime paused because the unresolved Strategic Fit claim requires "
                "confidential information from an authorized human reviewer."
            ),
        )
        run_summary = _write_artifacts(
            output_dir=output_path,
            scenario_name=scenario_name,
            mandate=mandate,
            contract=contract,
            memory=memory,
            loop_state=loop_state,
            terminal=terminal,
        )
        from .review_runtime import initialize_human_review_workspace

        initialize_human_review_workspace(
            output_dir=output_path,
            case_data=case_data,
            terminal=terminal,
            human_review_items=memory.human_review_items,
        )
        return _result(
            output_path=output_path,
            run_summary=run_summary,
            mandate=mandate,
            contract=contract,
            memory=memory,
            loop_state=loop_state,
            terminal=terminal,
        )

    actions = _normalise_research_actions(case_data)
    action_index = 0
    final_gate = gate_1
    terminal: TerminalState | None = None

    while decision.decision in {
        ControllerDecision.RETRY_TARGETED_RESEARCH,
        ControllerDecision.USE_ALTERNATE_METHOD,
    }:
        next_iteration = decision.next_iteration
        if next_iteration is None or next_iteration > loop_state.maximum_iterations:
            terminal = _create_terminal_state(
                status=TerminalStatus.STOPPED_ITERATION_BUDGET,
                mandate=mandate,
                memory=memory,
                loop_state=loop_state,
                final_gate=final_gate,
                stopping_reason=(
                    "The configured iteration budget was exhausted before Gate A passed."
                ),
            )
            break
        if action_index >= len(actions):
            technical = technical_failure_decision(
                iteration=loop_state.current_iteration,
                gap=latest_gap,
                reason="No deterministic research action was configured for the next iteration.",
            )
            memory.controller_decisions.append(technical)
            terminal = _create_terminal_state(
                status=TerminalStatus.FAILED_TECHNICAL,
                mandate=mandate,
                memory=memory,
                loop_state=loop_state,
                final_gate=final_gate,
                stopping_reason=technical.reason,
            )
            break

        loop_state.current_iteration = next_iteration
        loop_state.current_stage = "Re-plan"
        loop_state.current_return_target = latest_gap.return_target
        question = replan_for_gap(latest_gap, next_iteration)
        memory.replans.append(question)
        action = actions[action_index]
        action_index += 1
        prior_attempts = list(memory.research_attempts)

        try:
            attempt = _execute_research_action(
                case_id=mandate.case_id,
                action=action,
                question=question,
                claim=claim,
                memory=memory,
            )
        except (KeyError, TypeError, ValueError) as exc:
            attempt = ResearchAttempt(
                attempt_id=action.get("action_id", f"ATTEMPT-TECH-{next_iteration:02d}"),
                case_id=mandate.case_id,
                iteration=next_iteration,
                action_key=action.get("action_key", "INVALID_ACTION"),
                method=action.get("method", "invalid deterministic action"),
                question_id=question.question_id,
                return_target=question.owner_module,
                status=ResearchAttemptStatus.FAILED_TECHNICAL,
                source_ids_added=[],
                evidence_ids_added=[],
                outcome=f"Technical action failure: {exc}",
            )
            memory.research_attempts.append(attempt)
            loop_state.attempted_research_actions.append(attempt.attempt_id)
            loop_state.completed_iterations = next_iteration
            technical = technical_failure_decision(
                iteration=next_iteration,
                gap=latest_gap,
                reason=attempt.outcome,
            )
            memory.controller_decisions.append(technical)
            memory.iteration_records.append(
                IterationRecord(
                    iteration=next_iteration,
                    research_question_ids=[question.question_id],
                    modules_executed=[question.owner_module],
                    source_ids=[item.source_id for item in memory.sources],
                    evidence_ids=[item.evidence_id for item in memory.evidence],
                    claim_evidence_ids=list(claim.evidence_ids),
                    pce_status=claim.pce_status,
                    gate_status=final_gate.status,
                    gap_ids=[latest_gap.gap_id],
                    change_summary=attempt.outcome,
                    research_attempt_id=attempt.attempt_id,
                    evidence_snapshot_id=memory.evidence_snapshots[-1].snapshot_id,
                    controller_decision=technical.decision,
                )
            )
            terminal = _create_terminal_state(
                status=TerminalStatus.FAILED_TECHNICAL,
                mandate=mandate,
                memory=memory,
                loop_state=loop_state,
                final_gate=final_gate,
                stopping_reason=attempt.outcome,
            )
            break

        memory.research_attempts.append(attempt)
        loop_state.attempted_research_actions.append(attempt.attempt_id)
        question.status = QuestionStatus.COMPLETED
        loop_state.current_stage = contract.gate_name

        pce = run_claim_pce_precheck(
            case_id=mandate.case_id,
            claim=claim,
            sources=memory.sources,
            evidence=memory.evidence,
        )
        gate = evaluate_strategic_thesis_gate(
            mandate=mandate,
            contract=contract,
            claim=claim,
            pce_precheck=pce,
            iteration=next_iteration,
        )
        memory.pce_results.append(pce)
        memory.gate_results.append(gate)
        loop_state.gate_history.append(gate.status)
        current_snapshot = build_evidence_snapshot(
            iteration=next_iteration,
            sources=memory.sources,
            evidence=memory.evidence,
            claim=claim,
            gate_result=gate,
        )
        assessment = assess_no_progress(
            case_id=mandate.case_id,
            previous=memory.evidence_snapshots[-1],
            current=current_snapshot,
            attempt=attempt,
            prior_attempts=prior_attempts,
        )
        memory.evidence_snapshots.append(current_snapshot)
        memory.no_progress_assessments.append(assessment)
        loop_state.no_progress_count = (
            0 if assessment.material_progress else loop_state.no_progress_count + 1
        )
        loop_state.completed_iterations = next_iteration
        final_gate = gate

        if gate.status in {GateStatus.PASS, GateStatus.CONDITIONAL_PASS}:
            latest_gap = resolve_gap(latest_gap, next_iteration)
            memory.research_gaps.append(latest_gap)
        else:
            latest_gap = diagnose_gate_a_gap(
                gate,
                claim,
                gap_type=GapType.EVIDENCE_MISSING,
                previous_gap=latest_gap,
            )
            memory.research_gaps.append(latest_gap)

        decision = post_iteration_controller_decision(
            gate_result=gate,
            gap=latest_gap,
            loop_state=loop_state,
            assessment=assessment,
        )
        memory.controller_decisions.append(decision)
        memory.iteration_records.append(
            IterationRecord(
                iteration=next_iteration,
                research_question_ids=[question.question_id],
                modules_executed=[question.owner_module],
                source_ids=[item.source_id for item in memory.sources],
                evidence_ids=[item.evidence_id for item in memory.evidence],
                claim_evidence_ids=list(claim.evidence_ids),
                pce_status=claim.pce_status,
                gate_status=gate.status,
                gap_ids=[latest_gap.gap_id],
                change_summary=(
                    f"Research action {attempt.attempt_id} completed with "
                    f"{attempt.status.value}; material progress was "
                    f"{assessment.material_progress}."
                ),
                research_attempt_id=attempt.attempt_id,
                evidence_snapshot_id=current_snapshot.snapshot_id,
                no_progress_assessment_id=assessment.assessment_id,
                controller_decision=decision.decision,
            )
        )

        if decision.decision == ControllerDecision.ADVANCE:
            status = (
                TerminalStatus.COMPLETED_STRATEGIC_THESIS
                if gate.status == GateStatus.PASS
                else TerminalStatus.COMPLETED_CONDITIONAL_STRATEGIC_THESIS
            )
            terminal = _create_terminal_state(
                status=status,
                mandate=mandate,
                memory=memory,
                loop_state=loop_state,
                final_gate=gate,
                stopping_reason=(
                    "Strategic Thesis Gate passed within the configured control limits."
                    if gate.status == GateStatus.PASS
                    else "Strategic Thesis Gate conditionally passed with explicit caveats."
                ),
            )
            break
        if decision.decision == ControllerDecision.STOP_NO_PROGRESS:
            terminal = _create_terminal_state(
                status=TerminalStatus.STOPPED_NO_PROGRESS,
                mandate=mandate,
                memory=memory,
                loop_state=loop_state,
                final_gate=gate,
                stopping_reason=(
                    "Gate A remained failed and the maximum consecutive no-progress "
                    "iterations was reached."
                ),
            )
            break
        if decision.decision == ControllerDecision.STOP_ITERATION_BUDGET:
            terminal = _create_terminal_state(
                status=TerminalStatus.STOPPED_ITERATION_BUDGET,
                mandate=mandate,
                memory=memory,
                loop_state=loop_state,
                final_gate=gate,
                stopping_reason=(
                    "Gate A remained failed at the maximum iteration; no further "
                    "research iteration was started."
                ),
            )
            break

    if terminal is None:
        terminal = _create_terminal_state(
            status=TerminalStatus.FAILED_TECHNICAL,
            mandate=mandate,
            memory=memory,
            loop_state=loop_state,
            final_gate=final_gate,
            stopping_reason="The loop exited without a valid controller terminal decision.",
        )

    run_summary = _write_artifacts(
        output_dir=output_path,
        scenario_name=scenario_name,
        mandate=mandate,
        contract=contract,
        memory=memory,
        loop_state=loop_state,
        terminal=terminal,
    )
    if terminal.status == TerminalStatus.AWAITING_HUMAN_REVIEW:
        from .review_runtime import initialize_human_review_workspace

        initialize_human_review_workspace(
            output_dir=output_path,
            case_data=case_data,
            terminal=terminal,
            human_review_items=memory.human_review_items,
        )
    return _result(
        output_path=output_path,
        run_summary=run_summary,
        mandate=mandate,
        contract=contract,
        memory=memory,
        loop_state=loop_state,
        terminal=terminal,
    )
