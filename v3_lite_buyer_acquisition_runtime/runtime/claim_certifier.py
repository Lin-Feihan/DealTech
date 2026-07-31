from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v3_lite_buyer_acquisition_runtime.runtime.claim_evidence_check import (
    claim_evidence_results_by_claim_id,
    run_claim_evidence_check,
)
from v3_lite_buyer_acquisition_runtime.runtime.evidence_check import evidence_results_by_record_id, run_evidence_check
from v3_lite_buyer_acquisition_runtime.runtime.source_refetch_check import run_source_refetch_check, source_refetch_results_by_record_id
from v3_lite_buyer_acquisition_runtime.runtime.usage_check import run_usage_check, usage_results_by_claim_id


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
REPORT_ASSERTION_USE = "report_assertion"
RECOMMENDATION_BLOCKING_USES = {"final_recommendation", "ex_ante_recommendation", "recommendation_use"}
ANALYSIS_ALLOWED_STATUSES = {"certified", "certified_with_caveat"}
NEXT_WORKFLOW_ACTIONS = {
    "send_to_M6_analysis",
    "send_to_M6_with_caveat",
    "return_to_M2_source_retrieval",
    "return_to_M4_claim_rewrite",
    "route_to_M5_numeric_verification",
    "route_to_human_review",
    "block_pipeline_until_structure_repaired",
}


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
    evidence_check_results = run_evidence_check(evidence_repository)
    source_refetch_check_results = run_source_refetch_check(evidence_repository)
    claim_evidence_check_results = run_claim_evidence_check(graph, evidence_repository)
    usage_check_results = run_usage_check(graph, evidence_repository)
    citation_results = _build_compat_citation_results(graph, claim_evidence_check_results)
    temporal_results = _build_compat_temporal_results(graph)
    numeric_results: list[dict[str, Any]] = []
    records_by_id = {record["evidence_record_id"]: record for record in evidence_repository["evidence_records"]}
    evidence_check_by_record = evidence_results_by_record_id(evidence_check_results)
    source_refetch_by_record = source_refetch_results_by_record_id(source_refetch_check_results)
    claim_evidence_check_by_claim = claim_evidence_results_by_claim_id(claim_evidence_check_results)
    temporal_by_claim = {result["claim_id"]: result for result in temporal_results}
    usage_check_by_claim = usage_results_by_claim_id(usage_check_results)

    claim_certifications = []
    human_review_items = []
    for claim in graph["claim_nodes"]:
        cert = certify_claim(
            claim=claim,
            records_by_id=records_by_id,
            evidence_check_by_record=evidence_check_by_record,
            source_refetch_by_record=source_refetch_by_record,
            claim_evidence_check=claim_evidence_check_by_claim[claim["claim_id"]],
            temporal_result=temporal_by_claim[claim["claim_id"]],
            usage_check=usage_check_by_claim[claim["claim_id"]],
        )
        claim_certifications.append(cert)
        human_review_items.extend(_human_review_items_for_claim(cert, claim))

    verification_checks = _build_verification_checks(
        citation_results,
        temporal_results,
        numeric_results,
        evidence_check_results,
        source_refetch_check_results,
        claim_evidence_check_results,
        usage_check_results,
    )
    overall_status = _overall_certification_status(claim_certifications, human_review_items)
    analysis_gate_summary = _build_analysis_gate_summary(claim_certifications)
    report_gate_summary = _build_report_gate_summary(claim_certifications)
    recommendation_gate_summary = _build_recommendation_gate_summary(claim_certifications)
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
        "evidence_check_results": evidence_check_results,
        "source_refetch_check_results": source_refetch_check_results,
        "claim_evidence_check_results": claim_evidence_check_results,
        "usage_check_results": usage_check_results,
        "numeric_verification_results": numeric_results,
        "citation_verification_results": citation_results,
        "temporal_verification_results": temporal_results,
        "analysis_gate_summary": analysis_gate_summary,
        "report_gate_summary": report_gate_summary,
        "recommendation_gate_summary": recommendation_gate_summary,
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
    evidence_check_by_record: dict[str, dict[str, Any]],
    source_refetch_by_record: dict[str, list[dict[str, Any]]],
    claim_evidence_check: dict[str, Any],
    temporal_result: dict[str, Any],
    usage_check: dict[str, Any],
) -> dict[str, Any]:
    records = [records_by_id[record_id] for record_id in claim["supporting_evidence_record_ids"] if record_id in records_by_id]
    evidence_checks = [evidence_check_by_record[record["evidence_record_id"]] for record in records if record["evidence_record_id"] in evidence_check_by_record]
    source_refetch_checks = [check for record in records for check in source_refetch_by_record.get(record["evidence_record_id"], [])]
    repair_actions = _combine_repair_actions(evidence_checks, source_refetch_checks, claim_evidence_check, usage_check)
    caveats = []
    if temporal_result["verification_status"] == "passed_with_caveat":
        caveats.append(temporal_result["caveat"])
    caveats.extend(_check_caveats(evidence_checks))
    caveats.extend(_source_refetch_caveats(source_refetch_checks))
    caveats.extend(claim_evidence_check.get("required_caveats", []))
    caveats.extend(usage_check.get("required_caveats", []))
    if temporal_result["verification_status"] == "failed":
        status = "failed"
        basis = "Temporal verification failed."
    elif claim["support_level"] in {"gap_only", "unsupported"}:
        status, basis = _gap_or_unsupported_status(claim)
    elif _has_blocking_check(evidence_checks) or _has_blocking_source_refetch(source_refetch_checks) or claim_evidence_check["check_status"] in {"failed", "repair_required"}:
        status = "failed"
        basis = _blocking_check_basis(evidence_checks, source_refetch_checks, claim_evidence_check)
    elif claim.get("requires_numeric_verification") is True or claim["claim_type"] == "derived_numeric_candidate":
        status = "requires_numeric_verification"
        basis = "Usage gate blocks uncaveated financial conclusion until deterministic numeric verification passes."
    elif claim.get("requires_human_review") is True and claim.get("support_level") == "needs_review":
        status = "requires_human_review"
        basis = "Claim requires human review before certification."
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
    next_workflow_action = _next_workflow_action(status, caveats, repair_actions)
    return {
        "claim_certification_id": f"CC-{claim['claim_id'].split('-')[-1]}",
        "claim_id": claim["claim_id"],
        "claim_type": claim["claim_type"],
        "claim_statement": claim["claim_statement"],
        "certification_status": status,
        "certification_basis": basis,
        "supporting_evidence_record_ids": claim["supporting_evidence_record_ids"],
        "related_source_gap_ids": claim["related_source_gap_ids"],
        "evidence_check_status": _aggregate_check_status(evidence_checks),
        "source_refetch_check_status": _aggregate_source_refetch_status(source_refetch_checks),
        "claim_evidence_check_status": claim_evidence_check["check_status"],
        "usage_check_status": usage_check["usage_check_status"],
        "allowed_downstream_uses": usage_check["allowed_downstream_uses"],
        "blocked_downstream_uses": usage_check["blocked_downstream_uses"],
        "required_caveats": sorted(set(caveats)),
        "next_workflow_action": next_workflow_action,
        "repair_actions": repair_actions,
        "citation_check_status": _compat_citation_status(claim, claim_evidence_check),
        "temporal_check_status": temporal_result["verification_status"],
        "numeric_check_status": "not_applicable",
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
        "evidence_check_results",
        "source_refetch_check_results",
        "claim_evidence_check_results",
        "usage_check_results",
        "numeric_verification_results",
        "citation_verification_results",
        "temporal_verification_results",
        "analysis_gate_summary",
        "report_gate_summary",
        "recommendation_gate_summary",
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
        if "evidence_check_status" not in cert or "source_refetch_check_status" not in cert or "claim_evidence_check_status" not in cert:
            raise CertificationError(f"claim certification missing check status: {cert['claim_id']}")
        for field in ("usage_check_status", "allowed_downstream_uses", "blocked_downstream_uses", "required_caveats", "next_workflow_action", "repair_actions"):
            if field not in cert:
                raise CertificationError(f"claim certification missing usage field {field}: {cert['claim_id']}")
        if cert["next_workflow_action"] not in NEXT_WORKFLOW_ACTIONS:
            raise CertificationError(f"invalid next_workflow_action: {cert['claim_id']}")
        for action in cert["repair_actions"]:
            target = action.get("target")
            if target not in {"M2_source_retrieval", "M4_claim_evidence_graph", "M5_numeric_verification", "human_review", "block_pipeline_until_structure_repaired"}:
                raise CertificationError(f"invalid repair_action target: {cert['claim_id']} -> {target}")
            if "_or_" in target:
                raise CertificationError(f"mixed repair_action target not allowed: {cert['claim_id']} -> {target}")
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


def _combine_repair_actions(
    evidence_checks: list[dict[str, Any]],
    source_refetch_checks: list[dict[str, Any]],
    claim_evidence_check: dict[str, Any],
    usage_check: dict[str, Any],
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for check in evidence_checks:
        for action in check.get("repair_actions", []):
            actions.append(_normalize_repair_action(action, "evidence_check", check.get("evidence_record_id")))
    for check in source_refetch_checks:
        for action in check.get("repair_actions", []):
            actions.append(_normalize_repair_action(action, "source_refetch_check", check.get("evidence_record_id")))
    for action in claim_evidence_check.get("repair_actions", []):
        actions.append(_normalize_repair_action(action, "claim_evidence_check", claim_evidence_check.get("claim_id")))
    for action in usage_check.get("repair_actions", []):
        actions.append(_normalize_repair_action(action, "usage_check", usage_check.get("claim_id")))
    return _dedupe_action_dicts(actions)


def _normalize_repair_action(action: dict[str, Any], source_check: str, source_id: Any) -> dict[str, str]:
    return {
        "target": str(action.get("target") or "block_pipeline_until_structure_repaired"),
        "action": str(action.get("action") or "repair_structure"),
        "reason": str(action.get("reason") or "Repair required before downstream use."),
        "source_check": source_check,
        "source_id": str(source_id or ""),
    }


def _dedupe_action_dicts(actions: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    deduped = []
    for action in actions:
        key = (action["target"], action["action"], action["reason"], action["source_check"], action["source_id"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped


def _next_workflow_action(status: str, caveats: list[str], repair_actions: list[dict[str, str]]) -> str:
    if status == "certified_with_caveat" or (status == "certified" and caveats):
        return "send_to_M6_with_caveat"
    if status == "certified":
        return "send_to_M6_analysis"
    targets = {action["target"] for action in repair_actions}
    if "M5_numeric_verification" in targets:
        return "route_to_M5_numeric_verification"
    if "M2_source_retrieval" in targets:
        return "return_to_M2_source_retrieval"
    if "M4_claim_evidence_graph" in targets:
        return "return_to_M4_claim_rewrite"
    if "human_review" in targets:
        return "route_to_human_review"
    if repair_actions:
        return "block_pipeline_until_structure_repaired"
    if status == "requires_numeric_verification":
        return "route_to_M5_numeric_verification"
    if status == "requires_human_review":
        return "route_to_human_review"
    return "block_pipeline_until_structure_repaired"


def _build_analysis_gate_summary(claim_certifications: list[dict[str, Any]]) -> dict[str, Any]:
    allowed_claim_ids = []
    caveated_claim_ids = []
    blocked_claim_ids = []
    blocking_reasons = []
    for cert in claim_certifications:
        claim_id = cert["claim_id"]
        if cert["next_workflow_action"] == "send_to_M6_analysis":
            allowed_claim_ids.append(claim_id)
        elif cert["next_workflow_action"] == "send_to_M6_with_caveat":
            caveated_claim_ids.append(claim_id)
        else:
            blocked_claim_ids.append(claim_id)
            blocking_reasons.extend(_blocking_reasons_for_claim(cert, "analysis"))
    return {
        "analysis_allowed_claim_ids": allowed_claim_ids,
        "analysis_caveated_claim_ids": caveated_claim_ids,
        "analysis_blocked_claim_ids": blocked_claim_ids,
        "analysis_blocking_reasons": _ordered_unique(blocking_reasons),
    }


def _build_report_gate_summary(claim_certifications: list[dict[str, Any]]) -> dict[str, Any]:
    allowed_claim_ids = []
    caveated_claim_ids = []
    blocked_claim_ids = []
    blocking_reasons = []
    for cert in claim_certifications:
        claim_id = cert["claim_id"]
        report_allowed = REPORT_ASSERTION_USE in cert.get("allowed_downstream_uses", [])
        report_blocked = REPORT_ASSERTION_USE in cert.get("blocked_downstream_uses", []) or cert["certification_status"] not in {"certified", "certified_with_caveat"}
        if report_blocked:
            blocked_claim_ids.append(claim_id)
            blocking_reasons.extend(_blocking_reasons_for_claim(cert, REPORT_ASSERTION_USE))
        elif report_allowed and (cert["certification_status"] == "certified_with_caveat" or cert.get("required_caveats") or cert.get("caveats")):
            caveated_claim_ids.append(claim_id)
        elif report_allowed:
            allowed_claim_ids.append(claim_id)
    return {
        "report_allowed_claim_ids": allowed_claim_ids,
        "report_caveated_claim_ids": caveated_claim_ids,
        "report_blocked_claim_ids": blocked_claim_ids,
        "report_blocking_reasons": _ordered_unique(blocking_reasons),
    }


def _build_recommendation_gate_summary(claim_certifications: list[dict[str, Any]]) -> dict[str, Any]:
    supporting_claim_ids = []
    blocked_claim_ids = []
    blocking_reasons = []
    human_review_required_claim_ids = []
    for cert in claim_certifications:
        claim_id = cert["claim_id"]
        blocked_uses = set(cert.get("blocked_downstream_uses", []))
        requires_human_review = bool(cert.get("requires_human_review")) or cert.get("next_workflow_action") == "route_to_human_review"
        recommendation_blocked = bool(blocked_uses.intersection(RECOMMENDATION_BLOCKING_USES)) or requires_human_review or cert["certification_status"] not in {"certified", "certified_with_caveat"}
        if requires_human_review:
            human_review_required_claim_ids.append(claim_id)
        if recommendation_blocked:
            blocked_claim_ids.append(claim_id)
            blocking_reasons.extend(_blocking_reasons_for_claim(cert, "recommendation"))
        else:
            supporting_claim_ids.append(claim_id)
    return {
        "recommendation_allowed": bool(supporting_claim_ids) and not blocked_claim_ids,
        "recommendation_supporting_claim_ids": supporting_claim_ids,
        "recommendation_blocked_claim_ids": blocked_claim_ids,
        "recommendation_blocking_reasons": _ordered_unique(blocking_reasons),
        "human_review_required_claim_ids": human_review_required_claim_ids,
    }


def _blocking_reasons_for_claim(cert: dict[str, Any], downstream_use: str) -> list[str]:
    reasons = []
    for action in cert.get("repair_actions", []):
        reasons.append(f"{cert['claim_id']}: {action['reason']}")
    if not reasons:
        reasons.append(f"{cert['claim_id']}: {downstream_use} blocked by {cert['certification_status']} certification status.")
    return reasons


def _aggregate_check_status(checks: list[dict[str, Any]]) -> str:
    statuses = {check["check_status"] for check in checks}
    if "failed" in statuses:
        return "failed"
    if "repair_required" in statuses:
        return "repair_required"
    if "passed_with_caveat" in statuses:
        return "passed_with_caveat"
    if "passed" in statuses:
        return "passed"
    return "not_applicable"


def _aggregate_source_refetch_status(checks: list[dict[str, Any]]) -> str:
    statuses = {check["refetch_status"] for check in checks}
    quote_statuses = {check["quote_match_status"] for check in checks}
    if "failed" in statuses or "not_matched" in quote_statuses:
        return "failed"
    if "provider_unavailable" in statuses:
        return "provider_unavailable"
    if "text_unavailable" in statuses:
        return "text_unavailable"
    if "verified" in statuses:
        return "verified"
    return "not_applicable"


def _has_blocking_check(checks: list[dict[str, Any]]) -> bool:
    return any(check["check_status"] in {"failed", "repair_required"} for check in checks)


def _has_blocking_source_refetch(checks: list[dict[str, Any]]) -> bool:
    return any(check["refetch_status"] in {"failed", "provider_unavailable"} or check["quote_match_status"] == "not_matched" for check in checks)


def _check_caveats(checks: list[dict[str, Any]]) -> list[str]:
    caveats = []
    for check in checks:
        caveats.extend(check.get("required_caveats", []))
    return caveats


def _source_refetch_caveats(checks: list[dict[str, Any]]) -> list[str]:
    caveats = []
    for check in checks:
        if check["refetch_status"] == "text_unavailable":
            caveats.append(f"Source refetch text unavailable for {check['evidence_record_id']}; do not treat as independently quote-verified.")
        if check["quote_match_status"] == "weak_match":
            caveats.append(f"Source refetch weak quote match for {check['evidence_record_id']}; preserve wording caveat.")
    return caveats


def _blocking_check_basis(
    evidence_checks: list[dict[str, Any]],
    source_refetch_checks: list[dict[str, Any]],
    claim_evidence_check: dict[str, Any],
) -> str:
    reasons = []
    for check in evidence_checks:
        if check["check_status"] in {"failed", "repair_required"}:
            reasons.extend(check.get("blocking_reasons", []))
            reasons.extend(action.get("reason", "") for action in check.get("repair_actions", []))
    for check in source_refetch_checks:
        if check["refetch_status"] in {"failed", "provider_unavailable"} or check["quote_match_status"] == "not_matched":
            reasons.extend(check.get("blocking_reasons", []))
            reasons.extend(action.get("reason", "") for action in check.get("repair_actions", []))
    if claim_evidence_check["check_status"] in {"failed", "repair_required"}:
        reasons.extend(claim_evidence_check.get("blocking_reasons", []))
        reasons.extend(action.get("reason", "") for action in claim_evidence_check.get("repair_actions", []))
    unique_reasons = _ordered_unique([reason for reason in reasons if reason])
    if unique_reasons:
        return "Evidence or claim-evidence gate failed: " + "; ".join(unique_reasons)
    return "Evidence or claim-evidence gate requires repair before certification."


def _build_compat_citation_results(graph: dict[str, Any], claim_evidence_check_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks_by_claim_id = {result["claim_id"]: result for result in claim_evidence_check_results}
    results = []
    for index, claim in enumerate(graph["claim_nodes"], start=1):
        check = checks_by_claim_id[claim["claim_id"]]
        results.append(
            {
                "citation_check_id": f"CV-{index:03d}",
                "claim_id": claim["claim_id"],
                "verification_status": _compat_citation_status(claim, check),
                "supporting_edge_ids": [],
                "supporting_evidence_record_ids": list(claim.get("supporting_evidence_record_ids", [])),
                "source_ids": sorted(set(claim.get("supporting_source_ids", []))),
                "source_tiers": sorted(set(claim.get("source_tiers", []))),
                "raw_evidence_ids": sorted(set(claim.get("supporting_raw_evidence_ids", []))),
                "provenance_fields_present": bool(claim.get("supporting_evidence_record_ids")),
                "forbidden_source_markers_detected": [],
                "caveat": "Compatibility citation status derived from claim-evidence gate; legacy citation verifier was not run.",
            }
        )
    return results


def _compat_citation_status(claim: dict[str, Any], claim_evidence_check: dict[str, Any]) -> str:
    if claim.get("support_level") in {"gap_only", "unsupported"} or not claim.get("supporting_evidence_record_ids"):
        return "not_applicable"
    if claim_evidence_check["check_status"] in {"failed", "repair_required"}:
        return "failed"
    return "passed"


def _build_compat_temporal_results(graph: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for index, claim in enumerate(graph["claim_nodes"], start=1):
        status, caveat = _compat_temporal_status(claim)
        results.append(
            {
                "temporal_check_id": f"TV-{index:03d}",
                "claim_id": claim["claim_id"],
                "verification_status": status,
                "temporal_scope": claim.get("temporal_scope", ""),
                "permitted_use": claim.get("permitted_use", ""),
                "supporting_time_relations": [claim.get("evidence_time_relation_to_decision_date")]
                if claim.get("evidence_time_relation_to_decision_date")
                else [],
                "hindsight_leakage_warning_preserved": bool(claim.get("hindsight_leakage_warning")),
                "caveat": caveat,
            }
        )
    return results


def _compat_temporal_status(claim: dict[str, Any]) -> tuple[str, str]:
    temporal_scope = claim.get("temporal_scope")
    permitted_use = claim.get("permitted_use")
    warning_text = str(claim.get("hindsight_leakage_warning", ""))
    warning_preserved = bool(warning_text)
    if temporal_scope == "source_gap":
        return "not_applicable", "Source-gap claim has no evidence timing and cannot be certified from evidence."
    if temporal_scope in {"post_decision", "retrospective"}:
        if permitted_use == "ex_ante_deal_evaluation":
            return "failed", "Post-decision or retrospective evidence cannot support ex-ante buyer decision claims."
        if not warning_preserved:
            return "failed", "Hindsight warning is missing for post-decision or retrospective evidence."
        return "passed_with_caveat", "Evidence may support retrospective validation only; preserve a retrospective/source-limit caveat and do not word it as ex-ante buyer decision support."
    if "mixed temporal support" in warning_text.lower():
        return "passed_with_caveat", "Mixed temporal support requires explicit retrospective/source-limit caveat even when anchored to decision-time transaction verification."
    if temporal_scope == "at_decision" and permitted_use != "transaction_terms_verification":
        return "passed_with_caveat", "At-decision evidence is not being used for transaction_terms_verification; preserve narrow wording."
    return "passed", "Temporal scope and permitted use are aligned."


def _ordered_unique(values: list[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        if value in seen or value in {None, ""}:
            continue
        seen.add(value)
        unique.append(value)
    return unique


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
    evidence_check_results: list[dict[str, Any]],
    source_refetch_check_results: list[dict[str, Any]],
    claim_evidence_check_results: list[dict[str, Any]],
    usage_check_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        _summary_check("VC-001", "evidence", evidence_check_results, "check_status"),
        _summary_check("VC-002", "source_refetch", source_refetch_check_results, "refetch_status"),
        _summary_check("VC-003", "claim_evidence", claim_evidence_check_results, "check_status"),
        _summary_check("VC-004", "usage", usage_check_results, "usage_check_status"),
        _summary_check("VC-005", "citation_compat", citation_results, "verification_status"),
        _summary_check("VC-006", "temporal_compat", temporal_results, "verification_status"),
        _summary_check("VC-007", "numeric_compat", numeric_results, "verification_status"),
    ]


def _summary_check(check_id: str, check_type: str, results: list[dict[str, Any]], status_key: str) -> dict[str, Any]:
    statuses = Counter(result[status_key] for result in results)
    failed = statuses.get("failed", 0)
    provider_unavailable = statuses.get("provider_unavailable", 0)
    repair_required = statuses.get("repair_required", 0)
    blocked = statuses.get("blocked", 0)
    text_unavailable = statuses.get("text_unavailable", 0)
    status = "failed" if failed else "repair_required" if repair_required or blocked or provider_unavailable else "passed_with_caveats" if text_unavailable or any(key.endswith("caveat") for key in statuses) else "passed"
    return {
        "verification_check_id": check_id,
        "check_type": check_type,
        "check_status": status,
        "result_count": len(results),
        "status_counts": dict(statuses),
        "blocking": bool(failed or repair_required or blocked or provider_unavailable),
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
