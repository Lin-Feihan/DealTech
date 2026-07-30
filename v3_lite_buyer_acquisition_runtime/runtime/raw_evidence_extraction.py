from __future__ import annotations

from pathlib import Path
from typing import Any

from v3_lite_buyer_acquisition_runtime.runtime.source_discovery import source_discovery_plan_id
from v3_lite_buyer_acquisition_runtime.runtime.source_retrieval import PERMITTED_USES, SOURCE_TIME_RELATIONS, SourceRetrievalError, manifest_id, resolve_source_path


class RawEvidenceExtractionError(ValueError):
    pass


EVIDENCE_TARGETS = [
    {"category": "transaction_terms", "fact_type": "sale_timing", "anchors": ["march 2021", "fronthera"], "need_ids": ["SN-001"], "workstream_ids": ["WS-001"], "requirement_ids": ["ER-001"], "verification_ids": ["VT-001", "VT-002"]},
    {"category": "transaction_terms", "fact_type": "stock_purchase_agreement_date", "anchors": ["stock purchase agreement", "march 5, 2021"], "need_ids": ["SN-001"], "workstream_ids": ["WS-001", "WS-005"], "requirement_ids": ["ER-001", "ER-006"], "verification_ids": ["VT-001", "VT-002", "VT-003"]},
    {"category": "transaction_economics", "fact_type": "base_initial_consideration", "anchors": ["$60", "base initial consideration"], "need_ids": ["SN-002"], "workstream_ids": ["WS-005", "WS-006"], "requirement_ids": ["ER-001", "ER-006"], "verification_ids": ["VT-001", "VT-003"]},
    {"category": "transaction_economics", "fact_type": "milestone_consideration_cap", "anchors": ["$120", "milestone consideration"], "anchor_groups": [["$120m", "milestone consideration"], ["$120,000,000", "total milestone payment amount"], ["up to an aggregate of $120", "contingent consideration"]], "need_ids": ["SN-002"], "workstream_ids": ["WS-005", "WS-006"], "requirement_ids": ["ER-001", "ER-006"], "verification_ids": ["VT-001", "VT-003"]},
    {"category": "transaction_economics", "fact_type": "headline_maximum_value", "anchors": ["$180", "maximum aggregate"], "need_ids": ["SN-002"], "workstream_ids": ["WS-005", "WS-006"], "requirement_ids": ["ER-001", "ER-006"], "verification_ids": ["VT-001", "VT-003"]},
    {"category": "milestone_economics", "fact_type": "milestone_payment_2022", "anchors": ["$37", "2022", "milestone"], "need_ids": ["SN-003"], "workstream_ids": ["WS-006"], "requirement_ids": ["ER-002", "ER-006"], "verification_ids": ["VT-001", "VT-002"]},
    {"category": "milestone_economics", "fact_type": "milestone_payment_2024", "anchors": ["$23", "2024", "milestone"], "anchor_groups": [["$23.0 million", "2024", "milestone"], ["$23 million", "2024", "milestone"]], "need_ids": ["SN-003"], "workstream_ids": ["WS-006"], "requirement_ids": ["ER-002", "ER-006"], "verification_ids": ["VT-001", "VT-002"]},
    {"category": "buyer_identity", "fact_type": "entity_lineage", "anchors": ["fl2021-001", "esker", "alumis"], "need_ids": ["SN-004"], "workstream_ids": ["WS-001", "WS-003"], "requirement_ids": ["ER-002"], "verification_ids": ["VT-005"]},
    {"category": "founder_background", "fact_type": "founder_role", "anchors": ["bohan jin", "co-founder"], "need_ids": ["SN-005"], "workstream_ids": ["WS-004"], "requirement_ids": ["ER-003", "ER-007"], "verification_ids": ["VT-004", "VT-007"]},
    {"category": "founder_background", "fact_type": "vp_chemistry_role", "anchors": ["bohan jin", "vp chemistry"], "need_ids": ["SN-005"], "workstream_ids": ["WS-004"], "requirement_ids": ["ER-003", "ER-007"], "verification_ids": ["VT-004", "VT-007"]},
    {"category": "founder_background", "fact_type": "director_status", "anchors": ["bohan jin", "director"], "need_ids": ["SN-005"], "workstream_ids": ["WS-004"], "requirement_ids": ["ER-003", "ER-007"], "verification_ids": ["VT-004", "VT-007"]},
    {"category": "ownership_governance", "fact_type": "shareholding_2017", "anchors": ["bohan jin", "11.12%", "2017"], "need_ids": ["SN-005", "SN-008"], "workstream_ids": ["WS-004"], "requirement_ids": ["ER-003", "ER-007"], "verification_ids": ["VT-004", "VT-007"]},
    {"category": "source_uncertainty", "fact_type": "personal_proceeds_not_verified", "anchors": ["personal realized proceeds", "not verified"], "need_ids": ["SN-008"], "workstream_ids": ["WS-004", "WS-009"], "requirement_ids": ["ER-007"], "verification_ids": ["VT-004", "VT-007"]},
    {"category": "source_uncertainty", "fact_type": "pre_sale_cap_table_gap", "anchors": ["cap table", "source gap"], "need_ids": ["SN-008"], "workstream_ids": ["WS-004", "WS-009"], "requirement_ids": ["ER-003", "ER-007"], "verification_ids": ["VT-004", "VT-007"]},
    {"category": "scientific_asset", "fact_type": "tyk2_inhibitor_chemistry", "anchors": ["tyk2", "inhibitor"], "need_ids": ["SN-006", "SN-007"], "workstream_ids": ["WS-002", "WS-003"], "requirement_ids": ["ER-004", "ER-005"], "verification_ids": ["VT-006"]},
    {"category": "asset_lineage", "fact_type": "esk_001_asset_lineage", "anchors": ["esk-001"], "need_ids": ["SN-006", "SN-007"], "workstream_ids": ["WS-003"], "requirement_ids": ["ER-005"], "verification_ids": ["VT-006"]},
    {"category": "asset_lineage", "fact_type": "envudeucitinib_asset_lineage", "anchors": ["envudeucitinib"], "need_ids": ["SN-006", "SN-007"], "workstream_ids": ["WS-003"], "requirement_ids": ["ER-005"], "verification_ids": ["VT-006"]},
    {"category": "ip_evidence", "fact_type": "patent_record", "anchors": ["patent", "tyk2"], "need_ids": ["SN-006"], "workstream_ids": ["WS-002", "WS-003", "WS-004"], "requirement_ids": ["ER-004", "ER-005"], "verification_ids": ["VT-006"], "required_source_type_markers": ["patent"]},
]


