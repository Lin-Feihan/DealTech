from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class ReportRendererError(ValueError):
    pass


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
REPORT_STRUCTURE_PATH = RUNTIME_ROOT / "config" / "professional_report_structure.json"
REPORT_STYLE_GUIDE_PATH = RUNTIME_ROOT / "config" / "report_style_guide.json"

ALLOWED_CLAIM_STATUSES = {"certified", "certified_with_caveat"}
BLOCKING_CERTIFICATION_STATUSES = {"repair_required", "failed"}
UNAUTHORIZED_RECOMMENDATION_TERMS = (
    "Proceed",
    "Proceed with Conditions",
    "Renegotiate",
    "Defer",
    "Walk Away",
    "proceed",
    "renegotiate",
    "defer",
    "walk-away",
)
MAIN_BODY_FORBIDDEN_MARKERS = (
    "CL-",
    "ER-",
    "RE-",
    "claim_id",
    "raw_evidence_id",
    "certification_status",
    "claim_node",
    "evidence_record",
    "support_level",
)


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
    audit_package: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_renderer_inputs(report_manifest, analysis_package, certification_result, audit_package)
    blocked_reasons = rendering_blockers(report_manifest, analysis_package, certification_result)
    if blocked_reasons:
        return {
            "rendering_status": "blocked",
            "final_report_generated": False,
            "final_report_path": None,
            "blocked_reasons": blocked_reasons,
        }

    markdown = build_final_report_markdown(analysis_package, certification_result, audit_package=audit_package)
    _validate_markdown(markdown, recommendation_allowed=bool(analysis_package.get("recommendation_allowed")))
    output_dir.mkdir(parents=True, exist_ok=True)
    final_report_path = output_dir / "final_report.md"
    final_report_path.write_text(markdown, encoding="utf-8")
    return {
        "rendering_status": "rendered",
        "final_report_generated": True,
        "final_report_path": final_report_path,
        "blocked_reasons": [],
    }


def validate_renderer_inputs(
    report_manifest: Any,
    analysis_package: Any,
    certification_result: Any,
    audit_package: Any | None = None,
) -> None:
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
    if audit_package is not None:
        if not isinstance(audit_package, dict):
            raise ReportRendererError("audit_package must be an object when provided.")
        if audit_package.get("generated_artifact") != "audit_package.json":
            raise ReportRendererError("optional audit_package must be audit_package.json.")
        if audit_package.get("case_id") != analysis_package.get("case_id"):
            raise ReportRendererError("optional audit_package case_id must match analysis_package case_id.")


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


def build_final_report_markdown(
    analysis_package: dict[str, Any],
    certification_result: dict[str, Any],
    audit_package: dict[str, Any] | None = None,
) -> str:
    report_structure = _load_report_structure()
    _load_report_style_guide()
    allowed_claims_by_id = {
        claim["claim_id"]: claim
        for claim in certification_result["claim_certifications"]
        if claim["certification_status"] in ALLOWED_CLAIM_STATUSES
    }
    sections_by_id = {section["section_id"]: section for section in analysis_package["analysis_sections"]}
    context = {
        "analysis_package": analysis_package,
        "allowed_claims_by_id": allowed_claims_by_id,
        "sections_by_id": sections_by_id,
        "audit_package": audit_package,
    }

    lines = [
        "# Buyer-Side Acquisition Analysis Report",
        "",
        f"Case: {_clean_text(analysis_package['case_id'])}",
        "",
        "This report is rendered only from gate-approved, source-bounded analysis artifacts. It is prepared as a buyer-side acquisition memo and remains subject to the limitations noted below.",
        "",
    ]
    for section in report_structure["sections"]:
        section_id = section["section_id"]
        if section_id == "cover":
            continue
        if section_id == "limitations":
            lines.extend(_render_limitations(context, section))
        elif section_id == "appendix_source_list":
            lines.extend(_render_source_appendix(audit_package))
        elif section_id == "decision_readiness_or_recommendation":
            lines.extend(_render_decision_readiness(context, section))
        else:
            lines.extend(_render_professional_section(context, section))
    return "\n".join(lines).rstrip() + "\n"


