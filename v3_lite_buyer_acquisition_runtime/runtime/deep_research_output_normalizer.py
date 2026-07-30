from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from v3_lite_buyer_acquisition_runtime.runtime.raw_evidence_extraction import EVIDENCE_TARGETS, validate_raw_evidence
from v3_lite_buyer_acquisition_runtime.runtime.source_discovery import source_discovery_plan_id
from v3_lite_buyer_acquisition_runtime.runtime.source_retrieval import manifest_id, validate_retrieved_sources_manifest


class DeepResearchNormalizationError(ValueError):
    pass


SOURCE_TIME_RELATIONS = {"pre_decision", "at_decision", "post_decision", "retrospective", "unknown"}
PERMITTED_USES = {
    "ex_ante_deal_evaluation",
    "transaction_terms_verification",
    "retrospective_outcome_validation",
    "source_lead_only",
    "gap_tracking",
}
FORBIDDEN_EVIDENCE_MARKERS = ("case_seed", "mandate notes", "user-provided notes", "model memory")
TIER_4_NON_AUTHORITATIVE_MARKERS = (
    "model-generated research summary",
    "deep research summary",
    "unofficial summary",
    "user-provided case brief",
    "blog",
)


def normalize_deep_research_output(
    deep_research_response: dict[str, Any],
    source_discovery_plan: dict[str, Any],
    decision_date_text: str,
    retrieved_by: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    decision_date = _parse_decision_date(decision_date_text)
    valid_source_need_ids = {need["source_need_id"] for need in source_discovery_plan["source_needs"]}
    valid_workstream_ids = {
        workstream_id for need in source_discovery_plan["source_needs"] for workstream_id in need["related_workstream_ids"]
    }
    valid_requirement_ids = {
        requirement_id for need in source_discovery_plan["source_needs"] for requirement_id in need["related_evidence_requirement_ids"]
    }
    search_query_ids = {query["query_id"] for query in source_discovery_plan["search_queries"]}
    search_queries_by_source_need = {
        need_id: sorted(
            query["query_id"]
            for query in source_discovery_plan["search_queries"]
            if need_id in query.get("related_source_need_ids", [])
        )
        for need_id in valid_source_need_ids
    }

    sources_by_provider_id = {source["provider_source_id"]: source for source in deep_research_response["sources"]}
    if not sources_by_provider_id:
        raise DeepResearchNormalizationError("Deep Research response contained zero sources; normalization failed closed.")

    source_to_need_ids: dict[str, set[str]] = {provider_source_id: set() for provider_source_id in sources_by_provider_id}
    raw_evidence_items: list[dict[str, Any]] = []
    failed_source_need_entries: list[dict[str, str]] = []

    for evidence_item in deep_research_response["evidence_items"]:
        provider_source_id = evidence_item.get("provider_source_id", "")
        if provider_source_id not in sources_by_provider_id:
            failed_source_need_entries.extend(
                _failed_entries_from_unresolved_item(
                    evidence_item,
                    source_discovery_plan,
                    "Deep Research evidence item referenced an unknown or missing source and was excluded from normalized raw evidence.",
                )
            )
            continue

        source = sources_by_provider_id[provider_source_id]
        related_source_need_ids = _normalize_related_ids(
            evidence_item.get("related_workstream_ids", []),
            evidence_item.get("related_evidence_requirement_ids", []),
            evidence_item.get("related_verification_target_ids", []),
            evidence_item.get("fact_type", ""),
            source,
            source_discovery_plan,
        )
        if related_source_need_ids:
            source_to_need_ids[provider_source_id].update(related_source_need_ids)
        if _contains_forbidden_evidence_marker(source) or _contains_forbidden_evidence_marker(evidence_item):
            failed_source_need_entries.extend(
                _failed_entries_from_unresolved_item(
                    evidence_item,
                    source_discovery_plan,
                    "Deep Research evidence referenced forbidden non-source material such as case_seed, mandate notes, user-provided notes, or model memory.",
                )
            )
            continue

        source_tier = _classify_source_tier(source)
        if source_tier == "Tier 4":
            failed_source_need_entries.extend(
                _failed_entries_from_unresolved_item(
                    evidence_item,
                    source_discovery_plan,
                    "Deep Research summary or other Tier 4 material is not treated as authoritative evidence; original cited sources are required.",
                )
            )
            continue

        if not related_source_need_ids:
            failed_source_need_entries.extend(
                _failed_entries_from_unresolved_item(
                    evidence_item,
                    source_discovery_plan,
                    "Deep Research evidence could not be mapped to a known source_need_id and was excluded.",
                )
            )
            continue
        source_to_need_ids[provider_source_id].update(related_source_need_ids)

        related_workstream_ids = _normalize_known_ids(
            evidence_item.get("related_workstream_ids", []),
            valid_workstream_ids,
            _fact_target_ids(evidence_item.get("fact_type", ""), "workstream_ids"),
        )
        related_requirement_ids = _normalize_known_ids(
            evidence_item.get("related_evidence_requirement_ids", []),
            valid_requirement_ids,
            _fact_target_ids(evidence_item.get("fact_type", ""), "requirement_ids"),
        )
        related_verification_ids = [verification_id for verification_id in evidence_item.get("related_verification_target_ids", []) if verification_id]
        if not related_verification_ids:
            related_verification_ids = _fact_target_ids(evidence_item.get("fact_type", ""), "verification_ids")

        temporal = _infer_temporal_metadata(source, decision_date)
        evidence_id = f"RE-DR-{len(raw_evidence_items) + 1:03d}-{_safe_id(provider_source_id)}"
        raw_evidence_items.append(
            {
                "evidence_id": evidence_id,
                "case_id": deep_research_response["case_id"],
                "source_id": _normalized_source_id(provider_source_id),
                "source_title": source["title"],
                "source_url_or_file": source["url"],
                "source_type": source["source_type"],
                "source_tier": source_tier,
                "retrieval_date": _date_text(deep_research_response["completed_at"]),
                "extraction_location": _normalized_extraction_location(source, evidence_item),
                "extracted_text_or_summary": evidence_item["extracted_text_or_summary"],
                "extraction_mode": _extraction_mode(evidence_item["extracted_text_or_summary"]),
                "related_source_need_ids": related_source_need_ids,
                "related_workstream_ids": related_workstream_ids,
                "related_evidence_requirement_ids": related_requirement_ids,
                "related_verification_target_ids": related_verification_ids,
                "evidence_category": _fact_target_value(evidence_item.get("fact_type", ""), "category") or "deep_research_candidate",
                "raw_fact_type": evidence_item["fact_type"],
                "confidence_preliminary": _normalized_confidence(evidence_item.get("confidence_preliminary", ""), source_tier),
                "source_is_authoritative": source_tier in {"Tier 1", "Tier 2"} and _has_authoritative_locator(source),
                "case_seed_only": False,
                "extraction_notes": (
                    "Normalized from an external Deep Research cited source. Original cited source matters; provider narrative is not certified evidence."
                ),
                "downstream_use_warning": _downstream_use_warning(source_tier, temporal["permitted_use"]),
                "evidence_time_relation_to_decision_date": temporal["source_time_relation_to_decision_date"],
                "permitted_use": temporal["permitted_use"],
                "hindsight_leakage_warning": _hindsight_leakage_warning(temporal["source_time_relation_to_decision_date"]),
            }
        )

    for unresolved_gap in deep_research_response["unresolved_gaps"]:
        failed_source_need_entries.extend(_failed_entries_from_gap(unresolved_gap, source_discovery_plan))

    normalized_sources = []
    for provider_source_id, source in sources_by_provider_id.items():
        related_source_need_ids = sorted(source_to_need_ids[provider_source_id])
        if not related_source_need_ids:
            related_source_need_ids = _infer_source_need_ids_from_text(
                _source_context_text(source),
                source_discovery_plan,
            )
        if not related_source_need_ids:
            raise DeepResearchNormalizationError(
                f"Deep Research source {provider_source_id} could not be mapped to any source_need_id; normalization failed closed."
            )
        if set(related_source_need_ids) - valid_source_need_ids:
            raise DeepResearchNormalizationError(f"Deep Research source {provider_source_id} mapped to unknown source_need_id.")
        related_search_query_ids = sorted(
            {
                query_id
                for source_need_id in related_source_need_ids
                for query_id in search_queries_by_source_need.get(source_need_id, [])
                if query_id in search_query_ids
            }
        )
        temporal = _infer_temporal_metadata(source, decision_date)
        source_tier = _classify_source_tier(source)
        normalized_sources.append(
            {
                "source_id": _normalized_source_id(provider_source_id),
                "title": source["title"],
                "url_or_file": source["url"],
                "source_type": source["source_type"],
                "source_tier": source_tier,
                "source_owner": source["source_owner"],
                "retrieval_date": _date_text(deep_research_response["completed_at"]),
                "retrieved_by": retrieved_by,
                "related_source_need_ids": related_source_need_ids,
                "related_search_query_ids": related_search_query_ids,
                "reliability_reason": source["source_reliability_rationale"],
                "use_limitations": _use_limitations(source, source_tier, temporal["permitted_use"]),
                "source_date_or_period": source["source_date_or_period"],
                "source_time_relation_to_decision_date": temporal["source_time_relation_to_decision_date"],
                "permitted_use": temporal["permitted_use"],
                "local_cache_path": source["url"],
            }
        )

    failed_source_needs = _dedupe_failed_source_needs(failed_source_need_entries)
    manifest = {
        "case_id": deep_research_response["case_id"],
        "generated_artifact": "retrieved_sources_manifest.json",
        "retrieval_mode": "deep_research",
        "retrieval_date": _date_text(deep_research_response["completed_at"]),
        "source_discovery_plan_id": source_discovery_plan_id(source_discovery_plan),
        "evidence_coverage_status": "partial" if failed_source_needs else "complete",
        "retrieved_sources": normalized_sources,
        "failed_source_needs": failed_source_needs,
    }
    validate_retrieved_sources_manifest(manifest, source_discovery_plan, allow_remote_sources=True)

    raw_evidence = {
        "case_id": deep_research_response["case_id"],
        "generated_artifact": "raw_evidence.json",
        "stage": "M2_raw_evidence_extraction",
        "source_bounded": True,
        "evidence_coverage_status": manifest["evidence_coverage_status"],
        "failed_source_needs": manifest["failed_source_needs"],
        "external_retrieval_performed": True,
        "source_discovery_plan_id": manifest["source_discovery_plan_id"],
        "retrieved_sources_manifest_id": manifest_id(manifest),
        "raw_evidence_items": raw_evidence_items,
    }
    validate_raw_evidence(raw_evidence, manifest, source_discovery_plan)
    return manifest, raw_evidence


def _failed_entries_from_unresolved_item(
    evidence_item: dict[str, Any],
    source_discovery_plan: dict[str, Any],
    reason: str,
) -> list[dict[str, str]]:
    source_need_ids = _normalize_related_ids(
        evidence_item.get("related_workstream_ids", []),
        evidence_item.get("related_evidence_requirement_ids", []),
        evidence_item.get("related_verification_target_ids", []),
        evidence_item.get("fact_type", ""),
        evidence_item,
        source_discovery_plan,
    )
    if not source_need_ids:
        source_need_ids = _infer_source_need_ids_from_text(
            " ".join(
                str(part)
                for part in (
                    evidence_item.get("fact_type", ""),
                    evidence_item.get("extracted_text_or_summary", ""),
                    " ".join(evidence_item.get("caveats", [])),
                )
            ),
            source_discovery_plan,
        )
    if not source_need_ids:
        raise DeepResearchNormalizationError(
            f"Could not map Deep Research evidence item {evidence_item.get('provider_evidence_id', '<unknown>')} to source needs."
        )
    return [{"source_need_id": source_need_id, "reason": reason} for source_need_id in source_need_ids]


def _failed_entries_from_gap(unresolved_gap: dict[str, Any], source_discovery_plan: dict[str, Any]) -> list[dict[str, str]]:
    source_need_ids = _infer_source_need_ids_from_text(
        " ".join(
            [
                unresolved_gap["gap_description"],
                unresolved_gap["reason_unresolved"],
                unresolved_gap["recommended_next_search"],
                " ".join(unresolved_gap.get("attempted_source_types", [])),
            ]
        ),
        source_discovery_plan,
    )
    if not source_need_ids:
        raise DeepResearchNormalizationError(f"Could not map unresolved gap {unresolved_gap['gap_id']} to source_need_id.")
    return [
        {
            "source_need_id": source_need_id,
            "reason": f"{unresolved_gap['gap_description']} Unresolved because: {unresolved_gap['reason_unresolved']}",
        }
        for source_need_id in source_need_ids
    ]


def _normalize_related_ids(
    related_workstream_ids: list[str],
    related_requirement_ids: list[str],
    related_verification_ids: list[str],
    fact_type: str,
    source_or_item: dict[str, Any],
    source_discovery_plan: dict[str, Any],
) -> list[str]:
    source_needs = source_discovery_plan["source_needs"]
    mapped = sorted(
        {
            need["source_need_id"]
            for need in source_needs
            if set(related_workstream_ids).intersection(need.get("related_workstream_ids", []))
            or set(related_requirement_ids).intersection(need.get("related_evidence_requirement_ids", []))
            or set(related_verification_ids).intersection(need.get("related_verification_target_ids", []))
        }
    )
    if mapped:
        return mapped
    return _infer_source_need_ids_from_text(_source_context_text(source_or_item), source_discovery_plan)


def _normalize_known_ids(candidate_ids: list[str], valid_ids: set[str], fallback_ids: list[str]) -> list[str]:
    normalized = [candidate_id for candidate_id in candidate_ids if candidate_id in valid_ids]
    if normalized:
        return sorted(set(normalized))
    return [fallback_id for fallback_id in fallback_ids if fallback_id in valid_ids]


def _fact_target_ids(fact_type: str, field: str) -> list[str]:
    for target in EVIDENCE_TARGETS:
        if target["fact_type"] == fact_type:
            value = target.get(field, [])
            return list(value) if isinstance(value, list) else []
    return []


def _fact_target_value(fact_type: str, field: str) -> str | None:
    for target in EVIDENCE_TARGETS:
        if target["fact_type"] == fact_type:
            value = target.get(field)
            return str(value) if value is not None else None
    return None


def _infer_source_need_ids_from_text(text: str, source_discovery_plan: dict[str, Any]) -> list[str]:
    normalized_text = text.lower()
    scored_matches: list[tuple[int, str]] = []
    for need in source_discovery_plan["source_needs"]:
        tokens = _keywords_for_need(need)
        score = sum(1 for token in tokens if token in normalized_text)
        if score:
            scored_matches.append((score, need["source_need_id"]))
    if not scored_matches:
        return []
    best_score = max(score for score, _ in scored_matches)
    return sorted({need_id for score, need_id in scored_matches if score == best_score})


def _keywords_for_need(need: dict[str, Any]) -> tuple[str, ...]:
    target_text = " ".join(
        str(part)
        for part in (
            need.get("purpose", ""),
            need.get("target_fact_or_question", ""),
            " ".join(need.get("preferred_source_types", [])),
        )
        if part
    )
    return tuple(_generic_tokens(target_text))


def _generic_tokens(text: str) -> list[str]:
    stopwords = {
        "about",
        "against",
        "authoritative",
        "before",
        "buyer",
        "candidate",
        "company",
        "direct",
        "evidence",
        "fact",
        "filing",
        "known",
        "locate",
        "official",
        "question",
        "source",
        "sources",
        "target",
        "transaction",
        "without",
    }
    tokens = []
    current = ""
    for character in text.lower():
        if character.isalnum() or character in {"-", "_", "$", "%"}:
            current += character
        else:
            if len(current) >= 5 and current not in stopwords:
                tokens.append(current)
            current = ""
    if len(current) >= 5 and current not in stopwords:
        tokens.append(current)
    return _ordered_unique(tokens)[:16]


def _ordered_unique(values: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _classify_source_tier(source: dict[str, Any]) -> str:
    text = _source_context_text(source)
    if _contains_forbidden_evidence_marker(source) or any(marker in text for marker in TIER_4_NON_AUTHORITATIVE_MARKERS):
        return "Tier 4"
    provided_tier = source.get("source_tier")
    if provided_tier in {"Tier 1", "Tier 2", "Tier 3", "Tier 4"}:
        return provided_tier
    if any(marker in text for marker in ("sec filing", "sec ", "10-k", "s-1", "424b4", "stock purchase agreement", "regulator", "stock exchange", "patent office", "clinicaltrials", "clinical trial registry", "regulatory database")):
        return "Tier 1"
    if any(marker in text for marker in ("press release", "investor presentation", "pipeline page", "official company", "company website", "official website")):
        return "Tier 2"
    if any(marker in text for marker in ("reuters", "bloomberg", "financial news", "transaction database", "conference bio", "secondary profile", "news")):
        return "Tier 3"
    if any(marker in text for marker in TIER_4_NON_AUTHORITATIVE_MARKERS):
        return "Tier 4"
    return "Tier 4"


def _infer_temporal_metadata(source: dict[str, Any], decision_date: date) -> dict[str, str]:
    provided_relation = source.get("source_time_relation_to_decision_date")
    provided_use = source.get("permitted_use")
    if provided_relation in SOURCE_TIME_RELATIONS and provided_use in PERMITTED_USES:
        return {
            "source_time_relation_to_decision_date": provided_relation,
            "permitted_use": provided_use,
        }
    text = _source_context_text(source)
    period = str(source.get("source_date_or_period", "")).lower()
    if "current as of retrieval" in period or "current" in period or "pipeline page" in text:
        return {
            "source_time_relation_to_decision_date": "retrospective",
            "permitted_use": "retrospective_outcome_validation",
        }
    if "stock purchase agreement" in text or "signed agreement" in text:
        return {
            "source_time_relation_to_decision_date": "at_decision",
            "permitted_use": "transaction_terms_verification",
        }
    years = _extract_years(period) or _extract_years(text)
    if years:
        earliest = min(years)
        latest = max(years)
        if latest < decision_date.year:
            return {
                "source_time_relation_to_decision_date": "pre_decision",
                "permitted_use": "ex_ante_deal_evaluation",
            }
        if earliest > decision_date.year:
            return {
                "source_time_relation_to_decision_date": "post_decision",
                "permitted_use": "retrospective_outcome_validation",
            }
        if earliest == decision_date.year or latest == decision_date.year:
            if any(marker in text for marker in ("agreement", "sec filing", "stock exchange", "regulator filing")):
                return {
                    "source_time_relation_to_decision_date": "at_decision",
                    "permitted_use": "transaction_terms_verification",
                }
            return {
                "source_time_relation_to_decision_date": "at_decision",
                "permitted_use": "ex_ante_deal_evaluation",
            }
    return {
        "source_time_relation_to_decision_date": "unknown",
        "permitted_use": "source_lead_only",
    }


def _contains_forbidden_evidence_marker(payload: dict[str, Any]) -> bool:
    text = _source_context_text(payload)
    return any(marker in text for marker in FORBIDDEN_EVIDENCE_MARKERS)


def _has_authoritative_locator(source: dict[str, Any]) -> bool:
    locator = str(source.get("url", "")).strip().lower()
    if locator.startswith("http://") or locator.startswith("https://"):
        return True
    return any(marker in locator for marker in ("sec-", "sec ", "patent", "clinicaltrials", "accession", "exhibit"))


def _normalized_source_id(provider_source_id: str) -> str:
    return f"SRC-DR-{_safe_id(provider_source_id)}"


def _normalized_extraction_location(source: dict[str, Any], evidence_item: dict[str, Any]) -> dict[str, Any]:
    location = evidence_item.get("extraction_location_if_available")
    if isinstance(location, dict):
        return location
    if isinstance(location, str) and location.strip():
        return {"provider_location": location.strip(), "source_url": source["url"]}
    return {"provider_source_id": source["provider_source_id"], "source_url": source["url"]}


def _extraction_mode(extracted_text_or_summary: str) -> str:
    if len(extracted_text_or_summary) <= 360:
        return "exact_quote"
    return "bounded_summary"


def _normalized_confidence(confidence: str, source_tier: str) -> str:
    value = confidence.strip().lower()
    if value in {"high", "medium", "low"}:
        return value
    if source_tier == "Tier 1":
        return "high"
    if source_tier == "Tier 2":
        return "medium"
    return "low"


def _downstream_use_warning(source_tier: str, permitted_use: str) -> str:
    if source_tier in {"Tier 3", "Tier 4"}:
        return (
            "Deep Research normalized evidence from a non-primary source. Use only as a lead or low-confidence contextual input until a higher-tier source confirms it."
        )
    if permitted_use != "transaction_terms_verification" and permitted_use != "ex_ante_deal_evaluation":
        return (
            "Deep Research normalized evidence is source-bounded but time-limited. Do not use as ex-ante decision support without downstream caveat and certification."
        )
    return (
        "Deep Research normalized evidence is source-bounded raw evidence only. Do not use as a certified claim, valuation conclusion, recommendation, or final-report assertion until downstream validation."
    )


def _use_limitations(source: dict[str, Any], source_tier: str, permitted_use: str) -> str:
    limitations = [str(source.get("source_limitations", "")).strip()]
    if source_tier == "Tier 4":
        limitations.append("Tier 4 material is not authoritative and should not directly support transaction economics.")
    if permitted_use in {"retrospective_outcome_validation", "source_lead_only", "gap_tracking"}:
        limitations.append("Temporal scope limits this source to retrospective validation, lead generation, or gap tracking.")
    return " ".join(part for part in limitations if part)


def _hindsight_leakage_warning(source_time_relation_to_decision_date: str) -> str:
    if source_time_relation_to_decision_date == "at_decision":
        return "No hindsight leakage warning: source is contemporaneous with the transaction decision date and limited to its permitted use."
    if source_time_relation_to_decision_date == "pre_decision":
        return "No hindsight leakage warning: source predates the decision date, subject to reliability and downstream certification."
    if source_time_relation_to_decision_date == "post_decision":
        return "Hindsight leakage warning: post-decision evidence may support retrospective validation, but must not support ex-ante buyer decision claims without explicit caveat."
    if source_time_relation_to_decision_date == "retrospective":
        return "Hindsight leakage warning: retrospective evidence may support outcome validation or source leads, but must not be treated as decision-date evidence without explicit caveat."
    return "Temporal relation unknown: use only as a source lead or gap-tracking input until downstream validation resolves timing."


def _source_context_text(payload: dict[str, Any]) -> str:
    return " ".join(str(value).lower() for value in payload.values() if isinstance(value, (str, int, float)))


def _parse_decision_date(decision_date_text: str) -> date:
    try:
        return date.fromisoformat(decision_date_text)
    except ValueError as exc:
        raise DeepResearchNormalizationError(f"Invalid decision_date for Deep Research normalization: {decision_date_text}") from exc


def _date_text(timestamp: str) -> str:
    if "T" in timestamp:
        return timestamp.split("T", 1)[0]
    return timestamp


def _extract_years(text: str) -> list[int]:
    years: list[int] = []
    current = ""
    for character in text:
        if character.isdigit():
            current += character
            continue
        if len(current) == 4 and current.startswith(("19", "20")):
            years.append(int(current))
        current = ""
    if len(current) == 4 and current.startswith(("19", "20")):
        years.append(int(current))
    return years


def _safe_id(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value)


def _dedupe_failed_source_needs(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        key = (entry["source_need_id"], entry["reason"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped
