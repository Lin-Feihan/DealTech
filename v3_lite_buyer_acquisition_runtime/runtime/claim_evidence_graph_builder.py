from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v3_lite_buyer_acquisition_runtime.runtime.source_retrieval import PERMITTED_USES


class ClaimEvidenceGraphError(ValueError):
    pass


GENERIC_FACT_TYPES = {
    "transaction_background",
    "transaction_terms",
    "transaction_timing",
    "transaction_document_date",
    "transaction_parties",
    "transaction_consideration",
    "contingent_consideration",
    "milestone_economics",
    "milestone_payment",
    "financing_or_payment_mechanics",
    "entity_identity",
    "entity_lineage",
    "asset_or_product_identity",
    "scientific_asset",
    "asset_lineage",
    "ownership_or_governance",
    "management_or_key_person",
    "intellectual_property",
    "regulatory_or_clinical",
    "financial_performance",
    "valuation_input",
    "synergy_or_value_creation",
    "market_or_competitive_position",
    "legal_or_regulatory_risk",
    "integration_or_operational_risk",
    "source_gap_claim",
    "generic_fact",
    "derived_numeric_candidate",
}
CLAIM_TYPES = GENERIC_FACT_TYPES
SUPPORT_LEVELS = {"source_supported", "partially_supported", "gap_only", "unsupported", "conflicting", "requires_numeric_verification"}
CERTIFICATION_STATUSES = {"uncertified", "pending_verification", "failed_precheck", "not_applicable"}
EDGE_TYPES = {"supports", "partially_supports", "contextualizes", "contradicts", "requires_verification", "blocked_by_source_gap"}
EVIDENCE_RECORD_REQUIRED_FIELDS = {
    "canonical_fact_key",
    "canonical_fact_type",
    "source_ids",
    "support_status",
    "evidence_time_relation_to_decision_date",
    "permitted_use",
    "downstream_use_warning",
}


