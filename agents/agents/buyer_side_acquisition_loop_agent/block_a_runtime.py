from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .attachment_ingestion import (
    attachment_manifest_artifact,
    output_directory_is_writable,
    prepare_attachments,
    validate_no_plaintext_credentials,
)
from .block_a_evaluation import (
    assess_block_a_module,
    dependent_synthesis_modules,
    evaluate_block_a_gate,
    latest_claims,
    smallest_responsible_gap,
)
from .block_a_models import (
    BLOCK_A_DEPENDENCIES,
    BLOCK_A_MODULE_NAMES,
    BLOCK_A_ORDER,
    BlockAOutcome,
    BlockAResearchPlan,
    BlockARunResult,
)
from .block_a_registry import SharedBlockARegistry, utc_now
from .business_certification import run_business_certification
from .business_contracts import load_module_contracts, load_prompt_registry
from .business_models import BusinessBlock, ResearchRequest
from .live_research_models import (
    AttachmentValidationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderMode,
    ProviderOutputValidationError,
)
from .live_research_provider import (
    DeterministicBlockAResearchProvider,
    OpenAIResearchProvider,
    RecordedResearchProvider,
    _source_model,
    check_openai_live_configuration,
)
from .models import Claim, Evidence, EvidenceStatus
from .storage import load_case, to_primitive, write_json


MODULE_FILENAMES = {
    "A1": "a1_transaction_context.json",
    "A2": "a2_buyer_strategic_need.json",
    "A3": "a3_strategic_rationale.json",
    "A4": "a4_target_attractiveness.json",
    "A5": "a5_target_capability_business_quality.json",
    "A6": "a6_industry_competitive_position.json",
    "A7": "a7_strategic_fit.json",
}

PROHIBITED_CONCLUSIONS = {
    "A1": ["valuation", "purchase price", "strategic fit", "Go / No-Go"],
    "A2": ["target attractiveness", "strategic fit", "valuation", "Go / No-Go"],
    "A3": ["valuation", "pricing", "financing", "returns", "quantified synergy", "Go / No-Go"],
    "A4": ["purchase-price valuation", "complete target universe", "Go / No-Go"],
    "A5": ["Strategic Thesis Gate", "valuation", "Block B", "Block C", "Go / No-Go"],
    "A6": ["definitive antitrust legal conclusion", "valuation", "Go / No-Go"],
    "A7": ["quantified synergy", "synergy valuation", "returns", "Go / No-Go"],
}

REQUIRED_CASE_FIELDS = {
    "schema_version", "case_id", "as_of_date", "mandate_id",
    "research_contract_id", "provider", "mandate", "research",
}
REQUIRED_MANDATE_FIELDS = {
    "buyer_name", "buyer_description", "target_name", "target_description",
    "transaction_type", "transaction_stage", "decision_question",
    "buyer_strategic_need", "initial_strategic_rationale", "jurisdictions",
    "known_terms", "unknown_terms", "confidentiality_permissions",
    "human_review_roles",
}
REQUIRED_RESEARCH_FIELDS = {
    "attachments", "module_budgets", "total_block_a_budget",
    "maximum_repair_iterations", "preferred_source_types",
    "excluded_source_types", "confidentiality_restrictions",
}


def _provider_mode(
    case_data: dict[str, Any], override: str | ProviderMode | None
) -> ProviderMode:
    raw = override.value if isinstance(override, ProviderMode) else override
    raw = raw or case_data.get("provider", {}).get("mode")
    if not raw:
        raise ProviderConfigurationError("Provider mode must be explicit.")
    try:
        return ProviderMode(str(raw))
    except ValueError as exc:
        raise ProviderConfigurationError(f"Unsupported provider mode: {raw}") from exc


