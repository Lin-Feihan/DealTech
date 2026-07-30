from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v3_lite_buyer_acquisition_runtime.runtime.source_retrieval import PERMITTED_USES


class ClaimEvidenceGraphError(ValueError):
    pass


CLAIM_TYPES = {
    "transaction_terms",
    "milestone_economics",
    "entity_lineage",
    "scientific_asset",
    "asset_lineage",
    "derived_numeric_candidate",
    "ownership_or_founder_background",
    "personal_proceeds",
    "cap_table",
    "source_gap_claim",
}
SUPPORT_LEVELS = {"source_supported", "partially_supported", "gap_only", "unsupported", "conflicting", "requires_numeric_verification"}
CERTIFICATION_STATUSES = {"uncertified", "pending_verification", "failed_precheck", "not_applicable"}
EDGE_TYPES = {"supports", "partially_supports", "contextualizes", "contradicts", "requires_verification", "blocked_by_source_gap"}
EVIDENCE_RECORD_REQUIRED_FIELDS = {
    "canonical_fact_key",
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
    evidence_records_by_key = {record["canonical_fact_key"]: record for record in evidence_repository["evidence_records"]}
    claim_nodes: list[dict[str, Any]] = []
    evidence_edges: list[dict[str, Any]] = []

    for record in evidence_repository["evidence_records"]:
        claim_spec = _claim_spec_for_evidence_record(record)
        if claim_spec is None:
            continue
        claim = _build_claim_node_from_record(case_id, len(claim_nodes) + 1, record, claim_spec)
        claim_nodes.append(claim)
        evidence_edges.append(_build_evidence_edge(len(evidence_edges) + 1, claim, record))

    derived_claim = _build_derived_180m_candidate(case_id, len(claim_nodes) + 1, evidence_records_by_key)
    if derived_claim is not None:
        claim_nodes.append(derived_claim)
        for evidence_record_id in derived_claim["supporting_evidence_record_ids"]:
            record = next(record for record in evidence_repository["evidence_records"] if record["evidence_record_id"] == evidence_record_id)
            evidence_edges.append(_build_evidence_edge(len(evidence_edges) + 1, derived_claim, record, edge_type="requires_verification"))

    gap_nodes = _build_gap_nodes(evidence_repository["source_gaps"])
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


def _claim_spec_for_evidence_record(record: dict[str, Any]) -> dict[str, str] | None:
    key = record["canonical_fact_key"]
    specs = {
        "acquisition_timing_march_2021": {
            "claim_type": "transaction_terms",
            "claim_statement": "The FronThera transaction was linked to March 2021 timing.",
            "claim_scope": "candidate_transaction_timing_claim",
        },
        "stock_purchase_agreement_date_2021_03_05": {
            "claim_type": "transaction_terms",
            "claim_statement": "The stock purchase agreement was dated March 5, 2021.",
            "claim_scope": "candidate_transaction_document_date_claim",
        },
        "base_initial_consideration_60m": {
            "claim_type": "transaction_terms",
            "claim_statement": "The base initial consideration was $60M.",
            "claim_scope": "candidate_transaction_terms_claim",
        },
        "milestone_consideration_cap_120m": {
            "claim_type": "milestone_economics",
            "claim_statement": "The milestone consideration cap was up to $120M.",
            "claim_scope": "candidate_milestone_terms_claim",
        },
        "milestone_payment_2022_37m": {
            "claim_type": "milestone_economics",
            "claim_statement": "Alumis made or incurred a $37M milestone payment in 2022.",
            "claim_scope": "candidate_retrospective_milestone_outcome_claim",
        },
        "milestone_payment_2024_23m": {
            "claim_type": "milestone_economics",
            "claim_statement": "Alumis made or incurred a $23M milestone payment in 2024.",
            "claim_scope": "candidate_retrospective_milestone_outcome_claim",
        },
        "fl2021_001_to_esker_to_alumis_entity_lineage": {
            "claim_type": "entity_lineage",
            "claim_statement": "FL2021-001 changed to Esker Therapeutics and later Alumis.",
            "claim_scope": "candidate_entity_lineage_claim",
        },
        "esk_001_tyk2_inhibitor": {
            "claim_type": "scientific_asset",
            "claim_statement": "ESK-001 is associated with TYK2 inhibitor asset lineage.",
            "claim_scope": "candidate_scientific_asset_claim",
        },
        "envudeucitinib_formerly_esk_001": {
            "claim_type": "asset_lineage",
            "claim_statement": "Envudeucitinib is associated with the formerly named ESK-001 asset lineage.",
            "claim_scope": "candidate_asset_lineage_claim",
        },
        "alumis_pipeline_current_envudeucitinib": {
            "claim_type": "asset_lineage",
            "claim_statement": "Current Alumis pipeline context associates envudeucitinib with ESK-001/TYK2 asset status.",
            "claim_scope": "candidate_current_pipeline_context_claim",
        },
    }
    return specs.get(key)


def _build_claim_node_from_record(case_id: str, index: int, record: dict[str, Any], claim_spec: dict[str, str]) -> dict[str, Any]:
    support_level = _support_level_from_record(record)
    temporal_scope = record["evidence_time_relation_to_decision_date"]
    requires_human_review = support_level in {"partially_supported", "conflicting"} or temporal_scope in {"post_decision", "retrospective"}
    return {
        "claim_id": f"CL-{index:03d}",
        "case_id": case_id,
        "claim_type": claim_spec["claim_type"],
        "claim_statement": claim_spec["claim_statement"],
        "claim_scope": claim_spec["claim_scope"],
        "temporal_scope": temporal_scope,
        "permitted_use": record["permitted_use"],
        "supporting_evidence_record_ids": [record["evidence_record_id"]],
        "contradicting_evidence_record_ids": [],
        "related_source_gap_ids": [],
        "support_level": support_level,
        "certification_status": "pending_verification",
        "requires_numeric_verification": False,
        "requires_human_review": requires_human_review,
        "confidence_preliminary": record["confidence_preliminary"],
        "downstream_use_warning": _claim_downstream_warning(record),
        "hindsight_leakage_warning": record["hindsight_leakage_warning"],
    }


def _build_derived_180m_candidate(case_id: str, index: int, records_by_key: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    base = records_by_key.get("base_initial_consideration_60m")
    milestone_cap = records_by_key.get("milestone_consideration_cap_120m")
    direct_180 = records_by_key.get("headline_maximum_value_180m")
    if direct_180 is not None or base is None or milestone_cap is None:
        return None
    return {
        "claim_id": f"CL-{index:03d}",
        "case_id": case_id,
        "claim_type": "derived_numeric_candidate",
        "claim_statement": "Potential maximum consideration requires numeric verification from $60M base consideration plus up to $120M milestone consideration.",
        "claim_scope": "candidate_derived_numeric_claim",
        "temporal_scope": "at_decision",
        "permitted_use": "transaction_terms_verification",
        "supporting_evidence_record_ids": [base["evidence_record_id"], milestone_cap["evidence_record_id"]],
        "contradicting_evidence_record_ids": [],
        "related_source_gap_ids": [],
        "support_level": "requires_numeric_verification",
        "certification_status": "pending_verification",
        "requires_numeric_verification": True,
        "requires_human_review": True,
        "confidence_preliminary": "medium",
        "downstream_use_warning": "Derived numeric candidate only. This is not certified and must not be used as final deal value until M5 numeric verification confirms arithmetic, definitions, and source scope.",
        "hindsight_leakage_warning": "No hindsight leakage warning: derived only from at-decision transaction-term evidence, but still requires numeric verification before certification.",
    }


def _build_gap_nodes(source_gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gap_nodes = []
    for index, source_gap in enumerate(source_gaps, start=1):
        gap_nodes.append(
            {
                "gap_node_id": f"GN-{index:03d}",
                "source_gap_id": source_gap["source_gap_id"],
                "missing_source_need_id": source_gap["missing_source_need_id"],
                "gap_statement": source_gap["missing_source_description"],
                "affected_claim_types": _affected_claim_types_for_gap(source_gap),
                "downstream_risk": source_gap["downstream_risk"],
                "recommended_repair_target": source_gap["recommended_repair_target"],
            }
        )
    return gap_nodes


def _build_gap_claim_node(case_id: str, index: int, gap_node: dict[str, Any]) -> dict[str, Any]:
    claim_type, claim_statement, support_level = _gap_claim_spec(gap_node)
    return {
        "claim_id": f"CL-{index:03d}",
        "case_id": case_id,
        "claim_type": claim_type,
        "claim_statement": claim_statement,
        "claim_scope": "candidate_source_gap_claim",
        "temporal_scope": "source_gap",
        "permitted_use": "gap_tracking",
        "supporting_evidence_record_ids": [],
        "contradicting_evidence_record_ids": [],
        "related_source_gap_ids": [gap_node["source_gap_id"]],
        "support_level": support_level,
        "certification_status": "failed_precheck",
        "requires_numeric_verification": False,
        "requires_human_review": True,
        "confidence_preliminary": "low",
        "downstream_use_warning": "Gap-only candidate claim. Do not use as a report assertion until M2 source retrieval repair supplies authoritative evidence and later stages verify it.",
        "hindsight_leakage_warning": "Source gap only: no evidence timing is available; do not treat this as source-supported evidence.",
    }


def _build_evidence_edge(index: int, claim: dict[str, Any], record: dict[str, Any], edge_type: str | None = None) -> dict[str, Any]:
    resolved_edge_type = edge_type or _edge_type_from_claim(claim)
    return {
        "edge_id": f"EDGE-{index:03d}",
        "claim_id": claim["claim_id"],
        "evidence_record_id": record["evidence_record_id"],
        "edge_type": resolved_edge_type,
        "support_strength": _support_strength_from_record(record, resolved_edge_type),
        "temporal_alignment": _temporal_alignment(record),
        "source_tier_basis": record["strongest_source_tier"],
        "notes": _edge_notes(claim, record, resolved_edge_type),
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
            "Gap-only claims must remain blocked until M2_source_retrieval repairs the missing authoritative sources.",
        ],
    }


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


def _claim_downstream_warning(record: dict[str, Any]) -> str:
    base = "Candidate claim only. M4 maps evidence but does not certify, recommend, value, or generate report assertions."
    return f"{base} {record['downstream_use_warning']} {record['hindsight_leakage_warning']}"


def _affected_claim_types_for_gap(source_gap: dict[str, Any]) -> list[str]:
    affected_fact_types = set(source_gap.get("affected_fact_types", []))
    if "pre_sale_cap_table_gap" in affected_fact_types:
        return ["cap_table"]
    if {"founder_role", "vp_chemistry_role", "director_status", "shareholding_2017"}.intersection(affected_fact_types):
        return ["ownership_or_founder_background"]
    if "personal_proceeds_not_verified" in affected_fact_types:
        return ["personal_proceeds"]
    if "patent_record" in affected_fact_types:
        return ["source_gap_claim", "scientific_asset", "asset_lineage"]
    return ["source_gap_claim"]


def _gap_claim_spec(gap_node: dict[str, Any]) -> tuple[str, str, str]:
    statement = gap_node["gap_statement"]
    affected_claim_types = gap_node["affected_claim_types"]
    if "ownership_or_founder_background" in affected_claim_types:
        return (
            "ownership_or_founder_background",
            "Bohan Jin role and 2017 11.12% shareholding remain source-gap dependent.",
            "gap_only",
        )
    if "personal_proceeds" in affected_claim_types:
        return "personal_proceeds", "Bohan Jin personal realized proceeds remain unsupported.", "unsupported"
    if "cap_table" in affected_claim_types:
        return "cap_table", "Immediate pre-sale cap table remains unsupported.", "unsupported"
    if "patent" in statement.lower() or "scientific_asset" in affected_claim_types:
        return "source_gap_claim", "Official patent-office verification remains source-gap dependent.", "gap_only"
    return "source_gap_claim", f"Source gap remains unresolved: {statement}", "gap_only"


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
        return "Evidence record contributes to a derived numeric candidate only; later numeric verification is required."
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


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
