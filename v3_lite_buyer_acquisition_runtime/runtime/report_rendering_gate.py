from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v3_lite_buyer_acquisition_runtime.runtime.claim_certifier import certification_result_source_id


class ReportRenderingGateError(ValueError):
    pass


RENDERING_STATUSES = {
    "ready_to_render",
    "blocked_by_repair_required",
    "blocked_by_certification_failure",
    "blocked_by_human_review",
    "blocked_by_analysis_readiness",
    "failed_closed",
}


def load_json_artifact(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise ReportRenderingGateError(f"Artifact not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReportRenderingGateError(f"Invalid JSON artifact at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReportRenderingGateError(f"Artifact at {path} must be a JSON object.")
    return payload


def analysis_package_source_id(analysis_package: dict[str, Any]) -> str:
    return f"ANALYSIS-{analysis_package['case_id']}-{analysis_package['created_at']}"


def repair_plan_source_id(repair_plan: dict[str, Any]) -> str:
    return f"REPAIR-{repair_plan['case_id']}-{repair_plan['created_from_certification_result_id']}"


def build_report_manifest(
    analysis_package: dict[str, Any],
    certification_result: dict[str, Any],
    repair_plan: dict[str, Any],
) -> dict[str, Any]:
    validate_m7_inputs(analysis_package, certification_result, repair_plan)
    blocked_reasons = _blocked_reasons(analysis_package, certification_result, repair_plan)
    rendering_status = _rendering_status(analysis_package, certification_result, repair_plan, blocked_reasons)
    manifest = {
        "case_id": analysis_package["case_id"],
        "generated_artifact": "report_manifest.json",
        "stage": "M7_report_rendering_gate",
        "source_bounded": True,
        "created_from_analysis_package_id": analysis_package_source_id(analysis_package),
        "created_from_certification_result_id": certification_result_source_id(certification_result),
        "created_from_repair_plan_id": repair_plan_source_id(repair_plan),
        "created_at": _now_utc_iso(),
        "rendering_status": rendering_status,
        "final_report_generated": False if blocked_reasons else True,
        "blocked_reasons": blocked_reasons,
        "allowed_sections": _allowed_sections(),
        "excluded_sections": _excluded_sections(),
        "required_repairs_before_report": _required_repairs_before_report(repair_plan),
        "human_review_required": bool(analysis_package.get("human_review_items")),
        "next_action": _next_action(rendering_status),
    }
    validate_report_manifest(manifest)
    return manifest


def validate_m7_inputs(analysis_package: Any, certification_result: Any, repair_plan: Any) -> None:
    for name, payload in {
        "analysis_package": analysis_package,
        "certification_result": certification_result,
        "repair_plan": repair_plan,
    }.items():
        if not isinstance(payload, dict):
            raise ReportRenderingGateError(f"{name} must be an object.")
    if analysis_package.get("generated_artifact") != "analysis_package.json":
        raise ReportRenderingGateError("M7 requires analysis_package.json input.")
    if certification_result.get("generated_artifact") != "certification_result.json":
        raise ReportRenderingGateError("M7 requires certification_result.json input.")
    if repair_plan.get("generated_artifact") != "repair_plan.json":
        raise ReportRenderingGateError("M7 requires repair_plan.json input.")
    if analysis_package.get("stage") != "M6_evidence_bounded_deal_analysis":
        raise ReportRenderingGateError("analysis_package.stage must be M6_evidence_bounded_deal_analysis.")
    if certification_result.get("stage") != "M5_loop_certification":
        raise ReportRenderingGateError("certification_result.stage must be M5_loop_certification.")
    if repair_plan.get("stage") != "M5_repair_plan":
        raise ReportRenderingGateError("repair_plan.stage must be M5_repair_plan.")
    if analysis_package.get("source_bounded") is not True:
        raise ReportRenderingGateError("analysis_package.source_bounded must be true.")
    if certification_result.get("source_bounded") is not True:
        raise ReportRenderingGateError("certification_result.source_bounded must be true.")
    for field in ("recommendation_allowed", "final_report_allowed", "analysis_readiness_status"):
        if field not in analysis_package:
            raise ReportRenderingGateError(f"analysis_package missing {field}.")
    if not isinstance(repair_plan.get("repair_steps"), list):
        raise ReportRenderingGateError("repair_plan must include repair_steps array.")
    if not isinstance(analysis_package.get("human_review_items"), list):
        raise ReportRenderingGateError("analysis_package must include human_review_items array.")
    if analysis_package.get("case_id") != certification_result.get("case_id") or analysis_package.get("case_id") != repair_plan.get("case_id"):
        raise ReportRenderingGateError("M7 input case_id values must match.")


def validate_report_manifest(manifest: Any) -> None:
    if not isinstance(manifest, dict):
        raise ReportRenderingGateError("report_manifest must be an object.")
    required = {
        "case_id",
        "generated_artifact",
        "stage",
        "source_bounded",
        "created_from_analysis_package_id",
        "created_from_certification_result_id",
        "created_from_repair_plan_id",
        "created_at",
        "rendering_status",
        "final_report_generated",
        "blocked_reasons",
        "allowed_sections",
        "excluded_sections",
        "required_repairs_before_report",
        "human_review_required",
        "next_action",
    }
    missing = sorted(field for field in required if field not in manifest)
    if missing:
        raise ReportRenderingGateError(f"report_manifest missing field(s): {', '.join(missing)}")
    if manifest["generated_artifact"] != "report_manifest.json":
        raise ReportRenderingGateError("generated_artifact must be report_manifest.json.")
    if manifest["stage"] != "M7_report_rendering_gate":
        raise ReportRenderingGateError("stage must be M7_report_rendering_gate.")
    if manifest["source_bounded"] is not True:
        raise ReportRenderingGateError("report_manifest must be source_bounded.")
    if manifest["rendering_status"] not in RENDERING_STATUSES:
        raise ReportRenderingGateError("invalid rendering_status.")
    if manifest["blocked_reasons"] and manifest["final_report_generated"] is not False:
        raise ReportRenderingGateError("blocked rendering cannot generate final_report.md.")
    for repair in manifest["required_repairs_before_report"]:
        for field in ("repair_step_id", "reason", "target_state", "target_artifact", "related_claim_ids", "related_research_gap_ids"):
            if field not in repair:
                raise ReportRenderingGateError(f"required repair missing {field}.")


def _blocked_reasons(
    analysis_package: dict[str, Any],
    certification_result: dict[str, Any],
    repair_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    reasons = []
    if certification_result.get("overall_certification_status") == "repair_required":
        reasons.append(_reason("BR-001", "certification_result overall status is repair_required", "certification_gate", "high"))
    if analysis_package.get("final_report_allowed") is False:
        reasons.append(_reason("BR-002", "analysis_package final_report_allowed is false", "analysis_gate", "high"))
    if analysis_package.get("recommendation_allowed") is False:
        reasons.append(_reason("BR-003", "analysis_package recommendation_allowed is false", "analysis_gate", "high"))
    if analysis_package.get("analysis_readiness_status") == "limited_by_repair_required":
        reasons.append(_reason("BR-004", "analysis_readiness_status is limited_by_repair_required", "analysis_readiness_gate", "high"))
    if repair_plan.get("repair_steps"):
        reasons.append(_reason("BR-005", "unresolved source gaps remain", "repair_plan_gate", "high"))
    if analysis_package.get("human_review_items"):
        reasons.append(_reason("BR-006", "human review items remain unresolved", "human_review_gate", "high"))
    if _has_derived_180m_gap(analysis_package, repair_plan):
        reasons.append(_reason("BR-007", "derived $180M wording requires caveat or direct source before final report use", "numeric_wording_gate", "medium"))
    if _has_blocked_topic(analysis_package, "founder ownership economics"):
        reasons.append(_reason("BR-008", "founder ownership gap remains unresolved", "source_gap_gate", "high"))
    if _has_blocked_topic(analysis_package, "Bohan Jin personal realized proceeds"):
        reasons.append(_reason("BR-009", "Bohan Jin personal proceeds gap remains unresolved", "source_gap_gate", "high"))
    if _has_blocked_topic(analysis_package, "immediate pre-sale cap table"):
        reasons.append(_reason("BR-010", "pre-sale cap table gap remains unresolved", "source_gap_gate", "high"))
    if _has_blocked_topic(analysis_package, "official patent-office confirmation"):
        reasons.append(_reason("BR-011", "patent-office verification gap remains unresolved", "source_gap_gate", "medium"))
    return reasons


def _rendering_status(
    analysis_package: dict[str, Any],
    certification_result: dict[str, Any],
    repair_plan: dict[str, Any],
    blocked_reasons: list[dict[str, Any]],
) -> str:
    if certification_result.get("overall_certification_status") == "repair_required" or repair_plan.get("repair_steps"):
        return "blocked_by_repair_required"
    if certification_result.get("overall_certification_status") == "failed":
        return "blocked_by_certification_failure"
    if analysis_package.get("human_review_items"):
        return "blocked_by_human_review"
    if analysis_package.get("analysis_readiness_status") != "ready_for_limited_analysis":
        return "blocked_by_analysis_readiness"
    if blocked_reasons:
        return "blocked_by_analysis_readiness"
    return "ready_to_render"


def _allowed_sections() -> list[dict[str, str]]:
    return [
        _section("AS-001", "evidence-bounded analysis package exists", "internal_non_final_material"),
        _section("AS-002", "certification summary exists", "internal_non_final_material"),
        _section("AS-003", "repair plan exists", "internal_non_final_material"),
        _section("AS-004", "source gap summary exists", "internal_non_final_material"),
    ]


def _excluded_sections() -> list[dict[str, str]]:
    return [
        _section("ES-001", "executive investment recommendation", "blocked_until_repair_and_human_review"),
        _section("ES-002", "final Proceed / Walk Away recommendation", "blocked_until_repair_and_human_review"),
        _section("ES-003", "uncaveated valuation or headline deal value", "blocked_until_direct_source_or_caveated_numeric_treatment"),
        _section("ES-004", "founder proceeds analysis", "blocked_by_unresolved_source_gap"),
        _section("ES-005", "pre-sale cap table analysis", "blocked_by_unresolved_source_gap"),
        _section("ES-006", "official patent-office validated asset lineage", "blocked_by_unresolved_source_gap"),
        _section("ES-007", "final report narrative", "blocked_until_final_report_allowed"),
    ]


def _required_repairs_before_report(repair_plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "repair_step_id": step["repair_step_id"],
            "reason": step["reason"],
            "target_state": step["target_state"],
            "target_artifact": step["target_artifact"],
            "related_claim_ids": step["related_claim_ids"],
            "related_research_gap_ids": step["related_research_gap_ids"],
            "required_source_types": step.get("required_source_types", []),
        }
        for step in repair_plan["repair_steps"]
    ]


def _next_action(rendering_status: str) -> str:
    if rendering_status == "ready_to_render":
        return "render_final_report_after_explicit_user_request"
    return "complete_required_source_repairs_and_human_review_before_report_rendering"


def _reason(reason_id: str, reason_text: str, gate: str, severity: str) -> dict[str, str]:
    return {
        "blocked_reason_id": reason_id,
        "reason": reason_text,
        "gate": gate,
        "severity": severity,
    }


def _section(section_id: str, section_name: str, status: str) -> dict[str, str]:
    return {
        "section_id": section_id,
        "section_name": section_name,
        "status": status,
    }


def _has_derived_180m_gap(analysis_package: dict[str, Any], repair_plan: dict[str, Any]) -> bool:
    return any("180M" in item.get("blocked_topic", "") or "$180M" in item.get("reason", "") for item in analysis_package.get("blocked_analysis_items", [])) or any(
        "$180M" in step.get("reason", "") for step in repair_plan.get("repair_steps", [])
    )


def _has_blocked_topic(analysis_package: dict[str, Any], topic: str) -> bool:
    return any(item.get("blocked_topic") == topic for item in analysis_package.get("blocked_analysis_items", []))


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
