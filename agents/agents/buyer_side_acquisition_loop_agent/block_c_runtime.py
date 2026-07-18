from __future__ import annotations

import copy
import hashlib
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
from .block_c_evaluation import (
    dependent_block_c_modules,
    evaluate_block_c_gate,
    synthesize_decision_state,
)
from .block_c_models import (
    BLOCK_C_DEPENDENCIES,
    BLOCK_C_MODULE_NAMES,
    BLOCK_C_ORDER,
    BlockCInputBundle,
    BlockCModuleExecution,
    BlockCOutcome,
    BlockCResearchGap,
    BlockCResearchGapType,
    BlockCResearchPlan,
    BlockCRunResult,
    DiligenceFinding,
    DownsideScenario,
    IntegrationRisk,
    RegulatoryRisk,
)
from .business_certification import run_business_certification
from .business_contracts import load_module_contracts, load_prompt_registry
from .business_loop import enter_unified_loop
from .business_models import BusinessBlock, BusinessMandate, ResearchRequest
from .certification_adapter import run_claim_pce_precheck
from .live_research_models import (
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
from .models import Claim, Evidence, EvidenceStatus, PCEStatus, Source
from .reporting import generate_reporting_package
from .storage import load_case, to_primitive, write_json


REQUIRED_CASE_FIELDS = {
    "schema_version", "case_id", "as_of_date", "provider",
    "block_c_input_bundle", "research",
}

HASHED_UPSTREAM_FIELDS = (
    "mandate_reference",
    "research_contract_reference",
    "gate_a_history",
    "gate_b_history",
    "admitted_strategic_claims",
    "admitted_financial_claims",
    "calculations",
    "calculation_replays",
)

PROHIBITED_CONCLUSIONS = {
    "C1": ["unperformed diligence complete", "Gate C", "Decision State", "transaction approval"],
    "C2": ["definitive legal advice", "invented filing threshold", "Gate C", "Decision State"],
    "C3": ["Strategic Fit proves integration success", "invented retention outcome", "Gate C", "Decision State"],
    "C4": ["invented downside probability", "unverified upside offset", "Gate C", "Decision State"],
    "C5": ["Gate C", "final Decision State", "delivery permission", "final human transaction approval"],
}

RECORD_COLLECTIONS = {
    "C1": "diligence_findings",
    "C2": "regulatory_risks",
    "C3": "integration_risks",
    "C4": "downside_scenarios",
    "C5": "decision_inputs",
}


def canonical_artifact_hash(value: Any) -> str:
    encoded = json.dumps(to_primitive(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _provider_mode(value: str | ProviderMode | None, case_data: dict[str, Any]) -> ProviderMode:
    selected = value or case_data.get("provider", {}).get("mode")
    try:
        return selected if isinstance(selected, ProviderMode) else ProviderMode(str(selected))
    except ValueError as exc:
        raise ProviderConfigurationError(f"Unsupported provider mode: {selected}") from exc


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


def _gate_hash(row: dict[str, Any]) -> str:
    return canonical_artifact_hash({key: value for key, value in row.items() if key != "artifact_hash"})


def validate_block_c_input_bundle(case_data: dict[str, Any]) -> tuple[BlockCInputBundle, dict[str, Any]]:
    try:
        bundle = BlockCInputBundle.from_dict(copy.deepcopy(case_data["block_c_input_bundle"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ProviderConfigurationError(f"Invalid BlockCInputBundle: {exc}") from exc
    case_id = str(case_data.get("case_id", ""))
    if bundle.schema_version not in {"milestone-8-block-c", "release-candidate-1"}:
        raise ProviderConfigurationError(
            f"Unsupported BlockCInputBundle schema: {bundle.schema_version}"
        )
    if bundle.schema_version == "release-candidate-1":
        if not bundle.run_id or bundle.run_id != str(case_data.get("run_id", "")):
            raise ProviderConfigurationError("BlockCInputBundle contains a mismatched run ID")
        if not bundle.as_of_date or bundle.as_of_date != str(case_data.get("as_of_date", "")):
            raise ProviderConfigurationError("BlockCInputBundle contains a mismatched as-of date")
        if not bundle.artifact_references:
            raise ProviderConfigurationError("BlockCInputBundle is missing artifact references")
    mandate = bundle.mandate_reference
    contract = bundle.research_contract_reference
    if not case_id or len({case_id, bundle.case_id, str(mandate.get("case_id", "")), str(contract.get("case_id", ""))}) != 1:
        raise ProviderConfigurationError("BlockCInputBundle contains mismatched case IDs")
    for history, gate_id in ((bundle.gate_a_history, "GATE_A"), (bundle.gate_b_history, "GATE_B")):
        for row in history:
            if row.get("case_id") != case_id or row.get("gate_id") != gate_id:
                raise ProviderConfigurationError(f"{gate_id} history contains mismatched provenance")
            if not row.get("provenance") or not row.get("artifact_hash"):
                raise ProviderConfigurationError(f"{gate_id} history is missing Gate provenance")
            if row["artifact_hash"] != _gate_hash(row):
                raise ProviderConfigurationError(f"{gate_id} history artifact was modified or is invalid")
    if bundle.gate_a_history[-1].get("status") not in {"PASS", "CONDITIONAL_PASS"}:
        raise ProviderConfigurationError("Block C requires a frozen PASS or CONDITIONAL_PASS Gate A")
    if bundle.gate_b_history[-1].get("status") not in {"PASS", "CONDITIONAL_PASS", "RENEGOTIATE_PRICE"}:
        raise ProviderConfigurationError("Block C received incompatible Gate B Decision State inputs")
    missing_hashes = [name for name in HASHED_UPSTREAM_FIELDS if name not in bundle.artifact_hashes]
    if missing_hashes:
        raise ProviderConfigurationError(f"BlockCInputBundle artifact hashes are incomplete: {missing_hashes}")
    hash_checks = {
        name: bundle.artifact_hashes[name] == canonical_artifact_hash(getattr(bundle, name))
        for name in HASHED_UPSTREAM_FIELDS
    }
    if not all(hash_checks.values()):
        invalid = [name for name, passed in hash_checks.items() if not passed]
        raise ProviderConfigurationError(f"Modified or invalid upstream artifacts: {invalid}")
    calculation_ids = [str(row.get("calculation_id", "")) for row in bundle.calculations]
    replay_ids = [str(row.get("calculation_id", "")) for row in bundle.calculation_replays]
    if not calculation_ids or set(calculation_ids) != set(replay_ids) or len(calculation_ids) != len(replay_ids):
        raise ProviderConfigurationError("Incomplete replay references in BlockCInputBundle")
    if any(row.get("status") != "PASS" for row in bundle.calculation_replays):
        raise ProviderConfigurationError("BlockCInputBundle requires valid PASS Calculation replay results")
    expected_modules = {f"A{i}" for i in range(1, 8)} | {f"B{i}" for i in range(1, 6)}
    module_ids = {str(row.get("module_id", "")) for row in bundle.upstream_module_results}
    if module_ids != expected_modules:
        raise ProviderConfigurationError("Frozen upstream module references must cover A1-A7 and B1-B5 without execution")
    constraints = {
        "maximum_equity_purchase_price": mandate.get("maximum_equity_purchase_price"),
        "maximum_pro_forma_leverage": mandate.get("maximum_pro_forma_leverage"),
        "minimum_closing_liquidity": mandate.get("minimum_closing_liquidity"),
        "minimum_roic": mandate.get("minimum_roic"),
        "minimum_irr": mandate.get("minimum_irr"),
    }
    supplied = {
        **bundle.price_constraints,
        **bundle.financing_constraints,
        **bundle.return_thresholds,
    }
    inconsistent = [key for key, value in constraints.items() if str(supplied.get(key)) != str(value)]
    if inconsistent:
        raise ProviderConfigurationError(f"BlockCInputBundle constraints conflict with the Mandate: {inconsistent}")
    if bundle.transaction_stage != mandate.get("process_stage"):
        raise ProviderConfigurationError("BlockCInputBundle transaction stage conflicts with the Mandate")
    fingerprint = canonical_artifact_hash({name: getattr(bundle, name) for name in HASHED_UPSTREAM_FIELDS})
    return bundle, {
        "case_id_match": True,
        "gate_provenance_complete": True,
        "artifact_hash_checks": hash_checks,
        "calculation_replay_references_complete": True,
        "decision_inputs_compatible": True,
        "gate_history_immutable_fingerprint": fingerprint,
        "validated": True,
    }


def _validate_case(case_data: dict[str, Any]) -> tuple[BlockCInputBundle, dict[str, Any]]:
    missing = sorted(REQUIRED_CASE_FIELDS - set(case_data))
    if missing:
        raise ProviderConfigurationError(f"Milestone 8 case misses fields: {missing}")
    if case_data.get("schema_version") != "milestone-8-block-c":
        raise ProviderConfigurationError("Block C runtime requires schema_version milestone-8-block-c")
    validate_no_plaintext_credentials(case_data)
    bundle, validation = validate_block_c_input_bundle(case_data)
    mandate = BusinessMandate.from_dict(bundle.mandate_reference)
    research = case_data["research"]
    for name in (
        "selected_diligence_workstreams", "attachments", "module_budgets",
        "maximum_repair_iterations", "materiality_thresholds", "severity_thresholds",
        "confidentiality_permissions", "private_information_boundaries",
        "human_review_roles", "completion_criteria",
    ):
        if name not in research:
            raise ProviderConfigurationError(f"Block C research.{name} is required")
    if set(research["selected_diligence_workstreams"]) != set(mandate.selected_diligence_workstreams):
        raise ProviderConfigurationError("Selected diligence workstreams must follow the frozen Mandate")
    if list(research.get("jurisdictions", [])) != bundle.transaction_jurisdictions:
        raise ProviderConfigurationError("Research jurisdictions must match the frozen upstream bundle")
    return bundle, validation


def build_block_c_research_plan(case_data: dict[str, Any], bundle: BlockCInputBundle | None = None) -> BlockCResearchPlan:
    bundle = bundle or validate_block_c_input_bundle(case_data)[0]
    contracts = {item.module_id: item for item in load_module_contracts() if item.module_id in BLOCK_C_ORDER}
    prompts = load_prompt_registry()
    research = case_data["research"]
    prompt_manifest = {module_id: contracts[module_id].prompt_reference for module_id in BLOCK_C_ORDER}
    if any(reference.rsplit("#", 1)[-1] not in prompts for reference in prompt_manifest.values()):
        raise ProviderConfigurationError("Block C plan references an unapproved prompt")
    permissions = {
        module_id: [
            str(row["attachment_id"])
            for row in research["attachments"]
            if module_id in row.get("permitted_modules", [])
        ]
        for module_id in BLOCK_C_ORDER
    }
    return BlockCResearchPlan(
        plan_id=f"PLAN-BLOCK-C-{bundle.case_id}",
        case_id=bundle.case_id,
        module_order=list(BLOCK_C_ORDER),
        dependency_graph={key: list(value) for key, value in BLOCK_C_DEPENDENCIES.items()},
        selected_diligence_workstreams=list(research["selected_diligence_workstreams"]),
        module_questions={module_id: list(contracts[module_id].required_research_questions) for module_id in BLOCK_C_ORDER},
        jurisdictions=list(bundle.transaction_jurisdictions),
        transaction_stage=bundle.transaction_stage,
        materiality_thresholds=dict(research["materiality_thresholds"]),
        severity_thresholds=dict(research["severity_thresholds"]),
        preferred_source_types={module_id: list(contracts[module_id].preferred_source_types) for module_id in BLOCK_C_ORDER},
        confidentiality_permissions=permissions,
        private_information_boundaries=list(research["private_information_boundaries"]),
        research_budgets={key: dict(value) for key, value in research["module_budgets"].items()},
        repair_budget={"maximum_repair_iterations": int(research["maximum_repair_iterations"])},
        human_review_roles=list(research["human_review_roles"]),
        completion_criteria=list(research["completion_criteria"]),
        prompt_manifest=prompt_manifest,
    )


def check_block_c_configuration(
    case_path: Path,
    *,
    provider: str | ProviderMode | None = None,
    module: str = "BLOCK_C",
    output_dir: Path | None = None,
    enable_live: bool = False,
) -> dict[str, Any]:
    issues: list[str] = []
    checks = {
        "api_key_and_model": False,
        "sdk": False,
        "case_valid": False,
        "upstream_bundle_valid": False,
        "jurisdictions_present": False,
        "attachment_permissions_valid": False,
        "prompts_available": False,
        "output_directory_writable": False,
        "explicit_live_enable": bool(enable_live),
    }
    mode: ProviderMode | None = None
    case_data: dict[str, Any] = {}
    case_path = case_path.resolve()
    try:
        case_data = load_case(case_path)
        mode = _provider_mode(provider, case_data)
    except (ProviderError, ValueError, OSError) as exc:
        issues.append(str(exc))
    if mode == ProviderMode.OPENAI_LIVE:
        live = check_openai_live_configuration()
        checks["api_key_and_model"] = live["checks"]["api_key_present"] and live["checks"]["model_present"]
        checks["sdk"] = live["checks"]["sdk_available"]
        issues.extend(live["issues"])
        if not enable_live:
            issues.append("Paid live execution is disabled; pass --enable-live explicitly after configuration succeeds.")
    elif mode is not None:
        checks["api_key_and_model"] = True
        checks["sdk"] = True
        checks["explicit_live_enable"] = False
    destination = (output_dir or case_path.parent / "run_output").resolve()
    checks["output_directory_writable"] = output_directory_is_writable(destination)
    if not checks["output_directory_writable"]:
        issues.append(f"Output directory is not writable: {destination}")
    if module not in {*BLOCK_C_ORDER, "BLOCK_C"}:
        issues.append("Milestone 8 module selection must be C1-C5 or BLOCK_C")
    bundle: BlockCInputBundle | None = None
    if case_data:
        try:
            bundle, _ = _validate_case(case_data)
            checks["case_valid"] = True
            checks["upstream_bundle_valid"] = True
            checks["jurisdictions_present"] = bool(bundle.transaction_jurisdictions)
            build_block_c_research_plan(case_data, bundle)
            checks["prompts_available"] = True
        except (ProviderError, ValueError, OSError) as exc:
            issues.append(str(exc))
        try:
            _, blocked = prepare_attachments(
                case_dir=case_path.parent,
                manifest=case_data.get("research", {}).get("attachments", []),
                provider_mode=mode or ProviderMode.RECORDED,
            )
            checks["attachment_permissions_valid"] = not blocked
            if blocked:
                issues.extend(item["reason"] for item in blocked)
        except (ProviderError, ValueError, OSError) as exc:
            issues.append(str(exc))
        if mode in {ProviderMode.RECORDED, ProviderMode.DETERMINISTIC}:
            try:
                _recording_path(case_path, case_data)
            except (ProviderError, ValueError, OSError) as exc:
                issues.append(str(exc))
    return {
        "ready": not issues,
        "provider_mode": mode.value if mode else str(provider or ""),
        "module_selection": module,
        "checks": checks,
        "live_execution_enabled": bool(mode == ProviderMode.OPENAI_LIVE and enable_live and not issues),
        "paid_request_made": False,
        "issues": list(dict.fromkeys(issues)),
    }


def _dependency_claims(registry: SharedBlockARegistry, module_id: str, bundle: BlockCInputBundle) -> list[dict[str, Any]]:
    rows = [
        {
            "claim_id": row["claim_id"],
            "claim_text": row["claim_text"],
            "owning_module": row.get("business_module", ""),
            "pce_status": row.get("pce_status", "Not Certified"),
            "limitations": "Frozen admitted upstream Claim; analytical dependency only.",
        }
        for row in [*bundle.admitted_strategic_claims, *bundle.admitted_financial_claims]
    ]
    for dependency in BLOCK_C_DEPENDENCIES[module_id]:
        for claim in latest_claims(registry.claims, dependency):
            rows.append({
                "claim_id": claim["claim_id"],
                "claim_text": claim["claim_text"],
                "owning_module": dependency,
                "pce_status": claim.get("pce_status", "Not Certified"),
                "limitations": claim.get("limitations", ""),
            })
    return rows


def _build_request(
    *,
    case_data: dict[str, Any],
    bundle: BlockCInputBundle,
    plan: BlockCResearchPlan,
    contract: Any,
    registry: SharedBlockARegistry,
    iteration: int,
    version: int,
    open_gaps: list[dict[str, Any]],
) -> ResearchRequest:
    mandate = bundle.mandate_reference
    budget = plan.research_budgets[contract.module_id]
    selected_workstreams = plan.selected_diligence_workstreams if contract.module_id == "C1" else []
    return ResearchRequest(
        request_id=f"RQ-{contract.module_id}-I{iteration:02d}-V{version:02d}",
        case_id=bundle.case_id,
        module_id=contract.module_id,
        module_name=contract.professional_name,
        owning_block=BusinessBlock.BLOCK_C,
        prompt_reference=contract.prompt_reference,
        research_questions=list(plan.module_questions[contract.module_id]),
        mandate_id=mandate["mandate_id"],
        contract_id=bundle.research_contract_reference["contract_id"],
        provenance_boundary="Frozen Block A and Block B results are read-only; only admitted Block C objects may update Block C Memory.",
        buyer_identity=mandate["buyer_name"],
        buyer_description=mandate.get("buyer_description", ""),
        target_identity=mandate["target_name"],
        target_description=mandate.get("target_description", ""),
        transaction_context=mandate["decision_question"],
        research_question="; ".join(plan.module_questions[contract.module_id]),
        business_purpose=contract.business_purpose,
        decision_relevance=contract.decision_relevance,
        required_claim_types=list(contract.required_claims),
        preferred_source_types=list(contract.preferred_source_types),
        excluded_source_types=list(case_data["research"].get("excluded_source_types", [])),
        evidence_threshold={
            "minimum_independent_sources_per_material_claim": 1,
            "exact_locator_required": True,
            "selected_diligence_workstreams": selected_workstreams,
            "materiality_thresholds": plan.materiality_thresholds,
            "severity_thresholds": plan.severity_thresholds,
        },
        counterevidence_requirement="A material counterevidence record is mandatory.",
        material_unknowns=list(contract.explicit_unknown_requirements),
        supplied_attachments=[row for row in case_data["research"]["attachments"] if row["attachment_id"] in plan.confidentiality_permissions[contract.module_id]],
        confidentiality_constraints=list(case_data["research"].get("confidentiality_restrictions", [])),
        as_of_date=case_data["as_of_date"],
        jurisdiction=list(plan.jurisdictions),
        prior_attempts=[{"module_id": contract.module_id, "version": value} for value in range(1, version)],
        open_gaps=open_gaps,
        previous_evidence=[row for row in registry.evidence if row.get("owning_module") == contract.module_id],
        search_budget=dict(budget),
        dependency_claims=_dependency_claims(registry, contract.module_id, bundle),
        known_facts=[
            {"fact": f"Frozen Gate A is {bundle.gate_a_history[-1]['status']}", "source": "validated BlockCInputBundle"},
            {"fact": f"Frozen Gate B is {bundle.gate_b_history[-1]['status']}", "source": "validated BlockCInputBundle"},
        ],
        known_unknowns=list(case_data["research"].get("known_unknowns", [])),
        existing_counterevidence=[row for row in registry.counterevidence],
        query_budget=int(budget.get("maximum_queries", 0)),
        tool_call_budget=int(budget.get("maximum_tool_calls", 0)),
        prohibited_conclusions=list(PROHIBITED_CONCLUSIONS[contract.module_id]),
        attachment_use=list(plan.confidentiality_permissions[contract.module_id]),
    )


def _select_provider(
    *,
    mode: ProviderMode,
    recording_path: Path | None,
    attempt_index: int,
    attachments: list[Any],
    registry: SharedBlockARegistry,
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


def _parse_records(module_id: str, payload: dict[str, Any], selected_workstreams: list[str]) -> list[Any]:
    rows = payload.get(RECORD_COLLECTIONS[module_id], [])
    if not isinstance(rows, list):
        raise ProviderConfigurationError(f"{RECORD_COLLECTIONS[module_id]} must be a list")
    if module_id == "C1":
        records = [DiligenceFinding.from_dict(row) for row in rows]
        returned = {item.workstream for item in records}
        if returned - set(selected_workstreams):
            raise ProviderConfigurationError("C1 falsely marked an unselected diligence workstream complete")
        return records
    if module_id == "C2":
        records = [RegulatoryRisk.from_dict(row) for row in rows]
        for item in records:
            if (item.assumption_ids or item.unknown_ids or "uncertain" in item.current_status.lower()) and not item.legal_adviser_review_required:
                raise ProviderConfigurationError("Material uncertain legal interpretation must route to Human Review")
        return records
    if module_id == "C3":
        return [IntegrationRisk.from_dict(row) for row in rows]
    if module_id == "C4":
        return [DownsideScenario.from_dict(row) for row in rows]
    if rows:
        reserved = {"decision_state", "gate_c_result", "delivery_permission", "final_human_transaction_approval"}
        if any(reserved & set(row) for row in rows if isinstance(row, dict)):
            raise ProviderConfigurationError("C5 provider output cannot select Gate C, Decision State or delivery permission")
    return []


def _record_id(record: Any) -> str:
    for name in ("finding_id", "regulatory_risk_id", "risk_id", "scenario_id"):
        if hasattr(record, name):
            return str(getattr(record, name))
    return ""


def _latest_records(records: list[Any]) -> list[Any]:
    by_id: dict[str, Any] = {}
    for item in records:
        key = _record_id(item)
        if key:
            prior = by_id.get(key)
            if prior is None or item.version > prior.version:
                by_id[key] = item
    return list(by_id.values())


def _execute_module(
    *,
    case_data: dict[str, Any],
    bundle: BlockCInputBundle,
    plan: BlockCResearchPlan,
    contract: Any,
    registry: SharedBlockARegistry,
    mode: ProviderMode,
    recording_path: Path | None,
    attachments: list[Any],
    iteration: int,
    version: int,
    open_gaps: list[dict[str, Any]],
    output: Path,
) -> tuple[Any, list[Any], BlockCModuleExecution]:
    request = _build_request(
        case_data=case_data, bundle=bundle, plan=plan, contract=contract,
        registry=registry, iteration=iteration, version=version, open_gaps=open_gaps,
    )
    provider = _select_provider(
        mode=mode, recording_path=recording_path, attempt_index=version - 1,
        attachments=attachments, registry=registry,
    )
    research_bundle = provider.research(request, contract)
    payload = research_bundle.provider_artifacts["provider_response_structured"]
    records = _parse_records(contract.module_id, payload, plan.selected_diligence_workstreams)
    attempt_ids = {str(getattr(item, "provider_attempt_id", "")) for item in records}
    attempt_ids.discard("")
    if len(attempt_ids) > 1:
        raise ProviderConfigurationError(f"{contract.module_id} records contain multiple provider attempt IDs")
    provider_attempt_id = next(iter(attempt_ids), f"ATTEMPT-{contract.module_id}-{version:02d}")
    registry.admit(
        admitted=research_bundle.provider_artifacts["admitted_objects"],
        conflicts=list(research_bundle.provider_artifacts.get("conflicts", [])),
        module_id=contract.module_id,
        module_name=contract.professional_name,
        research_question_id=request.request_id,
        iteration=iteration,
        provider_attempt=provider_attempt_id,
        source_aliases=research_bundle.provider_artifacts.get("source_aliases", {}),
    )
    _write_provider_attempt(output, contract.module_id, version, request, research_bundle.provider_artifacts)
    execution = BlockCModuleExecution(
        module_id=contract.module_id,
        module_name=contract.professional_name,
        version=version,
        iteration=iteration,
        request_id=request.request_id,
        provider_attempt_id=provider_attempt_id,
        prompt_reference=contract.prompt_reference,
        dependency_claim_ids=[str(row["claim_id"]) for row in request.dependency_claims],
        status="ADMITTED",
        result=to_primitive(research_bundle.module_result),
        registered_record_ids=[_record_id(item) for item in records],
        pce_statuses={},
        er_brb_statuses={},
    )
    return research_bundle, records, execution


def _detect_research_gaps(
    *,
    plan: BlockCResearchPlan,
    records: dict[str, list[Any]],
    registry: SharedBlockARegistry,
    iteration: int,
) -> list[BlockCResearchGap]:
    evidence_ids = {str(row["evidence_id"]) for row in registry.evidence}
    source_ids = {str(row["source_id"]) for row in registry.sources}
    findings = _latest_records(records["C1"])
    regulatory = _latest_records(records["C2"])
    integration = _latest_records(records["C3"])
    scenarios = _latest_records(records["C4"])
    gaps: list[BlockCResearchGap] = []
    covered = {item.workstream for item in findings}
    missing_workstreams = sorted(set(plan.selected_diligence_workstreams) - covered)
    if missing_workstreams:
        gaps.append(BlockCResearchGap(
            gap_id=f"GAP-C1-COVERAGE-I{iteration:02d}",
            gap_type=BlockCResearchGapType.EVIDENCE_MISSING,
            owning_module="C1",
            description=f"Selected diligence workstreams lack findings: {missing_workstreams}",
            required_action="Return only to C1 and register findings for the selected scope.",
            closure_test="Every selected workstream has a traceable finding and no unselected workstream is marked complete.",
            status="OPEN", created_iteration=iteration,
        ))
    unsupported_regulatory = [
        item.regulatory_risk_id for item in regulatory
        if not item.source_ids or not item.evidence_ids
        or not set(item.source_ids) <= source_ids or not set(item.evidence_ids) <= evidence_ids
    ]
    if unsupported_regulatory:
        gaps.append(BlockCResearchGap(
            gap_id=f"GAP-C2-EVIDENCE-I{iteration:02d}",
            gap_type=BlockCResearchGapType.EVIDENCE_MISSING,
            owning_module="C2",
            description=f"Regulatory risk records lack admitted Source/Evidence lineage: {unsupported_regulatory}",
            required_action="Return only to C2 for authoritative regulatory evidence; retain qualified-counsel review.",
            closure_test="Every material RegulatoryRisk references admitted Source and Evidence IDs without inventing a legal conclusion.",
            status="OPEN", created_iteration=iteration,
        ))
    unsupported_integration = [
        item.risk_id for item in integration
        if not set(item.source_ids) <= source_ids or not set(item.evidence_ids) <= evidence_ids
    ]
    if unsupported_integration:
        gaps.append(BlockCResearchGap(
            gap_id=f"GAP-C3-EVIDENCE-I{iteration:02d}",
            gap_type=BlockCResearchGapType.INTEGRATION_ASSUMPTION_UNSUPPORTED,
            owning_module="C3",
            description=f"Integration risk lacks independent evidence: {unsupported_integration}",
            required_action="Return only to C3; Strategic Fit is not integration-success evidence.",
            closure_test="Integration risk references admitted non-Strategic-Fit Source and Evidence IDs.",
            status="OPEN", created_iteration=iteration,
        ))
    incomplete_scenarios = [
        item.scenario_id for item in scenarios
        if not ((item.financial_inputs and item.resulting_metrics) or (not item.financial_inputs and item.limitations))
    ]
    if incomplete_scenarios:
        gaps.append(BlockCResearchGap(
            gap_id=f"GAP-C4-SCENARIO-I{iteration:02d}",
            gap_type=BlockCResearchGapType.DOWNSIDE_SCENARIO_INCOMPLETE,
            owning_module="C4",
            description=f"Downside scenarios are incomplete: {incomplete_scenarios}",
            required_action="Return only to C4 and quantify from registered inputs or retain a qualitative limitation.",
            closure_test="No downside percentage, probability or result is invented.",
            status="OPEN", created_iteration=iteration,
        ))
    return gaps


def _certify(case_id: str, registry: SharedBlockARegistry) -> dict[str, Any]:
    evidence_by_id = {row["evidence_id"]: row for row in registry.evidence}
    sources = [_source_model(row, "Block C shared Source Registry") for row in registry.sources]
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
    claims: list[Claim] = []
    for row in registry.claims:
        source_ids = sorted({
            evidence_by_id[item]["source_id"]
            for item in row.get("supporting_evidence_ids", []) if item in evidence_by_id
        })
        claims.append(Claim(
            claim_id=row["claim_id"], claim_text=row["claim_text"],
            business_module=row["owning_module"],
            evidence_ids=list(row["supporting_evidence_ids"]), source_ids=source_ids,
            human_review_required=bool(row["human_review_required"]),
            calculation_required=False, calculation_replayed=True,
            claim_class=row["claim_class"], materiality=row["materiality"],
            counterevidence_ids=list(row["counterevidence_ids"]),
        ))
    prechecks = [
        {"claim_id": claim.claim_id, **run_claim_pce_precheck(case_id=case_id, claim=claim, sources=sources, evidence=evidence)}
        for claim in claims
    ]
    result = run_business_certification(case_id=case_id, sources=sources, evidence=evidence, claims=claims)
    result["pce_prechecks"] = prechecks
    result["execution_order"] = [
        "frozen calculation replay validation", "PCE precheck", "ER/BRB",
        "final PCE delivery control", "Gate C", "controlled Decision State synthesis",
    ]
    registry.apply_certification(result)
    return result


def _latest_module_results(bundles: list[Any]) -> list[Any]:
    by_module: dict[str, Any] = {}
    for bundle in bundles:
        by_module[bundle.module_result.module_id] = bundle.module_result
    return [by_module[item] for item in BLOCK_C_ORDER if item in by_module]


def _upstream_reporting_objects(bundle: BlockCInputBundle) -> tuple[list[Source], list[Evidence], list[Claim]]:
    sources = [Source(**row) for row in bundle.sources]
    evidence = [Evidence(**{**row, "status": EvidenceStatus(row["status"])}) for row in bundle.evidence]
    claims = [
        Claim(**{**row, "pce_status": PCEStatus(row["pce_status"])})
        for row in [*bundle.admitted_strategic_claims, *bundle.admitted_financial_claims]
    ]
    return sources, evidence, claims


def _current_c_objects(registry: SharedBlockARegistry) -> tuple[list[Source], list[Evidence], list[Claim]]:
    source_models = [_source_model(row, "Block C shared Source Registry") for row in registry.sources]
    evidence_models = [
        Evidence(
            evidence_id=row["evidence_id"], claim_id=row["claim_id"], source_id=row["source_id"],
            extracted_fact=row["extracted_fact"], evidence_type=row["evidence_type"],
            confidence=row["strength"], status=EvidenceStatus.AVAILABLE,
            supports_claim=row["direction"] == "support",
            human_review_required="management" in row["evidence_type"].lower(),
            limitations=row.get("limitations", ""),
        ) for row in registry.evidence
    ]
    evidence_by_id = {row.evidence_id: row for row in evidence_models}
    claim_models = []
    for row in registry.claims:
        supporting = list(row.get("supporting_evidence_ids", []))
        claim_models.append(Claim(
            claim_id=row["claim_id"], claim_text=row["claim_text"], business_module=row["owning_module"],
            evidence_ids=supporting,
            source_ids=sorted({evidence_by_id[item].source_id for item in supporting if item in evidence_by_id}),
            pce_status=PCEStatus(row.get("pce_status", "Not Certified")),
            human_review_required=bool(row.get("human_review_required")),
            claim_class=row.get("claim_class", "evidence-supported inference"),
            materiality=row.get("materiality", "material"),
            calculation_required=False, calculation_replayed=True,
            counterevidence_ids=list(row.get("counterevidence_ids", [])),
            delivery_allowed=row.get("pce_status") in {"Certified", "Certified with Caveat"},
        ))
    return source_models, evidence_models, claim_models


def _gate_for_reporting(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "gate_id": row["gate_id"],
        "gate_name": row.get("gate_name", "Strategic Thesis Gate" if row["gate_id"] == "GATE_A" else "Value Creation Gate"),
        "block": row.get("block", "Block A: Strategic Thesis" if row["gate_id"] == "GATE_A" else "Block B: Value Creation and Pricing"),
        "status": row["status"],
        "criteria": row.get("criteria", []),
        "failed_criterion_ids": row.get("failed_criterion_ids", []),
        "conditions": row.get("conditions", []),
        "gap_ids": row.get("gap_ids", []),
        "pce_statuses": row.get("pce_statuses", {}),
        "er_brb_summary": row.get("er_brb_summary", {}),
        "calculation_replay_statuses": row.get("calculation_replay_statuses", {}),
        "human_review_items": row.get("human_review_items", []),
        "prior_gate_history": row.get("prior_gate_history", []),
        "business_reason": row.get("business_reason", f"Frozen validated {row['gate_id']} result."),
    }


def _write_outputs(
    *, output: Path, case_data: dict[str, Any], bundle: BlockCInputBundle,
    bundle_validation: dict[str, Any], plan: BlockCResearchPlan, attachments: list[Any],
    registry: SharedBlockARegistry, executions: list[BlockCModuleExecution],
    records: dict[str, list[Any]], gap_history: list[dict[str, Any]],
    certification: dict[str, Any], gates: list[Any], loops: list[dict[str, Any]],
    iterations: list[dict[str, Any]], human_reviews: list[dict[str, Any]],
    decision: Any, immutable_after: dict[str, Any], summary: dict[str, Any],
) -> None:
    write_json(output / "00_input" / "case.json", case_data)
    write_json(output / "00_input" / "block_c_input_bundle.json", bundle)
    write_json(output / "00_input" / "block_c_input_validation.json", bundle_validation)
    write_json(output / "00_input" / "block_c_research_plan.json", plan)
    write_json(output / "00_input" / "attachment_manifest.json", attachment_manifest_artifact(attachments))
    write_json(output / "00_input" / "upstream_integrity_after.json", immutable_after)
    write_json(output / "01_research" / "source_registry.json", registry.source_output())
    write_json(output / "01_research" / "evidence.json", registry.evidence)
    write_json(output / "01_research" / "claims.json", registry.claims)
    write_json(output / "01_research" / "assumptions.json", registry.assumptions)
    write_json(output / "01_research" / "unknowns.json", registry.unknowns)
    write_json(output / "01_research" / "counterevidence.json", registry.counterevidence)
    write_json(output / "02_modules" / "module_executions.json", executions)
    for module_id in BLOCK_C_ORDER:
        write_json(output / "02_modules" / f"{module_id.lower()}_executions.json", [item for item in executions if item.module_id == module_id])
    write_json(output / "03_risk_records" / "diligence_finding_history.json", records["C1"])
    write_json(output / "03_risk_records" / "regulatory_risk_history.json", records["C2"])
    write_json(output / "03_risk_records" / "integration_risk_history.json", records["C3"])
    write_json(output / "03_risk_records" / "downside_scenario_history.json", records["C4"])
    write_json(output / "03_risk_records" / "latest_diligence_findings.json", _latest_records(records["C1"]))
    write_json(output / "03_risk_records" / "latest_regulatory_risks.json", _latest_records(records["C2"]))
    write_json(output / "03_risk_records" / "latest_integration_risks.json", _latest_records(records["C3"]))
    write_json(output / "03_risk_records" / "latest_downside_scenarios.json", _latest_records(records["C4"]))
    write_json(output / "04_controls" / "pce_prechecks.json", certification.get("pce_prechecks", []))
    write_json(output / "04_controls" / "pce_results.json", certification.get("pce_result", {}))
    write_json(output / "04_controls" / "er_brb_results.json", certification.get("er_brb_results", []))
    write_json(output / "04_controls" / "certification_adapter_boundary.json", certification.get("adapter_boundary", {}))
    write_json(output / "04_controls" / "control_execution_order.json", certification.get("execution_order", []))
    write_json(output / "04_controls" / "human_review_items.json", human_reviews)
    write_json(output / "05_gate_c" / "gate_c_history.json", gates)
    write_json(output / "05_gate_c" / "gate_c_result.json", gates[-1])
    write_json(output / "05_gate_c" / "decision_state.json", decision)
    write_json(output / "09_loop" / "research_gap_history.json", gap_history)
    write_json(output / "09_loop" / "unified_loop_events.json", loops)
    write_json(output / "09_loop" / "iteration_records.json", iterations)
    write_json(output / "09_loop" / "memory_state.json", {
        "append_only": True,
        "gate_a_history_unchanged": immutable_after["gate_a_history_unchanged"],
        "gate_b_history_unchanged": immutable_after["gate_b_history_unchanged"],
        "block_c_module_result_versions": {module_id: [item.version for item in executions if item.module_id == module_id] for module_id in BLOCK_C_ORDER},
        "gate_c_result_count": len(gates),
        "gap_history_count": len(gap_history),
    })
    write_json(output / "run_summary.json", summary)


def run_block_c_case(
    case_path: Path,
    output_dir: Path | None = None,
    *,
    provider: str | ProviderMode | None = None,
    module: str = "BLOCK_C",
    enable_live: bool = False,
) -> BlockCRunResult:
    case_path = case_path.resolve()
    case_data = load_case(case_path)
    bundle, bundle_validation = _validate_case(case_data)
    if module != "BLOCK_C":
        raise ProviderConfigurationError("Complete Milestone 8 execution requires --module BLOCK_C")
    mode = _provider_mode(provider, case_data)
    if mode == ProviderMode.OPENAI_LIVE:
        check = check_block_c_configuration(case_path, provider=mode, module=module, output_dir=output_dir, enable_live=enable_live)
        if not check["ready"]:
            raise ProviderConfigurationError("; ".join(check["issues"]))
    output = (output_dir or case_path.parent / "run_output").resolve()
    if not output_directory_is_writable(output):
        raise ProviderConfigurationError(f"Output directory is not writable: {output}")
    plan = build_block_c_research_plan(case_data, bundle)
    mandate = BusinessMandate.from_dict(bundle.mandate_reference)
    attachments, blocked = prepare_attachments(
        case_dir=case_path.parent, manifest=case_data["research"]["attachments"], provider_mode=mode,
    )
    if mode == ProviderMode.OPENAI_LIVE and blocked:
        raise ProviderConfigurationError("; ".join(item["reason"] for item in blocked))
    recording = _recording_path(case_path, case_data) if mode != ProviderMode.OPENAI_LIVE else None
    contracts = {item.module_id: item for item in load_module_contracts() if item.module_id in BLOCK_C_ORDER}
    registry = SharedBlockARegistry()
    bundles: list[Any] = []
    executions: list[BlockCModuleExecution] = []
    records: dict[str, list[Any]] = {module_id: [] for module_id in BLOCK_C_ORDER}
    versions = {module_id: 0 for module_id in BLOCK_C_ORDER}
    upstream_gate_fingerprint = canonical_artifact_hash({
        "gate_a_history": bundle.gate_a_history,
        "gate_b_history": bundle.gate_b_history,
    })

    for module_id in BLOCK_C_ORDER:
        versions[module_id] += 1
        research_bundle, new_records, execution = _execute_module(
            case_data=case_data, bundle=bundle, plan=plan, contract=contracts[module_id],
            registry=registry, mode=mode, recording_path=recording, attachments=attachments,
            iteration=1, version=versions[module_id], open_gaps=[], output=output,
        )
        bundles.append(research_bundle)
        records[module_id].extend(new_records)
        executions.append(execution)

    active_gaps = _detect_research_gaps(plan=plan, records=records, registry=registry, iteration=1)
    certification = _certify(bundle.case_id, registry)
    human_reviews = [
        *[dict(item) for item in bundle.human_review_items],
        *[dict(item) for item in case_data["research"].get("human_review_items", [])],
    ]
    gate = evaluate_block_c_gate(
        module_results=_latest_module_results(bundles),
        findings=_latest_records(records["C1"]),
        regulatory_risks=_latest_records(records["C2"]),
        integration_risks=_latest_records(records["C3"]),
        downside_scenarios=_latest_records(records["C4"]),
        input_bundle=bundle, mandate=mandate, registry=registry, certification=certification,
        research_gaps=active_gaps, human_review_items=human_reviews,
    )
    gates = [gate]
    gap_history = [
        {**to_primitive(item), "status": "OPEN", "created_iteration": 1, "resolved_iteration": None}
        for item in active_gaps
    ]
    iterations = [{
        "iteration": 1,
        "modules_executed": list(BLOCK_C_ORDER),
        "block_a_modules_executed": [],
        "block_b_modules_executed": [],
        "gate_c_status": gate.status.value,
        "gap_ids": [item.gap_id for item in active_gaps],
        "change_summary": "Initial C1-C5 research, frozen replay validation, PCE, ER/BRB and Gate C completed.",
    }]
    loops: list[dict[str, Any]] = []

    if gate.status.value not in {"PASS", "CONDITIONAL_PASS", "RENEGOTIATE"}:
        if not active_gaps:
            raise ProviderConfigurationError("Gate C failed without a research Gap that can enter the targeted loop")
        loop = enter_unified_loop(gate, 1)
        responsible = active_gaps[0].owning_module
        repair_modules = [responsible, *dependent_block_c_modules(responsible)]
        repair_modules = [item for item in BLOCK_C_ORDER if item in set(repair_modules)]
        loop["loop_controller"]["return_modules"] = repair_modules
        loop["replan"]["return_modules"] = repair_modules
        loop["replan"]["invalidated_modules"] = repair_modules
        loop["replan"]["block_a_modules"] = []
        loop["replan"]["block_b_modules"] = []
        loops.append(loop)
        if int(plan.repair_budget["maximum_repair_iterations"]) < 1:
            raise ProviderConfigurationError("Block C repair budget is exhausted")
        for module_id in repair_modules:
            versions[module_id] += 1
            research_bundle, new_records, execution = _execute_module(
                case_data=case_data, bundle=bundle, plan=plan, contract=contracts[module_id],
                registry=registry, mode=mode, recording_path=recording, attachments=attachments,
                iteration=2, version=versions[module_id],
                open_gaps=[to_primitive(item) for item in active_gaps if item.owning_module == responsible],
                output=output,
            )
            execution.invalidated_by = [responsible] if module_id != responsible else []
            bundles.append(research_bundle)
            records[module_id].extend(new_records)
            executions.append(execution)
        new_gaps = _detect_research_gaps(plan=plan, records=records, registry=registry, iteration=2)
        unresolved_keys = {(item.gap_type.value, item.owning_module) for item in new_gaps}
        for row in gap_history:
            if (row["gap_type"], row["owning_module"]) not in unresolved_keys:
                row["status"] = "RESOLVED"
                row["resolved_iteration"] = 2
        active_gaps = new_gaps
        gap_history.extend({**to_primitive(item), "status": "OPEN", "created_iteration": 2, "resolved_iteration": None} for item in new_gaps)
        certification = _certify(bundle.case_id, registry)
        final_gate = evaluate_block_c_gate(
            module_results=_latest_module_results(bundles),
            findings=_latest_records(records["C1"]),
            regulatory_risks=_latest_records(records["C2"]),
            integration_risks=_latest_records(records["C3"]),
            downside_scenarios=_latest_records(records["C4"]),
            input_bundle=bundle, mandate=mandate, registry=registry, certification=certification,
            research_gaps=active_gaps, human_review_items=human_reviews,
        )
        gates.append(final_gate)
        iterations.append({
            "iteration": 2,
            "modules_executed": repair_modules,
            "block_a_modules_executed": [],
            "block_b_modules_executed": [],
            "gate_c_status": final_gate.status.value,
            "gap_ids": [item.gap_id for item in active_gaps],
            "change_summary": f"Targeted repair returned to {responsible}; only dependent Block C modules were invalidated.",
        })

    final_gate = gates[-1]
    decision = synthesize_decision_state(
        case_id=bundle.case_id, mandate=mandate, input_bundle=bundle, gate_c=final_gate,
        research_gaps=active_gaps, human_review_items=human_reviews,
    )
    latest_results = _latest_module_results(bundles)
    c5 = next(item for item in latest_results if item.module_id == "C5")
    c5.structured_output = {
        **c5.structured_output,
        "decision_state": [decision.state.value],
        "rationale": list(decision.rationale),
        "conditions": list(decision.conditions),
        "walk_away_triggers": list(decision.walk_away_triggers),
        "authority_boundary": [decision.authority_boundary],
        "controlled_synthesis": True,
        "provider_selected_decision_state": False,
    }
    c5.business_conclusion = (
        f"Controlled synthesis produced {decision.state.value}; price and return conditions prevent proceeding at the current terms. "
        "This is machine decision support, not final human transaction approval."
    )
    current_fingerprint = canonical_artifact_hash({
        "gate_a_history": bundle.gate_a_history,
        "gate_b_history": bundle.gate_b_history,
    })
    immutable_after = {
        "initial_gate_history_fingerprint": upstream_gate_fingerprint,
        "final_gate_history_fingerprint": current_fingerprint,
        "gate_a_history_unchanged": bundle.gate_a_history == case_data["block_c_input_bundle"]["gate_a_history"],
        "gate_b_history_unchanged": bundle.gate_b_history == case_data["block_c_input_bundle"]["gate_b_history"],
        "fingerprint_unchanged": current_fingerprint == upstream_gate_fingerprint,
        "block_a_research_executed": False,
        "block_b_research_executed": False,
    }
    if not all((immutable_after["gate_a_history_unchanged"], immutable_after["gate_b_history_unchanged"], immutable_after["fingerprint_unchanged"])):
        raise ProviderConfigurationError("Gate A or Gate B history changed during Block C")

    upstream_sources, upstream_evidence, upstream_claims = _upstream_reporting_objects(bundle)
    c_sources, c_evidence, c_claims = _current_c_objects(registry)
    report_case_data = {
        **case_data,
        "mandate": bundle.mandate_reference,
        "human_review_items": human_reviews,
    }
    gate_a_report = _gate_for_reporting(bundle.gate_a_history[-1])
    gate_b_report = _gate_for_reporting(bundle.gate_b_history[-1])
    reporting_package = generate_reporting_package(
        output_dir=output,
        case_data=report_case_data,
        mandate=mandate,
        module_results=[*bundle.upstream_module_results, *latest_results],
        sources=[*upstream_sources, *c_sources],
        evidence=[*upstream_evidence, *c_evidence],
        claims=[*upstream_claims, *c_claims],
        assumptions=[*bundle.assumptions, *registry.assumptions],
        unknowns=[*bundle.unknowns, *registry.unknowns],
        counterevidence=[*bundle.counterevidence, *registry.counterevidence],
        calculations=bundle.calculations,
        replays=bundle.calculation_replays,
        calculation_gaps=bundle.open_calculation_gaps,
        research_gaps=[to_primitive(item) for item in active_gaps],
        gates=[gate_a_report, gate_b_report, final_gate],
        gate_histories={"GATE_A": bundle.gate_a_history, "GATE_B": bundle.gate_b_history, "GATE_C": [to_primitive(item) for item in gates]},
        decision=decision,
        certification=certification,
        block_c_records={
            "C1": _latest_records(records["C1"]),
            "C2": _latest_records(records["C2"]),
            "C3": _latest_records(records["C3"]),
            "C4": _latest_records(records["C4"]),
        },
    )
    terminal = to_primitive(reporting_package["terminal_state"])
    summary = {
        "schema_version": "milestone-8-block-c",
        "case_id": bundle.case_id,
        "provider_mode": mode.value,
        "modules_executed": [item.module_id for item in executions],
        "module_execution_count": len(executions),
        "iterations": len(iterations),
        "initial_gate_c_status": gates[0].status.value,
        "final_gate_c_status": final_gate.status.value,
        "final_decision_state": decision.state.value,
        "selected_diligence_workstreams": list(plan.selected_diligence_workstreams),
        "block_a_research_executed": False,
        "block_b_research_executed": False,
        "gate_a_history_unchanged": True,
        "gate_b_history_unchanged": True,
        "report_generated": reporting_package["report_path"].is_file(),
        "delivery_outcome": reporting_package["verification"]["delivery_outcome"],
        "decision_state_is_final_human_approval": False,
        "output_dir": str(output),
    }
    _write_outputs(
        output=output, case_data=case_data, bundle=bundle, bundle_validation=bundle_validation,
        plan=plan, attachments=attachments, registry=registry, executions=executions,
        records=records, gap_history=gap_history, certification=certification, gates=gates,
        loops=loops, iterations=iterations, human_reviews=human_reviews, decision=decision,
        immutable_after=immutable_after, summary=summary,
    )
    try:
        outcome = BlockCOutcome(final_gate.status.value)
    except ValueError:
        outcome = BlockCOutcome.FAILED_TECHNICAL
    return BlockCRunResult(
        case_id=bundle.case_id, provider_mode=mode, outcome=outcome,
        output_dir=str(output), iterations=len(iterations), module_executions=len(executions),
        gate_c_result=to_primitive(final_gate), decision_state=to_primitive(decision),
        delivery_outcome=to_primitive(reporting_package["verification"]["delivery_outcome"]),
        terminal_state=terminal,
    )
