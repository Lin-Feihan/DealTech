from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.claim_certifier import certification_result_source_id


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
BLOCKING_CLAIM_STATUSES = {"unsupported", "blocked_by_source_gap", "failed", "requires_numeric_verification", "requires_human_review"}
FAILED_NUMERIC_STATUSES = {"failed", "insufficient_numeric_support"}


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
        "manifest_warnings": _manifest_warnings(analysis_package, certification_result, repair_plan),
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
    if not isinstance(certification_result.get("claim_certifications"), list):
        raise ReportRenderingGateError("certification_result must include claim_certifications array.")
    if not isinstance(certification_result.get("numeric_verification_results"), list):
        raise ReportRenderingGateError("certification_result must include numeric_verification_results array.")
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
    if certification_result.get("overall_certification_status") == "failed":
        reasons.append(_reason("BR-002", "certification_result overall status is failed", "certification_gate", "high"))
    if analysis_package.get("final_report_allowed") is False:
        reasons.append(_reason("BR-003", "analysis_package final_report_allowed is false", "analysis_gate", "high"))
    if analysis_package.get("recommendation_allowed") is False:
        reasons.append(_reason("BR-004", "analysis_package recommendation_allowed is false", "analysis_gate", "high"))
    if analysis_package.get("analysis_readiness_status") != "ready_for_limited_analysis":
        reasons.append(_reason("BR-005", f"analysis_readiness_status is {analysis_package.get('analysis_readiness_status')}", "analysis_readiness_gate", "high"))
    if repair_plan.get("repair_steps"):
        reasons.append(_reason("BR-006", "repair plan has unresolved steps", "repair_plan_gate", "high"))
    if analysis_package.get("human_review_items"):
        reasons.append(_reason("BR-007", "human review items remain unresolved", "human_review_gate", "high"))
    failed_claims = [claim for claim in certification_result["claim_certifications"] if claim["certification_status"] in BLOCKING_CLAIM_STATUSES]
    if failed_claims:
        reasons.append(_reason("BR-008", "one or more claims are failed, unsupported, source-gap-blocked, or require review", "claim_certification_gate", "high"))
    failed_numeric = [result for result in certification_result["numeric_verification_results"] if result.get("verification_status") in FAILED_NUMERIC_STATUSES]
    if failed_numeric:
        reasons.append(_reason("BR-009", "one or more numeric verification checks failed or lack inputs", "numeric_verification_gate", "high"))
    if analysis_package.get("blocked_analysis_items"):
        reasons.append(_reason("BR-010", "analysis package contains blocked analysis items", "blocked_analysis_gate", "high"))
    if _uses_post_decision_as_ex_ante_support(certification_result):
        reasons.append(_reason("BR-011", "post-decision or retrospective evidence requires caveated use", "temporal_gate", "medium"))
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
        _section("AS-001", "source-bounded analysis package", "internal_non_final_material"),
        _section("AS-002", "certification summary", "internal_non_final_material"),
        _section("AS-003", "repair plan", "internal_non_final_material"),
        _section("AS-004", "source gap summary", "internal_non_final_material"),
    ]


def _excluded_sections() -> list[dict[str, str]]:
    return [
        _section("ES-001", "investment recommendation", "blocked_until_repair_and_human_review"),
        _section("ES-002", "final proceed or walk-away decision", "blocked_until_repair_and_human_review"),
        _section("ES-003", "uncaveated valuation or deal-value conclusion", "blocked_until_certified_numeric_support"),
        _section("ES-004", "unsupported value-transfer analysis", "blocked_by_unresolved_source_gap"),
        _section("ES-005", "unsupported ownership analysis", "blocked_by_unresolved_source_gap"),
        _section("ES-006", "unsupported legal or diligence conclusion", "blocked_by_unresolved_source_gap"),
        _section("ES-007", "final report narrative", "blocked_until_final_report_allowed"),
    ]


def _required_repairs_before_report(repair_plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "repair_step_id": step["repair_step_id"],
            "reason": _neutral_repair_reason(step),
            "target_state": step["target_state"],
            "target_artifact": step["target_artifact"],
            "related_claim_ids": step["related_claim_ids"],
            "related_research_gap_ids": step["related_research_gap_ids"],
            "required_source_types": [_neutral_source_type(value) for value in step.get("required_source_types", [])],
        }
        for step in repair_plan["repair_steps"]
    ]


def _manifest_warnings(analysis_package: dict[str, Any], certification_result: dict[str, Any], repair_plan: dict[str, Any]) -> list[str]:
    warnings = []
    if analysis_package.get("caveats"):
        warnings.append("Analysis caveats must be preserved in any later report-rendering decision.")
    if certification_result.get("numeric_verification_results"):
        warnings.append("Numeric verification supports arithmetic only and does not authorize valuation conclusions.")
    if repair_plan.get("repair_steps"):
        warnings.append("Repair steps remain unresolved; final report generation stays blocked.")
    return warnings


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


def _uses_post_decision_as_ex_ante_support(certification_result: dict[str, Any]) -> bool:
    return any(result.get("verification_status") == "passed_with_caveat" for result in certification_result.get("temporal_verification_results", []))


def _neutral_repair_reason(step: dict[str, Any]) -> str:
    action = step.get("repair_action") or "repair_required"
    claim_ids = ", ".join(step.get("related_claim_ids", [])) or "no direct claim id"
    return f"{action} remains unresolved for {claim_ids}; complete source-bounded repair before report rendering."


def _neutral_source_type(value: str) -> str:
    lowered = value.lower()
    if any(term in lowered for term in ("ownership", "capitalization", "schedule")):
        return "authoritative ownership or capitalization source"
    if any(term in lowered for term in ("agreement", "announcement", "filing", "financial")):
        return "authoritative transaction or financial source"
    if any(term in lowered for term in ("intellectual", "assignment", "asset")):
        return "authoritative asset or intellectual property source"
    if any(term in lowered for term in ("clinical", "regulatory")):
        return "authoritative regulatory or clinical source"
    return "authoritative primary source"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
