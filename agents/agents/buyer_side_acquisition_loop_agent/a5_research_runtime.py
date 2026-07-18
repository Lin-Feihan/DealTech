from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .attachment_ingestion import (
    attachment_manifest_artifact,
    output_directory_is_writable,
    prepare_attachments,
    validate_no_plaintext_credentials,
)
from .business_certification import run_business_certification
from .business_contracts import load_module_contracts, load_prompt_registry
from .business_models import BusinessBlock, ResearchRequest
from .live_research_models import (
    A5Outcome,
    A5RunResult,
    AttachmentValidationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderMode,
    ProviderOutputValidationError,
)
from .live_research_provider import (
    OpenAIResearchProvider,
    RecordedResearchProvider,
    _source_model,
    check_openai_live_configuration,
)
from .models import Claim, Evidence, EvidenceStatus, PCEStatus
from .provider_validation import OBJECT_COLLECTIONS
from .storage import load_case, to_primitive, write_json


REQUIRED_RESEARCH_FIELDS = {
    "buyer",
    "target",
    "transaction_context",
    "buyer_strategic_need",
    "strategic_rationale",
    "research_question",
    "decision_relevance",
    "required_claim_types",
    "preferred_source_types",
    "excluded_source_types",
    "evidence_threshold",
    "counterevidence_requirement",
    "material_unknowns",
    "confidentiality_constraints",
    "as_of_date",
    "jurisdictions",
    "search_budget",
    "attachments",
}


def _provider_mode(case_data: dict[str, Any], override: str | ProviderMode | None) -> ProviderMode:
    raw = override.value if isinstance(override, ProviderMode) else override
    if raw is None:
        raw = case_data.get("provider", {}).get("mode")
    if not raw:
        raise ProviderConfigurationError("Provider mode must be explicit in case configuration or CLI input.")
    try:
        return ProviderMode(str(raw))
    except ValueError as exc:
        raise ProviderConfigurationError(f"Unsupported provider mode: {raw}") from exc


def _validate_case(case_data: dict[str, Any], module: str | None) -> None:
    validate_no_plaintext_credentials(case_data)
    if case_data.get("schema_version") != "milestone-5-a5":
        raise ProviderConfigurationError("A5 provider runtime requires schema_version milestone-5-a5.")
    for field in ("case_id", "mandate_id", "research_contract_id"):
        if not str(case_data.get(field, "")).strip():
            raise ProviderConfigurationError(f"{field} is required.")
    if (module or case_data.get("module_id")) != "A5":
        raise ProviderConfigurationError("Milestone 5 live research is restricted to module A5.")
    research = case_data.get("research")
    if not isinstance(research, dict):
        raise ProviderConfigurationError("research must be a mapping.")
    missing = sorted(REQUIRED_RESEARCH_FIELDS - set(research))
    if missing:
        raise ProviderConfigurationError(f"A5 research case misses fields: {missing}")
    for party in ("buyer", "target"):
        value = research.get(party)
        if not isinstance(value, dict) or not str(value.get("identity", "")).strip() or not str(value.get("description", "")).strip():
            raise ProviderConfigurationError(f"research.{party} requires identity and description.")
    for field in (
        "transaction_context", "buyer_strategic_need", "strategic_rationale",
        "research_question", "decision_relevance", "counterevidence_requirement", "as_of_date",
    ):
        if not str(research.get(field, "")).strip():
            raise ProviderConfigurationError(f"research.{field} is required.")
    budget = research["search_budget"]
    maximum_iterations = int(budget.get("maximum_loop_iterations", 2))
    if maximum_iterations < 1 or maximum_iterations > 2:
        raise ProviderConfigurationError("A5 pilot maximum_loop_iterations must be 1 or 2.")


def _recording_path(case_path: Path, case_data: dict[str, Any]) -> Path:
    relative = str(case_data.get("provider", {}).get("recording_path", ""))
    if not relative or Path(relative).is_absolute():
        raise ProviderConfigurationError("Recorded mode requires a relative recording_path.")
    root = case_path.parent.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ProviderConfigurationError("recording_path escapes the case directory.") from exc
    if not path.is_file():
        raise ProviderConfigurationError(f"Recorded provider fixture does not exist: {relative}")
    return path


def _empty_memory() -> dict[str, list[dict[str, Any]]]:
    return {name: [] for name in OBJECT_COLLECTIONS}