def extract_raw_evidence(source_discovery_plan: dict[str, Any], retrieved_sources_manifest: dict[str, Any], manifest_path: Path | None = None) -> dict[str, Any]:
    source_ids = {source["source_id"] for source in retrieved_sources_manifest["retrieved_sources"]}
    items: list[dict[str, Any]] = []

    for source in retrieved_sources_manifest["retrieved_sources"]:
        try:
            source_path = resolve_source_path(source, manifest_path)
        except SourceRetrievalError as exc:
            raise RawEvidenceExtractionError(str(exc)) from exc
        text = source_path.read_text(encoding="utf-8")
        items.extend(_extract_items_from_text(text, source, source_path, source_discovery_plan["case_id"], source_ids))

    raw_evidence = {
        "case_id": source_discovery_plan["case_id"],
        "generated_artifact": "raw_evidence.json",
        "stage": "M2_raw_evidence_extraction",
        "source_bounded": True,
        "evidence_coverage_status": retrieved_sources_manifest["evidence_coverage_status"],
        "failed_source_needs": retrieved_sources_manifest["failed_source_needs"],
        "external_retrieval_performed": retrieved_sources_manifest["retrieval_mode"] == "authoritative_url_retrieval",
        "source_discovery_plan_id": source_discovery_plan_id(source_discovery_plan),
        "retrieved_sources_manifest_id": manifest_id(retrieved_sources_manifest),
        "raw_evidence_items": items,
    }
    validate_raw_evidence(raw_evidence, retrieved_sources_manifest, source_discovery_plan)
    return raw_evidence


