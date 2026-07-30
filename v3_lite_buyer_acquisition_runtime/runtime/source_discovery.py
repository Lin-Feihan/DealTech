from __future__ import annotations

from typing import Any


class SourceDiscoveryPlanValidationError(ValueError):
    pass


def build_source_discovery_plan(case_seed: dict[str, Any], research_plan: dict[str, Any]) -> dict[str, Any]:
    if case_seed["case_id"] != research_plan["case_id"]:
        raise SourceDiscoveryPlanValidationError("case_seed and research_plan case_id values must match.")

    plan = _build_generic_source_discovery_plan(case_seed, research_plan)
    validate_source_discovery_plan(plan)
    return plan


def source_discovery_plan_id(plan: dict[str, Any]) -> str:
    return f"SDP-{plan['case_id']}-{plan['seed_id']}"


def validate_source_discovery_plan(plan: Any) -> None:
    if not isinstance(plan, dict):
        raise SourceDiscoveryPlanValidationError("source_discovery_plan must be an object.")
    required = (
        "case_id",
        "seed_id",
        "generated_artifact",
        "discovery_scope",
        "source_needs",
        "search_queries",
        "retrieval_targets",
        "source_priority_rules",
        "forbidden_source_uses",
    )
    missing = [field for field in required if field not in plan]
    if missing:
        raise SourceDiscoveryPlanValidationError(f"Missing source discovery field(s): {', '.join(missing)}")
    if plan["generated_artifact"] != "source_discovery_plan.json":
        raise SourceDiscoveryPlanValidationError("generated_artifact must be source_discovery_plan.json.")
    for field in ("source_needs", "search_queries", "retrieval_targets"):
        if not isinstance(plan[field], list) or not plan[field]:
            raise SourceDiscoveryPlanValidationError(f"{field} must be a non-empty array.")

    source_need_ids = {need["source_need_id"] for need in plan["source_needs"]}
    for query in plan["search_queries"]:
        unknown = set(query.get("related_source_need_ids", [])) - source_need_ids
        if unknown:
            raise SourceDiscoveryPlanValidationError(f"Search query references unknown source_need_id(s): {sorted(unknown)}")
    for target in plan["retrieval_targets"]:
        unknown = set(target.get("related_source_need_ids", [])) - source_need_ids
        if unknown:
            raise SourceDiscoveryPlanValidationError(f"Retrieval target references unknown source_need_id(s): {sorted(unknown)}")


def _build_generic_source_discovery_plan(case_seed: dict[str, Any], research_plan: dict[str, Any]) -> dict[str, Any]:
    source_needs = _build_source_needs(research_plan)
    source_needs.extend(_build_case_seed_source_needs(case_seed, research_plan, len(source_needs) + 1))
    search_queries = _build_search_queries(case_seed, research_plan, source_needs)
    retrieval_targets = _build_retrieval_targets(source_needs)
    return _plan(case_seed, source_needs, search_queries, retrieval_targets)


def _build_source_needs(research_plan: dict[str, Any]) -> list[dict[str, Any]]:
    workstream_ids = _all_ids(research_plan.get("workstreams", []))
    verification_target_ids = _all_ids(research_plan.get("verification_targets", []))
    source_needs = []
    for index, requirement in enumerate(research_plan.get("evidence_requirements", []), start=1):
        source_needs.append(
            _source_need(
                f"SN-{index:03d}",
                "Locate authoritative source for evidence requirement",
                requirement["description"],
                _preferred_source_types_for_requirement(requirement["description"]),
                "Tier 1 preferred",
                workstream_ids,
                [requirement["id"]],
                verification_target_ids,
            )
        )
    return source_needs