def _validate_block_a_case(case_data: dict[str, Any]) -> None:
    validate_no_plaintext_credentials(case_data)
    missing = sorted(REQUIRED_CASE_FIELDS - set(case_data))
    if missing:
        raise ProviderConfigurationError(f"Block A case misses fields: {missing}")
    if case_data.get("schema_version") != "milestone-6-block-a":
        raise ProviderConfigurationError(
            "Complete Block A provider runtime requires schema_version milestone-6-block-a."
        )
    for field in ("case_id", "as_of_date", "mandate_id", "research_contract_id"):
        if not str(case_data.get(field, "")).strip():
            raise ProviderConfigurationError(f"{field} is required.")
    mandate = case_data.get("mandate")
    if not isinstance(mandate, dict):
        raise ProviderConfigurationError("mandate must be a mapping.")
    missing = sorted(REQUIRED_MANDATE_FIELDS - set(mandate))
    if missing:
        raise ProviderConfigurationError(f"Mandate misses fields: {missing}")
    for field in (
        "buyer_name", "buyer_description", "target_name", "transaction_type",
        "transaction_stage", "decision_question", "buyer_strategic_need",
        "initial_strategic_rationale",
    ):
        if not str(mandate.get(field, "")).strip():
            raise ProviderConfigurationError(f"mandate.{field} is required.")
    for field in (
        "jurisdictions", "known_terms", "unknown_terms",
        "confidentiality_permissions", "human_review_roles",
    ):
        if not isinstance(mandate.get(field), list):
            raise ProviderConfigurationError(f"mandate.{field} must be a list.")
    for field in ("jurisdictions", "unknown_terms", "confidentiality_permissions", "human_review_roles"):
        if not mandate[field]:
            raise ProviderConfigurationError(f"mandate.{field} must identify at least one item.")
    research = case_data.get("research")
    if not isinstance(research, dict):
        raise ProviderConfigurationError("research must be a mapping.")
    missing = sorted(REQUIRED_RESEARCH_FIELDS - set(research))
    if missing:
        raise ProviderConfigurationError(f"Block A research configuration misses fields: {missing}")
    budgets = research.get("module_budgets")
    if not isinstance(budgets, dict) or set(BLOCK_A_MODULE_NAMES) - set(budgets):
        raise ProviderConfigurationError("module_budgets must explicitly cover A1 through A7.")
    for module_id, budget in budgets.items():
        if module_id in BLOCK_A_MODULE_NAMES:
            for field in ("maximum_queries", "maximum_tool_calls", "maximum_estimated_tokens"):
                if int(budget.get(field, 0)) < 1:
                    raise ProviderConfigurationError(f"{module_id} budget {field} must be positive.")
    repairs = int(research.get("maximum_repair_iterations", -1))
    if repairs < 0 or repairs > 2:
        raise ProviderConfigurationError("maximum_repair_iterations must be between 0 and 2.")
    total = research.get("total_block_a_budget")
    required_requests = 7 + (3 * repairs)
    if not isinstance(total, dict) or int(total.get("maximum_provider_requests", 0)) < required_requests:
        raise ProviderConfigurationError(
            f"total_block_a_budget must permit at least {required_requests} provider requests "
            "for the selected repair budget."
        )


def _recording_path(path: Path, case_data: dict[str, Any]) -> Path:
    relative = str(case_data.get("provider", {}).get("recording_path", ""))
    if not relative or Path(relative).is_absolute():
        raise ProviderConfigurationError("Recorded or deterministic Block A mode requires a relative recording_path.")
    root = path.parent.resolve()
    recording = (root / relative).resolve()
    try:
        recording.relative_to(root)
    except ValueError as exc:
        raise ProviderConfigurationError("recording_path escapes the case directory.") from exc
    if not recording.is_file():
        raise ProviderConfigurationError(f"Block A recording does not exist: {relative}")
    return recording


def build_block_a_research_plan(case_data: dict[str, Any]) -> BlockAResearchPlan:
    contracts = {
        item.module_id: item for item in load_module_contracts() if item.module_id in BLOCK_A_MODULE_NAMES
    }
    prompts = load_prompt_registry()
    research = case_data["research"]
    attachment_use: dict[str, list[str]] = {module_id: [] for module_id in BLOCK_A_MODULE_NAMES}
    for row in research["attachments"]:
        for module_id in row.get("modules", ["A5"]):
            if module_id in attachment_use:
                attachment_use[module_id].append(row["attachment_id"])
    prompt_manifest: dict[str, str] = {}
    for module_id, contract in contracts.items():
        prompt_id = contract.prompt_reference.rsplit("#", 1)[-1]
        if prompt_id not in prompts:
            raise ProviderConfigurationError(f"Approved prompt is missing for {module_id}.")
        prompt_manifest[module_id] = contract.prompt_reference
    thresholds = {
        module_id: {
            "minimum_independent_sources_per_material_claim": int(
                research.get("evidence_thresholds", {})
                .get(module_id, {})
                .get("minimum_independent_sources_per_material_claim", 1)
            ),
            "exact_locator_required": True,
            "counterevidence_required": True,
        }
        for module_id in BLOCK_A_MODULE_NAMES
    }
    return BlockAResearchPlan(
        plan_id=f"PLAN-BLOCK-A-{case_data['case_id']}",
        case_id=case_data["case_id"],
        as_of_date=case_data["as_of_date"],
        modules_selected=list(BLOCK_A_ORDER),
        module_order=list(BLOCK_A_ORDER),
        dependency_graph={key: list(value) for key, value in BLOCK_A_DEPENDENCIES.items()},
        research_questions={
            module_id: list(contracts[module_id].required_research_questions)
            for module_id in BLOCK_A_ORDER
        },
        preferred_source_types={
            module_id: list(contracts[module_id].preferred_source_types)
            for module_id in BLOCK_A_ORDER
        },
        evidence_thresholds=thresholds,
        counterevidence_requirements={
            module_id: contracts[module_id].counterevidence_requirements[0]
            for module_id in BLOCK_A_ORDER
        },
        attachment_use=attachment_use,
        confidentiality_restrictions=list(research["confidentiality_restrictions"]),
        per_module_search_budget={key: dict(value) for key, value in research["module_budgets"].items()},
        total_block_a_budget=dict(research["total_block_a_budget"]),
        repair_budget={"maximum_repair_iterations": int(research["maximum_repair_iterations"])},
        human_review_boundaries=list(case_data["mandate"]["human_review_roles"]),
        completion_criteria=[
            "Every A1-A7 module has a non-empty validated result.",
            "Every material Claim has admitted Source-Evidence-Claim lineage and PCE status.",
            "Counterevidence, conflicts, assumptions, unknowns and Human Review items remain visible.",
            "Gate A is evaluated independently of the provider.",
        ],
        prompt_manifest=prompt_manifest,
    )