def validate_raw_evidence(raw_evidence: Any, retrieved_sources_manifest: dict[str, Any], source_discovery_plan: dict[str, Any]) -> None:
    if not isinstance(raw_evidence, dict):
        raise RawEvidenceExtractionError("raw_evidence must be an object.")
    if raw_evidence.get("generated_artifact") != "raw_evidence.json":
        raise RawEvidenceExtractionError("generated_artifact must be raw_evidence.json.")
    if raw_evidence.get("stage") != "M2_raw_evidence_extraction":
        raise RawEvidenceExtractionError("stage must be M2_raw_evidence_extraction.")
    if raw_evidence.get("source_bounded") is not True:
        raise RawEvidenceExtractionError("raw_evidence must be source_bounded.")
    if raw_evidence.get("evidence_coverage_status") not in {"complete", "partial"}:
        raise RawEvidenceExtractionError("evidence_coverage_status must be complete or partial.")
    if raw_evidence["evidence_coverage_status"] != retrieved_sources_manifest["evidence_coverage_status"]:
        raise RawEvidenceExtractionError("raw_evidence coverage status must match retrieved_sources_manifest.")
    if raw_evidence.get("failed_source_needs") != retrieved_sources_manifest["failed_source_needs"]:
        raise RawEvidenceExtractionError("raw_evidence failed_source_needs must match retrieved_sources_manifest.")
    source_ids = {source["source_id"] for source in retrieved_sources_manifest["retrieved_sources"]}
    source_need_ids = {need["source_need_id"] for need in source_discovery_plan["source_needs"]}
    workstream_ids = {workstream_id for need in source_discovery_plan["source_needs"] for workstream_id in need["related_workstream_ids"]}
    requirement_ids = {requirement_id for need in source_discovery_plan["source_needs"] for requirement_id in need["related_evidence_requirement_ids"]}
    required_fields = (
        "evidence_id",
        "case_id",
        "source_id",
        "source_title",
        "source_url_or_file",
        "source_type",
        "source_tier",
        "retrieval_date",
        "extraction_location",
        "extracted_text_or_summary",
        "extraction_mode",
        "related_source_need_ids",
        "related_workstream_ids",
        "related_evidence_requirement_ids",
        "related_verification_target_ids",
        "evidence_category",
        "raw_fact_type",
        "confidence_preliminary",
        "source_is_authoritative",
        "case_seed_only",
        "extraction_notes",
        "downstream_use_warning",
        "evidence_time_relation_to_decision_date",
        "permitted_use",
        "hindsight_leakage_warning",
    )
    for item in raw_evidence["raw_evidence_items"]:
        missing = [field for field in required_fields if field not in item]
        if missing:
            raise RawEvidenceExtractionError(f"Missing raw evidence item field(s): {', '.join(missing)}")
        if item["source_id"] not in source_ids:
            raise RawEvidenceExtractionError(f"Raw evidence cites unlisted source_id: {item['source_id']}")
        if item["source_type"] == "web_search":
            raise RawEvidenceExtractionError("Raw evidence may not cite web_search as a source type.")
        if item["case_seed_only"] is True and item["source_is_authoritative"] is True:
            raise RawEvidenceExtractionError("case_seed_only evidence cannot be authoritative.")
        if not item["related_source_need_ids"] or set(item["related_source_need_ids"]) - source_need_ids:
            raise RawEvidenceExtractionError(f"Raw evidence must map to known source needs: {item['evidence_id']}")
        if not item["related_workstream_ids"] and not item["related_evidence_requirement_ids"]:
            raise RawEvidenceExtractionError(f"Raw evidence must map to a workstream or evidence requirement: {item['evidence_id']}")
        if set(item["related_workstream_ids"]) - workstream_ids:
            raise RawEvidenceExtractionError(f"Raw evidence references unknown workstream: {item['evidence_id']}")
        if set(item["related_evidence_requirement_ids"]) - requirement_ids:
            raise RawEvidenceExtractionError(f"Raw evidence references unknown evidence requirement: {item['evidence_id']}")
        if item["evidence_time_relation_to_decision_date"] not in SOURCE_TIME_RELATIONS:
            raise RawEvidenceExtractionError(f"Invalid evidence_time_relation_to_decision_date: {item['evidence_id']}")
        if item["permitted_use"] not in PERMITTED_USES:
            raise RawEvidenceExtractionError(f"Invalid permitted_use: {item['evidence_id']}")
        source = next(source for source in retrieved_sources_manifest["retrieved_sources"] if source["source_id"] == item["source_id"])
        if item["evidence_time_relation_to_decision_date"] != source["source_time_relation_to_decision_date"]:
            raise RawEvidenceExtractionError(f"Raw evidence temporal relation must match source temporal relation: {item['evidence_id']}")
        if item["permitted_use"] != source["permitted_use"]:
            raise RawEvidenceExtractionError(f"Raw evidence permitted_use must match source permitted_use: {item['evidence_id']}")
        if item["evidence_time_relation_to_decision_date"] in {"post_decision", "retrospective"} and item["permitted_use"] == "ex_ante_deal_evaluation":
            warning = item["hindsight_leakage_warning"].lower()
            if "hindsight" not in warning or "caveat" not in warning:
                raise RawEvidenceExtractionError(f"Post-decision evidence cannot be labeled ex_ante_deal_evaluation without a hindsight caveat: {item['evidence_id']}")


