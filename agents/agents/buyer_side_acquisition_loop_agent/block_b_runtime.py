from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any

from .attachment_ingestion import (
    attachment_manifest_artifact,
    output_directory_is_writable,
    prepare_attachments,
    validate_no_plaintext_credentials,
)
from .block_a_evaluation import latest_claims
from .block_a_registry import SharedBlockARegistry
from .block_a_runtime import _write_provider_attempt
from .block_b_calculations import (
    CALCULATION_OWNERS,
    latest_calculations,
    mandate_threshold_gaps,
    run_block_b_calculations,
)
from .block_b_evaluation import dependent_block_b_modules, evaluate_block_b_gate
from .block_b_financials import (
    latest_financial_points,
    parse_block_b_financial_payload,
    supersede_financial_points,
    validate_synergy_separation,
)
from .block_b_models import (
    BLOCK_B_DEPENDENCIES,
    BLOCK_B_MODULE_NAMES,
    BLOCK_B_ORDER,
    BLOCK_B_REQUIRED_CALCULATIONS,
    BlockBModuleExecution,
    BlockBOutcome,
    BlockBResearchPlan,
    BlockBRunResult,
)
from .business_certification import run_business_certification
from .business_contracts import load_module_contracts, load_prompt_registry
from .business_loop import enter_unified_loop
from .business_models import BusinessBlock, BusinessMandate, ResearchRequest
from .certification_adapter import run_claim_pce_precheck
from .live_research_models import (
    AttachmentValidationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderMode,
)
from .live_research_provider import (
    DeterministicBlockAResearchProvider,
    OpenAIResearchProvider,
    RecordedResearchProvider,
    _source_model,
    check_openai_live_configuration,
)
from .models import Claim, Evidence, EvidenceStatus
from .pipeline_models import validate_block_b_input_bundle
from .storage import load_case, to_primitive, write_json
from .xlsx_ingestion import extract_xlsx_cells


REQUIRED_CASE_FIELDS = {
    "schema_version", "case_id", "as_of_date", "provider", "gate_a_result",
    "business_mandate", "research_contract", "research",
}

PROHIBITED_CONCLUSIONS = {
    "B1": ["synergy", "valuation", "purchase-price approval", "Gate B", "Go / No-Go"],
    "B2": ["Strategic Fit as quantified proof", "valuation", "Gate B", "Go / No-Go"],
    "B3": ["purchase-price approval", "financing commitment", "Gate B", "Go / No-Go"],
    "B4": ["financial capacity as willingness to pay", "return approval", "Gate B", "Go / No-Go"],
    "B5": ["invented hurdle", "positive IRR as automatic pass", "Gate B", "Go / No-Go"],
}


def _provider_mode(value: str | ProviderMode | None, case_data: dict[str, Any]) -> ProviderMode:
    selected = value or case_data.get("provider", {}).get("mode")
    try:
        return selected if isinstance(selected, ProviderMode) else ProviderMode(str(selected))
    except ValueError as exc:
        raise ProviderConfigurationError(f"Unsupported provider mode: {selected}") from exc


def _validate_case(case_data: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_CASE_FIELDS - set(case_data))
    if missing:
        raise ProviderConfigurationError(f"Milestone 7 case misses fields: {missing}")
    if case_data.get("schema_version") != "milestone-7-block-b":
        raise ProviderConfigurationError("Block B runtime requires schema_version milestone-7-block-b")
    gate_a = case_data["gate_a_result"]
    if gate_a.get("gate_id") != "GATE_A" or gate_a.get("status") not in {"PASS", "CONDITIONAL_PASS"}:
        raise ProviderConfigurationError("Block B requires an admitted PASS or CONDITIONAL_PASS Gate A result")
    if gate_a.get("downstream_permission") not in {
        "BLOCK_B_MAY_START", "BLOCK_B_MAY_START_WITH_CONDITIONS"
    }:
        raise ProviderConfigurationError("Gate A did not permit Block B")
    if "block_b_input_bundle" in case_data:
        try:
            validate_block_b_input_bundle(
                case_data["block_b_input_bundle"],
                case_id=str(case_data["case_id"]),
                run_id=str(case_data.get("run_id", "")),
                as_of_date=str(case_data["as_of_date"]),
            )
        except (TypeError, ValueError) as exc:
            raise ProviderConfigurationError(f"Invalid BlockBInputBundle: {exc}") from exc
    validate_no_plaintext_credentials(case_data)
    threshold_gaps = mandate_threshold_gaps(case_data["business_mandate"])
    if threshold_gaps:
        raise ProviderConfigurationError(
            "; ".join(
                f"{item.gap_type.value}: {item.missing_or_conflicting_inputs[0]}"
                for item in threshold_gaps
            )
        )
    BusinessMandate.from_dict(case_data["business_mandate"])
    research = case_data["research"]
    for name in (
        "required_periods", "attachments", "xlsx_extractions", "module_budgets",
        "maximum_repair_iterations", "human_review_boundaries",
    ):
        if name not in research:
            raise ProviderConfigurationError(f"Block B research.{name} is required")


