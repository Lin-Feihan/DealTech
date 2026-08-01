from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditPackageError(ValueError):
    pass


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
REPORT_STRUCTURE_PATH = RUNTIME_ROOT / "config" / "professional_report_structure.json"


BLOCKED_CERTIFICATION_STATUSES = {
    "unsupported",
    "blocked_by_source_gap",
    "failed",
    "requires_numeric_verification",
    "requires_human_review",
}


def load_json_artifact(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise AuditPackageError(f"Artifact not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AuditPackageError(f"Invalid JSON artifact at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuditPackageError(f"Artifact at {path} must be a JSON object.")
    return payload


def load_report_structure(path: Path = REPORT_STRUCTURE_PATH) -> dict[str, Any]:
    structure = load_json_artifact(path)
    validate_report_structure(structure)
    return structure


def validate_report_structure(structure: Any) -> None:
    if not isinstance(structure, dict):
        raise AuditPackageError("professional report structure must be an object.")
    sections = structure.get("sections")
    if not isinstance(sections, list) or not sections:
        raise AuditPackageError("professional report structure must include non-empty sections array.")
    seen = set()
    for section in sections:
        if not isinstance(section, dict):
            raise AuditPackageError("professional report structure sections must be objects.")
        for field in (
            "section_id",
            "section_title",
            "purpose",
            "source_analysis_section_ids",
            "required_when_available",
            "may_be_blocked_if_missing_evidence",
        ):
            if field not in section:
                raise AuditPackageError(f"professional report structure section missing {field}.")
        if section["section_id"] in seen:
            raise AuditPackageError(f"duplicate report section_id: {section['section_id']}")
        seen.add(section["section_id"])
        if not isinstance(section["source_analysis_section_ids"], list):
            raise AuditPackageError("source_analysis_section_ids must be an array.")


def build_audit_package(
    report_manifest: dict[str, Any],
    analysis_package: dict[str, Any],
    certification_result: dict[str, Any],
    claim_evidence_graph: dict[str, Any],
    evidence_repository: dict[str, Any],
    report_structure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_step6a_inputs(report_manifest, analysis_package, certification_result, claim_evidence_graph, evidence_repository)
    report_structure = report_structure or load_report_structure()
    validate_report_structure(report_structure)

    claims_by_id = {claim["claim_id"]: claim for claim in claim_evidence_graph["claim_nodes"]}
    claim_certs_by_id = {claim["claim_id"]: claim for claim in certification_result.get("claim_certifications", [])}
    records_by_id = {record["evidence_record_id"]: record for record in evidence_repository["evidence_records"]}
    analysis_sections_by_id = {section["section_id"]: section for section in analysis_package["analysis_sections"]}
    preserved_caveats_by_claim = _preserved_caveats_by_claim(analysis_package)

    report_section_trace = _build_report_section_trace(
        report_structure=report_structure,
        analysis_sections_by_id=analysis_sections_by_id,
        claims_by_id=claims_by_id,
        records_by_id=records_by_id,
        preserved_caveats_by_claim=preserved_caveats_by_claim,
    )
    source_citation_table = _source_citation_table(report_section_trace, records_by_id)
    excluded_claims = _excluded_claims(analysis_package, claim_certs_by_id, claims_by_id)
    caveat_map = _caveat_map(analysis_package, report_section_trace)
    recommendation_gate_record = _recommendation_gate_record(analysis_package, certification_result)

    package = {
        "case_id": analysis_package["case_id"],
        "generated_artifact": "audit_package.json",
        "stage": "Step6A_professional_report_audit_package",
        "source_bounded": True,
        "created_at": _now_utc_iso(),
        "created_from_report_manifest_id": _report_manifest_source_id(report_manifest),
        "created_from_analysis_package_id": analysis_package.get("created_from_analysis_package_id") or _analysis_package_source_id(analysis_package),
        "created_from_certification_result_id": _certification_result_source_id(certification_result),
        "created_from_claim_evidence_graph_id": _claim_evidence_graph_source_id(claim_evidence_graph),
        "created_from_evidence_repository_id": _evidence_repository_source_id(evidence_repository),
        "report_generation_allowed": _report_generation_allowed(report_manifest, analysis_package),
        "recommendation_allowed": recommendation_gate_record["recommendation_allowed"],
        "report_section_trace": report_section_trace,
        "source_citation_table": source_citation_table,
        "excluded_claims": excluded_claims,
        "caveat_map": caveat_map,
        "human_review_summary": _human_review_summary(analysis_package, certification_result),
        "recommendation_gate_record": recommendation_gate_record,
        "audit_summary": _audit_summary(report_section_trace, source_citation_table, excluded_claims, caveat_map),
    }
    validate_audit_package(package)
    return package


def validate_step6a_inputs(
    report_manifest: Any,
    analysis_package: Any,
    certification_result: Any,
    claim_evidence_graph: Any,
    evidence_repository: Any,
) -> None:
    artifacts = {
        "report_manifest": report_manifest,
        "analysis_package": analysis_package,
        "certification_result": certification_result,
        "claim_evidence_graph": claim_evidence_graph,
        "evidence_repository": evidence_repository,
    }
    for name, payload in artifacts.items():
        if not isinstance(payload, dict):
            raise AuditPackageError(f"{name} must be an object.")
    expected = {
        "report_manifest": ("report_manifest.json", "M7_report_rendering_gate"),
        "analysis_package": ("analysis_package.json", "M6_evidence_bounded_deal_analysis"),
        "certification_result": ("certification_result.json", "M5_loop_certification"),
        "claim_evidence_graph": ("claim_evidence_graph.json", "M4_claim_evidence_graph"),
        "evidence_repository": ("evidence_repository.json", "M3_evidence_repository"),
    }
    for name, (artifact, stage) in expected.items():
        payload = artifacts[name]
        if payload.get("generated_artifact") != artifact:
            raise AuditPackageError(f"Step 6A requires {artifact} input for {name}.")
        if payload.get("stage") != stage:
            raise AuditPackageError(f"Step 6A requires {name}.stage == {stage}.")
    for name, payload in artifacts.items():
        if payload.get("source_bounded") is not True:
            raise AuditPackageError(f"Step 6A requires source_bounded {name}.")
    case_ids = {payload.get("case_id") for payload in artifacts.values()}
    if len(case_ids) != 1:
        raise AuditPackageError("Step 6A input case_id values must match.")
    if not isinstance(report_manifest.get("blocked_reasons"), list):
        raise AuditPackageError("report_manifest must include blocked_reasons array.")
    if not isinstance(analysis_package.get("analysis_sections"), list):
        raise AuditPackageError("analysis_package must include analysis_sections array.")
    if not isinstance(certification_result.get("claim_certifications"), list):
        raise AuditPackageError("certification_result must include claim_certifications array.")
    if not isinstance(claim_evidence_graph.get("claim_nodes"), list):
        raise AuditPackageError("claim_evidence_graph must include claim_nodes array.")
    if not isinstance(evidence_repository.get("evidence_records"), list):
        raise AuditPackageError("evidence_repository must include evidence_records array.")


def validate_audit_package(package: Any) -> None:
    if not isinstance(package, dict):
        raise AuditPackageError("audit_package must be an object.")
    required = {
        "case_id",
        "generated_artifact",
        "stage",
        "source_bounded",
        "created_at",
        "created_from_report_manifest_id",
        "created_from_analysis_package_id",
        "created_from_certification_result_id",
        "created_from_claim_evidence_graph_id",
        "created_from_evidence_repository_id",
        "report_generation_allowed",
        "recommendation_allowed",
        "report_section_trace",
        "source_citation_table",
        "excluded_claims",
        "caveat_map",
        "human_review_summary",
        "recommendation_gate_record",
        "audit_summary",
    }
    missing = sorted(field for field in required if field not in package)
    if missing:
        raise AuditPackageError(f"audit_package missing field(s): {', '.join(missing)}")
    if package["generated_artifact"] != "audit_package.json":
        raise AuditPackageError("generated_artifact must be audit_package.json.")
    if package["stage"] != "Step6A_professional_report_audit_package":
        raise AuditPackageError("stage must be Step6A_professional_report_audit_package.")
    if package["source_bounded"] is not True:
        raise AuditPackageError("audit_package must be source_bounded.")
    if not package["report_section_trace"]:
        raise AuditPackageError("audit_package must include report_section_trace records.")
    for trace in package["report_section_trace"]:
        _validate_trace_record(trace)


def _build_report_section_trace(
    report_structure: dict[str, Any],
    analysis_sections_by_id: dict[str, dict[str, Any]],
    claims_by_id: dict[str, dict[str, Any]],
    records_by_id: dict[str, dict[str, Any]],
    preserved_caveats_by_claim: dict[str, list[str]],
) -> list[dict[str, Any]]:
    traces = []
    all_analysis_sections = list(analysis_sections_by_id.values())
    for report_section in report_structure["sections"]:
        source_ids = report_section["source_analysis_section_ids"]
        if report_section["section_id"] == "appendix_source_list" and not source_ids:
            source_sections = all_analysis_sections
        else:
            source_sections = [analysis_sections_by_id[section_id] for section_id in source_ids if section_id in analysis_sections_by_id]
        used_claim_ids = _dedupe(value for section in source_sections for value in section.get("supporting_claim_ids", []))
        used_evidence_record_ids = _evidence_ids_for_claims(used_claim_ids, claims_by_id, source_sections)
        used_source_ids = _source_ids_for_evidence(used_evidence_record_ids, records_by_id)
        required_caveats = _dedupe(
            caveat
            for section in source_sections
            for caveat in section.get("caveats", [])
        )
        required_caveats = _dedupe(required_caveats + [caveat for claim_id in used_claim_ids for caveat in preserved_caveats_by_claim.get(claim_id, [])])
        excluded_claim_ids = _dedupe(value for section in source_sections for value in section.get("excluded_claim_ids", []))
        trace_notes = _trace_notes(report_section, source_sections, used_claim_ids, used_evidence_record_ids, used_source_ids)
        traces.append(
            {
                "report_section_id": report_section["section_id"],
                "report_section_title": report_section["section_title"],
                "source_analysis_section_ids": source_ids,
                "used_claim_ids": used_claim_ids,
                "used_evidence_record_ids": used_evidence_record_ids,
                "used_source_ids": used_source_ids,
                "required_caveats": required_caveats,
                "excluded_claim_ids": excluded_claim_ids,
                "trace_notes": trace_notes,
            }
        )
    return traces


def _evidence_ids_for_claims(used_claim_ids: list[str], claims_by_id: dict[str, dict[str, Any]], source_sections: list[dict[str, Any]]) -> list[str]:
    evidence_ids = []
    for claim_id in used_claim_ids:
        evidence_ids.extend(claims_by_id.get(claim_id, {}).get("supporting_evidence_record_ids", []))
    evidence_ids.extend(value for section in source_sections for value in section.get("supporting_evidence_record_ids", []))
    return _dedupe(evidence_ids)


def _source_ids_for_evidence(used_evidence_record_ids: list[str], records_by_id: dict[str, dict[str, Any]]) -> list[str]:
    return _dedupe(source_id for evidence_id in used_evidence_record_ids for source_id in records_by_id.get(evidence_id, {}).get("source_ids", []))


def _source_citation_table(report_section_trace: list[dict[str, Any]], records_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for trace in report_section_trace:
        for evidence_id in trace["used_evidence_record_ids"]:
            record = records_by_id.get(evidence_id, {})
            source_ids = record.get("source_ids", [])
            source_titles = record.get("source_titles", [])
            source_tiers = record.get("source_tiers", [])
            for index, source_id in enumerate(source_ids):
                row = rows.setdefault(
                    source_id,
                    {
                        "source_id": source_id,
                        "source_title": source_titles[index] if index < len(source_titles) else "",
                        "source_tier": source_tiers[index] if index < len(source_tiers) else "",
                        "evidence_record_ids": [],
                        "claim_ids": [],
                        "report_section_ids": [],
                    },
                )
                row["evidence_record_ids"].append(evidence_id)
                row["claim_ids"].extend(trace["used_claim_ids"])
                row["report_section_ids"].append(trace["report_section_id"])
    for row in rows.values():
        row["evidence_record_ids"] = _dedupe(row["evidence_record_ids"])
        row["claim_ids"] = _dedupe(row["claim_ids"])
        row["report_section_ids"] = _dedupe(row["report_section_ids"])
    return sorted(rows.values(), key=lambda row: row["source_id"])


def _excluded_claims(
    analysis_package: dict[str, Any],
    claim_certs_by_id: dict[str, dict[str, Any]],
    claims_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    excluded_ids = set(analysis_package.get("excluded_claim_ids", []))
    for section in analysis_package.get("analysis_sections", []):
        excluded_ids.update(section.get("excluded_claim_ids", []))
    rows = []
    for claim_id in sorted(excluded_ids):
        cert = claim_certs_by_id.get(claim_id, {})
        claim = claims_by_id.get(claim_id, {})
        status = cert.get("certification_status") or claim.get("certification_status") or "excluded_by_analysis_package"
        rows.append(
            {
                "claim_id": claim_id,
                "claim_type": claim.get("claim_type") or cert.get("claim_type") or "",
                "certification_status": status,
                "exclusion_reason": _exclusion_reason(claim_id, status, analysis_package),
                "related_source_gap_ids": cert.get("related_source_gap_ids") or claim.get("related_source_gap_ids", []),
            }
        )
    return rows


def _exclusion_reason(claim_id: str, status: str, analysis_package: dict[str, Any]) -> str:
    for reason in analysis_package.get("exclusion_reasons", []):
        if claim_id in reason:
            return reason
    if status in BLOCKED_CERTIFICATION_STATUSES:
        return f"Claim has blocked certification status: {status}."
    return "Claim is excluded from the analysis package and must not appear as a report fact."


def _caveat_map(analysis_package: dict[str, Any], report_section_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in analysis_package.get("preserved_caveats", []):
        claim_id = item.get("claim_id", "")
        for caveat_index, caveat in enumerate(item.get("caveats", []), start=1):
            rows.append(
                {
                    "caveat_id": f"CAV-{claim_id}-{caveat_index:03d}",
                    "caveat_text": caveat,
                    "related_claim_ids": [claim_id] if claim_id else [],
                    "report_section_ids": _sections_for_claim(claim_id, report_section_trace),
                }
            )
    for item in analysis_package.get("caveats", []):
        caveat_id = item.get("caveat_id") or f"CAV-PKG-{len(rows) + 1:03d}"
        related_claim_ids = item.get("related_claim_ids", [])
        rows.append(
            {
                "caveat_id": caveat_id,
                "caveat_text": item.get("caveat_text") or item.get("caveat_type") or "Analysis caveat preserved from analysis_package.",
                "related_claim_ids": related_claim_ids,
                "report_section_ids": _sections_for_any_claim(related_claim_ids, report_section_trace),
            }
        )
    return _dedupe_dicts(rows)


def _human_review_summary(analysis_package: dict[str, Any], certification_result: dict[str, Any]) -> dict[str, Any]:
    items = analysis_package.get("human_review_items") or certification_result.get("human_review_items", [])
    return {
        "human_review_required": bool(items),
        "human_review_item_count": len(items),
        "human_review_items": items,
    }


def _recommendation_gate_record(analysis_package: dict[str, Any], certification_result: dict[str, Any]) -> dict[str, Any]:
    gate = certification_result.get("recommendation_gate_summary") or {}
    source = "analysis_package"
    recommendation_allowed = bool(analysis_package.get("recommendation_allowed", False))
    if "recommendation_allowed" in gate:
        source = "certification_result.recommendation_gate_summary"
        recommendation_allowed = bool(gate["recommendation_allowed"] and analysis_package.get("recommendation_allowed", False))
    return {
        "recommendation_allowed": recommendation_allowed,
        "source": source,
        "blocked_claim_ids": gate.get("recommendation_blocked_claim_ids", []) or analysis_package.get("excluded_claim_ids", []),
        "blocking_reasons": gate.get("recommendation_blocking_reasons", []),
        "decision_artifact_required_for_recommendation": True,
    }


def _audit_summary(
    report_section_trace: list[dict[str, Any]],
    source_citation_table: list[dict[str, Any]],
    excluded_claims: list[dict[str, Any]],
    caveat_map: list[dict[str, Any]],
) -> dict[str, Any]:
    traced_claim_ids = {claim_id for trace in report_section_trace for claim_id in trace["used_claim_ids"]}
    traced_evidence_ids = {evidence_id for trace in report_section_trace for evidence_id in trace["used_evidence_record_ids"]}
    return {
        "report_section_count": len(report_section_trace),
        "traced_claim_count": len(traced_claim_ids),
        "traced_evidence_record_count": len(traced_evidence_ids),
        "traced_source_count": len(source_citation_table),
        "excluded_claim_count": len(excluded_claims),
        "caveat_count": len(caveat_map),
        "notes": [
            "Step 6A packages trace information only; it does not render final_report.md.",
            "Step 6A does not create recommendation_decision.json or make recommendation decisions.",
            "Unsupported or excluded claims remain trace-only and must not be presented as report facts.",
        ],
    }


def _trace_notes(
    report_section: dict[str, Any],
    source_sections: list[dict[str, Any]],
    used_claim_ids: list[str],
    used_evidence_record_ids: list[str],
    used_source_ids: list[str],
) -> list[str]:
    notes = [report_section["purpose"]]
    if not source_sections:
        notes.append("No source analysis sections are mapped; this section is structural or appendix-only.")
    if source_sections and not used_claim_ids:
        notes.append("Mapped analysis sections do not contain usable supporting claims.")
    if used_claim_ids and not used_evidence_record_ids:
        notes.append("Claims are present but no evidence records were traced from available artifacts.")
    if used_evidence_record_ids and not used_source_ids:
        notes.append("Evidence records are present but source IDs were not available in the evidence repository.")
    return notes


def _preserved_caveats_by_claim(analysis_package: dict[str, Any]) -> dict[str, list[str]]:
    caveats: dict[str, list[str]] = {}
    for item in analysis_package.get("preserved_caveats", []):
        claim_id = item.get("claim_id")
        if not claim_id:
            continue
        caveats.setdefault(claim_id, []).extend(item.get("caveats", []))
    return {claim_id: _dedupe(values) for claim_id, values in caveats.items()}


def _sections_for_claim(claim_id: str, report_section_trace: list[dict[str, Any]]) -> list[str]:
    return [trace["report_section_id"] for trace in report_section_trace if claim_id in trace["used_claim_ids"]]


def _sections_for_any_claim(claim_ids: list[str], report_section_trace: list[dict[str, Any]]) -> list[str]:
    if not claim_ids:
        return []
    claim_set = set(claim_ids)
    return [trace["report_section_id"] for trace in report_section_trace if claim_set.intersection(trace["used_claim_ids"])]


def _report_generation_allowed(report_manifest: dict[str, Any], analysis_package: dict[str, Any]) -> bool:
    return bool(
        report_manifest.get("rendering_status") == "ready_to_render"
        and report_manifest.get("final_report_generated") is True
        and analysis_package.get("final_report_allowed") is True
    )


def _validate_trace_record(trace: dict[str, Any]) -> None:
    for field in (
        "report_section_id",
        "report_section_title",
        "source_analysis_section_ids",
        "used_claim_ids",
        "used_evidence_record_ids",
        "used_source_ids",
        "required_caveats",
        "excluded_claim_ids",
        "trace_notes",
    ):
        if field not in trace:
            raise AuditPackageError(f"report_section_trace missing {field}.")


def _report_manifest_source_id(report_manifest: dict[str, Any]) -> str:
    return f"REPORT-MANIFEST-{report_manifest['case_id']}-{report_manifest.get('created_at', 'unknown')}"


def _analysis_package_source_id(analysis_package: dict[str, Any]) -> str:
    return f"ANALYSIS-{analysis_package['case_id']}-{analysis_package.get('created_at', 'unknown')}"


def _certification_result_source_id(certification_result: dict[str, Any]) -> str:
    return f"CERT-{certification_result['case_id']}-{certification_result.get('created_at', 'unknown')}"


def _claim_evidence_graph_source_id(claim_evidence_graph: dict[str, Any]) -> str:
    return f"GRAPH-{claim_evidence_graph['case_id']}-{claim_evidence_graph.get('created_at', 'unknown')}"


def _evidence_repository_source_id(evidence_repository: dict[str, Any]) -> str:
    return f"EVIDENCE-{evidence_repository['case_id']}-{evidence_repository.get('created_at', 'unknown')}"


def _dedupe(values: Any) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value is None:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _dedupe_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        key = json.dumps(item, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
