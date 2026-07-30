from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ReportRendererError(ValueError):
    pass


ALLOWED_CLAIM_STATUSES = {"certified", "certified_with_caveat"}
BLOCKING_CERTIFICATION_STATUSES = {"repair_required", "failed"}
FORBIDDEN_REPORT_TERMS = ("Proceed", "Walk Away")


def load_json_artifact(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise ReportRendererError(f"Artifact not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReportRendererError(f"Invalid JSON artifact at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReportRendererError(f"Artifact at {path} must be a JSON object.")
    return payload


def render_report_if_allowed(
    report_manifest: dict[str, Any],
    analysis_package: dict[str, Any],
    certification_result: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    validate_renderer_inputs(report_manifest, analysis_package, certification_result)
    blocked_reasons = rendering_blockers(report_manifest, analysis_package, certification_result)
    if blocked_reasons:
        return {
            "rendering_status": "blocked",
            "final_report_generated": False,
            "final_report_path": None,
            "blocked_reasons": blocked_reasons,
        }

    markdown = build_final_report_markdown(analysis_package, certification_result)
    _validate_markdown(markdown)
    output_dir.mkdir(parents=True, exist_ok=True)
    final_report_path = output_dir / "final_report.md"
    final_report_path.write_text(markdown, encoding="utf-8")
    return {
        "rendering_status": "rendered",
        "final_report_generated": True,
        "final_report_path": final_report_path,
        "blocked_reasons": [],
    }


def validate_renderer_inputs(report_manifest: Any, analysis_package: Any, certification_result: Any) -> None:
    for name, payload in {
        "report_manifest": report_manifest,
        "analysis_package": analysis_package,
        "certification_result": certification_result,
    }.items():
        if not isinstance(payload, dict):
            raise ReportRendererError(f"{name} must be an object.")
    if report_manifest.get("generated_artifact") != "report_manifest.json" or report_manifest.get("stage") != "M7_report_rendering_gate":
        raise ReportRendererError("M7.1 requires report_manifest.json from M7_report_rendering_gate.")
    if analysis_package.get("generated_artifact") != "analysis_package.json" or analysis_package.get("stage") != "M6_evidence_bounded_deal_analysis":
        raise ReportRendererError("M7.1 requires analysis_package.json from M6_evidence_bounded_deal_analysis.")
    if certification_result.get("generated_artifact") != "certification_result.json" or certification_result.get("stage") != "M5_loop_certification":
        raise ReportRendererError("M7.1 requires certification_result.json from M5_loop_certification.")
    if analysis_package.get("source_bounded") is not True or certification_result.get("source_bounded") is not True:
        raise ReportRendererError("M7.1 requires source_bounded analysis and certification inputs.")
    if report_manifest.get("case_id") != analysis_package.get("case_id") or report_manifest.get("case_id") != certification_result.get("case_id"):
        raise ReportRendererError("M7.1 input case_id values must match.")
    for field in ("rendering_status", "required_repairs_before_report", "blocked_reasons"):
        if field not in report_manifest:
            raise ReportRendererError(f"report_manifest missing {field}.")
    for field in ("final_report_allowed", "analysis_sections", "caveats", "human_review_items"):
        if field not in analysis_package:
            raise ReportRendererError(f"analysis_package missing {field}.")
    if "overall_certification_status" not in certification_result or "claim_certifications" not in certification_result:
        raise ReportRendererError("certification_result missing required certification status or claims.")


def rendering_blockers(
    report_manifest: dict[str, Any],
    analysis_package: dict[str, Any],
    certification_result: dict[str, Any],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if report_manifest["rendering_status"] != "ready_to_render":
        blockers.append(_blocker("RB-001", f"report_manifest.rendering_status is {report_manifest['rendering_status']}", "report_manifest_gate"))
    if analysis_package["final_report_allowed"] is not True:
        blockers.append(_blocker("RB-002", "analysis_package.final_report_allowed is not true", "analysis_permission_gate"))
    if certification_result["overall_certification_status"] in BLOCKING_CERTIFICATION_STATUSES:
        blockers.append(_blocker("RB-003", f"certification_result.overall_certification_status is {certification_result['overall_certification_status']}", "certification_gate"))
    if report_manifest.get("required_repairs_before_report"):
        blockers.append(_blocker("RB-004", "report_manifest has unresolved required repairs before report", "repair_gate"))
    blocking_human_review = _blocking_human_review_items(analysis_package)
    if blocking_human_review:
        blockers.append(_blocker("RB-005", "analysis_package has unresolved blocking human review items", "human_review_gate"))
    blockers.extend(report_manifest.get("blocked_reasons", []))
    return blockers


def build_final_report_markdown(analysis_package: dict[str, Any], certification_result: dict[str, Any]) -> str:
    allowed_claims_by_id = {
        claim["claim_id"]: claim
        for claim in certification_result["claim_certifications"]
        if claim["certification_status"] in ALLOWED_CLAIM_STATUSES
    }
    sections_by_id = {section["section_id"]: section for section in analysis_package["analysis_sections"]}
    lines = [
        "# Evidence-Bounded Acquisition Analysis Report",
        "",
        f"Case ID: `{analysis_package['case_id']}`",
        "",
        "Report status: rendered from gate-approved source-bounded analysis package.",
        "",
        "## Source and Certification Basis",
        "",
        f"- Analysis readiness: `{analysis_package.get('analysis_readiness_status', 'not_recorded')}`",
        f"- Certification status: `{certification_result['overall_certification_status']}`",
        f"- Evidence coverage: `{analysis_package['evidence_coverage_status']}`",
        "- This report uses only certified or certified-with-caveat claims and analysis package sections.",
        "",
        "## Executive Summary",
        "",
        _summary_from_sections(sections_by_id),
        "",
    ]
    lines.extend(_render_analysis_section("Transaction Background", sections_by_id.get("transaction_terms_analysis"), allowed_claims_by_id))
    lines.extend(_render_analysis_section("Transaction Terms", sections_by_id.get("transaction_terms_analysis"), allowed_claims_by_id))
    lines.extend(_render_analysis_section("Milestone Economics", sections_by_id.get("milestone_economics_analysis"), allowed_claims_by_id))
    lines.extend(_render_analysis_section("Entity and Asset Lineage", sections_by_id.get("entity_and_asset_lineage_analysis"), allowed_claims_by_id))
    lines.extend(_render_gap_section(sections_by_id.get("evidence_gap_and_risk_analysis")))
    lines.extend(_render_human_review_notes(analysis_package.get("human_review_items", [])))
    lines.extend(_render_caveats(analysis_package.get("caveats", [])))
    lines.extend(_render_claim_appendix(allowed_claims_by_id))
    return "\n".join(lines).rstrip() + "\n"


def _render_analysis_section(title: str, section: dict[str, Any] | None, allowed_claims_by_id: dict[str, dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not section:
        return lines + ["No gate-approved analysis section was provided.", ""]
    rendered = []
    for finding in section.get("findings", []):
        related_claim_ids = [claim_id for claim_id in finding.get("related_claim_ids", []) if claim_id in allowed_claims_by_id]
        if not related_claim_ids:
            continue
        status = finding.get("certification_status", "not_recorded")
        if status not in ALLOWED_CLAIM_STATUSES:
            continue
        caveat_marker = " Caveat preserved." if finding.get("caveated") else ""
        rendered.append(f"- {finding['finding_text']} [{', '.join(related_claim_ids)}; {status}].{caveat_marker}")
    if not rendered:
        rendered.append("No certified or certified-with-caveat findings are available for this section.")
    return lines + rendered + [""]


def _render_gap_section(section: dict[str, Any] | None) -> list[str]:
    lines = ["## Evidence Gaps and Limitations", ""]
    if not section:
        return lines + ["No source gap summary was provided.", ""]
    findings = []
    for finding in section.get("findings", []):
        findings.append(f"- {finding['finding_text']} This is a limitation, not a factual finding.")
    if not findings:
        findings.append("No source gaps were provided.")
    return lines + findings + [""]


def _render_human_review_notes(human_review_items: list[dict[str, Any]]) -> list[str]:
    lines = ["## Human Review Notes", ""]
    if not human_review_items:
        return lines + ["No unresolved blocking human review items were provided.", ""]
    rendered = []
    for item in human_review_items:
        rendered.append(
            f"- {item.get('human_review_item_id', 'HR-unlisted')}: {item.get('review_reason', 'review required')} "
            f"[{', '.join(item.get('related_claim_ids', [])) or 'no claim id'}]."
        )
    return lines + rendered + [""]


def _render_caveats(caveats: list[dict[str, Any]]) -> list[str]:
    lines = ["## Certification Caveats", ""]
    if not caveats:
        return lines + ["No certification caveats were provided.", ""]
    rendered = [f"- {caveat.get('caveat_id', 'CAV-unlisted')}: {caveat.get('caveat_text', '')}" for caveat in caveats]
    return lines + rendered + [""]


def _render_claim_appendix(allowed_claims_by_id: dict[str, dict[str, Any]]) -> list[str]:
    lines = ["## Appendix: Claim-Evidence References", ""]
    if not allowed_claims_by_id:
        return lines + ["No certified claim references were provided.", ""]
    rendered = []
    for claim_id in sorted(allowed_claims_by_id):
        claim = allowed_claims_by_id[claim_id]
        evidence_ids = ", ".join(claim.get("supporting_evidence_record_ids", [])) or "no evidence id"
        rendered.append(f"- {claim_id}: {claim['claim_statement']} Evidence: {evidence_ids}. Status: {claim['certification_status']}.")
    return lines + rendered + [""]


def _summary_from_sections(sections_by_id: dict[str, dict[str, Any]]) -> str:
    summaries = []
    for section_id in ("transaction_terms_analysis", "milestone_economics_analysis", "entity_and_asset_lineage_analysis"):
        section = sections_by_id.get(section_id)
        if section:
            summaries.append(section.get("summary", ""))
    return " ".join(summary for summary in summaries if summary) or "Gate-approved analysis sections were provided."


def _blocking_human_review_items(analysis_package: dict[str, Any]) -> list[dict[str, Any]]:
    if analysis_package.get("human_review_required") is True:
        return analysis_package.get("human_review_items", [])
    return [item for item in analysis_package.get("human_review_items", []) if item.get("severity") == "high" or item.get("blocks_report") is True]


def _validate_markdown(markdown: str) -> None:
    for term in FORBIDDEN_REPORT_TERMS:
        if term in markdown:
            raise ReportRendererError(f"Generated report contains forbidden recommendation term: {term}")


def _blocker(blocker_id: str, reason: str, gate: str) -> dict[str, str]:
    return {"blocked_reason_id": blocker_id, "reason": reason, "gate": gate, "severity": "high"}
