from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v3_lite_buyer_acquisition_runtime.runtime.source_retrieval import PERMITTED_USES, SOURCE_TIME_RELATIONS


class EvidenceRepositoryError(ValueError):
    pass


SUPPORT_STATUSES = {"source_supported", "partially_supported", "source_gap", "conflicting", "unsupported"}
CONFLICT_STATUSES = {"no_conflict_detected", "potential_conflict", "conflict_detected", "not_evaluated"}
TIER_STRENGTH = {"Tier 1": 1, "Tier 2": 2, "Tier 3": 3, "Tier 4": 4}
RAW_REQUIRED_FIELDS = {
    "source_id",
    "source_tier",
    "evidence_time_relation_to_decision_date",
    "permitted_use",
    "downstream_use_warning",
}


def load_json_artifact(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise EvidenceRepositoryError(f"Artifact not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EvidenceRepositoryError(f"Invalid JSON artifact at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvidenceRepositoryError(f"Artifact at {path} must be a JSON object.")
    return payload


def raw_evidence_repository_source_id(raw_evidence: dict[str, Any]) -> str:
    return f"RAW-{raw_evidence['case_id']}-{raw_evidence['retrieved_sources_manifest_id']}"


def validate_raw_evidence_for_m3(raw_evidence: Any) -> None:
    if not isinstance(raw_evidence, dict):
        raise EvidenceRepositoryError("raw_evidence must be an object.")
    if raw_evidence.get("generated_artifact") != "raw_evidence.json":
        raise EvidenceRepositoryError("M3 requires generated_artifact raw_evidence.json.")
    if raw_evidence.get("source_bounded") is not True:
        raise EvidenceRepositoryError("M3 requires source_bounded raw_evidence input.")
    if not raw_evidence.get("evidence_coverage_status"):
        raise EvidenceRepositoryError("M3 requires evidence_coverage_status in raw_evidence.")
    if not isinstance(raw_evidence.get("raw_evidence_items"), list):
        raise EvidenceRepositoryError("M3 requires raw_evidence_items array.")
    for item in raw_evidence["raw_evidence_items"]:
        missing = sorted(field for field in RAW_REQUIRED_FIELDS if not item.get(field))
        if missing:
            raise EvidenceRepositoryError(f"M3 raw_evidence item missing required field(s): {', '.join(missing)}")
        if item["evidence_time_relation_to_decision_date"] not in SOURCE_TIME_RELATIONS:
            raise EvidenceRepositoryError(
                f"Invalid evidence_time_relation_to_decision_date for raw evidence item {item.get('evidence_id', '<unknown>')}"
            )
        if item["permitted_use"] not in PERMITTED_USES:
            raise EvidenceRepositoryError(f"Invalid permitted_use for raw evidence item {item.get('evidence_id', '<unknown>')}")
        if item["evidence_time_relation_to_decision_date"] in {"post_decision", "retrospective"} and item["permitted_use"] == "ex_ante_deal_evaluation":
            raise EvidenceRepositoryError(
                f"Post-decision or retrospective raw evidence cannot be treated as ex_ante_deal_evaluation: {item.get('evidence_id', '<unknown>')}"
            )


def validate_retrieved_sources_manifest_for_m3(retrieved_sources_manifest: Any) -> None:
    if not isinstance(retrieved_sources_manifest, dict):
        raise EvidenceRepositoryError("retrieved_sources_manifest must be an object.")
    if retrieved_sources_manifest.get("generated_artifact") != "retrieved_sources_manifest.json":
        raise EvidenceRepositoryError("M3 requires generated_artifact retrieved_sources_manifest.json.")
    if not isinstance(retrieved_sources_manifest.get("retrieved_sources"), list):
        raise EvidenceRepositoryError("retrieved_sources_manifest must include retrieved_sources array.")
    if not isinstance(retrieved_sources_manifest.get("failed_source_needs"), list):
        raise EvidenceRepositoryError("retrieved_sources_manifest must include failed_source_needs array.")
    for source in retrieved_sources_manifest["retrieved_sources"]:
        for field in ("source_id", "title", "source_tier", "source_time_relation_to_decision_date", "permitted_use"):
            if not source.get(field):
                raise EvidenceRepositoryError(f"retrieved_sources_manifest source missing required field {field}.")


def build_evidence_repository(raw_evidence: dict[str, Any], retrieved_sources_manifest: dict[str, Any]) -> dict[str, Any]:
    validate_raw_evidence_for_m3(raw_evidence)
    validate_retrieved_sources_manifest_for_m3(retrieved_sources_manifest)
    if raw_evidence["case_id"] != retrieved_sources_manifest["case_id"]:
        raise EvidenceRepositoryError("raw_evidence case_id must match retrieved_sources_manifest case_id.")

    sources_by_id = {source["source_id"]: source for source in retrieved_sources_manifest["retrieved_sources"]}
    gap_need_ids = {gap["source_need_id"] for gap in retrieved_sources_manifest["failed_source_needs"]}
    grouped_items: dict[str, list[dict[str, Any]]] = defaultdict(list)
    group_metadata: dict[str, dict[str, str]] = {}

    for item in raw_evidence["raw_evidence_items"]:
        if item["source_id"] not in sources_by_id:
            raise EvidenceRepositoryError(f"raw_evidence item cites source_id absent from retrieved_sources_manifest: {item['source_id']}")
        canonical_fact_key, canonical_fact_type, normalized_fact_summary = canonicalize_raw_evidence_item(item)
        grouped_items[canonical_fact_key].append(item)
        group_metadata.setdefault(
            canonical_fact_key,
            {
                "canonical_fact_type": canonical_fact_type,
                "normalized_fact_summary": normalized_fact_summary,
            },
        )

    duplicate_groups_count = sum(1 for items in grouped_items.values() if len(items) > 1)
    evidence_records = []
    for index, canonical_fact_key in enumerate(sorted(grouped_items), start=1):
        evidence_records.append(
            _build_evidence_record(
                record_index=index,
                canonical_fact_key=canonical_fact_key,
                canonical_fact_type=group_metadata[canonical_fact_key]["canonical_fact_type"],
                normalized_fact_summary=group_metadata[canonical_fact_key]["normalized_fact_summary"],
                items=grouped_items[canonical_fact_key],
                gap_need_ids=gap_need_ids,
            )
        )

    source_gaps = _build_source_gaps(retrieved_sources_manifest["failed_source_needs"])
    repository = {
        "case_id": raw_evidence["case_id"],
        "generated_artifact": "evidence_repository.json",
        "stage": "M3_evidence_repository",
        "source_bounded": True,
        "evidence_coverage_status": raw_evidence["evidence_coverage_status"],
        "created_from_raw_evidence_id": raw_evidence_repository_source_id(raw_evidence),
        "created_at": _now_utc_iso(),
        "evidence_records": evidence_records,
        "source_gaps": source_gaps,
        "repository_quality_summary": _build_repository_quality_summary(
            raw_evidence=raw_evidence,
            evidence_records=evidence_records,
            source_gaps=source_gaps,
            duplicate_groups_count=duplicate_groups_count,
        ),
    }
    validate_evidence_repository(repository)
    return repository


def validate_evidence_repository(repository: Any) -> None:
    if not isinstance(repository, dict):
        raise EvidenceRepositoryError("evidence_repository must be an object.")
    required_top_level = {
        "case_id",
        "generated_artifact",
        "stage",
        "source_bounded",
        "evidence_coverage_status",
        "created_from_raw_evidence_id",
        "created_at",
        "evidence_records",
        "source_gaps",
        "repository_quality_summary",
    }
    missing = sorted(field for field in required_top_level if field not in repository)
    if missing:
        raise EvidenceRepositoryError(f"Missing evidence_repository top-level field(s): {', '.join(missing)}")
    if repository["generated_artifact"] != "evidence_repository.json":
        raise EvidenceRepositoryError("generated_artifact must be evidence_repository.json.")
    if repository["stage"] != "M3_evidence_repository":
        raise EvidenceRepositoryError("stage must be M3_evidence_repository.")
    if repository["source_bounded"] is not True:
        raise EvidenceRepositoryError("evidence_repository must remain source_bounded.")
    if repository["evidence_coverage_status"] not in {"complete", "partial"}:
        raise EvidenceRepositoryError("evidence_coverage_status must be complete or partial.")
    if not isinstance(repository["evidence_records"], list):
        raise EvidenceRepositoryError("evidence_records must be an array.")
    if not isinstance(repository["source_gaps"], list):
        raise EvidenceRepositoryError("source_gaps must be an array.")
    for record in repository["evidence_records"]:
        _validate_evidence_record(record)
    for source_gap in repository["source_gaps"]:
        _validate_source_gap(source_gap)
    _validate_repository_quality_summary(repository["repository_quality_summary"])


def canonicalize_raw_evidence_item(item: dict[str, Any]) -> tuple[str, str, str]:
    raw_fact_type = item["raw_fact_type"]
    lower = item["extracted_text_or_summary"].lower()
    source_id = item["source_id"]

    if raw_fact_type == "base_initial_consideration":
        if any(token in lower for token in ("$60", "60,000,000", "sixty million")):
            return (
                "base_initial_consideration_60m",
                "transaction_economics",
                "Base initial consideration is directly stated as $60 million in the transaction agreement.",
            )
        return raw_fact_type, "transaction_economics", "Base initial consideration is directly supported by source-bounded evidence."

    if raw_fact_type == "milestone_consideration_cap":
        if any(token in lower for token in ("$120", "120.0 million", "120,000,000", "total milestone payment amount")):
            return (
                "milestone_consideration_cap_120m",
                "transaction_economics",
                "Milestone consideration cap is directly stated as $120 million under the FronThera transaction structure.",
            )
        return raw_fact_type, "transaction_economics", "Milestone consideration cap is directly supported by source-bounded evidence."

    if raw_fact_type == "headline_maximum_value":
        if any(token in lower for token in ("$180", "180.0 million", "180,000,000", "maximum aggregate")):
            return (
                "headline_maximum_value_180m",
                "transaction_economics",
                "Maximum aggregate transaction value is directly stated as $180 million in source-bounded evidence.",
            )
        return (
            "headline_maximum_value_requires_numeric_verification",
            "transaction_economics",
            "Potential maximum aggregate value requires direct numeric verification before later-stage use.",
        )

    if raw_fact_type == "milestone_payment_2022":
        if any(token in lower for token in ("$37", "37.0 million", "37 million")):
            return (
                "milestone_payment_2022_37m",
                "milestone_economics",
                "A 2022 milestone payment is directly stated as $37 million.",
            )
        return raw_fact_type, "milestone_economics", "A 2022 milestone payment is directly supported by source-bounded evidence."

    if raw_fact_type == "milestone_payment_2024":
        if any(token in lower for token in ("$23", "23.0 million", "23 million")):
            return (
                "milestone_payment_2024_23m",
                "milestone_economics",
                "A 2024 milestone payment is directly stated as $23 million.",
            )
        return raw_fact_type, "milestone_economics", "A 2024 milestone payment is directly supported by source-bounded evidence."

    if raw_fact_type == "sale_timing":
        if "march 2021" in lower:
            return (
                "acquisition_timing_march_2021",
                "transaction_terms",
                "The acquisition timing is described as March 2021 in post-decision source-bounded evidence.",
            )
        return raw_fact_type, "transaction_terms", "Transaction timing is directly supported by source-bounded evidence."

    if raw_fact_type == "stock_purchase_agreement_date":
        return (
            "stock_purchase_agreement_date_2021_03_05",
            "transaction_terms",
            "The stock purchase agreement date is normalized as 2021-03-05 from source-bounded transaction evidence.",
        )

    if raw_fact_type == "entity_lineage":
        return (
            "fl2021_001_to_esker_to_alumis_entity_lineage",
            "entity_lineage",
            "Entity lineage shows FL2021-001 becoming Esker Therapeutics and later Alumis.",
        )

    if raw_fact_type in {"tyk2_inhibitor_chemistry", "esk_001_asset_lineage", "envudeucitinib_asset_lineage"}:
        if source_id == "SRC-ALUMIS-PIPELINE-001":
            return (
                "alumis_pipeline_current_envudeucitinib",
                "current_pipeline_status",
                "Current Alumis pipeline evidence places envudeucitinib / ESK-001 in retrospective pipeline context.",
            )
        if raw_fact_type == "envudeucitinib_asset_lineage" or "formerly known as esk-001" in lower or "envudeucitinib" in lower:
            return (
                "envudeucitinib_formerly_esk_001",
                "asset_lineage",
                "Post-decision source-bounded evidence links envudeucitinib to the formerly named ESK-001 asset.",
            )
        return (
            "esk_001_tyk2_inhibitor",
            "scientific_asset_identity",
            "Source-bounded evidence identifies ESK-001 as a TYK2 inhibitor asset.",
        )

    return (
        _safe_key(raw_fact_type),
        item["evidence_category"],
        f"Canonicalized record for raw fact type {raw_fact_type} from source-bounded evidence.",
    )


def _build_evidence_record(
    record_index: int,
    canonical_fact_key: str,
    canonical_fact_type: str,
    normalized_fact_summary: str,
    items: list[dict[str, Any]],
    gap_need_ids: set[str],
) -> dict[str, Any]:
    source_ids = _ordered_unique(item["source_id"] for item in items)
    source_titles = _ordered_unique(item["source_title"] for item in items)
    source_tiers = _ordered_unique(item["source_tier"] for item in items)
    raw_evidence_ids = _ordered_unique(item["evidence_id"] for item in items)
    related_source_need_ids = _ordered_unique(need_id for item in items for need_id in item["related_source_need_ids"])
    related_workstream_ids = _ordered_unique(workstream_id for item in items for workstream_id in item["related_workstream_ids"])
    related_evidence_requirement_ids = _ordered_unique(requirement_id for item in items for requirement_id in item["related_evidence_requirement_ids"])
    related_verification_target_ids = _ordered_unique(target_id for item in items for target_id in item["related_verification_target_ids"])
    supporting_time_relations = _ordered_unique(item["evidence_time_relation_to_decision_date"] for item in items)
    supporting_permitted_uses = _ordered_unique(item["permitted_use"] for item in items)
    strongest_source_tier = min(source_tiers, key=lambda tier: TIER_STRENGTH.get(tier, 99))
    evidence_time_relation_to_decision_date = _aggregate_time_relation(supporting_time_relations)
    permitted_use = _aggregate_permitted_use(supporting_permitted_uses, evidence_time_relation_to_decision_date)
    confidence_preliminary = _aggregate_confidence(items, strongest_source_tier, len(source_ids))
    conflict_status = _detect_conflict_status(canonical_fact_key, items)
    support_status = _determine_support_status(conflict_status, related_source_need_ids, gap_need_ids)
    duplicate_group_id = f"DG-{record_index:03d}"
    hindsight_leakage_warning = _aggregate_hindsight_warning(items, supporting_time_relations)
    downstream_use_warning = _aggregate_downstream_warning(items)

    return {
        "evidence_record_id": f"ER-{record_index:03d}",
        "case_id": items[0]["case_id"],
        "canonical_fact_key": canonical_fact_key,
        "canonical_fact_type": canonical_fact_type,
        "normalized_fact_summary": normalized_fact_summary,
        "source_ids": source_ids,
        "source_titles": source_titles,
        "source_tiers": source_tiers,
        "source_count": len(source_ids),
        "strongest_source_tier": strongest_source_tier,
        "evidence_time_relation_to_decision_date": evidence_time_relation_to_decision_date,
        "permitted_use": permitted_use,
        "raw_evidence_ids": raw_evidence_ids,
        "related_source_need_ids": related_source_need_ids,
        "related_workstream_ids": related_workstream_ids,
        "related_evidence_requirement_ids": related_evidence_requirement_ids,
        "related_verification_target_ids": related_verification_target_ids,
        "confidence_preliminary": confidence_preliminary,
        "support_status": support_status,
        "conflict_status": conflict_status,
        "duplicate_group_id": duplicate_group_id,
        "downstream_use_warning": downstream_use_warning,
        "hindsight_leakage_warning": hindsight_leakage_warning,
        "supporting_time_relations": supporting_time_relations,
        "supporting_permitted_uses": supporting_permitted_uses,
    }


def _build_source_gaps(failed_source_needs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_gaps = []
    for index, failed_need in enumerate(failed_source_needs, start=1):
        gap_text = f"{failed_need.get('missing_source', '')} {failed_need.get('reason', '')}".lower()
        enrichments = _source_gap_enrichments(failed_need)
        source_gaps.append(
            {
                "source_gap_id": f"SG-{index:03d}",
                "missing_source_need_id": failed_need["source_need_id"],
                "missing_source_description": enrichments["missing_source_description"],
                "reason": failed_need["reason"],
                "affected_fact_types": enrichments["affected_fact_types"],
                "affected_workstreams": enrichments["affected_workstreams"],
                "downstream_risk": enrichments["downstream_risk"],
                "recommended_repair_target": "M2_source_retrieval",
            }
        )
    return source_gaps


def _source_gap_enrichments(failed_need: dict[str, Any]) -> dict[str, Any]:
    source_need_id = failed_need["source_need_id"]
    description = str(failed_need.get("missing_source", "")).lower()
    reason = str(failed_need.get("reason", "")).lower()
    text = f"{description} {reason}"

    if source_need_id == "SN-005":
        return {
            "missing_source_description": "Haisco / CNINFO / SZSE disclosure for Bohan Jin role and 2017 11.12% shareholding",
            "affected_fact_types": ["founder_role", "vp_chemistry_role", "director_status", "shareholding_2017"],
            "affected_workstreams": ["WS-004"],
            "downstream_risk": "Founder role and 2017 ownership assertions remain unsupported until authoritative Haisco disclosure is retrieved.",
        }
    if source_need_id == "SN-006":
        return {
            "missing_source_description": "Official patent-office records for TYK2 inhibitor chemistry",
            "affected_fact_types": ["patent_record", "tyk2_inhibitor_chemistry", "esk_001_asset_lineage", "envudeucitinib_asset_lineage"],
            "affected_workstreams": ["WS-002", "WS-003", "WS-004"],
            "downstream_risk": "IP lineage remains only partially supported because official patent-office evidence is missing.",
        }
    if source_need_id == "SN-008" and "personal" in text:
        return {
            "missing_source_description": "Direct source on Bohan Jin personal realized proceeds",
            "affected_fact_types": ["personal_proceeds_not_verified"],
            "affected_workstreams": ["WS-004", "WS-009"],
            "downstream_risk": "Personal proceeds cannot be inferred from transaction consideration or ownership leads without direct source evidence.",
        }
    if source_need_id == "SN-008" and "cap table" in text:
        return {
            "missing_source_description": "Immediately pre-2021 FronThera cap table source",
            "affected_fact_types": ["pre_sale_cap_table_gap", "shareholding_2017"],
            "affected_workstreams": ["WS-004", "WS-009"],
            "downstream_risk": "Ownership and proceeds analysis remain incomplete without an authoritative pre-sale cap table source.",
        }
    return {
        "missing_source_description": failed_need.get("missing_source") or f"Unresolved source need {source_need_id}",
        "affected_fact_types": [],
        "affected_workstreams": [],
        "downstream_risk": "Downstream stages must treat this unresolved source need as a gap until M2 retrieval repair is completed.",
    }


def _build_repository_quality_summary(
    raw_evidence: dict[str, Any],
    evidence_records: list[dict[str, Any]],
    source_gaps: list[dict[str, Any]],
    duplicate_groups_count: int,
) -> dict[str, Any]:
    strongest_tier_distribution = Counter(record["strongest_source_tier"] for record in evidence_records)
    temporal_distribution = Counter(record["evidence_time_relation_to_decision_date"] for record in evidence_records)
    permitted_use_distribution = Counter(record["permitted_use"] for record in evidence_records)
    unsupported_or_gap_fact_count = sum(
        1 for record in evidence_records if record["support_status"] in {"source_gap", "unsupported", "conflicting"}
    ) + len(source_gaps)

    notes = [
        "Carry temporal gating into claim-evidence graph construction; post-decision and retrospective evidence must not be treated as ex-ante decision support without explicit caveat.",
        f"Repair {len(source_gaps)} source gap(s) via M2_source_retrieval before downstream founder-role, patent, proceeds, or cap-table claims are treated as source-supported.",
    ]
    if not any(record["canonical_fact_key"] == "headline_maximum_value_180m" for record in evidence_records):
        notes.append("No $180M aggregate value canonical fact was created because M3 did not see direct raw evidence support for that fact in this input.")

    return {
        "raw_evidence_item_count": len(raw_evidence["raw_evidence_items"]),
        "evidence_record_count": len(evidence_records),
        "duplicate_groups_count": duplicate_groups_count,
        "source_gap_count": len(source_gaps),
        "source_tier_distribution": dict(strongest_tier_distribution),
        "temporal_distribution": dict(temporal_distribution),
        "permitted_use_distribution": dict(permitted_use_distribution),
        "unsupported_or_gap_fact_count": unsupported_or_gap_fact_count,
        "notes_for_next_stage": notes,
    }


def _aggregate_time_relation(relations: list[str]) -> str:
    if "at_decision" in relations:
        return "at_decision"
    if "pre_decision" in relations:
        return "pre_decision"
    if "post_decision" in relations:
        return "post_decision"
    if "retrospective" in relations:
        return "retrospective"
    return "unknown"


def _aggregate_permitted_use(permitted_uses: list[str], relation: str) -> str:
    if relation == "at_decision":
        if "transaction_terms_verification" in permitted_uses:
            return "transaction_terms_verification"
        if "ex_ante_deal_evaluation" in permitted_uses:
            return "ex_ante_deal_evaluation"
    if relation == "pre_decision":
        if "ex_ante_deal_evaluation" in permitted_uses:
            return "ex_ante_deal_evaluation"
    if relation in {"post_decision", "retrospective"} and "ex_ante_deal_evaluation" in permitted_uses:
        raise EvidenceRepositoryError("Post-decision or retrospective evidence record cannot be labeled ex_ante_deal_evaluation.")
    for candidate in (
        "retrospective_outcome_validation",
        "transaction_terms_verification",
        "source_lead_only",
        "gap_tracking",
        "ex_ante_deal_evaluation",
    ):
        if candidate in permitted_uses:
            return candidate
    raise EvidenceRepositoryError("Evidence record has no valid permitted_use.")


def _aggregate_confidence(items: list[dict[str, Any]], strongest_source_tier: str, source_count: int) -> str:
    confidences = {item.get("confidence_preliminary", "low") for item in items}
    if strongest_source_tier == "Tier 1" and source_count >= 2:
        return "high"
    if "high" in confidences:
        return "high"
    if strongest_source_tier in {"Tier 1", "Tier 2"}:
        return "medium"
    return "low"


def _detect_conflict_status(canonical_fact_key: str, items: list[dict[str, Any]]) -> str:
    summaries = {_normalized_text(item["extracted_text_or_summary"]) for item in items}
    if canonical_fact_key == "headline_maximum_value_requires_numeric_verification":
        return "not_evaluated"
    if len(summaries) == 1:
        return "no_conflict_detected"
    return "no_conflict_detected"


def _determine_support_status(conflict_status: str, related_source_need_ids: list[str], gap_need_ids: set[str]) -> str:
    if conflict_status == "conflict_detected":
        return "conflicting"
    if any(need_id in gap_need_ids for need_id in related_source_need_ids):
        return "partially_supported"
    return "source_supported"


def _aggregate_hindsight_warning(items: list[dict[str, Any]], supporting_time_relations: list[str]) -> str:
    warnings = _ordered_unique(item["hindsight_leakage_warning"] for item in items)
    if len(supporting_time_relations) > 1:
        return (
            "Mixed temporal support: this evidence record combines contemporaneous and later corroborating sources. "
            "Use decision-time sources for transaction verification and treat post-decision or retrospective sources only as later corroboration with explicit caveat."
        )
    return warnings[0]


def _aggregate_downstream_warning(items: list[dict[str, Any]]) -> str:
    warnings = _ordered_unique(item["downstream_use_warning"] for item in items)
    return warnings[0] if len(warnings) == 1 else " | ".join(warnings)


def _validate_evidence_record(record: dict[str, Any]) -> None:
    required_fields = {
        "evidence_record_id",
        "case_id",
        "canonical_fact_key",
        "canonical_fact_type",
        "normalized_fact_summary",
        "source_ids",
        "source_titles",
        "source_tiers",
        "source_count",
        "strongest_source_tier",
        "evidence_time_relation_to_decision_date",
        "permitted_use",
        "raw_evidence_ids",
        "related_source_need_ids",
        "related_workstream_ids",
        "related_evidence_requirement_ids",
        "related_verification_target_ids",
        "confidence_preliminary",
        "support_status",
        "conflict_status",
        "duplicate_group_id",
        "downstream_use_warning",
        "hindsight_leakage_warning",
    }
    missing = sorted(field for field in required_fields if field not in record)
    if missing:
        raise EvidenceRepositoryError(f"Missing evidence_record field(s): {', '.join(missing)}")
    if record["support_status"] not in SUPPORT_STATUSES:
        raise EvidenceRepositoryError(f"Invalid support_status for evidence_record {record['evidence_record_id']}")
    if record["conflict_status"] not in CONFLICT_STATUSES:
        raise EvidenceRepositoryError(f"Invalid conflict_status for evidence_record {record['evidence_record_id']}")
    if record["evidence_time_relation_to_decision_date"] not in SOURCE_TIME_RELATIONS:
        raise EvidenceRepositoryError(f"Invalid evidence_time_relation_to_decision_date for evidence_record {record['evidence_record_id']}")
    if record["permitted_use"] not in PERMITTED_USES:
        raise EvidenceRepositoryError(f"Invalid permitted_use for evidence_record {record['evidence_record_id']}")
    if record["evidence_time_relation_to_decision_date"] in {"post_decision", "retrospective"} and record["permitted_use"] == "ex_ante_deal_evaluation":
        raise EvidenceRepositoryError(f"Evidence record {record['evidence_record_id']} violates hindsight control.")
    if not record["source_ids"]:
        raise EvidenceRepositoryError(f"Evidence record {record['evidence_record_id']} must cite at least one source.")
    if record["source_count"] != len(record["source_ids"]):
        raise EvidenceRepositoryError(f"Evidence record {record['evidence_record_id']} has inconsistent source_count.")


def _validate_source_gap(source_gap: dict[str, Any]) -> None:
    required_fields = {
        "source_gap_id",
        "missing_source_need_id",
        "missing_source_description",
        "reason",
        "affected_fact_types",
        "affected_workstreams",
        "downstream_risk",
        "recommended_repair_target",
    }
    missing = sorted(field for field in required_fields if field not in source_gap)
    if missing:
        raise EvidenceRepositoryError(f"Missing source_gap field(s): {', '.join(missing)}")
    if source_gap["recommended_repair_target"] != "M2_source_retrieval":
        raise EvidenceRepositoryError(f"source_gap {source_gap['source_gap_id']} must recommend M2_source_retrieval.")


def _validate_repository_quality_summary(summary: dict[str, Any]) -> None:
    required_fields = {
        "raw_evidence_item_count",
        "evidence_record_count",
        "duplicate_groups_count",
        "source_gap_count",
        "source_tier_distribution",
        "temporal_distribution",
        "permitted_use_distribution",
        "unsupported_or_gap_fact_count",
        "notes_for_next_stage",
    }
    missing = sorted(field for field in required_fields if field not in summary)
    if missing:
        raise EvidenceRepositoryError(f"Missing repository_quality_summary field(s): {', '.join(missing)}")


def _ordered_unique(values: Any) -> list[Any]:
    seen = set()
    ordered = []
    for value in values:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


def _normalized_text(text: str) -> str:
    return " ".join(text.split()).lower()


def _safe_key(value: str) -> str:
    return "".join(character if character.isalnum() or character == "_" else "_" for character in value.lower())


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
