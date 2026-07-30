from __future__ import annotations

from pathlib import Path
from typing import Any

from v3_lite_buyer_acquisition_runtime.runtime.source_discovery import source_discovery_plan_id
from v3_lite_buyer_acquisition_runtime.runtime.source_retrieval import PERMITTED_USES, SOURCE_TIME_RELATIONS, SourceRetrievalError, manifest_id, resolve_source_path


class RawEvidenceExtractionError(ValueError):
    pass


EVIDENCE_TARGETS = [
    {"category": "transaction", "fact_type": "transaction_background"},
    {"category": "transaction", "fact_type": "transaction_timing"},
    {"category": "transaction", "fact_type": "transaction_document_date"},
    {"category": "transaction", "fact_type": "transaction_parties"},
    {"category": "transaction", "fact_type": "transaction_consideration"},
    {"category": "transaction", "fact_type": "contingent_consideration"},
    {"category": "transaction", "fact_type": "milestone_payment"},
    {"category": "transaction", "fact_type": "financing_or_payment_mechanics"},
    {"category": "identity", "fact_type": "entity_identity"},
    {"category": "identity", "fact_type": "entity_lineage"},
    {"category": "identity", "fact_type": "asset_or_product_identity"},
    {"category": "governance", "fact_type": "ownership_or_governance"},
    {"category": "governance", "fact_type": "management_or_key_person"},
    {"category": "diligence", "fact_type": "intellectual_property"},
    {"category": "diligence", "fact_type": "regulatory_or_clinical"},
    {"category": "financial", "fact_type": "financial_performance"},
    {"category": "financial", "fact_type": "valuation_input"},
    {"category": "strategy", "fact_type": "synergy_or_value_creation"},
    {"category": "market", "fact_type": "market_or_competitive_position"},
    {"category": "risk", "fact_type": "legal_or_regulatory_risk"},
    {"category": "risk", "fact_type": "integration_or_operational_risk"},
    {"category": "source_uncertainty", "fact_type": "source_gap"},
    {"category": "generic", "fact_type": "generic_fact"},
]

STOPWORDS = {
    "about",
    "against",
    "and",
    "authoritative",
    "before",
    "buyer",
    "case",
    "company",
    "direct",
    "evidence",
    "fact",
    "filing",
    "from",
    "into",
    "lead",
    "materials",
    "needed",
    "official",
    "only",
    "source",
    "sources",
    "supporting",
    "target",
    "that",
    "this",
    "transaction",
    "with",
}


def extract_raw_evidence(source_discovery_plan: dict[str, Any], retrieved_sources_manifest: dict[str, Any], manifest_path: Path | None = None) -> dict[str, Any]:
    source_ids = {source["source_id"] for source in retrieved_sources_manifest["retrieved_sources"]}
    items: list[dict[str, Any]] = []

    for source in retrieved_sources_manifest["retrieved_sources"]:
        try:
            source_path = resolve_source_path(source, manifest_path)
        except SourceRetrievalError as exc:
            raise RawEvidenceExtractionError(str(exc)) from exc
        text = source_path.read_text(encoding="utf-8")
        items.extend(_extract_items_from_text(text, source, source_path, source_discovery_plan))

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


def _extract_items_from_text(text: str, source: dict[str, Any], source_path: Path, source_discovery_plan: dict[str, Any]) -> list[dict[str, Any]]:
    lower = text.lower()
    items = []
    for target in _derived_evidence_targets(source_discovery_plan, source):
        anchor = _best_anchor(lower, target["keywords"])
        if anchor is None:
            continue
        snippet, location = _bounded_snippet(text, anchor, source_path)
        items.append(
            {
                "evidence_id": f"RE-{len(items) + 1:03d}-{source['source_id']}",
                "case_id": source_discovery_plan["case_id"],
                "source_id": source["source_id"],
                "source_title": source["title"],
                "source_url_or_file": source["url_or_file"],
                "source_type": source["source_type"],
                "source_tier": source["source_tier"],
                "retrieval_date": source["retrieval_date"],
                "extraction_location": location,
                "extracted_text_or_summary": snippet,
                "extraction_mode": _extraction_mode(snippet, [anchor]),
                "related_source_need_ids": target["need_ids"],
                "related_workstream_ids": target["workstream_ids"],
                "related_evidence_requirement_ids": target["requirement_ids"],
                "related_verification_target_ids": target["verification_ids"],
                "evidence_category": target["category"],
                "raw_fact_type": target["fact_type"],
                "confidence_preliminary": "medium" if source["source_tier"] in {"Tier 1", "Tier 2"} else "low",
                "source_is_authoritative": source["source_tier"] in {"Tier 1", "Tier 2"},
                "case_seed_only": False,
                "extraction_notes": "Deterministic bounded extraction from retrieved source manifest source and generic source-discovery target; not normalized, certified, or analyzed.",
                "downstream_use_warning": "Raw evidence only. Do not use as a certified claim, valuation conclusion, recommendation, or final-report assertion until later validation and certification stages.",
                "evidence_time_relation_to_decision_date": source["source_time_relation_to_decision_date"],
                "permitted_use": source["permitted_use"],
                "hindsight_leakage_warning": _hindsight_leakage_warning(source),
            }
        )
    return items


