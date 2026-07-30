from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v3_lite_buyer_acquisition_runtime.runtime.citation_verifier import verify_citations
from v3_lite_buyer_acquisition_runtime.runtime.numeric_verifier import verify_numeric_claims
from v3_lite_buyer_acquisition_runtime.runtime.temporal_verifier import verify_temporal_alignment


class CertificationError(ValueError):
    pass


CLAIM_REQUIRED_FIELDS = {
    "claim_id",
    "claim_type",
    "claim_statement",
    "support_level",
    "certification_status",
    "supporting_evidence_record_ids",
    "related_source_gap_ids",
    "temporal_scope",
    "permitted_use",
}
CLAIM_CERTIFICATION_STATUSES = {
    "certified",
    "certified_with_caveat",
    "failed",
    "blocked_by_source_gap",
    "unsupported",
    "requires_numeric_verification",
    "requires_human_review",
    "not_applicable",
}
OVERALL_STATUSES = {"passed_with_caveats", "failed", "repair_required", "human_review_required"}


def load_json_artifact(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise CertificationError(f"Artifact not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CertificationError(f"Invalid JSON artifact at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CertificationError(f"Artifact at {path} must be a JSON object.")
    return payload


def graph_source_id(graph: dict[str, Any]) -> str:
    return f"GRAPH-{graph['case_id']}-{graph['created_at']}"


def evidence_repository_source_id(evidence_repository: dict[str, Any]) -> str:
    return f"REPO-{evidence_repository['case_id']}-{evidence_repository['created_at']}"


def certification_result_source_id(certification_result: dict[str, Any]) -> str:
    return f"CERT-{certification_result['case_id']}-{certification_result['created_at']}"


def build_certification_result(graph: dict[str, Any], evidence_repository: dict[str, Any]) -> dict[str, Any]:
    validate_m5_inputs(graph, evidence_repository)
    citation_results = verify_citations(graph, evidence_repository)
    temporal_results = verify_temporal_alignment(graph, evidence_repository)
    numeric_results = verify_numeric_claims(graph, evidence_repository)
    records_by_id = {record["evidence_record_id"]: record for record in evidence_repository["evidence_records"]}
    citation_by_claim = {result["claim_id"]: result for result in citation_results}
    temporal_by_claim = {result["claim_id"]: result for result in temporal_results}
    numeric_by_claim = {result["related_claim_id"]: result for result in numeric_results}

    claim_certifications = []
    human_review_items = []
    for claim in graph["claim_nodes"]:
        cert = certify_claim(
            claim=claim,
            records_by_id=records_by_id,
            citation_result=citation_by_claim[claim["claim_id"]],
            temporal_result=temporal_by_claim[claim["claim_id"]],
            numeric_result=numeric_by_claim.get(claim["claim_id"]),
        )
        claim_certifications.append(cert)
        human_review_items.extend(_human_review_items_for_claim(cert, claim))

    verification_checks = _build_verification_checks(citation_results, temporal_results, numeric_results)
    overall_status = _overall_certification_status(claim_certifications, human_review_items)
    result = {
        "case_id": graph["case_id"],
        "generated_artifact": "certification_result.json",
        "stage": "M5_loop_certification",
        "source_bounded": True,
        "evidence_coverage_status": graph["evidence_coverage_status"],
        "created_from_claim_evidence_graph_id": graph_source_id(graph),
        "created_from_evidence_repository_id": evidence_repository_source_id(evidence_repository),
        "created_at": _now_utc_iso(),
        "overall_certification_status": overall_status,
        "claim_certifications": claim_certifications,
        "verification_checks": verification_checks,
        "numeric_verification_results": numeric_results,
        "citation_verification_results": citation_results,
        "temporal_verification_results": temporal_results,
        "human_review_items": _dedupe_human_review_items(human_review_items),
        "next_action": _next_action(overall_status),
    }
    validate_certification_result(result)
    return result


def validate_m5_inputs(graph: Any, evidence_repository: Any) -> None:
    if not isinstance(graph, dict):
        raise CertificationError("claim_evidence_graph must be an object.")
    if not isinstance(evidence_repository, dict):
        raise CertificationError("evidence_repository must be an object.")
    if graph.get("generated_artifact") != "claim_evidence_graph.json":
        raise CertificationError("M5 requires generated_artifact claim_evidence_graph.json.")
    if evidence_repository.get("generated_artifact") != "evidence_repository.json":
        raise CertificationError("M5 requires generated_artifact evidence_repository.json.")
    if graph.get("source_bounded") is not True or evidence_repository.get("source_bounded") is not True:
        raise CertificationError("M5 requires source_bounded graph and evidence repository.")
    if graph.get("case_id") != evidence_repository.get("case_id"):
        raise CertificationError("M5 graph and evidence repository case_id must match.")
    for field in ("claim_nodes", "evidence_edges", "gap_nodes"):
        if not isinstance(graph.get(field), list):
            raise CertificationError(f"claim_evidence_graph missing array field {field}.")
    if not isinstance(evidence_repository.get("evidence_records"), list) or not isinstance(evidence_repository.get("source_gaps"), list):
        raise CertificationError("evidence_repository must include evidence_records and source_gaps arrays.")

    claim_ids = set()
    for claim in graph["claim_nodes"]:
        missing = sorted(field for field in CLAIM_REQUIRED_FIELDS if field not in claim)
        if missing:
            raise CertificationError(f"claim_node missing required field(s): {', '.join(missing)}")
        claim_ids.add(claim["claim_id"])

    record_ids = {record["evidence_record_id"] for record in evidence_repository["evidence_records"]}
    source_gap_ids = {source_gap["source_gap_id"] for source_gap in evidence_repository["source_gaps"]}
    graph_gap_source_ids = {gap_node["source_gap_id"] for gap_node in graph["gap_nodes"]}
    unknown_graph_gap_ids = sorted(graph_gap_source_ids - source_gap_ids)
    if unknown_graph_gap_ids:
        raise CertificationError(f"gap_node maps to unknown source_gap(s): {', '.join(unknown_graph_gap_ids)}")

    for edge in graph["evidence_edges"]:
        if edge.get("claim_id") not in claim_ids:
            raise CertificationError(f"evidence edge cites unknown claim_id: {edge.get('claim_id')}")
        if edge.get("evidence_record_id") not in record_ids:
            raise CertificationError(f"evidence edge cites unknown evidence_record_id: {edge.get('evidence_record_id')}")
    for claim in graph["claim_nodes"]:
        unknown_records = sorted(set(claim["supporting_evidence_record_ids"]) - record_ids)
        if unknown_records:
            raise CertificationError(f"claim cites unknown evidence_record_id(s): {claim['claim_id']} -> {', '.join(unknown_records)}")
        unknown_gaps = sorted(set(claim["related_source_gap_ids"]) - source_gap_ids)
        if unknown_gaps:
            raise CertificationError(f"claim cites unknown source_gap_id(s): {claim['claim_id']} -> {', '.join(unknown_gaps)}")


def certify_claim(
    claim: dict[str, Any],
    records_by_id: dict[str, dict[str, Any]],
    citation_result: dict[str, Any],
    temporal_result: dict[str, Any],
    numeric_result: dict[str, Any] | None,
) -> dict[str, Any]:
    records = [records_by_id[record_id] for record_id in claim["supporting_evidence_record_ids"] if record_id in records_by_id]
    caveats = []
    if temporal_result["verification_status"] == "passed_with_caveat":
        caveats.append(temporal_result["caveat"])
    if citation_result["verification_status"] not in {"passed", "not_applicable"}:
        status = "failed"
        basis = "Citation verification failed."
    elif temporal_result["verification_status"] == "failed":
        status = "failed"
        basis = "Temporal verification failed."
    elif claim["support_level"] in {"gap_only", "unsupported"}:
        status, basis = _gap_or_unsupported_status(claim)
    elif claim["claim_type"] == "derived_numeric_candidate":
        if numeric_result and numeric_result["verification_status"] == "passed_with_caveat":
            status = "certified_with_caveat"
            basis = "Arithmetic relationship verified from source-supported components only."
            caveats.append(numeric_result["caveat"])
        else:
            status = "requires_numeric_verification"
            basis = "Numeric verification failed or was not available."
    elif claim["support_level"] == "source_supported" and _all_tier1(records):
        if claim["temporal_scope"] == "at_decision" and claim["permitted_use"] == "transaction_terms_verification" and temporal_result["verification_status"] == "passed":
            status = "certified"
            basis = "Narrow claim is supported by Tier 1 decision-time transaction evidence."
        else:
            status = "certified_with_caveat"
            basis = "Narrow claim is source-supported, but temporal or use caveats must be preserved."
    elif claim["support_level"] == "partially_supported" and records:
        status = "certified_with_caveat"
        basis = "Claim is only partially supported and must be framed narrowly with caveat."
    else:
        status = "requires_human_review"
        basis = "Claim requires human review before certification."

    if _requires_human_review(status, claim):
        caveats.append("Human review required before downstream report wording or certification expansion.")
    return {
        "claim_certification_id": f"CC-{claim['claim_id'].split('-')[-1]}",
        "claim_id": claim["claim_id"],
        "claim_type": claim["claim_type"],
        "claim_statement": claim["claim_statement"],
        "certification_status": status,
        "certification_basis": basis,
        "supporting_evidence_record_ids": claim["supporting_evidence_record_ids"],
        "related_source_gap_ids": claim["related_source_gap_ids"],
        "citation_check_status": citation_result["verification_status"],
        "temporal_check_status": temporal_result["verification_status"],
        "numeric_check_status": numeric_result["verification_status"] if numeric_result else "not_applicable",
        "caveats": sorted(set(caveats)),
        "requires_human_review": _requires_human_review(status, claim),
        "downstream_use_warning": _downstream_warning(status, claim),
    }


def validate_certification_result(result: Any) -> None:
    if not isinstance(result, dict):
        raise CertificationError("certification_result must be an object.")
    required = {
        "case_id",
        "generated_artifact",
        "stage",
        "source_bounded",
        "evidence_coverage_status",
        "created_from_claim_evidence_graph_id",
        "created_from_evidence_repository_id",
        "created_at",
        "overall_certification_status",
        "claim_certifications",
        "verification_checks",
        "numeric_verification_results",
        "citation_verification_results",
        "temporal_verification_results",
        "human_review_items",
        "next_action",
    }
    missing = sorted(field for field in required if field not in result)
    if missing:
        raise CertificationError(f"certification_result missing field(s): {', '.join(missing)}")
    if result["generated_artifact"] != "certification_result.json":
        raise CertificationError("generated_artifact must be certification_result.json.")
    if result["stage"] != "M5_loop_certification":
        raise CertificationError("stage must be M5_loop_certification.")
    if result["source_bounded"] is not True:
        raise CertificationError("certification_result must remain source_bounded.")
    if result["overall_certification_status"] not in OVERALL_STATUSES:
        raise CertificationError("invalid overall_certification_status.")
    for cert in result["claim_certifications"]:
        if cert["certification_status"] not in CLAIM_CERTIFICATION_STATUSES:
            raise CertificationError(f"invalid claim certification status: {cert['claim_id']}")
        if cert["certification_status"] in {"certified", "certified_with_caveat"} and not cert["supporting_evidence_record_ids"]:
            raise CertificationError(f"certified claim lacks supporting evidence: {cert['claim_id']}")
        if cert["certification_status"] == "certified" and cert["related_source_gap_ids"]:
            raise CertificationError(f"certified claim is blocked by source gap: {cert['claim_id']}")


def _gap_or_unsupported_status(claim: dict[str, Any]) -> tuple[str, str]:
    if claim["claim_type"] == "personal_proceeds":
        return "unsupported", "Personal proceeds claim lacks direct authoritative support."
    if claim["related_source_gap_ids"]:
        return "blocked_by_source_gap", "Claim is blocked by unresolved source gap(s)."
    return "unsupported", "Claim lacks supporting evidence."


def _all_tier1(records: list[dict[str, Any]]) -> bool:
    return bool(records) and all("Tier 1" in record["source_tiers"] for record in records)


def _requires_human_review(status: str, claim: dict[str, Any]) -> bool:
    if status in {"blocked_by_source_gap", "unsupported", "requires_numeric_verification", "requires_human_review", "failed"}:
        return True
    if claim["claim_type"] in {"personal_proceeds", "ownership_or_founder_background", "derived_numeric_candidate"}:
        return True
    if claim["temporal_scope"] in {"post_decision", "retrospective"}:
        return True
    hindsight_warning = claim.get("hindsight_leakage_warning", "").lower()
    if "post-decision" in hindsight_warning or "retrospective" in hindsight_warning:
        return True
    return False


def _downstream_warning(status: str, claim: dict[str, Any]) -> str:
    if status == "certified":
        return "Certified only as a narrow evidence-backed claim. Do not use for valuation, recommendations, or final investment conclusions."
    if status == "certified_with_caveat":
        return "Certified only with caveat. Preserve source timing, permitted use, and wording limits; do not use for valuation or recommendations."
    if status == "blocked_by_source_gap":
        return "Blocked by source gap. Repair source retrieval before certification or report use."
    if status == "unsupported":
        return "Unsupported. Do not use as a factual assertion."
    return "Not certified for downstream report, valuation, recommendation, or investment conclusion use."


def _human_review_items_for_claim(cert: dict[str, Any], claim: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    if not cert["requires_human_review"]:
        return items
    reasons = []
    if claim["claim_type"] == "personal_proceeds":
        reasons.append("personal proceeds claim requires direct source and human review")
    if claim["claim_type"] == "ownership_or_founder_background":
        reasons.append("founder ownership economics require authoritative disclosure and human review")
    if claim["claim_type"] == "derived_numeric_candidate":
        reasons.append("derived transaction value wording requires human review")
    if claim["temporal_scope"] in {"post_decision", "retrospective"}:
        reasons.append("post-decision or retrospective evidence could be misworded as ex-ante knowledge")
    if cert["related_source_gap_ids"]:
        reasons.append("unresolved source gap blocks important claim")
    if not reasons:
        reasons.append("claim requires human review before downstream use")
    return [
        {
            "human_review_item_id": f"HR-{claim['claim_id']}",
            "related_claim_ids": [claim["claim_id"]],
            "related_source_gap_ids": cert["related_source_gap_ids"],
            "review_reason": "; ".join(reasons),
            "severity": "high" if cert["certification_status"] in {"blocked_by_source_gap", "unsupported", "failed"} else "medium",
            "required_action": "Review source limits and wording before any downstream use.",
        }
    ]


def _dedupe_human_review_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped = []
    for item in items:
        key = (tuple(item["related_claim_ids"]), item["review_reason"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def _build_verification_checks(
    citation_results: list[dict[str, Any]],
    temporal_results: list[dict[str, Any]],
    numeric_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        _summary_check("VC-001", "citation", citation_results),
        _summary_check("VC-002", "temporal", temporal_results),
        _summary_check("VC-003", "numeric", numeric_results),
    ]


def _summary_check(check_id: str, check_type: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = Counter(result["verification_status"] for result in results)
    failed = statuses.get("failed", 0)
    status = "failed" if failed else "passed_with_caveats" if any(key.endswith("caveat") for key in statuses) else "passed"
    return {
        "verification_check_id": check_id,
        "check_type": check_type,
        "check_status": status,
        "result_count": len(results),
        "status_counts": dict(statuses),
        "blocking": bool(failed),
    }


def _overall_certification_status(claim_certifications: list[dict[str, Any]], human_review_items: list[dict[str, Any]]) -> str:
    statuses = {cert["certification_status"] for cert in claim_certifications}
    if "failed" in statuses:
        return "failed"
    if statuses.intersection({"blocked_by_source_gap", "unsupported", "requires_numeric_verification"}):
        return "repair_required"
    if human_review_items:
        return "human_review_required"
    return "passed_with_caveats"


def _next_action(overall_status: str) -> str:
    if overall_status == "repair_required":
        return "run_targeted_source_repair_before_report_or_certification_expansion"
    if overall_status == "human_review_required":
        return "human_review_required_before_downstream_wording"
    if overall_status == "failed":
        return "stop_and_fix_verification_failures"
    return "eligible_for_next_stage_with_caveats"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