def _recording_path(case_path: Path, case_data: dict[str, Any]) -> Path:
    relative = str(case_data.get("provider", {}).get("recording", ""))
    if not relative or Path(relative).is_absolute():
        raise ProviderConfigurationError("Recorded provider path must be relative to the case directory")
    root = case_path.resolve().parent
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ProviderConfigurationError("Recorded provider path escapes the case directory") from exc
    if not candidate.is_file():
        raise ProviderConfigurationError(f"Recorded provider file does not exist: {relative}")
    return candidate


def build_block_b_research_plan(case_data: dict[str, Any]) -> BlockBResearchPlan:
    contracts = {item.module_id: item for item in load_module_contracts() if item.module_id in BLOCK_B_ORDER}
    prompts = load_prompt_registry()
    mandate = BusinessMandate.from_dict(case_data["business_mandate"])
    research = case_data["research"]
    attachment_permissions = {
        module_id: [
            str(row["attachment_id"])
            for row in research["attachments"]
            if module_id in row.get("permitted_modules", [])
        ]
        for module_id in BLOCK_B_ORDER
    }
    prompt_manifest = {
        module_id: contracts[module_id].prompt_reference for module_id in BLOCK_B_ORDER
    }
    if any(reference.rsplit("#", 1)[-1] not in prompts for reference in prompt_manifest.values()):
        raise ProviderConfigurationError("Block B plan references an unapproved prompt")
    return BlockBResearchPlan(
        plan_id=f"PLAN-BLOCK-B-{case_data['case_id']}",
        case_id=case_data["case_id"],
        module_order=list(BLOCK_B_ORDER),
        dependency_graph={key: list(value) for key, value in BLOCK_B_DEPENDENCIES.items()},
        module_questions={module_id: list(contracts[module_id].required_research_questions) for module_id in BLOCK_B_ORDER},
        required_periods=list(research["required_periods"]),
        transaction_currency=str(research.get("transaction_currency") or mandate.currency),
        reporting_currency=str(research.get("reporting_currency") or mandate.currency),
        reporting_unit=mandate.unit,
        required_calculations=list(BLOCK_B_REQUIRED_CALCULATIONS),
        price_thresholds={"maximum_equity_purchase_price": str(mandate.maximum_equity_purchase_price)},
        return_thresholds={"minimum_roic": str(mandate.minimum_roic), "minimum_irr": str(mandate.minimum_irr)},
        financing_thresholds={"maximum_pro_forma_leverage": str(mandate.maximum_pro_forma_leverage), "minimum_closing_liquidity": str(mandate.minimum_closing_liquidity)},
        attachment_permissions=attachment_permissions,
        research_budgets={key: dict(value) for key, value in research["module_budgets"].items()},
        repair_budget={"maximum_repair_iterations": int(research["maximum_repair_iterations"])},
        human_review_boundaries=list(research["human_review_boundaries"]),
        prompt_manifest=prompt_manifest,
    )


def _extract_xlsx_artifacts(case_path: Path, case_data: dict[str, Any], attachments: list[Any]) -> list[dict[str, Any]]:
    by_id = {item.attachment_id: item for item in attachments}
    rows = []
    for attachment_id, specifications in case_data["research"]["xlsx_extractions"].items():
        if attachment_id not in by_id:
            raise AttachmentValidationError(f"XLSX extraction references unknown attachment: {attachment_id}")
        attachment = by_id[attachment_id]
        if attachment.file_type != "xlsx":
            raise AttachmentValidationError(f"XLSX extraction target is not .xlsx: {attachment_id}")
        rows.extend(to_primitive(extract_xlsx_cells(Path(attachment.absolute_path), list(specifications))))
    return rows