def _extract_items_from_text(text: str, source: dict[str, Any], source_path: Path, case_id: str, source_ids: set[str]) -> list[dict[str, Any]]:
    lower = text.lower()
    items = []
    for target in EVIDENCE_TARGETS:
        if not _source_type_allowed_for_target(source, target):
            continue
        anchors = _matching_anchors(lower, target)
        if anchors is None:
            continue
        if all(anchor.lower() in lower for anchor in anchors):
            snippet, location = _bounded_snippet(text, anchors[0], source_path)
            items.append(
                {
                    "evidence_id": f"RE-{len(items) + 1:03d}-{source['source_id']}",
                    "case_id": case_id,
                    "source_id": source["source_id"],
                    "source_title": source["title"],
                    "source_url_or_file": source["url_or_file"],
                    "source_type": source["source_type"],
                    "source_tier": source["source_tier"],
                    "retrieval_date": source["retrieval_date"],
                    "extraction_location": location,
                    "extracted_text_or_summary": snippet,
                    "extraction_mode": _extraction_mode(snippet, anchors),
                    "related_source_need_ids": target["need_ids"],
                    "related_workstream_ids": target["workstream_ids"],
                    "related_evidence_requirement_ids": target["requirement_ids"],
                    "related_verification_target_ids": target["verification_ids"],
                    "evidence_category": target["category"],
                    "raw_fact_type": target["fact_type"],
                    "confidence_preliminary": "medium" if source["source_tier"] in {"Tier 1", "Tier 2"} else "low",
                    "source_is_authoritative": source["source_tier"] in {"Tier 1", "Tier 2"},
                    "case_seed_only": False,
                    "extraction_notes": "Deterministic bounded extraction from retrieved source manifest source; not normalized, certified, or analyzed.",
                    "downstream_use_warning": "Raw evidence only. Do not use as a certified claim, valuation conclusion, recommendation, or final-report assertion until later validation and certification stages.",
                    "evidence_time_relation_to_decision_date": source["source_time_relation_to_decision_date"],
                    "permitted_use": source["permitted_use"],
                    "hindsight_leakage_warning": _hindsight_leakage_warning(source),
                }
            )
    return items


def _matching_anchors(lower_text: str, target: dict[str, Any]) -> list[str] | None:
    anchor_groups = target.get("anchor_groups") or [target["anchors"]]
    for anchors in anchor_groups:
        if all(anchor.lower() in lower_text for anchor in anchors):
            return anchors
    return None


def _source_type_allowed_for_target(source: dict[str, Any], target: dict[str, Any]) -> bool:
    markers = target.get("required_source_type_markers")
    if not markers:
        return True
    source_text = f"{source['source_type']} {source['source_owner']} {source['title']}".lower()
    return any(marker.lower() in source_text for marker in markers)


def _bounded_snippet(text: str, anchor: str, source_path: Path) -> tuple[str, dict[str, Any]]:
    lower = text.lower()
    index = lower.find(anchor.lower())
    if index < 0:
        index = 0
    start = max(index - 220, 0)
    end = min(index + 520, len(text))
    snippet = " ".join(text[start:end].split())
    line = text[:index].count("\n") + 1
    return snippet, {
        "file_path": str(source_path),
        "line": line,
        "anchor": anchor,
    }


def _extraction_mode(snippet: str, anchors: list[str]) -> str:
    if len(snippet) <= 360 and all(anchor.lower() in snippet.lower() for anchor in anchors):
        return "exact_quote"
    return "bounded_summary"


def _hindsight_leakage_warning(source: dict[str, Any]) -> str:
    relation = source["source_time_relation_to_decision_date"]
    if relation == "at_decision":
        return "No hindsight leakage warning: source is contemporaneous with the transaction decision date and is limited to its permitted use."
    if relation == "pre_decision":
        return "No hindsight leakage warning: source predates the decision date, subject to source reliability and downstream certification."
    if relation == "post_decision":
        return "Hindsight leakage warning: post-decision evidence may support retrospective validation or outcome tracking, but must not support an ex-ante buyer decision claim without explicit caveat."
    if relation == "retrospective":
        return "Hindsight leakage warning: retrospective/current evidence may support outcome validation or source leads, but must not be treated as decision-date evidence without explicit caveat."
    return "Temporal relation unknown: use only as a source lead or gap-tracking input until downstream validation resolves timing."