def _live_enabled(explicit: bool) -> bool:
    return explicit or os.environ.get("ENABLE_LIVE_SMOKE_TEST", "").strip() == "1"


def _apply_live_environment_budgets(plan: BlockAResearchPlan) -> None:
    total_limit = os.environ.get("OPENAI_BLOCK_A_REQUEST_BUDGET", "").strip()
    if total_limit:
        plan.total_block_a_budget["maximum_provider_requests"] = min(
            int(plan.total_block_a_budget["maximum_provider_requests"]), int(total_limit)
        )
    per_module_limit = os.environ.get("OPENAI_PER_MODULE_BUDGET", "").strip()
    if per_module_limit:
        for budget in plan.per_module_search_budget.values():
            budget["maximum_tool_calls"] = min(
                int(budget["maximum_tool_calls"]), int(per_module_limit)
            )


def check_block_a_configuration(
    case_path: str | Path,
    *,
    provider: str | ProviderMode | None = None,
    module: str = "BLOCK_A",
    output_dir: str | Path | None = None,
    enable_live: bool = False,
) -> dict[str, Any]:
    path = Path(case_path).resolve()
    issues: list[str] = []
    mode: ProviderMode | None = None
    attachments: list[Any] = []
    blocked: list[dict[str, Any]] = []
    try:
        case_data = load_case(path)
        _validate_block_a_case(case_data)
        if module != "BLOCK_A":
            raise ProviderConfigurationError("Milestone 6 orchestration requires module selection BLOCK_A.")
        mode = _provider_mode(case_data, provider)
        plan = build_block_a_research_plan(case_data)
        if mode == ProviderMode.OPENAI_LIVE:
            _apply_live_environment_budgets(plan)
            minimum_requests = 7 + (3 * plan.repair_budget["maximum_repair_iterations"])
            if int(plan.total_block_a_budget["maximum_provider_requests"]) < minimum_requests:
                issues.append(
                    "OPENAI_BLOCK_A_REQUEST_BUDGET is below the case's complete-run and repair requirement."
                )
        if len(plan.prompt_manifest) != 7:
            issues.append("All seven approved Block A prompts must be available.")
        attachments, blocked = prepare_attachments(
            case_dir=path.parent,
            manifest=case_data["research"]["attachments"],
            provider_mode=mode,
        )
        issues.extend(row["reason"] for row in blocked)
        if mode in {ProviderMode.RECORDED, ProviderMode.DETERMINISTIC}:
            _recording_path(path, case_data)
        else:
            if case_data.get("provider", {}).get("mode") != ProviderMode.OPENAI_LIVE.value:
                issues.append("The case itself must explicitly select openai_live.")
            live = check_openai_live_configuration()
            issues.extend(live["issues"])
            if not _live_enabled(enable_live):
                issues.append("Live execution is not explicitly enabled by --enable-live or ENABLE_LIVE_SMOKE_TEST=1.")
        output = Path(output_dir).resolve() if output_dir else path.parent / "run_output"
        if not output_directory_is_writable(output):
            issues.append("Output directory is not writable.")
    except (AttachmentValidationError, ProviderConfigurationError, KeyError, TypeError, ValueError) as exc:
        issues.append(str(exc))
    return {
        "ready": not issues,
        "provider_mode": mode.value if mode else "INVALID",
        "module_selection": module,
        "case_valid": not any("misses" in row or "schema_version" in row for row in issues),
        "attachment_count": len(attachments),
        "blocked_attachments": blocked,
        "live_execution_enabled": _live_enabled(enable_live),
        "network_available": "NOT_CHECKED_NO_NETWORK_REQUEST_MADE",
        "issues": issues,
        "paid_request_made": False,
        "api_key_value_serialized": False,
    }