def check_block_b_configuration(
    case_path: Path, *, provider: str | ProviderMode | None = None,
    module: str = "BLOCK_B", output_dir: Path | None = None, enable_live: bool = False,
) -> dict[str, Any]:
    issues: list[str] = []
    paid_request_made = False
    case_path = case_path.resolve()
    case_data: dict[str, Any] = {}
    mode: ProviderMode | None = None
    try:
        case_data = load_case(case_path)
        _validate_case(case_data)
        mode = _provider_mode(provider, case_data)
        if module not in {*BLOCK_B_ORDER, "BLOCK_B"}:
            raise ProviderConfigurationError("Milestone 7 module selection must be B1-B5 or BLOCK_B")
        plan = build_block_b_research_plan(case_data)
        attachments, blocked = prepare_attachments(
            case_dir=case_path.parent,
            manifest=case_data["research"]["attachments"],
            provider_mode=mode,
        )
        _extract_xlsx_artifacts(case_path, case_data, attachments)
        if blocked:
            issues.extend(item["reason"] for item in blocked)
        destination = (output_dir or case_path.parent / "run_output").resolve()
        if not output_directory_is_writable(destination):
            issues.append(f"Output directory is not writable: {destination}")
        if mode in {ProviderMode.RECORDED, ProviderMode.DETERMINISTIC}:
            _recording_path(case_path, case_data)
        if mode == ProviderMode.OPENAI_LIVE:
            live = check_openai_live_configuration()
            issues.extend(live["issues"])
            if not enable_live:
                issues.append("Paid live execution is disabled; pass --enable-live explicitly after configuration succeeds.")
            for attachment in attachments:
                if attachment.confidentiality.lower() != "public" and not attachment.allow_provider_upload:
                    # Local extraction is authorized, but upload remains forbidden.
                    continue
        _ = plan
    except (ProviderError, ValueError, OSError) as exc:
        issues.append(str(exc))
    return {
        "ready": not issues,
        "provider_mode": mode.value if mode else str(provider or ""),
        "module_selection": module,
        "live_execution_enabled": bool(mode == ProviderMode.OPENAI_LIVE and enable_live and not issues),
        "paid_request_made": paid_request_made,
        "issues": list(dict.fromkeys(issues)),
    }


def _dependency_claims(
    registry: SharedBlockARegistry, module_id: str, gate_a_result: dict[str, Any]
) -> list[dict[str, Any]]:
    rows = [dict(item) for item in gate_a_result.get("admitted_claims", [])]
    for dependency in BLOCK_B_DEPENDENCIES[module_id]:
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
    *, case_data: dict[str, Any], plan: BlockBResearchPlan,
    contract: Any, registry: SharedBlockARegistry, iteration: int, version: int,
    open_gaps: list[dict[str, Any]],
) -> ResearchRequest:
    mandate = case_data["business_mandate"]
    budget = plan.research_budgets[contract.module_id]
    return ResearchRequest(
        request_id=f"RQ-{contract.module_id}-I{iteration:02d}-V{version:02d}",
        case_id=case_data["case_id"], module_id=contract.module_id,
        module_name=contract.professional_name, owning_block=BusinessBlock.BLOCK_B,
        prompt_reference=contract.prompt_reference,
        research_questions=list(plan.module_questions[contract.module_id]),
        mandate_id=mandate["mandate_id"],
        contract_id=case_data["research_contract"]["contract_id"],
        provenance_boundary="Only admitted Sources, Evidence, explicit Assumptions and dependency Claims may support Block B.",
        buyer_identity=mandate["buyer_name"], buyer_description=mandate.get("buyer_description", ""),
        target_identity=mandate["target_name"], target_description=mandate.get("target_description", ""),
        transaction_context=mandate["decision_question"],
        research_question="; ".join(plan.module_questions[contract.module_id]),
        business_purpose=contract.business_purpose,
        decision_relevance=contract.decision_relevance,
        required_claim_types=list(contract.required_claims),
        preferred_source_types=list(contract.preferred_source_types),
        excluded_source_types=list(case_data["research"].get("excluded_source_types", [])),
        evidence_threshold={"minimum_independent_sources_per_material_claim": 1, "exact_locator_required": True},
        counterevidence_requirement="A material counterevidence record is mandatory.",
        material_unknowns=list(contract.explicit_unknown_requirements),
        supplied_attachments=[row for row in case_data["research"]["attachments"] if row["attachment_id"] in plan.attachment_permissions[contract.module_id]],
        confidentiality_constraints=list(case_data["research"].get("confidentiality_restrictions", [])),
        as_of_date=case_data["as_of_date"],
        jurisdiction=list(mandate.get("jurisdictions", [])),
        prior_attempts=[{"module_id": contract.module_id, "version": value} for value in range(1, version)],
        open_gaps=open_gaps,
        previous_evidence=[row for row in registry.evidence if row.get("owning_module") == contract.module_id],
        search_budget=dict(budget),
        dependency_claims=_dependency_claims(registry, contract.module_id, case_data["gate_a_result"]),
        known_facts=list(case_data["research"].get("known_facts", [])),
        known_unknowns=list(case_data["research"].get("known_unknowns", [])),
        existing_counterevidence=[row for row in registry.counterevidence],
        query_budget=int(budget.get("maximum_queries", 0)),
        tool_call_budget=int(budget.get("maximum_tool_calls", 0)),
        prohibited_conclusions=list(PROHIBITED_CONCLUSIONS[contract.module_id]),
        attachment_use=list(plan.attachment_permissions[contract.module_id]),
    )


