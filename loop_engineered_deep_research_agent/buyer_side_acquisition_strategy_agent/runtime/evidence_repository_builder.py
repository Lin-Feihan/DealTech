from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.source_retrieval import PERMITTED_USES, SOURCE_TIME_RELATIONS


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
GENERIC_FACT_TYPES = {
    "transaction_background",
    "transaction_timing",
    "transaction_document_date",
    "transaction_parties",
    "transaction_consideration",
    "contingent_consideration",
    "milestone_payment",
    "financing_or_payment_mechanics",
    "entity_identity",
    "entity_lineage",
    "asset_or_product_identity",
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
    "source_gap",
    "generic_fact",
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
        canonical_fact_key, canonical_fact_type, normalized_fact_summary, structured_attributes = canonicalize_raw_evidence_item(item)
        grouped_items[canonical_fact_key].append(item)
        group_metadata.setdefault(
            canonical_fact_key,
            {
                "canonical_fact_type": canonical_fact_type,
                "normalized_fact_summary": normalized_fact_summary,
                "structured_attributes": structured_attributes,
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
                structured_attributes=group_metadata[canonical_fact_key]["structured_attributes"],
                items=grouped_items[canonical_fact_key],
                gap_need_ids=gap_need_ids,
            )
        )

    source_gaps = _build_source_gaps(retrieved_sources_manifest["failed_source_needs"])
    candidate_claims, candidate_claim_evidence_links = _translate_research_candidates(
        raw_evidence=raw_evidence,
        evidence_records=evidence_records,
        source_gaps=source_gaps,
    )
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
        "candidate_claims_from_research": candidate_claims,
        "candidate_claim_evidence_links_from_research": candidate_claim_evidence_links,
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
    _validate_research_candidates_in_repository(repository)
    _validate_repository_quality_summary(repository["repository_quality_summary"])


def canonicalize_raw_evidence_item(item: dict[str, Any]) -> tuple[str, str, str, dict[str, Any]]:
    raw_fact_type = item["raw_fact_type"]
    canonical_fact_type = _generic_fact_type(raw_fact_type, item["evidence_category"], item["extracted_text_or_summary"])
    attributes = _structured_attributes(canonical_fact_type, item)
    canonical_fact_key = _canonical_fact_key(canonical_fact_type, item, attributes)
    return (
        canonical_fact_key,
        canonical_fact_type,
        f"Canonicalized {canonical_fact_type} from source-bounded evidence; values remain in structured attributes and supporting raw evidence.",
        attributes,
    )


def _build_evidence_record(
    record_index: int,
    canonical_fact_key: str,
    canonical_fact_type: str,
    normalized_fact_summary: str,
    structured_attributes: dict[str, Any],
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
        "structured_attributes": structured_attributes,
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
                "provider_source_gap_ids": _ordered_unique([failed_need["provider_source_gap_id"]] if failed_need.get("provider_source_gap_id") else []),
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


def _translate_research_candidates(
    raw_evidence: dict[str, Any],
    evidence_records: list[dict[str, Any]],
    source_gaps: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_claims = raw_evidence.get("candidate_claims_from_research") or []
    claim_evidence_links = raw_evidence.get("candidate_claim_evidence_links_from_research") or []
    if not candidate_claims and not claim_evidence_links:
        return [], []

    raw_items_by_id = {item["evidence_id"]: item for item in raw_evidence["raw_evidence_items"]}
    provider_evidence_to_record_ids: dict[str, list[str]] = defaultdict(list)
    for record in evidence_records:
        for raw_evidence_id in record["raw_evidence_ids"]:
            provider_evidence_id = raw_items_by_id.get(raw_evidence_id, {}).get("provider_evidence_id")
            if provider_evidence_id:
                provider_evidence_to_record_ids[provider_evidence_id].append(record["evidence_record_id"])

    source_gap_ids_by_provider_gap_id: dict[str, list[str]] = defaultdict(list)
    for source_gap in source_gaps:
        for provider_gap_id in source_gap.get("provider_source_gap_ids", []):
            source_gap_ids_by_provider_gap_id[provider_gap_id].append(source_gap["source_gap_id"])

    translated_candidates = []
    for candidate_claim in candidate_claims:
        provider_gap_ids = list(candidate_claim.get("related_source_gap_ids", []))
        related_source_gap_ids = _ordered_unique(
            source_gap_id
            for provider_gap_id in provider_gap_ids
            for source_gap_id in source_gap_ids_by_provider_gap_id.get(provider_gap_id, [])
        )
        candidate = dict(candidate_claim)
        candidate["provider_related_source_gap_ids"] = provider_gap_ids
        candidate["related_source_gap_ids"] = related_source_gap_ids
        candidate["source_bounded_precheck_status"] = "pending_m4_mapping"
        if provider_gap_ids and not related_source_gap_ids:
            candidate["source_bounded_precheck_status"] = "gap_reference_requires_repair"
        translated_candidates.append(candidate)

    translated_links = []
    for link in claim_evidence_links:
        evidence_item_id = link["evidence_item_id"]
        mapped_record_ids = _ordered_unique(provider_evidence_to_record_ids.get(evidence_item_id, []))
        translated_link = dict(link)
        translated_link["mapped_evidence_record_ids"] = mapped_record_ids
        translated_link["mapping_status"] = "mapped_to_evidence_record" if mapped_record_ids else "evidence_item_not_in_repository_requires_repair"
        translated_links.append(translated_link)
    return translated_candidates, translated_links


def _validate_research_candidates_in_repository(repository: dict[str, Any]) -> None:
    candidate_claims = repository.get("candidate_claims_from_research", [])
    claim_evidence_links = repository.get("candidate_claim_evidence_links_from_research", [])
    if not isinstance(candidate_claims, list):
        raise EvidenceRepositoryError("candidate_claims_from_research must be an array when present.")
    if not isinstance(claim_evidence_links, list):
        raise EvidenceRepositoryError("candidate_claim_evidence_links_from_research must be an array when present.")
    candidate_claim_ids: set[str] = set()
    source_gap_ids = {source_gap["source_gap_id"] for source_gap in repository["source_gaps"]}
    evidence_record_ids = {record["evidence_record_id"] for record in repository["evidence_records"]}
    for candidate_claim in candidate_claims:
        if not isinstance(candidate_claim, dict):
            raise EvidenceRepositoryError("Each candidate_claims_from_research entry must be an object.")
        candidate_claim_id = candidate_claim.get("candidate_claim_id")
        if not isinstance(candidate_claim_id, str) or not candidate_claim_id.strip():
            raise EvidenceRepositoryError("candidate_claims_from_research entry missing candidate_claim_id.")
        if candidate_claim_id in candidate_claim_ids:
            raise EvidenceRepositoryError(f"Duplicate candidate_claim_id in evidence_repository: {candidate_claim_id}")
        candidate_claim_ids.add(candidate_claim_id)
        if not isinstance(candidate_claim.get("claim_statement"), str) or not candidate_claim["claim_statement"].strip():
            raise EvidenceRepositoryError(f"candidate_claim missing non-empty claim_statement: {candidate_claim_id}")
        if candidate_claim.get("certification_status") == "certified" or candidate_claim.get("is_certified") is True or candidate_claim.get("certified") is True:
            raise EvidenceRepositoryError(f"candidate_claim must not be certified in evidence_repository: {candidate_claim_id}")
        unknown_gaps = sorted(set(candidate_claim.get("related_source_gap_ids", [])) - source_gap_ids)
        if unknown_gaps:
            raise EvidenceRepositoryError(f"candidate_claim maps to unknown source_gap_id(s): {candidate_claim_id} -> {', '.join(unknown_gaps)}")
    for link in claim_evidence_links:
        if not isinstance(link, dict):
            raise EvidenceRepositoryError("Each candidate_claim_evidence_links_from_research entry must be an object.")
        candidate_claim_id = link.get("candidate_claim_id")
        if candidate_claim_id not in candidate_claim_ids:
            raise EvidenceRepositoryError(f"candidate_claim_evidence_link references unknown candidate_claim_id: {candidate_claim_id}")
        mapped_record_ids = link.get("mapped_evidence_record_ids", [])
        if not isinstance(mapped_record_ids, list):
            raise EvidenceRepositoryError("candidate_claim_evidence_link mapped_evidence_record_ids must be an array.")
        unknown_records = sorted(set(mapped_record_ids) - evidence_record_ids)
        if unknown_records:
            raise EvidenceRepositoryError(f"candidate_claim_evidence_link maps to unknown evidence_record_id(s): {', '.join(unknown_records)}")


def _source_gap_enrichments(failed_need: dict[str, Any]) -> dict[str, Any]:
    description = str(failed_need.get("missing_source", "")).lower()
    reason = str(failed_need.get("reason", "")).lower()
    text = f"{description} {reason}"
    if any(term in text for term in ("ownership", "governance", "cap table", "seller economics")):
        return _generic_gap("Missing ownership, governance, cap table, or seller-economics evidence", ["ownership_or_governance"], ["WS-005", "WS-009"], "Ownership and value-transfer analysis must remain caveated until direct supporting sources are retrieved.")
    if any(term in text for term in ("consideration", "purchase price", "payment", "transaction terms")):
        return _generic_gap("Missing direct consideration or transaction-term evidence", ["transaction_consideration", "contingent_consideration", "milestone_payment"], ["WS-004", "WS-005"], "Deal economics must not be treated as source-supported until direct transaction evidence is retrieved.")
    if any(term in text for term in ("patent", "intellectual property", "ip ")):
        return _generic_gap("Missing intellectual-property evidence", ["intellectual_property"], ["WS-003", "WS-007"], "Asset or technology ownership and protection claims remain incomplete without IP evidence.")
    if any(term in text for term in ("clinical", "regulatory", "approval", "trial")):
        return _generic_gap("Missing clinical, regulatory, or approval evidence", ["regulatory_or_clinical"], ["WS-007", "WS-008"], "Regulatory and development-risk claims must remain caveated until authoritative evidence is retrieved.")
    if any(term in text for term in ("valuation", "financial", "revenue", "margin", "forecast")):
        return _generic_gap("Missing valuation or financial-support evidence", ["valuation_input", "financial_performance"], ["WS-004"], "Valuation and return analysis must remain unsupported until source-backed financial inputs are retrieved.")
    if any(term in text for term in ("quote", "page", "location", "excerpt")):
        return _generic_gap("Missing source quote, page, or location detail", ["generic_fact"], [], "Downstream citation and certification should not rely on this item until source location is repaired.")
    return {
        "missing_source_description": failed_need.get("missing_source") or f"Unresolved source need {failed_need['source_need_id']}",
        "affected_fact_types": [],
        "affected_workstreams": [],
        "downstream_risk": "Downstream stages must treat this unresolved source need as a gap until M2 retrieval repair is completed.",
    }


def _generic_gap(description: str, fact_types: list[str], workstreams: list[str], downstream_risk: str) -> dict[str, Any]:
    return {
        "missing_source_description": description,
        "affected_fact_types": fact_types,
        "affected_workstreams": workstreams,
        "downstream_risk": downstream_risk,
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
        f"Repair {len(source_gaps)} source gap(s) via M2_source_retrieval before downstream ownership, governance, consideration, IP, regulatory, valuation, or source-location claims are treated as source-supported.",
    ]
    if not any(record["canonical_fact_type"] == "transaction_consideration" for record in evidence_records):
        notes.append("No transaction consideration canonical fact was created because M3 did not see direct raw evidence support for that fact type in this input.")

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


def _generic_fact_type(raw_fact_type: str, evidence_category: str, summary: str) -> str:
    candidate = _safe_key(raw_fact_type)
    if candidate in GENERIC_FACT_TYPES:
        return candidate
    text = f"{raw_fact_type} {evidence_category} {summary}".lower()
    if any(term in text for term in ("document date", "agreement date", "signing date", "effective date")):
        return "transaction_document_date"
    if any(term in text for term in ("timing", "closing", "signed", "announced")):
        return "transaction_timing"
    if any(term in text for term in ("party", "buyer", "seller", "target", "acquirer")):
        return "transaction_parties"
    if any(term in text for term in ("milestone payment", "earnout payment", "contingent payment")):
        return "milestone_payment"
    if any(term in text for term in ("contingent", "earnout", "milestone consideration")):
        return "contingent_consideration"
    if any(term in text for term in ("consideration", "purchase price", "payment", "transaction value", "deal value")):
        return "transaction_consideration"
    if any(term in text for term in ("financing", "funding")):
        return "financing_or_payment_mechanics"
    if any(term in text for term in ("entity", "name history", "lineage", "predecessor", "successor")):
        return "entity_lineage"
    if any(term in text for term in ("asset", "product", "pipeline", "program", "platform")):
        return "asset_or_product_identity"
    if any(term in text for term in ("ownership", "governance", "shareholder", "cap table", "stake")):
        return "ownership_or_governance"
    if any(term in text for term in ("management", "director", "officer", "key person", "founder", "executive")):
        return "management_or_key_person"
    if any(term in text for term in ("patent", "intellectual property", "ip ", "assignee", "inventor")):
        return "intellectual_property"
    if any(term in text for term in ("regulatory", "clinical", "approval", "trial")):
        return "regulatory_or_clinical"
    if any(term in text for term in ("revenue", "margin", "profit", "ebitda")):
        return "financial_performance"
    if any(term in text for term in ("valuation", "return", "multiple")):
        return "valuation_input"
    if any(term in text for term in ("synergy", "value creation")):
        return "synergy_or_value_creation"
    if any(term in text for term in ("market", "competitive", "competitor", "customer")):
        return "market_or_competitive_position"
    if any(term in text for term in ("legal", "liability", "lawsuit", "consent")):
        return "legal_or_regulatory_risk"
    if any(term in text for term in ("integration", "operational", "systems", "transition")):
        return "integration_or_operational_risk"
    if any(term in text for term in ("gap", "missing", "unresolved", "not verified")):
        return "source_gap"
    return "generic_fact"


def _structured_attributes(canonical_fact_type: str, item: dict[str, Any]) -> dict[str, Any]:
    summary = item["extracted_text_or_summary"]
    attributes: dict[str, Any] = {"source_record_ids": [item["evidence_id"]]}
    amounts = _extract_amounts(summary)
    dates = _extract_dates(summary)
    percentages = _extract_percentages(summary)
    if canonical_fact_type in {"transaction_consideration", "contingent_consideration", "milestone_payment", "financing_or_payment_mechanics", "valuation_input", "financial_performance"} and amounts:
        attributes["amounts"] = amounts
        attributes["currency"] = "USD" if any("$" in amount for amount in amounts) else "unknown"
    if canonical_fact_type in {"transaction_timing", "transaction_document_date", "milestone_payment", "entity_lineage", "ownership_or_governance"} and dates:
        attributes["dates_or_periods"] = dates
    if canonical_fact_type == "milestone_payment":
        attributes["trigger_description"] = _bounded_attribute_text(summary)
    if canonical_fact_type == "transaction_document_date":
        attributes["document_type"] = _document_type(item)
    if canonical_fact_type == "ownership_or_governance" and percentages:
        attributes["stakes_or_percentages"] = percentages
    if canonical_fact_type in {"entity_identity", "entity_lineage", "asset_or_product_identity", "management_or_key_person", "intellectual_property"}:
        attributes["described_subject"] = _bounded_attribute_text(summary)
    if canonical_fact_type == "source_gap":
        attributes["missing_fact_type"] = "unknown"
        attributes["next_search_target"] = _bounded_attribute_text(summary)
    return attributes


def _canonical_fact_key(canonical_fact_type: str, item: dict[str, Any], attributes: dict[str, Any]) -> str:
    relation_ids = item.get("related_evidence_requirement_ids") or item.get("related_source_need_ids") or [item["source_id"]]
    relation_part = "_".join(_safe_key(str(value)) for value in relation_ids[:3])
    if canonical_fact_type == "transaction_consideration" and not attributes.get("amounts"):
        return f"{canonical_fact_type}__requires_numeric_verification__{relation_part}"
    return f"{canonical_fact_type}__{relation_part}"


def _extract_amounts(text: str) -> list[str]:
    amounts = []
    parts = text.replace(",", "").split()
    for index, part in enumerate(parts):
        cleaned = part.strip(".;:()[]")
        if cleaned.startswith("$") and any(character.isdigit() for character in cleaned):
            suffix = parts[index + 1].strip(".;:()[]") if index + 1 < len(parts) else ""
            if suffix.lower() in {"million", "billion", "thousand"}:
                amounts.append(f"{cleaned} {suffix}")
            else:
                amounts.append(cleaned)
    return _ordered_unique(amounts)


def _extract_dates(text: str) -> list[str]:
    values = []
    for raw in text.replace(",", "").split():
        token = raw.strip(".;:()[]")
        if len(token) == 4 and token.isdigit() and token.startswith(("19", "20")):
            values.append(token)
        if len(token) == 10 and token[4] == "-" and token[7] == "-":
            values.append(token)
    return _ordered_unique(values)


def _extract_percentages(text: str) -> list[str]:
    return _ordered_unique(token.strip(".;:()[]") for token in text.split() if "%" in token and any(character.isdigit() for character in token))


def _document_type(item: dict[str, Any]) -> str:
    text = f"{item['source_title']} {item['source_type']} {item['extracted_text_or_summary']}".lower()
    if "agreement" in text:
        return "transaction agreement"
    if "filing" in text:
        return "regulatory filing"
    if "presentation" in text:
        return "presentation"
    return "source document"


def _bounded_attribute_text(text: str) -> str:
    return " ".join(text.split())[:240]


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
    if canonical_fact_key.startswith("transaction_consideration__requires_numeric_verification"):
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