def load_json_artifact(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise ClaimEvidenceGraphError(f"Artifact not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ClaimEvidenceGraphError(f"Invalid JSON artifact at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ClaimEvidenceGraphError(f"Artifact at {path} must be a JSON object.")
    return payload


def evidence_repository_source_id(evidence_repository: dict[str, Any]) -> str:
    return f"REPO-{evidence_repository['case_id']}-{evidence_repository['created_at']}"


def validate_evidence_repository_for_m4(evidence_repository: Any) -> None:
    if not isinstance(evidence_repository, dict):
        raise ClaimEvidenceGraphError("evidence_repository must be an object.")
    required_top_level = {
        "case_id",
        "generated_artifact",
        "source_bounded",
        "evidence_coverage_status",
        "evidence_records",
        "source_gaps",
    }
    missing = sorted(field for field in required_top_level if field not in evidence_repository)
    if missing:
        raise ClaimEvidenceGraphError(f"M4 evidence_repository missing required field(s): {', '.join(missing)}")
    if evidence_repository.get("generated_artifact") != "evidence_repository.json":
        raise ClaimEvidenceGraphError("M4 requires generated_artifact evidence_repository.json.")
    if evidence_repository.get("source_bounded") is not True:
        raise ClaimEvidenceGraphError("M4 requires source_bounded evidence_repository input.")
    if not evidence_repository.get("evidence_coverage_status"):
        raise ClaimEvidenceGraphError("M4 requires evidence_coverage_status.")
    if not isinstance(evidence_repository.get("evidence_records"), list):
        raise ClaimEvidenceGraphError("M4 requires evidence_records array.")
    if not isinstance(evidence_repository.get("source_gaps"), list):
        raise ClaimEvidenceGraphError("M4 requires source_gaps array.")
    for record in evidence_repository["evidence_records"]:
        missing_record_fields = sorted(field for field in EVIDENCE_RECORD_REQUIRED_FIELDS if not record.get(field))
        if missing_record_fields:
            raise ClaimEvidenceGraphError(
                f"M4 evidence_record missing required field(s): {', '.join(missing_record_fields)}"
            )
        if record["permitted_use"] not in PERMITTED_USES:
            raise ClaimEvidenceGraphError(f"Invalid permitted_use for evidence_record {record.get('evidence_record_id', '<unknown>')}")
        if record["evidence_time_relation_to_decision_date"] in {"post_decision", "retrospective"} and record["permitted_use"] == "ex_ante_deal_evaluation":
            raise ClaimEvidenceGraphError(
                f"Post-decision or retrospective evidence_record cannot be ex_ante_deal_evaluation: {record.get('evidence_record_id', '<unknown>')}"
            )


def build_claim_evidence_graph(evidence_repository: dict[str, Any]) -> dict[str, Any]:
    validate_evidence_repository_for_m4(evidence_repository)
    case_id = evidence_repository["case_id"]
    claim_nodes: list[dict[str, Any]] = []
    evidence_edges: list[dict[str, Any]] = []
    gap_nodes = _build_gap_nodes(evidence_repository["source_gaps"])

    if evidence_repository.get("candidate_claims_from_research"):
        records_by_id = {record["evidence_record_id"]: record for record in evidence_repository["evidence_records"]}
        candidate_claim_nodes, candidate_evidence_edges = _build_claim_nodes_from_research_candidates(
            case_id=case_id,
            candidate_claims=evidence_repository["candidate_claims_from_research"],
            claim_evidence_links=evidence_repository.get("candidate_claim_evidence_links_from_research", []),
            records_by_id=records_by_id,
        )
        claim_nodes.extend(candidate_claim_nodes)
        evidence_edges.extend(candidate_evidence_edges)
    else:
        for record in evidence_repository["evidence_records"]:
            if record["support_status"] not in {"source_supported", "partially_supported", "conflicting"}:
                continue
            claim = _build_claim_node_from_record(case_id, len(claim_nodes) + 1, record)
            claim_nodes.append(claim)
            evidence_edges.append(_build_evidence_edge(len(evidence_edges) + 1, claim, record))

    for gap_node in gap_nodes:
        claim_nodes.append(_build_gap_claim_node(case_id, len(claim_nodes) + 1, gap_node))

    graph = {
        "case_id": case_id,
        "generated_artifact": "claim_evidence_graph.json",
        "stage": "M4_claim_evidence_graph",
        "source_bounded": True,
        "evidence_coverage_status": evidence_repository["evidence_coverage_status"],
        "created_from_evidence_repository_id": evidence_repository_source_id(evidence_repository),
        "created_at": _now_utc_iso(),
        "claim_nodes": claim_nodes,
        "evidence_edges": evidence_edges,
        "gap_nodes": gap_nodes,
        "graph_quality_summary": _build_graph_quality_summary(claim_nodes, evidence_edges, gap_nodes),
    }
    validate_claim_evidence_graph(graph)
    return graph


def validate_claim_evidence_graph(graph: Any) -> None:
    if not isinstance(graph, dict):
        raise ClaimEvidenceGraphError("claim_evidence_graph must be an object.")
    required_top_level = {
        "case_id",
        "generated_artifact",
        "stage",
        "source_bounded",
        "evidence_coverage_status",
        "created_from_evidence_repository_id",
        "created_at",
        "claim_nodes",
        "evidence_edges",
        "gap_nodes",
        "graph_quality_summary",
    }
    missing = sorted(field for field in required_top_level if field not in graph)
    if missing:
        raise ClaimEvidenceGraphError(f"Missing claim_evidence_graph top-level field(s): {', '.join(missing)}")
    if graph["generated_artifact"] != "claim_evidence_graph.json":
        raise ClaimEvidenceGraphError("generated_artifact must be claim_evidence_graph.json.")
    if graph["stage"] != "M4_claim_evidence_graph":
        raise ClaimEvidenceGraphError("stage must be M4_claim_evidence_graph.")
    if graph["source_bounded"] is not True:
        raise ClaimEvidenceGraphError("claim_evidence_graph must remain source_bounded.")
    claim_ids = {claim["claim_id"] for claim in graph["claim_nodes"]}
    evidence_record_ids = {
        evidence_record_id
        for claim in graph["claim_nodes"]
        for evidence_record_id in claim["supporting_evidence_record_ids"] + claim["contradicting_evidence_record_ids"]
    }
    for claim in graph["claim_nodes"]:
        _validate_claim_node(claim)
    for edge in graph["evidence_edges"]:
        _validate_evidence_edge(edge, claim_ids, evidence_record_ids)
    for gap_node in graph["gap_nodes"]:
        _validate_gap_node(gap_node)
    _validate_graph_quality_summary(graph["graph_quality_summary"])


def _build_claim_node_from_record(case_id: str, index: int, record: dict[str, Any]) -> dict[str, Any]:
    formula = _formula_from_record(record)
    support_level = "requires_numeric_verification" if formula else _support_level_from_record(record)
    claim_type = "derived_numeric_candidate" if formula else _claim_type_from_record(record)
    temporal_scope = record["evidence_time_relation_to_decision_date"]
    requires_human_review = support_level in {"partially_supported", "conflicting", "requires_numeric_verification"} or temporal_scope in {"post_decision", "retrospective"}
    claim = {
        "claim_id": f"CL-{index:03d}",
        "case_id": case_id,
        "created_from_generic_fallback": True,
        "claim_type": claim_type,
        "claim_statement": _claim_statement(claim_type, formula),
        "claim_scope": _claim_scope(claim_type, formula),
        "temporal_scope": temporal_scope,
        "permitted_use": record["permitted_use"],
        "supporting_evidence_record_ids": [record["evidence_record_id"]],
        "contradicting_evidence_record_ids": [],
        "related_source_gap_ids": [],
        "support_level": support_level,
        "certification_status": "pending_verification",
        "requires_numeric_verification": bool(formula),
        "requires_human_review": requires_human_review,
        "confidence_preliminary": record["confidence_preliminary"],
        "supporting_source_ids": record.get("source_ids", []),
        "supporting_raw_evidence_ids": record.get("raw_evidence_ids", []),
        "source_tiers": record.get("source_tiers", []),
        "evidence_time_relation_to_decision_date": temporal_scope,
        "evidence_record_support_status": record["support_status"],
        "canonical_fact_key": record["canonical_fact_key"],
        "canonical_fact_type": record["canonical_fact_type"],
        "downstream_use_warning": _claim_downstream_warning(record, formula),
        "hindsight_leakage_warning": record["hindsight_leakage_warning"],
    }
    if formula:
        claim["numeric_formula"] = formula
    return claim


def _build_claim_nodes_from_research_candidates(
    case_id: str,
    candidate_claims: list[dict[str, Any]],
    claim_evidence_links: list[dict[str, Any]],
    records_by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    links_by_candidate_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in claim_evidence_links:
        links_by_candidate_id[link["candidate_claim_id"]].append(link)

    claim_nodes = []
    evidence_edges = []
    for index, candidate_claim in enumerate(candidate_claims, start=1):
        candidate_links = links_by_candidate_id.get(candidate_claim["candidate_claim_id"], [])
        claim = _build_claim_node_from_candidate(case_id, index, candidate_claim, candidate_links, records_by_id)
        claim_nodes.append(claim)
        for link in candidate_links:
            for evidence_record_id in link.get("mapped_evidence_record_ids", []):
                if evidence_record_id not in records_by_id:
                    raise ClaimEvidenceGraphError(f"candidate claim link maps to unknown evidence_record_id: {evidence_record_id}")
                record = records_by_id[evidence_record_id]
                evidence_edges.append(
                    _build_evidence_edge(
                        len(evidence_edges) + 1,
                        claim,
                        record,
                        edge_type=link["link_type"],
                        notes=link["rationale"],
                    )
                )
    return claim_nodes, evidence_edges


def _build_claim_node_from_candidate(
    case_id: str,
    index: int,
    candidate_claim: dict[str, Any],
    claim_evidence_links: list[dict[str, Any]],
    records_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    supporting_record_ids = _candidate_supporting_record_ids(claim_evidence_links)
    contradicting_record_ids = _candidate_contradicting_record_ids(claim_evidence_links)
    linked_record_ids = _ordered_unique([*supporting_record_ids, *contradicting_record_ids])
    linked_records = [records_by_id[record_id] for record_id in linked_record_ids if record_id in records_by_id]
    support_level = _candidate_support_level(candidate_claim, claim_evidence_links, supporting_record_ids, contradicting_record_ids)
    certification_status = "pending_verification" if linked_record_ids and support_level not in {"gap_only", "unsupported"} else "failed_precheck"
    if support_level == "gap_only":
        certification_status = "failed_precheck"
    requires_human_review = (
        bool(candidate_claim.get("requires_human_review"))
        or support_level in {"partially_supported", "conflicting", "requires_numeric_verification", "gap_only", "unsupported"}
        or candidate_claim.get("temporal_scope") in {"post_decision", "retrospective"}
    )
    claim = {
        "claim_id": f"CL-{index:03d}",
        "case_id": case_id,
        "created_from_candidate_claim_id": candidate_claim["candidate_claim_id"],
        "claim_type": _claim_type_from_candidate(candidate_claim),
        "claim_statement": candidate_claim["claim_statement"],
        "claim_scope": candidate_claim["claim_scope"],
        "temporal_scope": candidate_claim["temporal_scope"],
        "permitted_use": candidate_claim["permitted_use"],
        "supporting_evidence_record_ids": supporting_record_ids if support_level not in {"gap_only", "unsupported"} else [],
        "contradicting_evidence_record_ids": contradicting_record_ids,
        "related_source_gap_ids": candidate_claim.get("related_source_gap_ids", []),
        "support_level": support_level,
        "certification_status": certification_status,
        "requires_numeric_verification": bool(candidate_claim.get("requires_numeric_verification")) or any(link["link_type"] == "requires_verification" for link in claim_evidence_links),
        "requires_human_review": requires_human_review,
        "confidence_preliminary": _confidence(candidate_claim.get("confidence_preliminary", "low")),
        "supporting_source_ids": _ordered_unique(source_id for record in linked_records for source_id in record.get("source_ids", [])),
        "supporting_raw_evidence_ids": _ordered_unique(raw_id for record in linked_records for raw_id in record.get("raw_evidence_ids", [])),
        "source_tiers": _ordered_unique(tier for record in linked_records for tier in record.get("source_tiers", [])),
        "downstream_use_warning": _candidate_downstream_warning(candidate_claim, support_level, claim_evidence_links),
        "hindsight_leakage_warning": _candidate_hindsight_warning(candidate_claim, linked_records),
    }
    if candidate_claim.get("numeric_formula"):
        claim["numeric_formula"] = candidate_claim["numeric_formula"]
    return claim


def _candidate_supporting_record_ids(claim_evidence_links: list[dict[str, Any]]) -> list[str]:
    return _ordered_unique(
        record_id
        for link in claim_evidence_links
        if link["link_type"] in {"supports", "partially_supports", "contextualizes", "requires_verification"}
        for record_id in link.get("mapped_evidence_record_ids", [])
    )


def _candidate_contradicting_record_ids(claim_evidence_links: list[dict[str, Any]]) -> list[str]:
    return _ordered_unique(
        record_id
        for link in claim_evidence_links
        if link["link_type"] == "contradicts"
        for record_id in link.get("mapped_evidence_record_ids", [])
    )


def _candidate_support_level(
    candidate_claim: dict[str, Any],
    claim_evidence_links: list[dict[str, Any]],
    supporting_record_ids: list[str],
    contradicting_record_ids: list[str],
) -> str:
    if not supporting_record_ids and not contradicting_record_ids:
        return "gap_only" if candidate_claim.get("related_source_gap_ids") else "unsupported"
    if contradicting_record_ids:
        return "conflicting"
    if bool(candidate_claim.get("requires_numeric_verification")) or any(link["link_type"] == "requires_verification" for link in claim_evidence_links):
        return "requires_numeric_verification"
    if any(link["link_type"] in {"partially_supports", "contextualizes"} for link in claim_evidence_links):
        return "partially_supported"
    return "source_supported"


def _claim_type_from_candidate(candidate_claim: dict[str, Any]) -> str:
    claim_type = _safe_key(str(candidate_claim.get("claim_type") or "generic_fact"))
    return claim_type if claim_type in CLAIM_TYPES else "generic_fact"


def _confidence(value: str) -> str:
    return value if value in {"low", "medium", "high"} else "low"


def _candidate_downstream_warning(candidate_claim: dict[str, Any], support_level: str, claim_evidence_links: list[dict[str, Any]]) -> str:
    base = "Candidate claim from external research package only. M4 maps evidence but does not certify, recommend, value, or generate report assertions."
    if support_level in {"gap_only", "unsupported"}:
        base = f"{base} This claim is blocked from report use until source repair supplies mapped evidence and M5 verifies it."
    if any(link.get("mapping_status") == "evidence_item_not_in_repository_requires_repair" for link in claim_evidence_links):
        base = f"{base} One or more cited external evidence items did not survive source-bounded repository ingestion and require repair."
    warning = str(candidate_claim.get("downstream_use_warning", "")).strip()
    return f"{base} {warning}".strip()


def _candidate_hindsight_warning(candidate_claim: dict[str, Any], linked_records: list[dict[str, Any]]) -> str:
    temporal_scope = candidate_claim.get("temporal_scope")
    record_warnings = _ordered_unique(record.get("hindsight_leakage_warning", "") for record in linked_records if record.get("hindsight_leakage_warning"))
    if temporal_scope in {"post_decision", "retrospective"}:
        return "Hindsight caveat required: post-decision or retrospective candidate claim must not be treated as ex-ante buyer decision support. " + " ".join(record_warnings)
    if record_warnings:
        return " ".join(record_warnings)
    return "Candidate claim has no detected post-decision hindsight warning, but remains uncertified until M5 verification."


def _build_gap_nodes(source_gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gap_nodes = []
    for index, source_gap in enumerate(source_gaps, start=1):
        affected_claim_types = _affected_claim_types_for_gap(source_gap)
        gap_nodes.append(
            {
                "gap_node_id": f"GN-{index:03d}",
                "source_gap_id": source_gap["source_gap_id"],
                "missing_source_need_id": source_gap["missing_source_need_id"],
                "gap_statement": _generic_gap_statement(source_gap, affected_claim_types),
                "affected_claim_types": affected_claim_types,
                "downstream_risk": "Downstream use remains blocked until the missing source need is repaired with source-bounded evidence.",
                "recommended_repair_target": source_gap["recommended_repair_target"],
            }
        )
    return gap_nodes


def _build_gap_claim_node(case_id: str, index: int, gap_node: dict[str, Any]) -> dict[str, Any]:
    claim_type = gap_node["affected_claim_types"][0] if gap_node["affected_claim_types"] else "source_gap_claim"
    if claim_type not in CLAIM_TYPES:
        claim_type = "source_gap_claim"
    return {
        "claim_id": f"CL-{index:03d}",
        "case_id": case_id,
        "claim_type": claim_type,
        "claim_statement": f"Source gap blocks support for a {claim_type} claim area in this buyer-side acquisition case.",
        "claim_scope": "candidate_source_gap_claim",
        "temporal_scope": "source_gap",
        "permitted_use": "gap_tracking",
        "supporting_evidence_record_ids": [],
        "contradicting_evidence_record_ids": [],
        "related_source_gap_ids": [gap_node["source_gap_id"]],
        "support_level": "gap_only",
        "certification_status": "failed_precheck",
        "requires_numeric_verification": False,
        "requires_human_review": True,
        "confidence_preliminary": "low",
        "supporting_source_ids": [],
        "supporting_raw_evidence_ids": [],
        "source_tiers": [],
        "evidence_time_relation_to_decision_date": "source_gap",
        "downstream_use_warning": "Gap-only candidate claim. Do not use as a report assertion until source retrieval repair supplies authoritative evidence and later stages verify it.",
        "hindsight_leakage_warning": "Source gap only: no evidence timing is available; do not treat this as source-supported evidence.",
    }


def _build_evidence_edge(index: int, claim: dict[str, Any], record: dict[str, Any], edge_type: str | None = None, notes: str | None = None) -> dict[str, Any]:
    resolved_edge_type = edge_type or _edge_type_from_claim(claim)
    return {
        "edge_id": f"EDGE-{index:03d}",
        "claim_id": claim["claim_id"],
        "evidence_record_id": record["evidence_record_id"],
        "edge_type": resolved_edge_type,
        "support_strength": _support_strength_from_record(record, resolved_edge_type),
        "temporal_alignment": _temporal_alignment(record),
        "source_tier_basis": record["strongest_source_tier"],
        "notes": notes or _edge_notes(claim, record, resolved_edge_type),
    }


def _build_graph_quality_summary(claim_nodes: list[dict[str, Any]], evidence_edges: list[dict[str, Any]], gap_nodes: list[dict[str, Any]]) -> dict[str, Any]:
    support_counts = Counter(claim["support_level"] for claim in claim_nodes)
    temporal_distribution = Counter(claim["temporal_scope"] for claim in claim_nodes)
    return {
        "claim_node_count": len(claim_nodes),
        "evidence_edge_count": len(evidence_edges),
        "gap_node_count": len(gap_nodes),
        "source_supported_claim_count": support_counts["source_supported"],
        "partially_supported_claim_count": support_counts["partially_supported"],
        "gap_or_unsupported_claim_count": support_counts["gap_only"] + support_counts["unsupported"],
        "claims_requiring_numeric_verification_count": sum(1 for claim in claim_nodes if claim["requires_numeric_verification"]),
        "claims_requiring_human_review_count": sum(1 for claim in claim_nodes if claim["requires_human_review"]),
        "temporal_scope_distribution": dict(temporal_distribution),
        "notes_for_next_stage": [
            "All M4 claim nodes are uncertified, pending verification, failed precheck, or not applicable; M4 does not certify claims.",
            "M5 must carry forward temporal and hindsight controls before any certification or report use.",
            "Gap-only claims must remain blocked until source retrieval repairs the missing authoritative sources.",
            "Numeric verification is only required when an evidence record supplies an explicit formula.",
        ],
    }


def _claim_type_from_record(record: dict[str, Any]) -> str:
    claim_type = _safe_key(str(record.get("canonical_fact_type") or record.get("evidence_category") or "generic_fact"))
    return claim_type if claim_type in CLAIM_TYPES else "generic_fact"


def _claim_statement(claim_type: str, formula: dict[str, Any] | None) -> str:
    if formula:
        return "Generic fallback claim: source-bounded evidence provides an explicit numeric formula requiring arithmetic verification for this buyer-side acquisition case."
    return f"Generic fallback claim: source-bounded evidence supports a {claim_type} fact for this buyer-side acquisition case."


def _claim_scope(claim_type: str, formula: dict[str, Any] | None) -> str:
    if formula:
        return "candidate_numeric_formula_claim"
    return f"candidate_{claim_type}_claim"


def _formula_from_record(record: dict[str, Any]) -> dict[str, Any] | None:
    attributes = record.get("structured_attributes") or {}
    formula = attributes.get("numeric_formula") or attributes.get("calculation_formula") or attributes.get("formula")
    if isinstance(formula, str) and formula.strip():
        return {"expression": formula.strip()}
    if isinstance(formula, dict) and isinstance(formula.get("expression"), str) and formula["expression"].strip():
        return formula
    return None


def _support_level_from_record(record: dict[str, Any]) -> str:
    if record["support_status"] == "source_supported":
        return "source_supported"
    if record["support_status"] == "partially_supported":
        return "partially_supported"
    if record["support_status"] == "conflicting":
        return "conflicting"
    if record["support_status"] == "source_gap":
        return "gap_only"
    return "unsupported"


def _claim_downstream_warning(record: dict[str, Any], formula: dict[str, Any] | None) -> str:
    base = "Candidate claim only. M4 maps evidence but does not certify, recommend, value, or generate report assertions."
    if formula:
        base = f"{base} Numeric formula must be replayed by M5 before certification."
    return f"{base} {record['downstream_use_warning']} {record['hindsight_leakage_warning']}"


def _affected_claim_types_for_gap(source_gap: dict[str, Any]) -> list[str]:
    claim_types = []
    for fact_type in source_gap.get("affected_fact_types", []):
        mapped = _claim_type_from_gap_fact(str(fact_type))
        if mapped not in claim_types:
            claim_types.append(mapped)
    return claim_types or ["source_gap_claim"]


def _claim_type_from_gap_fact(fact_type: str) -> str:
    normalized = _safe_key(fact_type)
    text = normalized.replace("_", " ")
    if normalized in CLAIM_TYPES:
        return normalized
    if any(term in text for term in ("ownership", "shareholding", "governance", "founder", "director", "proceeds", "cap table")):
        return "ownership_or_governance"
    if any(term in text for term in ("patent", "intellectual", "ip", "asset", "chemistry")):
        return "intellectual_property"
    if any(term in text for term in ("clinical", "regulatory", "approval", "trial")):
        return "regulatory_or_clinical"
    if any(term in text for term in ("consideration", "payment", "value", "price")):
        return "transaction_consideration"
    return "source_gap_claim"


def _generic_gap_statement(source_gap: dict[str, Any], affected_claim_types: list[str]) -> str:
    need_id = source_gap.get("missing_source_need_id", "unknown_source_need")
    affected = ", ".join(affected_claim_types) if affected_claim_types else "source_gap_claim"
    return f"Unresolved source gap for {need_id}; affected generic claim area(s): {affected}."


def _edge_type_from_claim(claim: dict[str, Any]) -> str:
    if claim["support_level"] == "source_supported":
        return "supports"
    if claim["support_level"] == "partially_supported":
        return "partially_supports"
    if claim["support_level"] == "conflicting":
        return "contradicts"
    if claim["support_level"] == "requires_numeric_verification":
        return "requires_verification"
    return "contextualizes"


def _support_strength_from_record(record: dict[str, Any], edge_type: str) -> str:
    if edge_type == "requires_verification":
        return "verification_required"
    if record["confidence_preliminary"] == "high" and record["support_status"] == "source_supported":
        return "strong"
    if record["support_status"] == "source_supported":
        return "medium"
    if record["support_status"] == "partially_supported":
        return "partial"
    return "weak"


def _temporal_alignment(record: dict[str, Any]) -> str:
    relation = record["evidence_time_relation_to_decision_date"]
    if relation == "at_decision":
        return "decision_time_aligned"
    if relation == "pre_decision":
        return "pre_decision_aligned"
    if relation == "post_decision":
        return "post_decision_retrospective"
    if relation == "retrospective":
        return "retrospective_current_context"
    return "unknown_temporal_alignment"


def _edge_notes(claim: dict[str, Any], record: dict[str, Any], edge_type: str) -> str:
    if edge_type == "requires_verification":
        return "Evidence record provides an explicit numeric formula; later numeric verification is required."
    return f"Maps candidate claim to evidence record {record['canonical_fact_key']} with temporal scope {claim['temporal_scope']}."


def _validate_claim_node(claim: dict[str, Any]) -> None:
    required_fields = {
        "claim_id",
        "case_id",
        "claim_type",
        "claim_statement",
        "claim_scope",
        "temporal_scope",
        "permitted_use",
        "supporting_evidence_record_ids",
        "contradicting_evidence_record_ids",
        "related_source_gap_ids",
        "support_level",
        "certification_status",
        "requires_numeric_verification",
        "requires_human_review",
        "confidence_preliminary",
        "downstream_use_warning",
    }
    missing = sorted(field for field in required_fields if field not in claim)
    if missing:
        raise ClaimEvidenceGraphError(f"Missing claim_node field(s): {', '.join(missing)}")
    if claim["claim_type"] not in CLAIM_TYPES:
        raise ClaimEvidenceGraphError(f"Invalid claim_type for {claim['claim_id']}")
    if claim["support_level"] not in SUPPORT_LEVELS:
        raise ClaimEvidenceGraphError(f"Invalid support_level for {claim['claim_id']}")
    if claim["certification_status"] not in CERTIFICATION_STATUSES:
        raise ClaimEvidenceGraphError(f"Invalid certification_status for {claim['claim_id']}")
    if claim["certification_status"] == "certified":
        raise ClaimEvidenceGraphError(f"M4 must not certify claims: {claim['claim_id']}")
    if claim["temporal_scope"] in {"post_decision", "retrospective"} and claim["permitted_use"] == "ex_ante_deal_evaluation":
        raise ClaimEvidenceGraphError(f"Post-decision or retrospective claim cannot be ex_ante_deal_evaluation: {claim['claim_id']}")
    if claim["support_level"] in {"gap_only", "unsupported"} and claim["supporting_evidence_record_ids"]:
        raise ClaimEvidenceGraphError(f"Gap-only/unsupported claim cannot have supporting evidence: {claim['claim_id']}")
    if claim["support_level"] == "requires_numeric_verification" and not claim["requires_numeric_verification"]:
        raise ClaimEvidenceGraphError(f"Numeric verification claim missing flag: {claim['claim_id']}")


def _validate_evidence_edge(edge: dict[str, Any], claim_ids: set[str], evidence_record_ids: set[str]) -> None:
    required_fields = {"edge_id", "claim_id", "evidence_record_id", "edge_type", "support_strength", "temporal_alignment", "source_tier_basis", "notes"}
    missing = sorted(field for field in required_fields if field not in edge)
    if missing:
        raise ClaimEvidenceGraphError(f"Missing evidence_edge field(s): {', '.join(missing)}")
    if edge["claim_id"] not in claim_ids:
        raise ClaimEvidenceGraphError(f"evidence_edge cites unknown claim_id: {edge['claim_id']}")
    if edge["evidence_record_id"] not in evidence_record_ids:
        raise ClaimEvidenceGraphError(f"evidence_edge cites unknown evidence_record_id: {edge['evidence_record_id']}")
    if edge["edge_type"] not in EDGE_TYPES:
        raise ClaimEvidenceGraphError(f"Invalid edge_type for {edge['edge_id']}")


def _validate_gap_node(gap_node: dict[str, Any]) -> None:
    required_fields = {
        "gap_node_id",
        "source_gap_id",
        "missing_source_need_id",
        "gap_statement",
        "affected_claim_types",
        "downstream_risk",
        "recommended_repair_target",
    }
    missing = sorted(field for field in required_fields if field not in gap_node)
    if missing:
        raise ClaimEvidenceGraphError(f"Missing gap_node field(s): {', '.join(missing)}")
    if gap_node["recommended_repair_target"] != "M2_source_retrieval":
        raise ClaimEvidenceGraphError(f"gap_node must recommend M2_source_retrieval: {gap_node['gap_node_id']}")


def _validate_graph_quality_summary(summary: dict[str, Any]) -> None:
    required_fields = {
        "claim_node_count",
        "evidence_edge_count",
        "gap_node_count",
        "source_supported_claim_count",
        "partially_supported_claim_count",
        "gap_or_unsupported_claim_count",
        "claims_requiring_numeric_verification_count",
        "claims_requiring_human_review_count",
        "temporal_scope_distribution",
        "notes_for_next_stage",
    }
    missing = sorted(field for field in required_fields if field not in summary)
    if missing:
        raise ClaimEvidenceGraphError(f"Missing graph_quality_summary field(s): {', '.join(missing)}")


def _ordered_unique(values: Any) -> list[Any]:
    seen = set()
    unique = []
    for value in values:
        if value in seen or value in {None, ""}:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _safe_key(value: str) -> str:
    normalized = []
    previous_was_separator = False
    for character in value.lower():
        if character.isalnum():
            normalized.append(character)
            previous_was_separator = False
        elif not previous_was_separator:
            normalized.append("_")
            previous_was_separator = True
    return "".join(normalized).strip("_") or "generic_fact"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
