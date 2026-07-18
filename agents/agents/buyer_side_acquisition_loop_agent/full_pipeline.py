from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from .block_a_runtime import run_block_a_case
from .block_b_runtime import run_block_b_case
from .block_c_runtime import canonical_artifact_hash, run_block_c_case
from .live_research_models import ProviderConfigurationError, ProviderMode
from .live_research_provider import check_openai_live_configuration
from .pipeline_models import (
    BLOCK_B_HASHED_FIELDS,
    RC_SCHEMA_VERSION,
    canonical_sha256,
    validate_block_b_input_bundle,
)
from .storage import load_case, write_json


PIPELINE_STAGES = ("BLOCK_A", "BLOCK_B", "BLOCK_C", "REPORTING")
REQUIRED_MANDATE_FIELDS = (
    "mandate_id", "case_id", "perspective", "buyer_name", "target_name",
    "transaction_type", "process_stage", "decision_question",
    "strategic_objectives", "hard_constraints", "currency", "unit",
    "as_of_date", "maximum_equity_purchase_price", "minimum_roic",
    "minimum_irr", "maximum_pro_forma_leverage",
    "minimum_closing_liquidity", "selected_diligence_workstreams",
    "required_reviewer_roles", "authority_limit", "buyer_strategic_need",
)
REQUIRED_TEMPLATE_FIELDS = ("block_a_case", "block_b_case", "block_c_case")
BUSINESS_MANDATE_FIELDS = (
    "mandate_id", "case_id", "perspective", "buyer_name", "target_name",
    "transaction_type", "process_stage", "decision_question",
    "strategic_objectives", "hard_constraints", "currency", "unit",
    "as_of_date", "maximum_equity_purchase_price", "minimum_roic",
    "minimum_irr", "maximum_pro_forma_leverage", "minimum_closing_liquidity",
    "selected_diligence_workstreams", "required_reviewer_roles", "authority_limit",
)
TOP_LEVEL_ARTIFACTS = {
    "gate_a_result.json": "stages/block_a/gate_a/gate_a_result.json",
    "gate_b_result.json": "stages/block_b/06_gate_b/gate_b_result.json",
    "gate_c_result.json": "stages/block_c/05_gate_c/gate_c_result.json",
    "decision_state.json": "stages/block_c/05_gate_c/decision_state.json",
    "final_acquisition_strategy_report.md": "stages/block_c/reporting/final_acquisition_strategy_report.md",
    "final_delivery_verification.json": "stages/block_c/reporting/final_delivery_verification.json",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _business_mandate(case_data: dict[str, Any]) -> dict[str, Any]:
    return {name: copy.deepcopy(case_data["mandate"][name]) for name in BUSINESS_MANDATE_FIELDS}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_relative(base: Path, value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise ProviderConfigurationError(f"{label} must be repository-relative")
    resolved = (base / path).resolve()
    if not resolved.is_file():
        raise ProviderConfigurationError(f"{label} does not exist: {value}")
    return resolved


def check_full_pipeline_case(case_path: Path) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    data: dict[str, Any] = {}
    try:
        case_path = case_path.resolve()
        data = load_case(case_path)
        if data.get("schema_version") != RC_SCHEMA_VERSION:
            issues.append(f"schema_version must be {RC_SCHEMA_VERSION}")
        for field in ("case_id", "run_id", "as_of_date", "mandate", "research_contract", "templates", "provider"):
            if data.get(field) in (None, "", [], {}):
                issues.append(f"Missing required field: {field}")
        mandate = data.get("mandate", {})
        for field in REQUIRED_MANDATE_FIELDS:
            if mandate.get(field) in (None, "", [], {}):
                issues.append(f"Missing required field: mandate.{field}")
        if mandate and data.get("case_id") and mandate.get("case_id") != data.get("case_id"):
            issues.append("mandate.case_id does not match case_id")
        if mandate and data.get("as_of_date") and mandate.get("as_of_date") != data.get("as_of_date"):
            issues.append("mandate.as_of_date does not match as_of_date")
        contract = data.get("research_contract", {})
        for field in ("contract_id", "case_id", "scope", "source_policy", "unknown_policy", "calculation_policy", "delivery_policy"):
            if contract.get(field) in (None, "", [], {}):
                issues.append(f"Missing required field: research_contract.{field}")
        if contract and data.get("case_id") and contract.get("case_id") != data.get("case_id"):
            issues.append("research_contract.case_id does not match case_id")
        templates = data.get("templates", {})
        for field in REQUIRED_TEMPLATE_FIELDS:
            value = templates.get(field)
            if not value:
                issues.append(f"Missing required field: templates.{field}")
            else:
                try:
                    _resolve_relative(case_path.parent, str(value), f"templates.{field}")
                except ProviderConfigurationError as exc:
                    issues.append(str(exc))
        mode = data.get("provider", {}).get("mode")
        if mode not in {ProviderMode.RECORDED.value, ProviderMode.OPENAI_LIVE.value}:
            issues.append("provider.mode must be recorded or openai_live")
        if mode == ProviderMode.RECORDED.value:
            warnings.append("Recorded provider responses are deterministic fixtures, not current live research.")
        if data.get("confidentiality", {}).get("contains_confidential_information"):
            warnings.append("Case is marked confidential; provider and attachment permissions require Human Review.")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues.append(str(exc))
    status = "NOT_READY" if issues else ("READY_WITH_WARNINGS" if warnings else "READY")
    return {"status": status, "ready": not issues, "issues": issues, "warnings": warnings, "paid_request_made": False}


def check_full_pipeline_configuration(case_path: Path, *, enable_live: bool = False) -> dict[str, Any]:
    check = check_full_pipeline_case(case_path)
    if not check["ready"]:
        return {**check, "live_execution_enabled": False}
    data = load_case(case_path.resolve())
    if data["provider"]["mode"] != ProviderMode.OPENAI_LIVE.value:
        return {**check, "live_execution_enabled": False}
    issues = list(check["issues"])
    live = check_openai_live_configuration()
    issues.extend(live["issues"])
    if not data.get("provider", {}).get("allow_live_requests", False):
        issues.append("provider.allow_live_requests must be true for a live full-pipeline run")
    if not enable_live:
        issues.append("Paid live execution is disabled; pass --enable-live explicitly after configuration succeeds.")
    return {
        **check,
        "status": "NOT_READY" if issues else check["status"],
        "ready": not issues,
        "issues": list(dict.fromkeys(issues)),
        "live_execution_enabled": bool(enable_live and not issues),
        "paid_request_made": False,
    }


def _copy_case_asset(source: Path, case_dir: Path, category: str, name: str | None = None) -> str:
    destination_dir = case_dir / category
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / (name or source.name)
    shutil.copy2(source, destination)
    return destination.relative_to(case_dir).as_posix()


def _prepare_stage_case(
    *, template_path: Path, stage_case_dir: Path, mode: str, case_data: dict[str, Any]
) -> tuple[dict[str, Any], Path]:
    template = load_case(template_path)
    stage_case_dir.mkdir(parents=True, exist_ok=True)
    template["case_id"] = case_data["case_id"]
    template["run_id"] = case_data["run_id"]
    template["as_of_date"] = case_data["as_of_date"]
    template["provider"]["mode"] = mode
    recording_key = "recording_path" if "recording_path" in template["provider"] else "recording"
    if mode == ProviderMode.RECORDED.value:
        source = _resolve_relative(template_path.parent, template["provider"][recording_key], "provider recording")
        template["provider"][recording_key] = _copy_case_asset(source, stage_case_dir, "recordings", "responses.json")
    for attachment in template.get("research", {}).get("attachments", []):
        source = _resolve_relative(template_path.parent, attachment["path"], f"attachment {attachment.get('attachment_id', '')}")
        attachment["path"] = _copy_case_asset(source, stage_case_dir, "attachments")
    return template, stage_case_dir / "case.json"


def _gate_history(rows: list[dict[str, Any]], *, case_id: str, gate_id: str, provenance: str) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for index, original in enumerate(rows, start=1):
        row = copy.deepcopy(original)
        row["case_id"] = case_id
        row["gate_id"] = gate_id
        row["version"] = index
        row["provenance"] = provenance
        row.setdefault("conditions", [])
        if gate_id == "GATE_A":
            row.setdefault("criteria", row.get("criterion_results", []))
            row.setdefault("failed_criterion_ids", row.get("failed_criteria", []))
            row.setdefault("business_reason", row.get("authority_boundary", "Deterministic Gate A result."))
        row["artifact_hash"] = canonical_sha256({key: value for key, value in row.items() if key != "artifact_hash"})
        history.append(row)
    return history


def _latest_claim_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    superseded = {str(row.get("supersedes_claim_id")) for row in rows if row.get("supersedes_claim_id")}
    return [row for row in rows if str(row.get("claim_id")) not in superseded]


def _normalise_sources(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        source_id = str(row["source_id"])
        output[source_id] = {
            "source_id": source_id,
            "source_name": str(row.get("page_title") or row.get("original_filename") or source_id),
            "source_type": str(row.get("source_type") or "registered source"),
            "url_or_file": str(row.get("url") or row.get("original_filename") or f"registered:{source_id}"),
            "used_for": ", ".join(sorted({str(item.get("module_name") or item.get("owning_module")) for item in row.get("module_uses", []) if item})) or "acquisition analysis",
            "reliability_tier": str(row.get("source_tier") or "registered source"),
            "pce_eligible": bool(row.get("pce_eligible")),
            "source_replay_status": "completed",
            "limitations": str(row.get("limitations") or ""),
        }
    return list(output.values())


def _normalise_evidence(rows: list[dict[str, Any]], claim_ids: set[str]) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": str(row["evidence_id"]),
            "claim_id": str(row["claim_id"]),
            "source_id": str(row["source_id"]),
            "extracted_fact": str(row["extracted_fact"]),
            "evidence_type": str(row.get("evidence_type") or "registered evidence"),
            "confidence": str(row.get("strength") or "medium"),
            "status": "AVAILABLE",
            "supports_claim": row.get("direction", "support") == "support",
            "human_review_required": "management" in str(row.get("evidence_type", "")).lower(),
            "limitations": str(row.get("limitations") or ""),
        }
        for row in rows if str(row.get("claim_id")) in claim_ids
    ]


def _normalise_claims(
    rows: list[dict[str, Any]], evidence: list[dict[str, Any]], calculations: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    evidence_source = {row["evidence_id"]: row["source_id"] for row in evidence}
    calculations = calculations or []
    calc_by_claim: dict[str, list[str]] = {}
    for calculation in calculations:
        for claim_id in calculation.get("linked_claim_ids", []):
            calc_by_claim.setdefault(str(claim_id), []).append(str(calculation["calculation_id"]))
    output = []
    for row in _latest_claim_rows(rows):
        evidence_ids = [str(value) for value in row.get("supporting_evidence_ids", []) if value in evidence_source]
        calculation_ids = calc_by_claim.get(str(row["claim_id"]), [])
        pce_status = str(row.get("pce_status") or "Not Certified")
        output.append({
            "claim_id": str(row["claim_id"]),
            "claim_text": str(row["claim_text"]),
            "business_module": str(row.get("owning_module") or row.get("owning_module_id") or "Acquisition analysis"),
            "evidence_ids": evidence_ids,
            "source_ids": sorted({evidence_source[item] for item in evidence_ids}),
            "pce_status": pce_status,
            "human_review_required": bool(row.get("human_review_required")),
            "claim_class": str(row.get("claim_class") or "evidence-supported inference"),
            "materiality": str(row.get("materiality") or "material"),
            "calculation_required": bool(calculation_ids),
            "calculation_replayed": bool(calculation_ids),
            "calculation_ids": calculation_ids,
            "counterevidence_ids": list(row.get("counterevidence_ids", [])),
            "delivery_allowed": pce_status in {"Certified", "Certified with Caveat"},
        })
    return output


def _module_results(block_a: Path, block_b: Path) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for module_id, slug in (
        ("A1", "a1_transaction_context"), ("A2", "a2_buyer_strategic_need"),
        ("A3", "a3_strategic_rationale"), ("A4", "a4_target_attractiveness"),
        ("A5", "a5_target_capability_business_quality"),
        ("A6", "a6_industry_competitive_position"), ("A7", "a7_strategic_fit"),
    ):
        row = _read_json(block_a / "modules" / f"{slug}.json")["final_result"]
        output.append({
            "module_id": module_id, "professional_name": row["module_name"],
            "business_conclusion": row["business_conclusion"], "claim_ids": row.get("claim_ids", []),
            "supporting_evidence_ids": row.get("evidence_ids", []), "counterevidence_ids": row.get("counterevidence_ids", []),
            "calculation_ids": [], "assumptions": row.get("assumption_ids", []), "unknowns": row.get("unknown_ids", []),
            "limitations": row.get("limitations", []), "facts": row.get("facts", []), "inferences": row.get("inferences", []),
            "structured_output": row.get("structured_output", {}),
        })
    executions = _read_json(block_b / "02_modules" / "module_executions.json")
    by_module: dict[str, dict[str, Any]] = {}
    for execution in executions:
        by_module[execution["module_id"]] = execution["result"]
    output.extend(by_module[module_id] for module_id in ("B1", "B2", "B3", "B4", "B5"))
    return output


def _review_for_block_b(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_id": str(row.get("review_id") or row.get("human_review_item_id")),
        "owning_module": str(row.get("owning_module") or row.get("originating_module") or "A5"),
        "issue_type": str(row.get("issue_type") or "UPSTREAM_HUMAN_REVIEW"),
        "issue_description": str(row.get("issue_description") or row.get("description") or row.get("issue")),
        "required_reviewer_role": str(row.get("required_reviewer_role") or row.get("required_role") or "authorized reviewer"),
        "blocking": bool(row.get("blocking", False)),
        "status": str(row.get("status") or "OPEN"),
    }


def _review_for_block_c(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_id": str(row.get("review_id") or row.get("human_review_item_id")),
        "owning_module": str(row.get("owning_module") or row.get("originating_module") or "B4"),
        "issue": str(row.get("issue") or row.get("issue_description") or row.get("description")),
        "required_reviewer_role": str(row.get("required_reviewer_role") or row.get("required_role") or "authorized reviewer"),
        "blocking": bool(row.get("blocking", False)),
        "delivery_blocking": bool(row.get("delivery_blocking", False)),
        "status": str(row.get("status") or "OPEN"),
        "decision_impact": str(row.get("decision_impact") or "Authorized Human Review remains required; no transaction approval is granted."),
    }


def _build_block_b_bundle(case_data: dict[str, Any], block_a: Path) -> dict[str, Any]:
    gate_payload = _read_json(block_a / "gate_a" / "gate_a_result.json")
    gate_history = _gate_history(
        gate_payload["history"], case_id=case_data["case_id"], gate_id="GATE_A",
        provenance="stages/block_a/gate_a/gate_a_result.json",
    )
    claim_rows = _read_json(block_a / "research" / "claims.json")
    latest_ids = {row["claim_id"] for row in _latest_claim_rows(claim_rows)}
    evidence = _normalise_evidence(_read_json(block_a / "research" / "evidence.json"), latest_ids)
    bundle = {
        "schema_version": RC_SCHEMA_VERSION, "case_id": case_data["case_id"],
        "run_id": case_data["run_id"], "as_of_date": case_data["as_of_date"],
        "mandate_reference": _business_mandate(case_data), "research_contract_reference": case_data["research_contract"],
        "gate_a_history": gate_history,
        "admitted_claims": _normalise_claims(claim_rows, evidence),
        "sources": _normalise_sources(_read_json(block_a / "research" / "sources.json")),
        "evidence": evidence,
        "assumptions": _read_json(block_a / "research" / "assumptions.json"),
        "unknowns": _read_json(block_a / "research" / "unknowns.json"),
        "counterevidence": _read_json(block_a / "research" / "counterevidence.json"),
        "open_research_gaps": [row for row in _read_json(block_a / "loop" / "gaps.json") if row.get("status") == "OPEN"],
        "human_review_items": gate_history[-1].get("human_review_items", []),
        "mandate_constraints": {key: case_data["mandate"][key] for key in (
            "maximum_equity_purchase_price", "minimum_roic", "minimum_irr",
            "maximum_pro_forma_leverage", "minimum_closing_liquidity")},
        "provenance": {"producer": "actual Block A runtime", "stage": "BLOCK_A", "append_only": True},
        "artifact_references": {
            "gate_a": "stages/block_a/gate_a/gate_a_result.json",
            "claims": "stages/block_a/research/claims.json",
            "sources": "stages/block_a/research/sources.json",
            "evidence": "stages/block_a/research/evidence.json",
        },
        "artifact_hashes": {},
    }
    bundle["artifact_hashes"] = {name: canonical_sha256(bundle[name]) for name in BLOCK_B_HASHED_FIELDS}
    validate_block_b_input_bundle(bundle, case_id=case_data["case_id"], run_id=case_data["run_id"], as_of_date=case_data["as_of_date"])
    return bundle


def _build_block_c_bundle(case_data: dict[str, Any], block_a: Path, block_b: Path) -> dict[str, Any]:
    b_bundle = _build_block_b_bundle(case_data, block_a)
    gate_b_rows = _read_json(block_b / "06_gate_b" / "gate_b_history.json")
    gate_b_history = _gate_history(
        gate_b_rows, case_id=case_data["case_id"], gate_id="GATE_B",
        provenance="stages/block_b/06_gate_b/gate_b_history.json",
    )
    b_claim_rows = _read_json(block_b / "01_research" / "claims.json")
    b_latest_ids = {row["claim_id"] for row in _latest_claim_rows(b_claim_rows)}
    b_evidence = _normalise_evidence(_read_json(block_b / "01_research" / "evidence.json"), b_latest_ids)
    calculations = _read_json(block_b / "04_calculations" / "calculations.json")
    replays = _read_json(block_b / "04_calculations" / "calculation_replays.json")
    b_claims = _normalise_claims(b_claim_rows, b_evidence, calculations)
    sources = [*b_bundle["sources"], *_normalise_sources(_read_json(block_b / "01_research" / "source_registry.json"))]
    source_by_id = {row["source_id"]: row for row in sources}
    evidence = [*b_bundle["evidence"], *b_evidence]
    bundle = {
        "case_id": case_data["case_id"],
        "mandate_reference": _business_mandate(case_data),
        "research_contract_reference": case_data["research_contract"],
        "gate_a_history": b_bundle["gate_a_history"], "gate_b_history": gate_b_history,
        "admitted_strategic_claims": b_bundle["admitted_claims"], "admitted_financial_claims": b_claims,
        "sources": list(source_by_id.values()), "evidence": evidence,
        "assumptions": [*b_bundle["assumptions"], *_read_json(block_b / "01_research" / "assumptions.json")],
        "unknowns": [*b_bundle["unknowns"], *_read_json(block_b / "01_research" / "unknowns.json")],
        "counterevidence": [*b_bundle["counterevidence"], *_read_json(block_b / "01_research" / "counterevidence.json")],
        "calculations": calculations, "calculation_replays": replays,
        "open_research_gaps": [],
        "open_calculation_gaps": [row for row in _read_json(block_b / "04_calculations" / "calculation_gap_history.json") if row.get("status") == "OPEN"],
        "human_review_items": [_review_for_block_c(row) for row in _read_json(block_b / "05_controls" / "human_review_items.json")],
        "price_constraints": {"maximum_equity_purchase_price": case_data["mandate"]["maximum_equity_purchase_price"]},
        "financing_constraints": {
            "maximum_pro_forma_leverage": case_data["mandate"]["maximum_pro_forma_leverage"],
            "minimum_closing_liquidity": case_data["mandate"]["minimum_closing_liquidity"],
        },
        "return_thresholds": {"minimum_roic": case_data["mandate"]["minimum_roic"], "minimum_irr": case_data["mandate"]["minimum_irr"]},
        "transaction_jurisdictions": list(case_data["jurisdictions"]),
        "transaction_stage": case_data["mandate"]["process_stage"],
        "upstream_module_results": _module_results(block_a, block_b),
        "provenance": {"bundle_id": f"BCIB-{case_data['run_id']}", "producer": "actual Block A and Block B runtimes", "immutability_policy": "Gate histories and hashed upstream artifacts are append-only."},
        "artifact_hashes": {}, "schema_version": RC_SCHEMA_VERSION,
        "run_id": case_data["run_id"], "as_of_date": case_data["as_of_date"],
        "artifact_references": {
            "gate_a": "stages/block_a/gate_a/gate_a_result.json", "gate_b": "stages/block_b/06_gate_b/gate_b_result.json",
            "calculations": "stages/block_b/04_calculations/calculations.json", "replays": "stages/block_b/04_calculations/calculation_replays.json",
        },
    }
    for name in (
        "mandate_reference", "research_contract_reference", "gate_a_history", "gate_b_history",
        "admitted_strategic_claims", "admitted_financial_claims", "calculations", "calculation_replays",
    ):
        bundle["artifact_hashes"][name] = canonical_artifact_hash(bundle[name])
    return bundle


def _manifest_artifacts(output: Path, completed_stages: list[str]) -> list[dict[str, Any]]:
    allowed_roots = {"BLOCK_A": output / "stages" / "block_a", "BLOCK_B": output / "stages" / "block_b", "BLOCK_C": output / "stages" / "block_c"}
    paths: list[Path] = []
    for stage in completed_stages:
        root = allowed_roots.get(stage)
        if root and root.exists():
            paths.extend(path for path in root.rglob("*") if path.is_file())
    if "REPORTING" in completed_stages:
        paths.extend(path for path in output.iterdir() if path.is_file() and path.name != "run_manifest.json")
    return [
        {"path": path.relative_to(output).as_posix(), "sha256": _file_sha256(path), "bytes": path.stat().st_size}
        for path in sorted(set(paths))
    ]


def _write_manifest(output: Path, case_path: Path, case_data: dict[str, Any], completed_stages: list[str]) -> dict[str, Any]:
    manifest = {
        "schema_version": RC_SCHEMA_VERSION, "case_id": case_data["case_id"], "run_id": case_data["run_id"],
        "as_of_date": case_data["as_of_date"], "completed_stages": completed_stages,
        "next_stage": next((stage for stage in PIPELINE_STAGES if stage not in completed_stages), "COMPLETE"),
        "case_input": Path(os.path.relpath(case_path, output)).as_posix(),
        "artifacts": _manifest_artifacts(output, completed_stages),
        "append_only_gate_histories": True,
    }
    write_json(output / "run_manifest.json", manifest)
    return manifest


def validate_run_manifest(output: Path) -> dict[str, Any]:
    manifest_path = output / "run_manifest.json"
    if not manifest_path.is_file():
        raise ProviderConfigurationError("Run manifest is missing")
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != RC_SCHEMA_VERSION:
        raise ProviderConfigurationError("Unsupported run manifest schema")
    for artifact in manifest.get("artifacts", []):
        relative = Path(str(artifact.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            raise ProviderConfigurationError("Run manifest contains an unsafe artifact path")
        path = output / relative
        if not path.is_file() or _file_sha256(path) != artifact.get("sha256"):
            raise ProviderConfigurationError(f"Run artifact was altered or is missing: {relative.as_posix()}")
    return manifest


def _cross_block_consistency(output: Path, case_data: dict[str, Any]) -> dict[str, Any]:
    gate_a = _read_json(output / "gate_a_result.json")["final_result"]
    gate_b = _read_json(output / "gate_b_result.json")
    gate_c = _read_json(output / "gate_c_result.json")
    decision = _read_json(output / "decision_state.json")
    replays = _read_json(output / "stages" / "block_b" / "04_calculations" / "calculation_replays.json")
    checks = {
        "case_id_consistent": all(value == case_data["case_id"] for value in (
            _read_json(output / "stages" / "block_a" / "run_summary.json")["case_id"],
            _read_json(output / "stages" / "block_b" / "run_summary.json")["case_id"],
            _read_json(output / "stages" / "block_c" / "run_summary.json")["case_id"],
        )),
        "gate_a_allows_block_b": gate_a["status"] in {"PASS", "CONDITIONAL_PASS"},
        "gate_b_allows_block_c_decisioning": gate_b["status"] in {"PASS", "CONDITIONAL_PASS", "RENEGOTIATE_PRICE"},
        "gate_c_matches_decision_state": gate_c["status"] == decision["state"],
        "all_calculation_replays_pass": bool(replays) and all(row.get("status") == "PASS" for row in replays),
        "decision_state_is_not_human_approval": not bool(decision.get("is_final_human_approval", False)),
    }
    return {"schema_version": RC_SCHEMA_VERSION, "case_id": case_data["case_id"], "run_id": case_data["run_id"], "checks": checks, "passed": all(checks.values())}


def _finalize_reporting(output: Path, case_data: dict[str, Any]) -> dict[str, Any]:
    for target, source in TOP_LEVEL_ARTIFACTS.items():
        source_path = output / Path(source)
        if not source_path.is_file():
            raise ProviderConfigurationError(f"Required reporting artifact is missing: {source}")
        shutil.copy2(source_path, output / target)
    consistency = _cross_block_consistency(output, case_data)
    write_json(output / "cross_block_consistency_result.json", consistency)
    if not consistency["passed"]:
        raise ProviderConfigurationError("Cross-block consistency verification failed")
    a_summary = _read_json(output / "stages" / "block_a" / "run_summary.json")
    b_summary = _read_json(output / "stages" / "block_b" / "run_summary.json")
    c_summary = _read_json(output / "stages" / "block_c" / "run_summary.json")
    b_iterations = _read_json(output / "stages" / "block_b" / "07_loop" / "iteration_records.json")
    c_iterations = _read_json(output / "stages" / "block_c" / "09_loop" / "iteration_records.json")
    a_iterations = _read_json(output / "stages" / "block_a" / "loop" / "iteration_records.json")
    summary = {
        "schema_version": RC_SCHEMA_VERSION, "case_id": case_data["case_id"], "run_id": case_data["run_id"],
        "status": "COMPLETED", "provider_mode": case_data["provider"]["mode"],
        "module_counts": {"block_a": 7, "block_b": 5, "block_c": 5},
        "module_execution_counts": {"block_a": a_summary["module_execution_count"], "block_b": b_summary["module_execution_count"], "block_c": c_summary["module_execution_count"]},
        "targeted_repairs": {
            "block_a": a_iterations[1]["modules_executed"] if len(a_iterations) > 1 else [],
            "block_b": b_iterations[1]["modules_executed"] if len(b_iterations) > 1 else [],
            "block_c": c_iterations[1]["modules_executed"] if len(c_iterations) > 1 else [],
        },
        "gate_a": _read_json(output / "gate_a_result.json")["final_result"]["status"],
        "gate_b": _read_json(output / "gate_b_result.json")["status"],
        "gate_c": _read_json(output / "gate_c_result.json")["status"],
        "decision_state": _read_json(output / "decision_state.json")["state"],
        "delivery_outcome": _read_json(output / "final_delivery_verification.json")["delivery_outcome"],
        "final_report": "final_acquisition_strategy_report.md",
        "decision_state_is_final_human_approval": False,
        "paid_request_made": False,
    }
    write_json(output / "run_summary.json", summary)
    return summary


def run_full_pipeline(
    case_path: Path, output_dir: Path | None = None, *, resume: bool = False,
    enable_live: bool = False,
) -> dict[str, Any]:
    case_path = case_path.resolve()
    check = check_full_pipeline_case(case_path)
    if not check["ready"]:
        raise ProviderConfigurationError("; ".join(check["issues"]))
    case_data = load_case(case_path)
    if case_data["provider"]["mode"] == ProviderMode.OPENAI_LIVE.value:
        live_check = check_full_pipeline_configuration(case_path, enable_live=enable_live)
        if not live_check["ready"]:
            raise ProviderConfigurationError("; ".join(live_check["issues"]))
    output = (output_dir or case_path.parent / "run_output").resolve()
    output.mkdir(parents=True, exist_ok=True)
    completed: list[str] = []
    if resume and (output / "run_manifest.json").is_file():
        manifest = validate_run_manifest(output)
        if manifest.get("case_id") != case_data["case_id"] or manifest.get("run_id") != case_data["run_id"]:
            raise ProviderConfigurationError("Resume manifest case ID or run ID does not match the case")
        completed = list(manifest.get("completed_stages", []))
    elif (output / "run_manifest.json").exists():
        raise ProviderConfigurationError("Output already contains a run manifest; use --resume-run")
    templates = {
        name: _resolve_relative(case_path.parent, case_data["templates"][name], f"templates.{name}")
        for name in REQUIRED_TEMPLATE_FIELDS
    }
    mode = case_data["provider"]["mode"]
    pipeline_cases = output / "pipeline_cases"
    if "BLOCK_A" not in completed:
        config, path = _prepare_stage_case(template_path=templates["block_a_case"], stage_case_dir=pipeline_cases / "block_a", mode=mode, case_data=case_data)
        config["mandate_id"] = case_data["mandate"]["mandate_id"]
        config["research_contract_id"] = case_data["research_contract"]["contract_id"]
        config["mandate"].update({
            "buyer_name": case_data["mandate"]["buyer_name"], "target_name": case_data["mandate"]["target_name"],
            "transaction_stage": case_data["mandate"]["process_stage"], "decision_question": case_data["mandate"]["decision_question"],
            "buyer_strategic_need": case_data["mandate"]["buyer_strategic_need"], "jurisdictions": case_data["jurisdictions"],
        })
        write_json(path, config)
        run_block_a_case(path, output / "stages" / "block_a", provider=mode, module="BLOCK_A", enable_live=enable_live)
        completed.append("BLOCK_A")
        _write_manifest(output, case_path, case_data, completed)
    if "BLOCK_B" not in completed:
        config, path = _prepare_stage_case(template_path=templates["block_b_case"], stage_case_dir=pipeline_cases / "block_b", mode=mode, case_data=case_data)
        bundle = _build_block_b_bundle(case_data, output / "stages" / "block_a")
        config["business_mandate"] = _business_mandate(case_data)
        config["research_contract"] = copy.deepcopy(case_data["research_contract"])
        config["block_b_input_bundle"] = bundle
        config["gate_a_result"] = {**copy.deepcopy(bundle["gate_a_history"][-1]), "admitted_claims": copy.deepcopy(bundle["admitted_claims"])}
        config["research"]["human_review_items"] = [
            *config["research"].get("human_review_items", []),
            *[_review_for_block_b(row) for row in bundle["human_review_items"]],
        ]
        write_json(path, config)
        run_block_b_case(path, output / "stages" / "block_b", provider=mode, module="BLOCK_B", enable_live=enable_live)
        completed.append("BLOCK_B")
        _write_manifest(output, case_path, case_data, completed)
    if "BLOCK_C" not in completed:
        config, path = _prepare_stage_case(template_path=templates["block_c_case"], stage_case_dir=pipeline_cases / "block_c", mode=mode, case_data=case_data)
        config["block_c_input_bundle"] = _build_block_c_bundle(case_data, output / "stages" / "block_a", output / "stages" / "block_b")
        config["research"]["selected_diligence_workstreams"] = list(case_data["mandate"]["selected_diligence_workstreams"])
        config["research"]["jurisdictions"] = list(case_data["jurisdictions"])
        write_json(path, config)
        run_block_c_case(path, output / "stages" / "block_c", provider=mode, module="BLOCK_C", enable_live=enable_live)
        completed.append("BLOCK_C")
        _write_manifest(output, case_path, case_data, completed)
    if "REPORTING" not in completed:
        summary = _finalize_reporting(output, case_data)
        completed.append("REPORTING")
        manifest = _write_manifest(output, case_path, case_data, completed)
    else:
        summary = _read_json(output / "run_summary.json")
        manifest = validate_run_manifest(output)
    return {"summary": summary, "manifest": manifest, "output_dir": str(output)}


def resume_full_pipeline(output_dir: Path, *, enable_live: bool = False) -> dict[str, Any]:
    output = output_dir.resolve()
    manifest = validate_run_manifest(output)
    case_path = (output / manifest["case_input"]).resolve()
    if not case_path.is_file():
        raise ProviderConfigurationError("Original case input required for resume is unavailable")
    return run_full_pipeline(case_path, output, resume=True, enable_live=enable_live)