def _build_case_seed_source_needs(
    case_seed: dict[str, Any],
    research_plan: dict[str, Any],
    start_index: int,
) -> list[dict[str, Any]]:
    workstream_ids = _all_ids(research_plan.get("workstreams", []))
    requirement_ids = _all_ids(research_plan.get("evidence_requirements", []))
    verification_target_ids = _all_ids(research_plan.get("verification_targets", []))
    source_needs = []
    for offset, lead in enumerate(_case_seed_leads(case_seed), start=0):
        source_needs.append(
            _source_need(
                f"SN-{start_index + offset:03d}",
                "Locate authoritative source for case seed lead",
                lead,
                _preferred_source_types_for_requirement(lead),
                "Tier 1 preferred",
                workstream_ids,
                requirement_ids,
                verification_target_ids,
            )
        )
    return source_needs


def _build_search_queries(
    case_seed: dict[str, Any],
    research_plan: dict[str, Any],
    source_needs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    target = case_seed["case_parties"]["target"][0]
    buyer_names = case_seed.get("case_parties", {}).get("buyer_or_acquiring_vehicle", [])
    buyer = buyer_names[0] if buyer_names else "buyer"
    workstream_ids = _all_ids(research_plan.get("workstreams", []))
    verification_target_ids = _all_ids(research_plan.get("verification_targets", []))
    search_queries = []

    for index, lead in enumerate(_case_seed_leads(case_seed), start=1):
        need = source_needs[min(index - 1, len(source_needs) - 1)]
        search_queries.append(
            _search_query(
                f"SQ-{index:03d}",
                f"{target} {buyer} {lead}",
                "Find authoritative source for case seed lead without treating the seed as evidence.",
                _expected_source_type_for_lead(lead),
                "Tier 1 preferred",
                [need["source_need_id"]],
                workstream_ids,
                verification_target_ids,
            )
        )

    if not search_queries:
        search_queries.append(
            _search_query(
                "SQ-001",
                f"{target} {buyer} acquisition official filing transaction agreement",
                "Find authoritative transaction and diligence sources for the buyer-side acquisition case.",
                "official source",
                "Tier 1 preferred",
                [source_needs[0]["source_need_id"]],
                workstream_ids,
                verification_target_ids,
            )
        )
    return search_queries


def _case_seed_leads(case_seed: dict[str, Any]) -> list[str]:
    leads = list(case_seed.get("source_leads", []))
    leads.extend(case_seed.get("transaction_leads", []))
    leads.extend(case_seed.get("key_assets_or_topics", []))
    return leads


def _build_retrieval_targets(source_needs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_need_ids = _all_ids(source_needs)
    return [
        _retrieval_target(
            "RT-001",
            "Transaction agreements, announcements, regulatory filings, or official disclosures supporting deal terms and timing",
            "Buyer, target, seller, regulator, or securities filing system",
            "transaction agreement or official filing",
            "high",
            source_need_ids,
        ),
        _retrieval_target(
            "RT-002",
            "Audited financials, management materials, investor presentations, and other source-backed business-quality inputs",
            "Buyer, target, auditor, regulator, or investor-relations source",
            "financial or business disclosure",
            "high",
            source_need_ids,
        ),
        _retrieval_target(
            "RT-003",
            "Market, competitive, legal, regulatory, diligence, intellectual-property, and integration-risk sources relevant to the acquisition scope",
            "Regulator, court, patent office, industry source, company disclosure, or reputable secondary source",
            "diligence source",
            "medium",
            source_need_ids,
        ),
    ]


def _plan(
    case_seed: dict[str, Any],
    source_needs: list[dict[str, Any]],
    search_queries: list[dict[str, Any]],
    retrieval_targets: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "case_id": case_seed["case_id"],
        "seed_id": case_seed["seed_id"],
        "generated_artifact": "source_discovery_plan.json",
        "discovery_scope": "Find authoritative buyer-side acquisition sources. Case seed is a lead source only and cannot directly support high-confidence evidence.",
        "source_needs": source_needs,
        "search_queries": search_queries,
        "retrieval_targets": retrieval_targets,
        "source_priority_rules": [
            "Tier 1 sources are preferred for transaction economics, signed agreements, regulatory filings, official buyer or target disclosures, audited financials, legal, regulatory, and intellectual-property evidence.",
            "Tier 2 official company sources, investor presentations, and management materials may support strategy, business-quality, pipeline, market-position, synergy, and integration facts when Tier 1 is unavailable.",
            "Tier 3 market, industry, and reputable secondary sources may provide leads or context but should not replace official sources for transaction economics, valuation inputs, or legal claims.",
            "Case briefs, analyst notes, and mandate materials can generate leads but cannot alone support high-confidence transaction economics or diligence conclusions.",
            "Seller economics, ownership, liability, and value-transfer claims require direct evidence or remain unverified.",
        ],
        "forbidden_source_uses": [
            "Do not use model memory as evidence.",
            "Do not use case_seed facts as source-backed evidence.",
            "Do not cite web search results unless the retrieved source is logged in retrieved_sources_manifest.json.",
            "Do not resolve source conflicts in M2; record them for later certification.",
        ],
    }


def _source_need(id_: str, purpose: str, target: str, preferred_types: list[str], tier: str, workstreams: list[str], requirements: list[str], verification_targets: list[str]) -> dict[str, Any]:
    return {
        "source_need_id": id_,
        "purpose": purpose,
        "target_fact_or_question": target,
        "preferred_source_types": preferred_types,
        "preferred_source_tier": tier,
        "related_workstream_ids": workstreams,
        "related_evidence_requirement_ids": requirements,
        "related_verification_target_ids": verification_targets,
    }


def _search_query(id_: str, text: str, purpose: str, expected_type: str, tier: str, source_need_ids: list[str], workstreams: list[str], verification_targets: list[str]) -> dict[str, Any]:
    return {
        "query_id": id_,
        "query_text": text,
        "purpose": purpose,
        "expected_source_type": expected_type,
        "source_tier_target": tier,
        "related_source_need_ids": source_need_ids,
        "related_workstream_ids": workstreams,
        "related_verification_target_ids": verification_targets,
    }


def _retrieval_target(id_: str, description: str, owner: str, expected_type: str, priority: str, source_need_ids: list[str]) -> dict[str, Any]:
    return {
        "target_id": id_,
        "target_description": description,
        "likely_source_owner": owner,
        "expected_source_type": expected_type,
        "priority": priority,
        "related_source_need_ids": source_need_ids,
    }


def _preferred_source_types_for_requirement(description: str) -> list[str]:
    text = description.lower()
    preferred = ["official buyer or target disclosures", "company filings"]
    if any(term in text for term in ("transaction", "timing", "parties", "structure")):
        preferred.extend(["signed transaction agreements", "regulatory filings"])
    if any(term in text for term in ("financial", "valuation", "purchase-price", "financing", "return")):
        preferred.extend(["audited financials", "investor presentations"])
    if any(term in text for term in ("market", "competitive", "customer")):
        preferred.extend(["market reports", "industry reports"])
    if any(term in text for term in ("legal", "regulatory", "technology", "liability")):
        preferred.extend(["legal documents", "regulatory databases", "intellectual-property records"])
    return sorted(set(preferred))


def _expected_source_type_for_lead(lead: str) -> str:
    text = lead.lower()
    if any(term in text for term in ("agreement", "transaction", "filing", "prospectus", "annual report")):
        return "official filing or transaction agreement"
    if any(term in text for term in ("financial", "revenue", "margin", "forecast", "valuation")):
        return "financial disclosure"
    if any(term in text for term in ("market", "industry", "competitor", "customer")):
        return "market or industry source"
    if any(term in text for term in ("legal", "regulatory", "patent", "license", "approval")):
        return "legal, regulatory, or intellectual-property source"
    return "official source"


def _all_ids(items: list[dict[str, Any]]) -> list[str]:
    return [item.get("id") or item.get("source_need_id") for item in items if item.get("id") or item.get("source_need_id")]