def _render_professional_section(context: dict[str, Any], report_section: dict[str, Any]) -> list[str]:
    source_sections = _mapped_source_sections(context, report_section)
    narratives = _professional_narratives(source_sections)
    findings = _supporting_findings(context, source_sections)
    lines = [f"## {report_section['section_title']}", ""]
    if narratives:
        lines.extend(f"- {_clean_text(item)}" for item in narratives)
        if findings:
            lines.append("")
            lines.append("Supporting detail:")
            lines.extend(f"- {_clean_text(finding)}" for finding in findings)
    else:
        lines.append(_no_finding_sentence(report_section["section_id"]))
    return lines + [""]


def _render_decision_readiness(context: dict[str, Any], report_section: dict[str, Any]) -> list[str]:
    analysis_package = context["analysis_package"]
    source_sections = _mapped_source_sections(context, report_section)
    lines = [f"## {report_section['section_title']}", ""]
    if analysis_package.get("recommendation_allowed") is True and analysis_package.get("recommendation_decision"):
        lines.append(_clean_text(str(analysis_package["recommendation_decision"])))
    else:
        lines.append(
            "A final acquisition recommendation is not authorized by the upstream gates. This report should be used only for decision-readiness review."
        )
    for item in _professional_narratives(source_sections):
        lines.append(f"- {_clean_text(item)}")
    return lines + [""]


def _render_limitations(context: dict[str, Any], report_section: dict[str, Any]) -> list[str]:
    analysis_package = context["analysis_package"]
    audit_package = context["audit_package"]
    source_sections = _mapped_source_sections(context, report_section)
    lines = ["## Limitations", ""]
    limitations = []
    limitations.extend(_source_section_limitations(source_sections))
    limitations.extend(_caveat_texts(analysis_package.get("caveats", [])))
    if audit_package:
        limitations.extend(_audit_limitations(audit_package))
    if not limitations:
        limitations.append("No additional source-bounded limitations were provided by the upstream artifacts.")
    lines.extend(f"- {_clean_text(item)}" for item in _dedupe(limitations))
    return lines + [""]


def _render_source_appendix(audit_package: dict[str, Any] | None) -> list[str]:
    lines = ["## Appendix: Source List", ""]
    if not audit_package:
        return lines + ["Detailed source traceability is available in audit_package.json when provided.", ""]
    source_rows = audit_package.get("source_citation_table", [])
    if not source_rows:
        return lines + ["The audit package did not include a source citation table.", ""]
    for row in source_rows:
        title = _clean_text(row.get("source_title") or row.get("source_id") or "Untitled source")
        tier = _clean_text(row.get("source_tier") or "source tier not recorded")
        sections = ", ".join(_title_from_section_id(section_id) for section_id in row.get("report_section_ids", [])) or "report section not recorded"
        lines.append(f"- {title}. Source tier: {tier}. Used in: {sections}.")
    lines.append("")
    lines.append("Detailed claim, evidence, and source mapping remains in audit_package.json.")
    return lines + [""]


def _mapped_source_sections(context: dict[str, Any], report_section: dict[str, Any]) -> list[dict[str, Any]]:
    sections_by_id = context["sections_by_id"]
    return [sections_by_id[section_id] for section_id in report_section.get("source_analysis_section_ids", []) if section_id in sections_by_id]


def _professional_narratives(source_sections: list[dict[str, Any]]) -> list[str]:
    narratives = []
    for section in source_sections:
        for field in ("analyst_interpretation", "buyer_implication", "decision_impact", "analysis_boundary"):
            value = section.get(field)
            if value:
                narratives.append(value)
    return _dedupe(narratives)


def _supporting_findings(context: dict[str, Any], source_sections: list[dict[str, Any]]) -> list[str]:
    findings = []
    allowed_claims_by_id = context["allowed_claims_by_id"]
    for section in source_sections:
        for finding in section.get("findings", []):
            if _finding_is_allowed_fact(finding, allowed_claims_by_id):
                findings.append(finding["finding_text"])
    return _dedupe(findings)


def _finding_is_allowed_fact(finding: dict[str, Any], allowed_claims_by_id: dict[str, dict[str, Any]]) -> bool:
    related_claim_ids = finding.get("related_claim_ids", [])
    if not related_claim_ids:
        return False
    if not all(claim_id in allowed_claims_by_id for claim_id in related_claim_ids):
        return False
    return finding.get("certification_status") in ALLOWED_CLAIM_STATUSES