def _select_provider(
    *, mode: ProviderMode, recording_path: Path | None, attempt_index: int,
    attachments: list[Any], registry: SharedBlockARegistry,
) -> Any:
    kwargs = {
        "attachments": attachments,
        "prior_objects": registry.prior_objects(),
        "shared_registry": registry,
    }
    if mode == ProviderMode.RECORDED:
        return RecordedResearchProvider(recording_path, attempt_index=attempt_index, **kwargs)
    if mode == ProviderMode.DETERMINISTIC:
        return DeterministicBlockAResearchProvider(recording_path, attempt_index=attempt_index, **kwargs)
    return OpenAIResearchProvider(**kwargs)


def _execute_module(
    *, case_data: dict[str, Any], plan: BlockBResearchPlan, contract: Any,
    registry: SharedBlockARegistry, mode: ProviderMode, recording_path: Path | None,
    attachments: list[Any], iteration: int, version: int,
    open_gaps: list[dict[str, Any]], output: Path,
) -> tuple[Any, list[Any], list[Any], list[Any], BlockBModuleExecution]:
    request = _build_request(
        case_data=case_data, plan=plan, contract=contract, registry=registry,
        iteration=iteration, version=version, open_gaps=open_gaps,
    )
    provider = _select_provider(
        mode=mode, recording_path=recording_path, attempt_index=version - 1,
        attachments=attachments, registry=registry,
    )
    bundle = provider.research(request, contract)
    payload = bundle.provider_artifacts["provider_response_structured"]
    attempt_ids = {
        row.get("provider_attempt_id", "")
        for row in [*payload.get("financial_data_points", []), *payload.get("synergy_records", [])]
    }
    attempt_ids.discard("")
    if len(attempt_ids) > 1:
        raise ProviderConfigurationError(f"{contract.module_id} provider financial lineage contains multiple attempt IDs")
    provider_attempt_id = next(iter(attempt_ids), f"ATTEMPT-{contract.module_id}-{version:02d}")
    points, normalizations, synergies = parse_block_b_financial_payload(
        payload, module_id=contract.module_id, provider_attempt_id=provider_attempt_id
    )
    synergy_failures = validate_synergy_separation(synergies)
    if synergy_failures:
        raise ProviderConfigurationError(f"Unsupported quantified synergy records: {synergy_failures}")
    registry.admit(
        admitted=bundle.provider_artifacts["admitted_objects"],
        conflicts=list(bundle.provider_artifacts.get("conflicts", [])),
        module_id=contract.module_id, module_name=contract.professional_name,
        research_question_id=request.request_id, iteration=iteration,
        provider_attempt=provider_attempt_id,
        source_aliases=bundle.provider_artifacts.get("source_aliases", {}),
    )
    _write_provider_attempt(output, contract.module_id, version, request, bundle.provider_artifacts)
    execution = BlockBModuleExecution(
        module_id=contract.module_id, module_name=contract.professional_name,
        version=version, iteration=iteration, request_id=request.request_id,
        provider_attempt_id=provider_attempt_id,
        prompt_reference=contract.prompt_reference,
        dependency_claim_ids=[row["claim_id"] for row in request.dependency_claims],
        status="ADMITTED", result=to_primitive(bundle.module_result),
        financial_data_point_ids=[item.data_point_id for item in points],
        synergy_ids=[item.synergy_id for item in synergies], calculation_ids=[],
        pce_statuses={}, er_brb_statuses={}, gap_ids=[], invalidated_by=[],
    )
    return bundle, points, normalizations, synergies, execution