def _module_dependencies(registry: SharedBlockARegistry, module_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dependency in BLOCK_A_DEPENDENCIES[module_id]:
        for claim in latest_claims(registry.claims, dependency):
            rows.append(
                {
                    "claim_id": claim["claim_id"],
                    "claim_text": claim["claim_text"],
                    "owning_module": dependency,
                    "pce_status": claim.get("pce_status", "Not Certified"),
                    "limitations": claim.get("limitations", ""),
                }
            )
    return rows


def _build_request(
    *,
    case_data: dict[str, Any],
    plan: BlockAResearchPlan,
    contract: Any,
    registry: SharedBlockARegistry,
    module_version: int,
    iteration: int,
    attempts: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    attachments: list[Any],
    override_question: str | None = None,
) -> ResearchRequest:
    mandate = case_data["mandate"]
    questions = [override_question] if override_question else plan.research_questions[contract.module_id]
    dependencies = _module_dependencies(registry, contract.module_id)
    budget = plan.per_module_search_budget[contract.module_id]
    known_facts = [
        {"fact_type": "user_supplied_mandate", "field": "known_term", "value": value}
        for value in mandate["known_terms"]
    ]
    known_facts.extend(
        {
            "fact_type": "admitted_upstream_claim",
            "field": row["owning_module"],
            "value": row["claim_text"],
            "claim_id": row["claim_id"],
        }
        for row in dependencies
    )
    return ResearchRequest(
        request_id=f"REQ-{case_data['case_id']}-{contract.module_id}-I{iteration:02d}-V{module_version:02d}",
        case_id=case_data["case_id"],
        module_id=contract.module_id,
        module_name=contract.professional_name,
        owning_block=BusinessBlock.BLOCK_A,
        prompt_reference=contract.prompt_reference,
        research_questions=questions,
        mandate_id=case_data["mandate_id"],
        contract_id=case_data["research_contract_id"],
        provenance_boundary=(
            f"{contract.module_id} only. Provider output is untrusted until validation, admission, "
            "PCE and ER/BRB. The provider has no Gate A, Block B, Block C or recommendation authority."
        ),
        buyer_identity=mandate["buyer_name"],
        buyer_description=mandate["buyer_description"],
        target_identity=mandate["target_name"],
        target_description=mandate.get("target_description", ""),
        transaction_context=(
            f"{mandate['transaction_type']} at {mandate['transaction_stage']}; known terms: "
            + "; ".join(mandate["known_terms"])
        ),
        buyer_strategic_need=mandate["buyer_strategic_need"],
        strategic_rationale=mandate["initial_strategic_rationale"],
        research_question=questions[0],
        decision_relevance=contract.decision_relevance,
        required_claim_types=list(contract.required_claims),
        preferred_source_types=list(contract.preferred_source_types),
        excluded_source_types=list(case_data["research"]["excluded_source_types"]),
        evidence_threshold=dict(plan.evidence_thresholds[contract.module_id]),
        counterevidence_requirement=(
            plan.counterevidence_requirements[contract.module_id]
            + " Also state what contradicts the proposed conclusion, what credible alternative explanation exists, "
            "what material information is missing, and what would change the conclusion."
        ),
        material_unknowns=[str(value) for value in mandate["unknown_terms"]],
        supplied_attachments=attachment_manifest_artifact(attachments),
        confidentiality_constraints=list(plan.confidentiality_restrictions),
        as_of_date=case_data["as_of_date"],
        jurisdiction=list(mandate["jurisdictions"]),
        prior_attempts=[row for row in attempts if row.get("module_id") == contract.module_id],
        open_gaps=[row for row in gaps if row.get("status") == "OPEN"],
        previous_evidence=[
            row for row in registry.evidence
            if row.get("owning_module") == contract.module_id
            or row.get("owning_module") in BLOCK_A_DEPENDENCIES[contract.module_id]
        ],
        search_budget={
            **budget,
            "maximum_provider_attempts": int(os.environ.get("OPENAI_MAX_PROVIDER_ATTEMPTS", 2)),
            "timeout_seconds": float(os.environ.get("OPENAI_RESEARCH_TIMEOUT", 180)),
        },
        business_purpose=contract.business_purpose,
        dependency_claims=dependencies,
        known_facts=known_facts,
        known_unknowns=[
            {"unknown": value, "source": "Mandate", "material": True}
            for value in mandate["unknown_terms"]
        ],
        existing_counterevidence=list(registry.counterevidence),
        query_budget=int(budget["maximum_queries"]),
        tool_call_budget=int(budget["maximum_tool_calls"]),
        prohibited_conclusions=list(PROHIBITED_CONCLUSIONS[contract.module_id]),
        attachment_use=list(plan.attachment_use[contract.module_id]),
    )


def _validate_conflicts(
    conflicts: list[dict[str, Any]], registry: SharedBlockARegistry,
    admitted: dict[str, list[dict[str, Any]]], module_id: str,
) -> None:
    required = {
        "conflict_id", "related_claim_ids", "supporting_evidence_ids",
        "contradicting_evidence_ids", "conflict_type", "materiality",
        "possible_explanations", "resolution_status", "human_review_required",
    }
    claim_ids = {row["claim_id"] for row in registry.claims + admitted["claims"]}
    evidence_ids = {row["evidence_id"] for row in registry.evidence + admitted["evidence"]}
    known_conflicts = {row["conflict_id"] for row in registry.conflicts}
    for row in conflicts:
        missing = sorted(required - set(row))
        if missing:
            raise ProviderOutputValidationError(
                f"{module_id} conflict record misses fields: {missing}"
            )
        if row["conflict_id"] in known_conflicts:
            raise ProviderOutputValidationError(f"Conflict ID is not append-only: {row['conflict_id']}")
        if any(item not in claim_ids for item in row["related_claim_ids"]):
            raise ProviderOutputValidationError(f"{module_id} conflict references an unknown Claim.")
        if any(item not in evidence_ids for item in row["supporting_evidence_ids"] + row["contradicting_evidence_ids"]):
            raise ProviderOutputValidationError(f"{module_id} conflict references unknown Evidence.")


def _certify(case_id: str, registry: SharedBlockARegistry) -> dict[str, Any]:
    evidence_by_id = {row["evidence_id"]: row for row in registry.evidence}
    sources = [_source_model(row, "Block A shared Source Registry") for row in registry.sources]
    evidence = [
        Evidence(
            evidence_id=row["evidence_id"], claim_id=row["claim_id"],
            source_id=row["source_id"], extracted_fact=row["extracted_fact"],
            evidence_type=row["evidence_type"], confidence=row["strength"],
            status=EvidenceStatus.AVAILABLE, supports_claim=row["direction"] == "support",
            human_review_required="management" in row["evidence_type"].lower(),
            limitations=row.get("limitations", ""),
        )
        for row in registry.evidence
    ]
    claims = []
    for row in registry.claims:
        source_ids = sorted(
            {
                evidence_by_id[item]["source_id"]
                for item in row.get("supporting_evidence_ids", [])
                if item in evidence_by_id
            }
        )
        claims.append(
            Claim(
                claim_id=row["claim_id"], claim_text=row["claim_text"],
                business_module=row["owning_module"],
                evidence_ids=list(row["supporting_evidence_ids"]), source_ids=source_ids,
                human_review_required=bool(row["human_review_required"]),
                claim_class=row["claim_class"], materiality=row["materiality"],
                counterevidence_ids=list(row["counterevidence_ids"]),
            )
        )
    result = run_business_certification(
        case_id=case_id, sources=sources, evidence=evidence, claims=claims
    )
    registry.apply_certification(result)
    return result


def _write_provider_attempt(
    output: Path, module_id: str, version: int, request: ResearchRequest,
    artifacts: dict[str, Any],
) -> None:
    directory = output / "provider" / module_id / f"attempt_{version:02d}"
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
    for filename, value in mapping.items():
        write_json(directory / filename, value)


def _select_provider(
    *,
    mode: ProviderMode, recording_path: Path | None, attempt_index: int,
    attachments: list[Any], registry: SharedBlockARegistry,
) -> Any:
    if mode == ProviderMode.RECORDED:
        return RecordedResearchProvider(
            recording_path, attempt_index=attempt_index, attachments=attachments,
            prior_objects=registry.prior_objects(), shared_registry=registry,
        )
    if mode == ProviderMode.DETERMINISTIC:
        return DeterministicBlockAResearchProvider(
            recording_path, attempt_index=attempt_index, attachments=attachments,
            prior_objects=registry.prior_objects(), shared_registry=registry,
        )
    return OpenAIResearchProvider(
        attachments=attachments, prior_objects=registry.prior_objects(),
        shared_registry=registry,
    )


def _execute_module(
    *,
    case_data: dict[str, Any], plan: BlockAResearchPlan, contract: Any,
    registry: SharedBlockARegistry, mode: ProviderMode,
    recording_path: Path | None, attachments: list[Any], output: Path,
    iteration: int, version: int, attempts: list[dict[str, Any]],
    gaps: list[dict[str, Any]], override_question: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    request = _build_request(
        case_data=case_data, plan=plan, contract=contract, registry=registry,
        module_version=version, iteration=iteration, attempts=attempts, gaps=gaps,
        attachments=attachments, override_question=override_question,
    )
    provider = _select_provider(
        mode=mode, recording_path=recording_path, attempt_index=version - 1,
        attachments=attachments, registry=registry,
    )
    attempt_id = f"ATTEMPT-{contract.module_id}-V{version:02d}"
    try:
        bundle = provider.research(request, contract)
    except ProviderOutputValidationError as exc:
        artifacts = exc.artifacts or {
            "provider_response_raw": {}, "provider_trace": {"provider_type": mode.value},
            "tool_calls": [], "search_queries": [], "returned_citations": [],
            "validation_result": exc.validation, "admitted_objects": {}, "rejected_objects": [],
        }
        _write_provider_attempt(output, contract.module_id, version, request, artifacts)
        raise
    artifacts = bundle.provider_artifacts
    _write_provider_attempt(output, contract.module_id, version, request, artifacts)
    admitted = artifacts["admitted_objects"]
    conflicts = list(artifacts.get("conflicts", []))
    _validate_conflicts(conflicts, registry, admitted, contract.module_id)
    registry.admit(
        admitted=admitted, conflicts=conflicts, module_id=contract.module_id,
        module_name=contract.professional_name, research_question_id=request.request_id,
        iteration=iteration, provider_attempt=attempt_id,
        source_aliases=artifacts.get("source_aliases", {}),
    )
    certification = _certify(case_data["case_id"], registry)
    result = assess_block_a_module(
        request=request, bundle=bundle, registry=registry, contract=contract,
        threshold=plan.evidence_thresholds[contract.module_id],
        iteration=iteration, version=version,
    )
    attempt = {
        "provider_attempt_id": attempt_id,
        "module_id": contract.module_id,
        "module_name": contract.professional_name,
        "iteration": iteration,
        "module_version": version,
        "request_id": request.request_id,
        "prompt_reference": contract.prompt_reference,
        "provider_mode": mode.value,
        "question": request.research_question,
        "dependency_claim_ids": [row["claim_id"] for row in request.dependency_claims],
        "validation_status": artifacts["validation_result"]["status"],
        "admitted_source_ids": [row["source_id"] for row in admitted["sources"]],
        "admitted_evidence_ids": [row["evidence_id"] for row in admitted["evidence"]],
        "admitted_claim_ids": [row["claim_id"] for row in admitted["claims"]],
        "duplicate_source_candidates": [
            row for row in artifacts.get("rejected_objects", [])
            if row.get("object_type") == "DUPLICATE_SOURCE_CANDIDATE"
        ],
        "technical_failure": False,
    }
    attempts.append(attempt)
    return result, certification


def _write_outputs(
    *,
    output: Path, case_data: dict[str, Any], plan: BlockAResearchPlan,
    registry: SharedBlockARegistry, module_history: dict[str, list[dict[str, Any]]],
    certification: dict[str, Any], gate_history: list[dict[str, Any]],
    gaps: list[dict[str, Any]], attempts: list[dict[str, Any]],
    replans: list[dict[str, Any]], decisions: list[dict[str, Any]],
    iterations: list[dict[str, Any]], invalidations: list[dict[str, Any]],
    terminal_history: list[dict[str, Any]], attachments: list[Any],
) -> None:
    write_json(output / "planning" / "block_a_research_plan.json", plan)
    write_json(output / "planning" / "dependency_graph.json", plan.dependency_graph)
    write_json(output / "planning" / "research_questions.json", plan.research_questions)
    write_json(output / "planning" / "prompt_manifest.json", plan.prompt_manifest)
    write_json(output / "provider" / "attachment_manifest.json", attachment_manifest_artifact(attachments))
    write_json(output / "research" / "sources.json", registry.source_output())
    write_json(output / "research" / "evidence.json", registry.evidence)
    write_json(output / "research" / "claims.json", registry.claims)
    write_json(output / "research" / "assumptions.json", registry.assumptions)
    write_json(output / "research" / "unknowns.json", registry.unknowns)
    write_json(output / "research" / "counterevidence.json", registry.counterevidence)
    write_json(output / "research" / "conflicts.json", registry.conflicts)
    write_json(output / "research" / "claim_dependencies.json", registry.claim_dependencies)
    for module_id, filename in MODULE_FILENAMES.items():
        history = module_history.get(module_id, [])
        write_json(
            output / "modules" / filename,
            {"history": history, "final_result": history[-1] if history else None},
        )
    latest_module_results = {key: value[-1] for key, value in module_history.items() if value}
    write_json(
        output / "verification" / "evidence_quality_results.json",
        {
            key: {
                "status": value["status"],
                "source_diversity": value["source_diversity"],
                "failures": value["failures"],
            }
            for key, value in latest_module_results.items()
        },
    )
    write_json(output / "verification" / "pce_results.json", certification.get("pce_result", {}))
    write_json(output / "verification" / "er_brb_results.json", certification.get("er_brb_results", []))
    final_gate = gate_history[-1]
    write_json(output / "gate_a" / "criterion_results.json", final_gate["criterion_results"])
    write_json(output / "gate_a" / "gate_a_result.json", {"history": gate_history, "final_result": final_gate})
    write_json(output / "loop" / "gaps.json", gaps)
    write_json(output / "loop" / "research_attempts.json", attempts)
    write_json(output / "loop" / "replans.json", replans)
    write_json(output / "loop" / "controller_decisions.json", decisions)
    write_json(output / "loop" / "iteration_records.json", iterations)
    write_json(output / "loop" / "dependency_invalidations.json", invalidations)
    write_json(
        output / "loop" / "loop_state.json",
        {
            "status": final_gate["status"],
            "completed_iterations": len(iterations),
            "maximum_repair_iterations": plan.repair_budget["maximum_repair_iterations"],
            "provider_request_count": len(attempts),
            "maximum_provider_requests": plan.total_block_a_budget["maximum_provider_requests"],
            "open_gap_ids": [row["gap_id"] for row in gaps if row["status"] == "OPEN"],
            "history_is_append_only": True,
        },
    )
    write_json(output / "state" / "terminal_state_history.json", terminal_history)
    write_json(output / "state" / "final_terminal_state.json", terminal_history[-1])
    write_json(
        output / "run_summary.json",
        {
            "schema_version": "milestone-6-block-a",
            "case_id": case_data["case_id"],
            "provider_mode": attempts[0]["provider_mode"] if attempts else case_data["provider"]["mode"],
            "modules_executed": sorted(module_history),
            "module_execution_count": sum(len(value) for value in module_history.values()),
            "gate_a_result": final_gate["status"],
            "iterations": len(iterations),
            "targeted_repair_modules": sorted({row["target_module"] for row in replans}),
            "block_b_or_c_executed": False,
            "final_recommendation_generated": False,
            "output_directory": str(output),
        },
    )


def run_block_a_case(
    case_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    provider: str | ProviderMode | None = None,
    module: str = "BLOCK_A",
    enable_live: bool = False,
) -> BlockARunResult:
    path = Path(case_path).resolve()
    case_data = load_case(path)
    _validate_block_a_case(case_data)
    if module != "BLOCK_A":
        raise ProviderConfigurationError("Complete Block A execution requires --module BLOCK_A.")
    mode = _provider_mode(case_data, provider)
    if mode == ProviderMode.OPENAI_LIVE:
        check = check_block_a_configuration(
            path, provider=mode, module=module, output_dir=output_dir, enable_live=enable_live
        )
        if not check["ready"]:
            raise ProviderConfigurationError("; ".join(check["issues"]))
    output = Path(output_dir).resolve() if output_dir else path.parent / "run_output"
    output.mkdir(parents=True, exist_ok=True)
    plan = build_block_a_research_plan(case_data)
    if mode == ProviderMode.OPENAI_LIVE:
        _apply_live_environment_budgets(plan)
    contracts = {
        item.module_id: item for item in load_module_contracts() if item.module_id in BLOCK_A_MODULE_NAMES
    }
    attachments, blocked = prepare_attachments(
        case_dir=path.parent, manifest=case_data["research"]["attachments"],
        provider_mode=mode,
    )
    if blocked:
        raise ProviderConfigurationError(blocked[0]["reason"])
    recording = _recording_path(path, case_data) if mode != ProviderMode.OPENAI_LIVE else None
    registry = SharedBlockARegistry()
    module_history: dict[str, list[dict[str, Any]]] = {key: [] for key in BLOCK_A_MODULE_NAMES}
    attempts: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    replans: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    iterations: list[dict[str, Any]] = []
    invalidations: list[dict[str, Any]] = []
    gate_history: list[dict[str, Any]] = []
    terminal_history: list[dict[str, Any]] = []
    certification: dict[str, Any] = {"pce_result": {}, "er_brb_results": []}
    technical_failure: ProviderError | None = None
    try:
        executed: list[str] = []
        for module_id in plan.module_order:
            result, certification = _execute_module(
                case_data=case_data, plan=plan, contract=contracts[module_id],
                registry=registry, mode=mode, recording_path=recording,
                attachments=attachments, output=output, iteration=1, version=1,
                attempts=attempts, gaps=gaps,
            )
            module_history[module_id].append(result)
            executed.append(module_id)
        current = {key: value[-1] for key, value in module_history.items() if value}
        gate = evaluate_block_a_gate(
            case_data=case_data, module_results=current, registry=registry,
            certification=certification, iteration=1, open_gaps=gaps,
        )
        gate_history.append(gate)
        iterations.append(
            {
                "iteration": 1, "modules_executed": executed,
                "module_versions": {key: len(value) for key, value in module_history.items()},
                "gate_a_result": gate["status"], "gap_ids": [],
            }
        )
        repair_budget = plan.repair_budget["maximum_repair_iterations"]
        if gate["status"] == "FAIL_RESEARCH_GAP" and repair_budget > 0:
            gap = smallest_responsible_gap(gate, current, 1)
            gaps.append(gap)
            iterations[-1]["gap_ids"].append(gap["gap_id"])
            target = gap["originating_module"]
            prior_questions = {
                row["question"].strip().lower()
                for row in attempts if row["module_id"] == target
            }
            followup = (
                f"Which additional independent evidence resolves {gap['missing_evidence']} "
                f"for {BLOCK_A_MODULE_NAMES[target]} without repeating prior queries?"
            )
            if followup.strip().lower() in prior_questions:
                raise ProviderConfigurationError("Repeated repair question was prevented.")
            replan = {
                "replan_id": f"REPLAN-{target}-02",
                "originating_gap_id": gap["gap_id"],
                "failed_criterion": gap["failed_criterion"],
                "missing_evidence": gap["missing_evidence"],
                "target_module": target,
                "narrower_follow_up_question": followup,
                "prior_queries_repeated": False,
                "scope": "smallest_responsible_module",
            }
            replans.append(replan)
            decisions.append(
                {
                    "iteration": 1, "decision": "TARGETED_REPAIR",
                    "target_module": target, "gap_id": gap["gap_id"],
                    "all_modules_restarted": False,
                }
            )
            repair_modules = [target]
            changed_result, certification = _execute_module(
                case_data=case_data, plan=plan, contract=contracts[target], registry=registry,
                mode=mode, recording_path=recording, attachments=attachments, output=output,
                iteration=2, version=len(module_history[target]) + 1, attempts=attempts,
                gaps=gaps, override_question=followup,
            )
            module_history[target].append(changed_result)
            for downstream in dependent_synthesis_modules(target):
                if downstream not in module_history or not module_history[downstream]:
                    continue
                invalidation = {
                    "invalidation_id": f"INVALIDATE-{target}-{downstream}-02",
                    "changed_upstream_module": target,
                    "invalidated_module": downstream,
                    "invalidated_version": module_history[downstream][-1]["version"],
                    "reason": "An upstream Claim version changed; only dependent synthesis is rerun.",
                    "iteration": 2,
                    "prior_version_preserved": True,
                }
                invalidations.append(invalidation)
                synthesis_question = (
                    f"Re-synthesize {BLOCK_A_MODULE_NAMES[downstream]} using the new {target} Claim version; "
                    "preserve all counterevidence and do not repeat the earlier synthesis."
                )
                result, certification = _execute_module(
                    case_data=case_data, plan=plan, contract=contracts[downstream],
                    registry=registry, mode=mode, recording_path=recording,
                    attachments=attachments, output=output, iteration=2,
                    version=len(module_history[downstream]) + 1, attempts=attempts,
                    gaps=gaps, override_question=synthesis_question,
                )
                module_history[downstream].append(result)
                repair_modules.append(downstream)
            current = {key: value[-1] for key, value in module_history.items() if value}
            final_gate = evaluate_block_a_gate(
                case_data=case_data, module_results=current, registry=registry,
                certification=certification, iteration=2, open_gaps=gaps,
            )
            if final_gate["status"] in {"PASS", "CONDITIONAL_PASS"}:
                gap["status"] = "RESOLVED" if final_gate["status"] == "PASS" else "CONDITIONALLY_RESOLVED"
                gap["resolved_iteration"] = 2
                final_gate = evaluate_block_a_gate(
                    case_data=case_data, module_results=current, registry=registry,
                    certification=certification, iteration=2, open_gaps=gaps,
                )
            gate_history.append(final_gate)
            iterations.append(
                {
                    "iteration": 2, "modules_executed": repair_modules,
                    "module_versions": {key: len(value) for key, value in module_history.items()},
                    "gate_a_result": final_gate["status"], "gap_ids": [gap["gap_id"]],
                }
            )
            decisions.append(
                {
                    "iteration": 2,
                    "decision": "ADVANCE_BLOCK_A" if final_gate["status"] in {"PASS", "CONDITIONAL_PASS"} else "STOP_ITERATION_BUDGET",
                    "target_module": target,
                    "gate_a_result": final_gate["status"],
                }
            )
        else:
            decisions.append(
                {
                    "iteration": 1,
                    "decision": "ADVANCE_BLOCK_A" if gate["status"] in {"PASS", "CONDITIONAL_PASS"} else "STOP_ITERATION_BUDGET",
                    "gate_a_result": gate["status"],
                }
            )
    except ProviderError as exc:
        technical_failure = exc
        decisions.append(
            {
                "iteration": len(iterations) + 1,
                "decision": "FAIL_TECHNICAL",
                "error_class": exc.__class__.__name__,
                "reason": str(exc),
                "business_gap_created": False,
            }
        )
        gate_history.append(
            {
                "gate_result_id": "GATE-A-NOT-RUN-TECHNICAL",
                "gate_id": "GATE_A", "gate_name": "Strategic Thesis Gate",
                "iteration": len(iterations) + 1, "status": "FAILED_TECHNICAL",
                "criterion_results": [], "failed_criteria": [], "conditions": [],
                "open_gaps": [], "human_review_items": [],
                "downstream_permission": "BLOCK_B_NOT_PERMITTED",
                "business_outcome": "NOT_EVALUATED_TECHNICAL_FAILURE",
                "certification_summary": {"provider_selected_gate_result": False},
            }
        )
        iterations.append(
            {
                "iteration": len(iterations) + 1, "modules_executed": [],
                "gate_a_result": "FAILED_TECHNICAL", "gap_ids": [],
            }
        )
    final_gate = gate_history[-1]
    outcome_value = "FAILED_TECHNICAL" if technical_failure else final_gate["status"]
    outcome = BlockAOutcome(outcome_value)
    terminal = {
        "terminal_state_id": f"TERMINAL-BLOCK-A-{case_data['case_id']}-{len(iterations):02d}",
        "case_id": case_data["case_id"],
        "status": outcome.value,
        "gate_a_result": final_gate["status"],
        "gate_b_result": "NOT_RUN_MILESTONE_6",
        "gate_c_result": "NOT_RUN_MILESTONE_6",
        "iterations_used": len(iterations),
        "modules_executed": sorted(key for key, value in module_history.items() if value),
        "module_execution_count": sum(len(value) for value in module_history.values()),
        "open_gap_ids": [row["gap_id"] for row in gaps if row["status"] == "OPEN"],
        "human_review_items": final_gate.get("human_review_items", []),
        "stopping_reason": (
            str(technical_failure) if technical_failure
            else "Complete Block A reached an independently evaluated Strategic Thesis Gate outcome."
        ),
        "authority_boundary": "Milestone 6 does not execute live Block B, live Block C or a final Go / No-Go recommendation.",
        "timestamp": utc_now(),
    }
    terminal_history.append(terminal)
    _write_outputs(
        output=output, case_data=case_data, plan=plan, registry=registry,
        module_history=module_history, certification=certification,
        gate_history=gate_history, gaps=gaps, attempts=attempts, replans=replans,
        decisions=decisions, iterations=iterations, invalidations=invalidations,
        terminal_history=terminal_history, attachments=attachments,
    )
    return BlockARunResult(
        case_id=case_data["case_id"], provider_mode=mode, outcome=outcome,
        output_dir=str(output), iterations=len(iterations),
        module_executions=sum(len(value) for value in module_history.values()),
        gate_a_result=final_gate, terminal_state=terminal,
    )