def _no_finding_sentence(section_id: str) -> str:
    if section_id in {"due_diligence_priorities", "key_risks_and_red_flags"}:
        return "No additional source-bounded finding was available; this area should remain a diligence priority if material to the buyer's decision."
    return "No source-bounded finding was available for this section in the upstream analysis package."


def _source_section_limitations(source_sections: list[dict[str, Any]]) -> list[str]:
    limitations = []
    for section in source_sections:
        limitations.extend(section.get("caveats", []))
        limitations.extend(section.get("missing_inputs", []))
        for item in section.get("pending_diligence_items", []):
            if isinstance(item, dict):
                limitations.append(item.get("diligence_item") or item.get("description") or item.get("reason") or "")
            else:
                limitations.append(str(item))
        for item in section.get("imported_limitations_from_m5", []):
            if isinstance(item, dict):
                limitations.append(item.get("reason") or item.get("limitation") or item.get("description") or "")
            else:
                limitations.append(str(item))
        for finding in section.get("findings", []):
            text = finding.get("finding_text")
            if text and not _finding_is_allowed_fact(finding, {}):
                limitations.append(f"{text} This is a limitation, not a factual report finding.")
    return limitations


def _caveat_texts(caveats: list[dict[str, Any]]) -> list[str]:
    return [caveat.get("caveat_text", "") for caveat in caveats if caveat.get("caveat_text")]


def _audit_limitations(audit_package: dict[str, Any]) -> list[str]:
    limitations = []
    for item in audit_package.get("caveat_map", []):
        if item.get("caveat_text"):
            limitations.append(item["caveat_text"])
    human_review = audit_package.get("human_review_summary", {})
    if human_review.get("human_review_required"):
        limitations.append("Human review remains required for one or more upstream items before recommendation use.")
    summary = audit_package.get("audit_summary", {})
    if summary.get("excluded_claim_count", 0):
        limitations.append("One or more excluded claims remain audit-traceable but are not used as report facts.")
    return limitations


def _blocking_human_review_items(analysis_package: dict[str, Any]) -> list[dict[str, Any]]:
    if analysis_package.get("human_review_required") is True:
        return analysis_package.get("human_review_items", [])
    return [item for item in analysis_package.get("human_review_items", []) if item.get("severity") == "high" or item.get("blocks_report") is True]


def _validate_markdown(markdown: str, recommendation_allowed: bool) -> None:
    main_body = markdown.split("## Appendix: Source List", maxsplit=1)[0]
    for marker in MAIN_BODY_FORBIDDEN_MARKERS:
        if marker in main_body:
            raise ReportRendererError(f"Generated report main body contains forbidden internal marker: {marker}")
    if not recommendation_allowed:
        for term in UNAUTHORIZED_RECOMMENDATION_TERMS:
            if term in markdown:
                raise ReportRendererError(f"Generated report contains forbidden recommendation term: {term}")


def _load_report_structure() -> dict[str, Any]:
    structure = load_json_artifact(REPORT_STRUCTURE_PATH)
    if not isinstance(structure.get("sections"), list) or not structure["sections"]:
        raise ReportRendererError("professional_report_structure.json must include sections.")
    return structure


def _load_report_style_guide() -> dict[str, Any]:
    style_guide = load_json_artifact(REPORT_STYLE_GUIDE_PATH)
    if not style_guide.get("principles"):
        raise ReportRendererError("report_style_guide.json must include principles.")
    return style_guide


def _clean_text(value: Any) -> str:
    text = str(value).strip()
    replacements = {
        "overall_certification_status": "overall source review status",
        "certification_status": "source review status",
        "raw_evidence_id": "source evidence reference",
        "claim_id": "claim reference",
        "claim_node": "claim record",
        "evidence_record": "evidence record",
        "support_level": "support level",
        "certified-with-caveat": "subject to caveat",
        "certified_with_caveat": "subject to caveat",
        "certified": "source-supported",
        "certification": "source review",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\bClaim\s+CL-\d+\s+\(([^)]+)\)", r"A source-supported \1 claim", text)
    text = re.sub(r"\b(?:CL|ER|RE)-\d+\b", "upstream artifact", text)
    return text


def _title_from_section_id(section_id: str) -> str:
    return section_id.replace("_", " ").title()


def _dedupe(values: Any) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _blocker(blocker_id: str, reason: str, gate: str) -> dict[str, str]:
    return {"blocked_reason_id": blocker_id, "reason": reason, "gate": gate, "severity": "high"}