def _certify(
    case_id: str, registry: SharedBlockARegistry, calculations: list[Any]
) -> dict[str, Any]:
    evidence_by_id = {row["evidence_id"]: row for row in registry.evidence}
    sources = [_source_model(row, "Block B shared Source Registry") for row in registry.sources]
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
    calc_owners = {item.owning_module for item in latest_calculations(calculations) if item.replay_status.value == "PASS"}
    claims = []
    for row in registry.claims:
        source_ids = sorted({
            evidence_by_id[item]["source_id"]
            for item in row.get("supporting_evidence_ids", []) if item in evidence_by_id
        })
        calculation_required = row.get("owning_module_id") in {"B3", "B4", "B5"}
        claims.append(
            Claim(
                claim_id=row["claim_id"], claim_text=row["claim_text"],
                business_module=row["owning_module"],
                evidence_ids=list(row["supporting_evidence_ids"]), source_ids=source_ids,
                human_review_required=bool(row["human_review_required"]),
                calculation_required=calculation_required,
                calculation_replayed=(not calculation_required or row.get("owning_module_id") in calc_owners),
                claim_class=row["claim_class"], materiality=row["materiality"],
                counterevidence_ids=list(row["counterevidence_ids"]),
            )
        )
    prechecks = [
        {
            "claim_id": claim.claim_id,
            **run_claim_pce_precheck(case_id=case_id, claim=claim, sources=sources, evidence=evidence),
        }
        for claim in claims
    ]
    result = run_business_certification(
        case_id=case_id, sources=sources, evidence=evidence, claims=claims
    )
    result["pce_prechecks"] = prechecks
    result["execution_order"] = [
        "independent calculation replay", "PCE precheck", "ER/BRB", "final PCE delivery control", "Gate B"
    ]
    registry.apply_certification(result)
    return result


def _latest_module_results(bundles: list[Any]) -> list[Any]:
    by_module = {}
    for bundle in bundles:
        by_module[bundle.module_result.module_id] = bundle.module_result
    return [by_module[item] for item in BLOCK_B_ORDER if item in by_module]


def _unsupported_price_assumptions(registry: SharedBlockARegistry, points: list[Any]) -> list[str]:
    latest = [item for item in latest_financial_points(points) if item.metric == "offer_equity_value"]
    if not latest:
        return ["offered Equity Value is missing"]
    assumptions = {row["assumption_id"]: row for row in registry.assumptions}
    return [
        assumption_id for assumption_id in latest[-1].assumption_ids
        if assumption_id not in assumptions or not assumptions[assumption_id].get("supported", False)
    ]