def _derived_evidence_targets(source_discovery_plan: dict[str, Any], source: dict[str, Any]) -> list[dict[str, Any]]:
    related_need_ids = set(source.get("related_source_need_ids", []))
    needs = [need for need in source_discovery_plan["source_needs"] if not related_need_ids or need["source_need_id"] in related_need_ids]
    targets = []
    for need in needs:
        context = _target_context(need, source)
        fact_type = _classify_fact_type(_need_context(need))
        category = _category_for_fact_type(fact_type)
        keywords = _keywords_from_context(context)
        if not keywords:
            keywords = _keywords_from_context(_source_context(source))
        if not keywords:
            continue
        targets.append(
            {
                "category": category,
                "fact_type": fact_type,
                "keywords": keywords,
                "need_ids": [need["source_need_id"]],
                "workstream_ids": need.get("related_workstream_ids", []),
                "requirement_ids": need.get("related_evidence_requirement_ids", []),
                "verification_ids": need.get("related_verification_target_ids", []),
            }
        )
    return _dedupe_targets(targets)


def _target_context(need: dict[str, Any], source: dict[str, Any]) -> str:
    return " ".join(
        str(part)
        for part in (
            need.get("purpose", ""),
            need.get("target_fact_or_question", ""),
            " ".join(need.get("preferred_source_types", [])),
            _source_context(source),
        )
        if part
    )


def _need_context(need: dict[str, Any]) -> str:
    return " ".join(
        str(part)
        for part in (
            need.get("purpose", ""),
            need.get("target_fact_or_question", ""),
            " ".join(need.get("preferred_source_types", [])),
        )
        if part
    )


def _source_context(source: dict[str, Any]) -> str:
    return " ".join(
        str(source.get(field, ""))
        for field in ("title", "source_type", "source_owner", "source_date_or_period", "reliability_reason", "use_limitations")
    )


def _classify_fact_type(context: str) -> str:
    text = context.lower()
    if any(term in text for term in ("cap table", "seller economics", "ownership", "governance", "shareholder", "shareholding")):
        return "ownership_or_governance"
    if any(term in text for term in ("management", "director", "officer", "key person", "founder", "executive")):
        return "management_or_key_person"
    if any(term in text for term in ("milestone payment", "earnout payment", "contingent payment")):
        return "milestone_payment"
    if any(term in text for term in ("contingent", "earnout", "milestone consideration")):
        return "contingent_consideration"
    if any(term in text for term in ("consideration", "purchase price", "deal value", "transaction value", "payment")):
        return "transaction_consideration"
    if any(term in text for term in ("financing", "payment mechanics", "funding")):
        return "financing_or_payment_mechanics"
    if any(term in text for term in ("agreement date", "document date", "signing date", "effective date")):
        return "transaction_document_date"
    if any(term in text for term in ("timing", "closing", "signing", "announcement date", "transaction date")):
        return "transaction_timing"
    if any(term in text for term in ("party", "parties", "buyer", "seller", "target company", "acquirer")):
        return "transaction_parties"
    if any(term in text for term in ("entity history", "name history", "lineage", "successor", "predecessor")):
        return "entity_lineage"
    if any(term in text for term in ("entity identity", "company identity", "corporate identity")):
        return "entity_identity"
    if any(term in text for term in ("asset", "product", "pipeline", "program", "drug", "platform")):
        return "asset_or_product_identity"
    if any(term in text for term in ("patent", "intellectual property", "ip ", "inventor", "assignee")):
        return "intellectual_property"
    if any(term in text for term in ("regulatory", "clinical", "approval", "trial", "compliance")):
        return "regulatory_or_clinical"
    if any(term in text for term in ("financial performance", "revenue", "margin", "profit", "ebitda")):
        return "financial_performance"
    if any(term in text for term in ("valuation", "return", "multiple", "discount rate")):
        return "valuation_input"
    if any(term in text for term in ("synergy", "value creation", "strategic rationale")):
        return "synergy_or_value_creation"
    if any(term in text for term in ("market", "competitive", "competitor", "customer")):
        return "market_or_competitive_position"
    if any(term in text for term in ("legal", "liability", "lawsuit", "consent", "regulatory risk")):
        return "legal_or_regulatory_risk"
    if any(term in text for term in ("integration", "operational", "systems", "transition")):
        return "integration_or_operational_risk"
    if any(term in text for term in ("gap", "missing", "unresolved", "not verified")):
        return "source_gap"
    if "transaction" in text:
        return "transaction_background"
    return "generic_fact"


def _category_for_fact_type(fact_type: str) -> str:
    for target in EVIDENCE_TARGETS:
        if target["fact_type"] == fact_type:
            return target["category"]
    return "generic"


def _keywords_from_context(context: str) -> list[str]:
    tokens = []
    current = ""
    for character in context.lower():
        if character.isalnum() or character in {"$", "%", "-", "_"}:
            current += character
        else:
            if _keyword_is_useful(current):
                tokens.append(current)
            current = ""
    if _keyword_is_useful(current):
        tokens.append(current)
    return _ordered_unique(tokens)[:12]


def _keyword_is_useful(token: str) -> bool:
    return len(token) >= 5 and token not in STOPWORDS and not token.startswith(("ws-", "er-", "vt-", "sn-"))


def _best_anchor(lower_text: str, keywords: list[str]) -> str | None:
    for keyword in keywords:
        if keyword.lower() in lower_text:
            return keyword
    return None


def _dedupe_targets(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = []
    seen = set()
    for target in targets:
        key = (tuple(target["need_ids"]), target["fact_type"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(target)
    return deduped


def _ordered_unique(values: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


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