def _build_request(
    *,
    case_data: dict[str, Any],
    contract: Any,
    question: str,
    iteration: int,
    prior_attempts: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    memory: dict[str, list[dict[str, Any]]],
    attachments: list[Any],
) -> ResearchRequest:
    research = case_data["research"]
    return ResearchRequest(
        request_id=f"REQ-{case_data['case_id']}-A5-{iteration:02d}",
        case_id=case_data["case_id"],
        module_id="A5",
        module_name="Target Capability & Business Quality",
        owning_block=BusinessBlock.BLOCK_A,
        prompt_reference=contract.prompt_reference,
        research_questions=[question],
        mandate_id=str(case_data.get("mandate_id", f"MANDATE-{case_data['case_id']}")),
        contract_id=str(case_data.get("research_contract_id", f"RC-{case_data['case_id']}")),
        provenance_boundary=(
            "A5 research only; provider output is untrusted until Source-Evidence-Claim validation, "
            "PCE and ER/BRB complete. No Gate A, Block B, Block C, valuation or recommendation authority."
        ),
        buyer_identity=research["buyer"]["identity"],
        buyer_description=research["buyer"]["description"],
        target_identity=research["target"]["identity"],
        target_description=research["target"]["description"],
        transaction_context=research["transaction_context"],
        buyer_strategic_need=research["buyer_strategic_need"],
        strategic_rationale=research["strategic_rationale"],
        research_question=question,
        decision_relevance=research["decision_relevance"],
        required_claim_types=list(research["required_claim_types"]),
        preferred_source_types=list(research["preferred_source_types"]),
        excluded_source_types=list(research["excluded_source_types"]),
        evidence_threshold=dict(research["evidence_threshold"]),
        counterevidence_requirement=research["counterevidence_requirement"],
        material_unknowns=list(research["material_unknowns"]),
        supplied_attachments=attachment_manifest_artifact(attachments),
        confidentiality_constraints=list(research["confidentiality_constraints"]),
        as_of_date=research["as_of_date"],
        jurisdiction=list(research["jurisdictions"]),
        prior_attempts=list(prior_attempts),
        open_gaps=[row for row in gaps if row["status"] == "OPEN"],
        previous_evidence=list(memory["evidence"]),
        search_budget=dict(research["search_budget"]),
    )