def _write_outputs(
    *, output: Path, case_data: dict[str, Any], plan: BlockBResearchPlan,
    attachments: list[Any], xlsx_rows: list[dict[str, Any]], registry: SharedBlockARegistry,
    executions: list[BlockBModuleExecution], points: list[Any], normalizations: list[Any],
    synergies: list[Any], calculations: list[Any], replays: list[Any],
    gap_history: list[dict[str, Any]], certification: dict[str, Any],
    gates: list[Any], loops: list[dict[str, Any]], iterations: list[dict[str, Any]],
    human_reviews: list[dict[str, Any]], terminal: dict[str, Any], summary: dict[str, Any],
) -> None:
    write_json(output / "00_input" / "case.json", case_data)
    write_json(output / "00_input" / "business_mandate.json", case_data["business_mandate"])
    write_json(output / "00_input" / "research_contract.json", case_data["research_contract"])
    write_json(output / "00_input" / "admitted_gate_a_result.json", case_data["gate_a_result"])
    if "block_b_input_bundle" in case_data:
        write_json(output / "00_input" / "block_b_input_bundle.json", case_data["block_b_input_bundle"])
    write_json(output / "00_input" / "block_b_research_plan.json", plan)
    write_json(output / "00_input" / "attachment_manifest.json", attachment_manifest_artifact(attachments))
    write_json(output / "00_input" / "xlsx_extraction.json", xlsx_rows)
    write_json(output / "01_research" / "source_registry.json", registry.source_output())
    write_json(output / "01_research" / "evidence.json", registry.evidence)
    write_json(output / "01_research" / "claims.json", registry.claims)
    write_json(output / "01_research" / "assumptions.json", registry.assumptions)
    write_json(output / "01_research" / "unknowns.json", registry.unknowns)
    write_json(output / "01_research" / "counterevidence.json", registry.counterevidence)
    write_json(output / "01_research" / "duplicate_source_rejections.json", [
        row for path in sorted((output / "provider").glob("*/attempt_*/rejected_objects.json"))
        for row in (json.loads(path.read_text(encoding="utf-8")) if path.is_file() else [])
        if row.get("object_type") == "DUPLICATE_SOURCE_CANDIDATE"
    ])
    write_json(output / "02_modules" / "module_executions.json", executions)
    for module_id in BLOCK_B_ORDER:
        write_json(output / "02_modules" / f"{module_id.lower()}_executions.json", [item for item in executions if item.module_id == module_id])
    write_json(output / "03_financial_data" / "financial_data_points.json", points)
    write_json(output / "03_financial_data" / "normalization_records.json", normalizations)
    write_json(output / "03_financial_data" / "synergy_records.json", synergies)
    write_json(output / "04_calculations" / "calculations.json", calculations)
    write_json(output / "04_calculations" / "latest_calculations.json", latest_calculations(calculations))
    write_json(output / "04_calculations" / "calculation_replays.json", replays)
    write_json(output / "04_calculations" / "calculation_gap_history.json", gap_history)
    write_json(output / "05_controls" / "pce_prechecks.json", certification.get("pce_prechecks", []))
    write_json(output / "05_controls" / "pce_results.json", certification.get("pce_result", {}))
    write_json(output / "05_controls" / "er_brb_results.json", certification.get("er_brb_results", []))
    write_json(output / "05_controls" / "certification_adapter_boundary.json", certification.get("adapter_boundary", {}))
    write_json(output / "05_controls" / "control_execution_order.json", certification.get("execution_order", []))
    write_json(output / "05_controls" / "human_review_items.json", human_reviews)
    write_json(output / "06_gate_b" / "gate_b_history.json", gates)
    write_json(output / "06_gate_b" / "gate_b_result.json", gates[-1])
    write_json(output / "07_loop" / "loop_events.json", loops)
    write_json(output / "07_loop" / "iteration_records.json", iterations)
    write_json(output / "07_loop" / "terminal_state.json", terminal)
    write_json(output / "run_summary.json", summary)