def check_a5_configuration(
    case_path: str | Path,
    *,
    provider: str | ProviderMode | None = None,
    module: str | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(case_path).resolve()
    issues: list[str] = []
    mode: ProviderMode | None = None
    attachments: list[Any] = []
    blocked: list[dict[str, Any]] = []
    try:
        case_data = load_case(path)
        _validate_case(case_data, module)
        mode = _provider_mode(case_data, provider)
        if mode == ProviderMode.DETERMINISTIC:
            raise ProviderConfigurationError(
                "milestone-5-a5 cases require recorded or openai_live; deterministic mode remains on the existing runtime."
            )
        attachments, blocked = prepare_attachments(
            case_dir=path.parent,
            manifest=case_data["research"]["attachments"],
            provider_mode=mode,
        )
        if blocked:
            issues.extend(item["reason"] for item in blocked)
        contracts = {item.module_id: item for item in load_module_contracts()}
        prompts = load_prompt_registry()
        prompt_id = contracts["A5"].prompt_reference.rsplit("#", 1)[-1]
        if prompt_id not in prompts:
            issues.append("Approved A5 prompt is unavailable.")
        if mode == ProviderMode.RECORDED:
            _recording_path(path, case_data)
        elif mode == ProviderMode.OPENAI_LIVE:
            live = check_openai_live_configuration()
            issues.extend(live["issues"])
        output = Path(output_dir).resolve() if output_dir else path.parent / "run_output"
        if not output_directory_is_writable(output):
            issues.append("Output directory is not writable.")
    except (AttachmentValidationError, ProviderConfigurationError, KeyError, TypeError, ValueError) as exc:
        issues.append(str(exc))
    return {
        "ready": not issues,
        "provider_mode": mode.value if mode else "INVALID",
        "module_id": module or "A5",
        "case_valid": not any("research." in item or "schema_version" in item for item in issues),
        "attachment_count": len(attachments),
        "blocked_attachments": blocked,
        "issues": issues,
        "paid_request_made": False,
        "api_key_value_serialized": False,
    }


def _merge_memory(memory: dict[str, list[dict[str, Any]]], admitted: dict[str, list[dict[str, Any]]]) -> None:
    for name in OBJECT_COLLECTIONS:
        memory[name].extend(admitted[name])


def _latest_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in claims:
        family = str(row.get("claim_family_id") or row["claim_id"])
        if family not in latest or int(row.get("claim_version", 1)) > int(latest[family].get("claim_version", 1)):
            latest[family] = row
    return list(latest.values())


def _evaluate_a5_dependency(
    *,
    memory: dict[str, list[dict[str, Any]]],
    bundle: Any,
    certification: dict[str, Any],
    threshold: dict[str, Any],
) -> dict[str, Any]:
    evidence_by_id = {row["evidence_id"]: row for row in memory["evidence"]}
    pce_by_claim = {
        row["claim_id"]: row.get("PCE_status", "Not Certified")
        for row in certification["pce_result"].get("claim_results", [])
    }
    minimum_sources = int(threshold.get("minimum_independent_sources_per_material_claim", 1))
    latest_claims = _latest_claims(memory["claims"])
    failures: list[dict[str, Any]] = []
    caveats: list[str] = []
    for claim in latest_claims:
        support = [
            evidence_by_id[item]
            for item in claim["supporting_evidence_ids"]
            if item in evidence_by_id and evidence_by_id[item]["direction"] == "support"
        ]
        source_count = len({row["source_id"] for row in support})
        if claim["materiality"].lower() == "material" and source_count < minimum_sources:
            failures.append(
                {
                    "claim_id": claim["claim_id"],
                    "type": "SOURCE_DIVERSITY_GAP",
                    "reason": f"Material Claim has {source_count} supporting Sources; {minimum_sources} required.",
                }
            )
        if pce_by_claim.get(claim["claim_id"], "Not Certified") == "Not Certified":
            failures.append(
                {"claim_id": claim["claim_id"], "type": "PCE_LINEAGE_GAP", "reason": "Claim is Not Certified after PCE."}
            )
        if claim["human_review_required"]:
            caveats.append(f"Claim {claim['claim_id']} requires Human Review.")
    human_unknowns = [
        row for row in memory["unknowns"]
        if row["human_review_required"] and row["materiality"].lower() == "material"
    ]
    management_sources = [
        row for row in memory["sources"] if "management" in row["source_type"].lower()
    ]
    if management_sources:
        caveats.append("Management-only information remains management representation, not independent public evidence.")
    assessment = bundle.provider_artifacts["provider_response_structured"]["module_assessment"]
    if assessment["criterion_outcome"] == "FAIL":
        failures.append(
            {"claim_id": "A5", "type": "A5_CONTRACT_INSUFFICIENT", "reason": assessment["business_conclusion"]}
        )
    conditions = list(assessment["conditions"])
    caveats.extend(assessment["limitations"])
    if human_unknowns:
        status = A5Outcome.AWAITING_HUMAN_REVIEW
        reason = "Material private information cannot be established through public research."
    elif failures:
        status = A5Outcome.FAIL_RESEARCH_GAP
        reason = "A5 remains insufficient after PCE, evidence-threshold and module-contract checks."
    elif assessment["criterion_outcome"] == "CONDITION" or conditions or caveats or memory["counterevidence"]:
        status = A5Outcome.CONDITIONAL_PASS
        reason = "A5 is sufficient to inform Gate A dependencies with explicit conditions and counterevidence."
    else:
        status = A5Outcome.PASS
        reason = "A5 is sufficient to inform Gate A dependencies."
    return {
        "result_id": f"A5-DEPENDENCY-{len(memory['claims']):03d}",
        "module_id": "A5",
        "module_name": "Target Capability & Business Quality",
        "status": status.value,
        "a5_contract_sufficient": status in {A5Outcome.PASS, A5Outcome.CONDITIONAL_PASS},
        "gate_a_evaluated": False,
        "gate_a_dependency_ready": status in {A5Outcome.PASS, A5Outcome.CONDITIONAL_PASS},
        "authority_boundary": (
            "This is an A5 dependency result only. A5 cannot decide Strategic Thesis Gate, "
            "perform Block B or Block C analysis, value the target, or make a Go / No-Go recommendation."
        ),
        "failures": failures,
        "conditions": conditions,
        "caveats": sorted(set(caveats)),
        "pce_statuses": pce_by_claim,
        "counterevidence_ids": [row["counterevidence_id"] for row in memory["counterevidence"]],
        "unknown_ids": [row["unknown_id"] for row in memory["unknowns"]],
        "reason": reason,
    }


def _gap_from_dependency(result: dict[str, Any], iteration: int) -> dict[str, Any]:
    failure = (result.get("failures") or [{"type": "EVIDENCE_MISSING", "reason": result["reason"], "claim_id": "A5"}])[0]
    return {
        "gap_id": f"GAP-A5-{iteration:02d}",
        "gap_type": failure["type"],
        "originating_module": "A5",
        "originating_gate": "Strategic Thesis Gate dependency check",
        "affected_claim_id": failure.get("claim_id", "A5"),
        "description": failure["reason"],
        "required_action": "Run one narrower A5 follow-up focused on the failed evidence or source requirement.",
        "status": "OPEN",
        "created_iteration": iteration,
        "technical_failure": False,
    }


def _terminal(
    *, case_id: str, sequence: int, outcome: A5Outcome, dependency: dict[str, Any],
    gaps: list[dict[str, Any]], attempts: int, reason: str,
) -> dict[str, Any]:
    return {
        "terminal_state_id": f"TS-{case_id}-A5-{sequence:03d}",
        "case_id": case_id,
        "sequence_number": sequence,
        "status": outcome.value,
        "module_id": "A5",
        "module_result": dependency.get("status", "NOT_RUN"),
        "gate_a_result": "NOT_EVALUATED_A5_HAS_NO_GATE_AUTHORITY",
        "gate_b_result": "NOT_RUN",
        "gate_c_result": "NOT_RUN",
        "open_gaps": [row["gap_id"] for row in gaps if row["status"] == "OPEN"],
        "iterations_used": attempts,
        "stopping_reason": reason,
        "authority_boundary": "No valuation, Block B, Block C, Decision State or final recommendation was generated.",
    }


def _write_attempt_artifacts(output: Path, index: int, request: ResearchRequest, artifacts: dict[str, Any]) -> None:
    directory = output / "provider" / f"attempt_{index:02d}"
    write_json(directory / "provider_request.json", request)
    mapping = {
        "provider_response_raw.json": artifacts.get("provider_response_raw", {}),
        "provider_trace.json": artifacts.get("provider_trace", {}),
        "tool_calls.json": artifacts.get("tool_calls", []),
        "search_queries.json": artifacts.get("search_queries", []),
        "returned_citations.json": artifacts.get("returned_citations", []),
        "validation_result.json": artifacts.get("validation_result", {}),
        "admitted_objects.json": artifacts.get("admitted_objects", {}),
        "rejected_objects.json": artifacts.get("rejected_objects", []),
    }
    for name, value in mapping.items():
        write_json(directory / name, value)


def _write_outputs(
    *,
    output: Path,
    requests: list[ResearchRequest],
    artifact_history: list[dict[str, Any]],
    memory: dict[str, list[dict[str, Any]]],
    module_history: list[Any],
    certification: dict[str, Any] | None,
    dependency: dict[str, Any],
    attempts: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    replans: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    iterations: list[dict[str, Any]],
    terminal_history: list[dict[str, Any]],
    attachments: list[Any],
) -> None:
    provider_files = {
        "provider_request.json": requests,
        "provider_response_raw.json": [row.get("provider_response_raw", {}) for row in artifact_history],
        "provider_trace.json": [row.get("provider_trace", {}) for row in artifact_history],
        "tool_calls.json": [row.get("tool_calls", []) for row in artifact_history],
        "search_queries.json": [row.get("search_queries", []) for row in artifact_history],
        "returned_citations.json": [row.get("returned_citations", []) for row in artifact_history],
        "validation_result.json": [row.get("validation_result", {}) for row in artifact_history],
        "admitted_objects.json": [row.get("admitted_objects", {}) for row in artifact_history],
        "rejected_objects.json": [row.get("rejected_objects", []) for row in artifact_history],
        "attachment_manifest.json": attachment_manifest_artifact(attachments),
    }
    for name, value in provider_files.items():
        write_json(output / "provider" / name, value)
    research_names = {
        "sources.json": "sources",
        "evidence.json": "evidence",
        "claims.json": "claims",
        "assumptions.json": "assumptions",
        "unknowns.json": "unknowns",
        "counterevidence.json": "counterevidence",
    }
    for filename, key in research_names.items():
        write_json(output / "research" / filename, memory[key])
    write_json(
        output / "research" / "follow_up_questions.json",
        [row.get("follow_up_questions", []) for row in artifact_history],
    )
    write_json(
        output / "module" / "target_capability_business_quality_result.json",
        {"history": module_history, "final_result": module_history[-1] if module_history else None},
    )
    write_json(output / "module" / "pce_results.json", certification["pce_result"] if certification else {})
    write_json(output / "module" / "er_brb_results.json", certification["er_brb_results"] if certification else [])
    write_json(output / "module" / "gate_dependency_result.json", dependency)
    write_json(output / "loop" / "research_attempts.json", attempts)
    write_json(output / "loop" / "gaps.json", gaps)
    write_json(output / "loop" / "replan.json", replans)
    write_json(output / "loop" / "controller_decisions.json", decisions)
    write_json(output / "loop" / "iteration_records.json", iterations)
    write_json(
        output / "loop" / "loop_state.json",
        {
            "status": terminal_history[-1]["status"],
            "completed_iterations": len(attempts),
            "maximum_iterations": 2,
            "open_gap_ids": terminal_history[-1]["open_gaps"],
            "provider_attempts_are_append_only": True,
        },
    )
    write_json(output / "state" / "terminal_state_history.json", terminal_history)
    write_json(output / "state" / "final_terminal_state.json", terminal_history[-1])


def run_a5_research_case(
    case_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    provider: str | ProviderMode | None = None,
    module: str | None = None,
) -> A5RunResult:
    path = Path(case_path).resolve()
    case_data = load_case(path)
    _validate_case(case_data, module)
    mode = _provider_mode(case_data, provider)
    if mode == ProviderMode.DETERMINISTIC:
        raise ProviderConfigurationError(
            "A milestone-5-a5 case cannot silently fall back to deterministic mode."
        )
    output = Path(output_dir).resolve() if output_dir else path.parent / "run_output"
    output.mkdir(parents=True, exist_ok=True)
    contracts = {item.module_id: item for item in load_module_contracts()}
    contract = contracts["A5"]
    prompt_id = contract.prompt_reference.rsplit("#", 1)[-1]
    if prompt_id not in load_prompt_registry():
        raise ProviderConfigurationError("Approved A5 prompt is missing from the prompt registry.")
    attachments, blocked = prepare_attachments(
        case_dir=path.parent,
        manifest=case_data["research"]["attachments"],
        provider_mode=mode,
    )
    memory = _empty_memory()
    requests: list[ResearchRequest] = []
    artifact_history: list[dict[str, Any]] = []
    module_history: list[Any] = []
    attempts: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    replans: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    iterations: list[dict[str, Any]] = []
    terminal_history: list[dict[str, Any]] = []
    certification: dict[str, Any] | None = None
    dependency: dict[str, Any] = {
        "module_id": "A5", "status": "NOT_RUN", "gate_a_evaluated": False,
        "authority_boundary": "A5 has no Gate A authority.",
    }
    if blocked:
        gap = {
            "gap_id": "GAP-A5-CONFIDENTIAL-UPLOAD",
            "gap_type": "HUMAN_ONLY_INFORMATION",
            "originating_module": "A5",
            "description": blocked[0]["reason"],
            "required_action": "Obtain explicit provider-upload permission or route the document to an authorized human reviewer.",
            "status": "OPEN",
            "created_iteration": 0,
            "technical_failure": False,
        }
        gaps.append(gap)
        dependency = {
            **dependency,
            "status": A5Outcome.AWAITING_HUMAN_REVIEW.value,
            "a5_contract_sufficient": False,
            "gate_a_dependency_ready": False,
            "reason": blocked[0]["reason"],
        }
        artifact_history.append(
            {
                "provider_response_raw": {},
                "provider_trace": {
                    "provider_type": mode.value,
                    "validation_outcome": "NOT_SENT",
                    "error_class": "PROHIBITED_CONFIDENTIAL_UPLOAD",
                },
                "tool_calls": [],
                "search_queries": [],
                "returned_citations": [],
                "validation_result": {"status": "NOT_SENT", "blocked_attachments": blocked},
                "admitted_objects": _empty_memory(),
                "rejected_objects": blocked,
                "follow_up_questions": [],
            }
        )
        terminal_history.append(
            _terminal(
                case_id=case_data["case_id"], sequence=1,
                outcome=A5Outcome.AWAITING_HUMAN_REVIEW, dependency=dependency,
                gaps=gaps, attempts=0, reason=blocked[0]["reason"],
            )
        )
        _write_outputs(
            output=output, requests=requests, artifact_history=artifact_history, memory=memory,
            module_history=module_history, certification=certification, dependency=dependency,
            attempts=attempts, gaps=gaps, replans=replans, decisions=decisions,
            iterations=iterations, terminal_history=terminal_history, attachments=attachments,
        )
        write_json(
            output / "run_summary.json",
            {
                "schema_version": "milestone-5-a5",
                "case_id": case_data["case_id"],
                "provider_mode": mode.value,
                "module_id": "A5",
                "outcome": A5Outcome.AWAITING_HUMAN_REVIEW.value,
                "attempts": 0,
                "provider_request_made": False,
                "gate_a_evaluated": False,
                "block_b_or_c_executed": False,
                "final_recommendation_generated": False,
                "output_directory": str(output),
            },
        )
        return A5RunResult(
            case_id=case_data["case_id"], provider_mode=mode,
            outcome=A5Outcome.AWAITING_HUMAN_REVIEW, output_dir=str(output), attempts=0,
            gate_dependency_result=dependency, terminal_state=terminal_history[-1],
            admitted_objects=memory,
        )

    maximum_iterations = int(case_data["research"]["search_budget"].get("maximum_loop_iterations", 2))
    question = case_data["research"]["research_question"]
    prior_questions: list[str] = []
    prior_queries: set[str] = set()
    final_outcome = A5Outcome.FAILED_TECHNICAL

    for iteration in range(1, maximum_iterations + 1):
        if question.strip().lower() in {item.strip().lower() for item in prior_questions}:
            final_outcome = A5Outcome.STOPPED_NO_PROGRESS
            decisions.append(
                {"iteration": iteration, "decision": "STOP_NO_PROGRESS", "reason": "Identical research question repetition was prevented."}
            )
            break
        prior_questions.append(question)
        request = _build_request(
            case_data=case_data, contract=contract, question=question, iteration=iteration,
            prior_attempts=attempts, gaps=gaps, memory=memory, attachments=attachments,
        )
        requests.append(request)
        before_sources = {row["source_id"] for row in memory["sources"]}
        before_evidence = {row["evidence_id"] for row in memory["evidence"]}
        try:
            if mode == ProviderMode.RECORDED:
                selected = RecordedResearchProvider(
                    _recording_path(path, case_data), attempt_index=iteration - 1,
                    attachments=attachments,
                    prior_objects=memory,
                )
            else:
                selected = OpenAIResearchProvider(attachments=attachments, prior_objects=memory)
            bundle = selected.research(request, contract)
            artifacts = bundle.provider_artifacts
            _write_attempt_artifacts(output, iteration, request, artifacts)
            artifact_history.append(artifacts)
            admitted = artifacts["admitted_objects"]
            _merge_memory(memory, admitted)
            module_history.append(bundle.module_result)
            certification = run_business_certification(
                case_id=case_data["case_id"],
                sources=[_source_model(row) for row in memory["sources"]],
                evidence=[
                    Evidence(
                        evidence_id=row["evidence_id"], claim_id=row["claim_id"],
                        source_id=row["source_id"], extracted_fact=row["extracted_fact"],
                        evidence_type=row["evidence_type"], confidence=row["strength"],
                        status=EvidenceStatus.AVAILABLE,
                        supports_claim=row["direction"] == "support",
                        human_review_required="management" in row["evidence_type"].lower(),
                        limitations=row["limitations"],
                    ) for row in memory["evidence"]
                ],
                claims=[
                    Claim(
                        claim_id=row["claim_id"], claim_text=row["claim_text"],
                        business_module="Target Capability & Business Quality",
                        evidence_ids=list(row["supporting_evidence_ids"]),
                        source_ids=list({
                            evidence["source_id"] for evidence in memory["evidence"]
                            if evidence["evidence_id"] in row["supporting_evidence_ids"]
                        }),
                        human_review_required=bool(row["human_review_required"]),
                        claim_class=row["claim_class"], materiality=row["materiality"],
                        counterevidence_ids=list(row["counterevidence_ids"]),
                    ) for row in memory["claims"]
                ],
            )
            pce_by_claim = {
                row["claim_id"]: PCEStatus(row.get("PCE_status", "Not Certified"))
                for row in certification["pce_result"].get("claim_results", [])
            }
            bundle_statuses = [pce_by_claim.get(claim.claim_id, PCEStatus.NOT_CERTIFIED) for claim in bundle.claims]
            if PCEStatus.NOT_CERTIFIED in bundle_statuses:
                bundle.module_result.pce_status = PCEStatus.NOT_CERTIFIED
            elif PCEStatus.NEEDS_HUMAN_REVIEW in bundle_statuses:
                bundle.module_result.pce_status = PCEStatus.NEEDS_HUMAN_REVIEW
            elif PCEStatus.CERTIFIED_WITH_CAVEAT in bundle_statuses:
                bundle.module_result.pce_status = PCEStatus.CERTIFIED_WITH_CAVEAT
            else:
                bundle.module_result.pce_status = PCEStatus.CERTIFIED
            er_by_claim: dict[str, list[dict[str, Any]]] = {}
            for row in certification["er_brb_results"]:
                er_by_claim.setdefault(row["claim_id"], []).append(row)
            bundle.module_result.er_brb_result = {
                claim.claim_id: er_by_claim.get(claim.claim_id, []) for claim in bundle.claims
            }
            dependency = _evaluate_a5_dependency(
                memory=memory, bundle=bundle, certification=certification,
                threshold=request.evidence_threshold,
            )
            new_sources = sorted({row["source_id"] for row in memory["sources"]} - before_sources)
            new_evidence = sorted({row["evidence_id"] for row in memory["evidence"]} - before_evidence)
            current_queries = {item.strip().lower() for item in artifacts["search_queries"] if item.strip()}
            identical_queries = bool(current_queries) and current_queries.issubset(prior_queries)
            material_progress = bool(new_sources or new_evidence) and not identical_queries
            prior_queries.update(current_queries)
            attempt = {
                "attempt_id": f"A5-ATTEMPT-{iteration:02d}",
                "iteration": iteration,
                "provider_mode": mode.value,
                "request_id": request.request_id,
                "question": question,
                "response_id": bundle.response.response_id,
                "new_source_ids": new_sources,
                "new_evidence_ids": new_evidence,
                "searched_queries": artifacts["search_queries"],
                "identical_query_repetition": identical_queries,
                "material_progress": material_progress,
                "validation_status": artifacts["validation_result"]["status"],
            }
            attempts.append(attempt)
            iterations.append(
                {
                    "iteration": iteration,
                    "module": "A5",
                    "provider_attempt_id": attempt["attempt_id"],
                    "dependency_status": dependency["status"],
                    "new_source_ids": new_sources,
                    "new_evidence_ids": new_evidence,
                    "pce_statuses": dependency.get("pce_statuses", {}),
                    "gap_ids": [row["gap_id"] for row in gaps if row["status"] == "OPEN"],
                }
            )
        except ProviderOutputValidationError as exc:
            artifacts = exc.artifacts or {
                "provider_response_raw": {}, "provider_trace": {"provider_type": mode.value},
                "tool_calls": [], "search_queries": [], "returned_citations": [],
                "validation_result": exc.validation, "admitted_objects": _empty_memory(),
                "rejected_objects": exc.validation.get("rejected_objects", []), "follow_up_questions": [],
            }
            artifact_history.append(artifacts)
            _write_attempt_artifacts(output, iteration, request, artifacts)
            attempts.append(
                {
                    "attempt_id": f"A5-ATTEMPT-{iteration:02d}", "iteration": iteration,
                    "provider_mode": mode.value, "request_id": request.request_id,
                    "question": question, "status": "FAILED_TECHNICAL",
                    "error_class": "ProviderOutputValidationError",
                    "business_gap_created": False,
                }
            )
            dependency = {**dependency, "status": A5Outcome.FAILED_TECHNICAL.value, "reason": str(exc)}
            final_outcome = A5Outcome.FAILED_TECHNICAL
            decisions.append(
                {"iteration": iteration, "decision": "FAIL_TECHNICAL", "reason": str(exc), "business_gap_created": False}
            )
            break
        except ProviderError as exc:
            artifacts = {
                "provider_response_raw": {},
                "provider_trace": {"provider_type": mode.value, "validation_outcome": "NOT_ADMITTED", "error_class": exc.__class__.__name__},
                "tool_calls": [], "search_queries": [], "returned_citations": [],
                "validation_result": {"status": "TECHNICAL_FAILURE", "errors": [str(exc)]},
                "admitted_objects": _empty_memory(),
                "rejected_objects": [{"object_type": "technical_failure", "reason": str(exc)}],
                "follow_up_questions": [],
            }
            artifact_history.append(artifacts)
            _write_attempt_artifacts(output, iteration, request, artifacts)
            attempts.append(
                {"attempt_id": f"A5-ATTEMPT-{iteration:02d}", "iteration": iteration, "status": "FAILED_TECHNICAL", "error_class": exc.__class__.__name__, "business_gap_created": False}
            )
            dependency = {**dependency, "status": A5Outcome.FAILED_TECHNICAL.value, "reason": str(exc)}
            final_outcome = A5Outcome.FAILED_TECHNICAL
            decisions.append(
                {"iteration": iteration, "decision": "FAIL_TECHNICAL", "reason": str(exc), "business_gap_created": False}
            )
            break

        status = A5Outcome(dependency["status"])
        if status in {A5Outcome.PASS, A5Outcome.CONDITIONAL_PASS, A5Outcome.AWAITING_HUMAN_REVIEW}:
            for gap in gaps:
                if gap["status"] == "OPEN" and status in {A5Outcome.PASS, A5Outcome.CONDITIONAL_PASS}:
                    gap["status"] = "RESOLVED" if status == A5Outcome.PASS else "CONDITIONALLY_RESOLVED"
                    gap["resolved_iteration"] = iteration
            final_outcome = status
            decisions.append(
                {"iteration": iteration, "decision": "ADVANCE_A5_DEPENDENCY" if status != A5Outcome.AWAITING_HUMAN_REVIEW else "ESCALATE_HUMAN_REVIEW", "reason": dependency["reason"]}
            )
            break

        gap = _gap_from_dependency(dependency, iteration)
        gaps.append(gap)
        iterations[-1]["gap_ids"].append(gap["gap_id"])
        if iteration >= maximum_iterations:
            final_outcome = (
                A5Outcome.STOPPED_NO_PROGRESS
                if not attempts[-1].get("material_progress", False)
                else A5Outcome.STOPPED_ITERATION_BUDGET
            )
            decisions.append(
                {"iteration": iteration, "decision": final_outcome.value, "reason": "A5 remained insufficient after the permitted repair iteration."}
            )
            break
        followups = artifact_history[-1].get("follow_up_questions", [])
        if not followups:
            final_outcome = A5Outcome.STOPPED_NO_PROGRESS
            decisions.append(
                {"iteration": iteration, "decision": "STOP_NO_PROGRESS", "reason": "Provider supplied no narrower follow-up question."}
            )
            break
        repair_question = str(followups[0]).strip()
        if not repair_question or repair_question.lower() in {item.lower() for item in prior_questions}:
            final_outcome = A5Outcome.STOPPED_NO_PROGRESS
            decisions.append(
                {"iteration": iteration, "decision": "STOP_NO_PROGRESS", "reason": "Identical follow-up question repetition was prevented."}
            )
            break
        replans.append(
            {
                "replan_id": f"REPLAN-A5-{iteration + 1:02d}",
                "originating_gap_id": gap["gap_id"],
                "prior_question": question,
                "narrower_follow_up_question": repair_question,
                "target_module": "A5",
                "prohibited_scope": ["Gate A decision", "Block B", "Block C", "valuation", "final recommendation"],
            }
        )
        decisions.append(
            {"iteration": iteration, "decision": "TARGETED_REPAIR", "reason": gap["description"], "next_iteration": iteration + 1}
        )
        question = repair_question

    terminal = _terminal(
        case_id=case_data["case_id"], sequence=1, outcome=final_outcome,
        dependency=dependency, gaps=gaps, attempts=len(attempts),
        reason=dependency.get("reason", decisions[-1]["reason"] if decisions else final_outcome.value),
    )
    terminal_history.append(terminal)
    _write_outputs(
        output=output, requests=requests, artifact_history=artifact_history, memory=memory,
        module_history=module_history, certification=certification, dependency=dependency,
        attempts=attempts, gaps=gaps, replans=replans, decisions=decisions,
        iterations=iterations, terminal_history=terminal_history, attachments=attachments,
    )
    summary = {
        "schema_version": "milestone-5-a5",
        "case_id": case_data["case_id"],
        "provider_mode": mode.value,
        "module_id": "A5",
        "module_name": "Target Capability & Business Quality",
        "outcome": final_outcome.value,
        "attempts": len(attempts),
        "admitted_sources": len(memory["sources"]),
        "admitted_evidence": len(memory["evidence"]),
        "admitted_claims": len(memory["claims"]),
        "gate_a_evaluated": False,
        "block_b_or_c_executed": False,
        "final_recommendation_generated": False,
        "output_directory": str(output),
    }
    write_json(output / "run_summary.json", summary)
    return A5RunResult(
        case_id=case_data["case_id"], provider_mode=mode, outcome=final_outcome,
        output_dir=str(output), attempts=len(attempts), gate_dependency_result=dependency,
        terminal_state=terminal, admitted_objects=memory,
    )