def run_block_b_case(
    case_path: Path, output_dir: Path | None = None, *,
    provider: str | ProviderMode | None = None, module: str = "BLOCK_B",
    enable_live: bool = False,
) -> BlockBRunResult:
    case_path = case_path.resolve()
    case_data = load_case(case_path)
    _validate_case(case_data)
    if module != "BLOCK_B":
        raise ProviderConfigurationError("Complete Milestone 7 execution requires --module BLOCK_B")
    mode = _provider_mode(provider, case_data)
    if mode == ProviderMode.OPENAI_LIVE:
        check = check_block_b_configuration(
            case_path, provider=mode, module=module, output_dir=output_dir, enable_live=enable_live
        )
        if not check["ready"]:
            raise ProviderConfigurationError("; ".join(check["issues"]))
    output = (output_dir or case_path.parent / "run_output").resolve()
    if not output_directory_is_writable(output):
        raise ProviderConfigurationError(f"Output directory is not writable: {output}")
    plan = build_block_b_research_plan(case_data)
    mandate = BusinessMandate.from_dict(case_data["business_mandate"])
    attachments, blocked = prepare_attachments(
        case_dir=case_path.parent, manifest=case_data["research"]["attachments"],
        provider_mode=mode,
    )
    # Confidential local extraction remains available; blocked rows prevent live upload only.
    if mode == ProviderMode.OPENAI_LIVE and blocked:
        raise ProviderConfigurationError("; ".join(item["reason"] for item in blocked))
    xlsx_rows = _extract_xlsx_artifacts(case_path, case_data, attachments)
    recording = _recording_path(case_path, case_data) if mode != ProviderMode.OPENAI_LIVE else None
    contracts = {item.module_id: item for item in load_module_contracts() if item.module_id in BLOCK_B_ORDER}
    registry = SharedBlockARegistry()
    bundles: list[Any] = []
    executions: list[BlockBModuleExecution] = []
    points: list[Any] = []
    normalizations: list[Any] = []
    synergies: list[Any] = []
    versions = {item: 0 for item in BLOCK_B_ORDER}

    for module_id in BLOCK_B_ORDER:
        versions[module_id] += 1
        bundle, new_points, new_normalizations, new_synergies, execution = _execute_module(
            case_data=case_data, plan=plan, contract=contracts[module_id], registry=registry,
            mode=mode, recording_path=recording, attachments=attachments,
            iteration=1, version=versions[module_id], open_gaps=[], output=output,
        )
        bundles.append(bundle)
        points = supersede_financial_points(points, new_points)
        normalizations.extend(new_normalizations)
        synergies.extend(new_synergies)
        executions.append(execution)

    unsupported = _unsupported_price_assumptions(registry, points)
    calculations, replays, active_calc_gaps = run_block_b_calculations(
        points=points, mandate=mandate, iteration=1,
        unsupported_price_assumptions=unsupported,
    )
    certification = _certify(case_data["case_id"], registry, calculations)
    human_reviews = [dict(item) for item in case_data["research"].get("human_review_items", [])]
    gate = evaluate_block_b_gate(
        module_results=_latest_module_results(bundles), points=latest_financial_points(points),
        synergies=synergies, calculations=calculations, calculation_gaps=active_calc_gaps,
        research_gaps=[], integrity_gaps=[], mandate=mandate, registry=registry,
        certification=certification, human_review_items=human_reviews,
        gate_a_result=case_data["gate_a_result"],
    )
    gates = [gate]
    gap_history = [
        {**to_primitive(item), "status": "OPEN", "created_iteration": 1, "resolved_iteration": None}
        for item in active_calc_gaps
    ]
    iterations = [{
        "iteration": 1, "modules_executed": list(BLOCK_B_ORDER),
        "calculation_modules_executed": list(BLOCK_B_ORDER),
        "gate_b_status": gate.status.value, "gap_ids": [item.gap_id for item in active_calc_gaps],
        "change_summary": "Initial B1-B5 research, calculation replay, PCE and ER/BRB completed.",
    }]
    loops: list[dict[str, Any]] = []

    if gate.status.value not in {"PASS", "CONDITIONAL_PASS", "RENEGOTIATE_PRICE"}:
        loop = enter_unified_loop(gate, 1)
        responsible = active_calc_gaps[0].owning_module if active_calc_gaps else loop["replan"]["return_modules"][0]
        repair_modules = [responsible, *dependent_block_b_modules(responsible)]
        repair_modules = [item for item in BLOCK_B_ORDER if item in set(repair_modules)]
        loop["loop_controller"]["return_modules"] = repair_modules
        loop["replan"]["return_modules"] = repair_modules
        loop["replan"]["invalidated_calculation_modules"] = repair_modules
        loops.append(loop)
        if int(plan.repair_budget["maximum_repair_iterations"]) < 1:
            raise ProviderConfigurationError("Block B repair budget is exhausted")
        for module_id in repair_modules:
            versions[module_id] += 1
            bundle, new_points, new_normalizations, new_synergies, execution = _execute_module(
                case_data=case_data, plan=plan, contract=contracts[module_id], registry=registry,
                mode=mode, recording_path=recording, attachments=attachments,
                iteration=2, version=versions[module_id],
                open_gaps=[{"gap_id": item.gap_id, "gap_type": item.gap_type.value, "closure_test": item.closure_test} for item in active_calc_gaps if item.owning_module == responsible],
                output=output,
            )
            execution.invalidated_by = [responsible] if module_id != responsible else []
            bundles.append(bundle)
            points = supersede_financial_points(points, new_points)
            normalizations.extend(new_normalizations)
            synergies.extend(new_synergies)
            executions.append(execution)
        recalculation_modules = set(repair_modules)
        new_calculations, new_replays, new_gaps = run_block_b_calculations(
            points=points, mandate=mandate, iteration=2,
            module_ids=recalculation_modules,
            unsupported_price_assumptions=_unsupported_price_assumptions(registry, points),
        )
        calculations.extend(new_calculations)
        replays.extend(new_replays)
        for row in gap_history:
            row["status"] = "RESOLVED"
            row["resolved_iteration"] = 2
        active_calc_gaps = new_gaps
        gap_history.extend({**to_primitive(item), "status": "OPEN", "created_iteration": 2, "resolved_iteration": None} for item in new_gaps)
        certification = _certify(case_data["case_id"], registry, calculations)
        final_gate = evaluate_block_b_gate(
            module_results=_latest_module_results(bundles), points=latest_financial_points(points),
            synergies=synergies, calculations=calculations, calculation_gaps=active_calc_gaps,
            research_gaps=[], integrity_gaps=[], mandate=mandate, registry=registry,
            certification=certification, human_review_items=human_reviews,
            gate_a_result=case_data["gate_a_result"],
        )
        gates.append(final_gate)
        iterations.append({
            "iteration": 2, "modules_executed": repair_modules,
            "calculation_modules_executed": sorted(recalculation_modules),
            "gate_b_status": final_gate.status.value,
            "gap_ids": [item.gap_id for item in active_calc_gaps],
            "change_summary": f"Targeted repair returned to {responsible}; only dependent modules and calculations were invalidated.",
        })

    final_gate = gates[-1]
    terminal = {
        "terminal_state_id": f"TERMINAL-BLOCK-B-{case_data['case_id']}-{len(iterations):02d}",
        "status": "COMPLETED_BLOCK_B" if final_gate.status.value in {"PASS", "CONDITIONAL_PASS", "RENEGOTIATE_PRICE"} else "STOPPED_BLOCK_B",
        "case_id": case_data["case_id"], "gate_b_status": final_gate.status.value,
        "iterations": len(iterations), "module_executions": len(executions),
        "open_research_gap_ids": [], "open_calculation_gap_ids": [item.gap_id for item in active_calc_gaps],
        "human_review_item_ids": [item["review_id"] for item in human_reviews],
        "block_c_executed": False,
        "stopping_reason": "Block B Value Creation Gate completed; Block C is outside Milestone 7.",
    }
    summary = {
        "schema_version": "milestone-7-block-b", "case_id": case_data["case_id"],
        "provider_mode": mode.value, "modules_executed": [item.module_id for item in executions],
        "module_execution_count": len(executions), "iterations": len(iterations),
        "initial_gate_b_status": gates[0].status.value,
        "final_gate_b_status": final_gate.status.value,
        "required_calculations": list(BLOCK_B_REQUIRED_CALCULATIONS),
        "latest_calculation_types": [item.calculation_type for item in latest_calculations(calculations)],
        "all_latest_replays_passed": all(item.replay_status.value == "PASS" for item in latest_calculations(calculations)),
        "block_c_executed": False, "transaction_recommendation_generated": False,
        "output_dir": str(output),
    }
    _write_outputs(
        output=output, case_data=case_data, plan=plan, attachments=attachments,
        xlsx_rows=xlsx_rows, registry=registry, executions=executions, points=points,
        normalizations=normalizations, synergies=synergies, calculations=calculations,
        replays=replays, gap_history=gap_history, certification=certification,
        gates=gates, loops=loops, iterations=iterations, human_reviews=human_reviews,
        terminal=terminal, summary=summary,
    )
    outcome = BlockBOutcome(final_gate.status.value) if final_gate.status.value in {item.value for item in BlockBOutcome} else BlockBOutcome.FAILED_TECHNICAL
    return BlockBRunResult(
        case_id=case_data["case_id"], provider_mode=mode, outcome=outcome,
        output_dir=str(output), iterations=len(iterations), module_executions=len(executions),
        gate_b_result=to_primitive(final_gate), terminal_state=terminal,
    )
