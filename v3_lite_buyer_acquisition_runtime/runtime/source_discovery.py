from __future__ import annotations

from typing import Any

from v3_lite_buyer_acquisition_runtime.runtime.case_profile_loader import load_case_profile_for_case_id


class SourceDiscoveryPlanValidationError(ValueError):
    pass


def build_source_discovery_plan(case_seed: dict[str, Any], research_plan: dict[str, Any]) -> dict[str, Any]:
    if case_seed["case_id"] != research_plan["case_id"]:
        raise SourceDiscoveryPlanValidationError("case_seed and research_plan case_id values must match.")

    case_profile = load_case_profile_for_case_id(case_seed["case_id"])
    if case_profile:
        discovery_profile = case_profile["source_discovery_profile"]
        plan = _plan(
            case_seed,
            discovery_profile["source_needs"],
            discovery_profile["search_queries"],
            discovery_profile["retrieval_targets"],
            discovery_profile["source_priority_rules"],
            discovery_profile["forbidden_source_uses"],
        )
    else:
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
    source_needs = []
    for index, requirement in enumerate(research_plan.get("evidence_requirements", []), start=1):
        source_needs.append(
            _source_need(
                f"SN-{index:03d}",
                "Locate authoritative source for evidence requirement",
                requirement["description"],
                ["SEC filings", "company filings", "official sources", "reputable financial news"],
                "Tier 1 preferred",
                _all_ids(research_plan.get("workstreams", [])),
                [requirement["id"]],
                _all_ids(research_plan.get("verification_targets", [])),
            )
        )
    search_queries = [
        _search_query(
            f"SQ-{index:03d}",
            f"{case_seed['case_parties']['target'][0]} {lead}",
            "Find authoritative source for case seed lead without treating the seed as evidence.",
            "official source",
            "Tier 1 preferred",
            [source_needs[min(index - 1, len(source_needs) - 1)]["source_need_id"]],
            _all_ids(research_plan.get("workstreams", [])),
            _all_ids(research_plan.get("verification_targets", [])),
        )
        for index, lead in enumerate(case_seed.get("source_leads", []), start=1)
    ]
    retrieval_targets = [
        _retrieval_target(
            "RT-001",
            "Authoritative documents for transaction terms and buyer-side diligence",
            "Official source owner",
            "official source",
            "high",
            _all_ids(source_needs),
        ),
    ]
    return _plan(
        case_seed,
        source_needs,
        search_queries,
        retrieval_targets,
        _default_source_priority_rules(),
        _default_forbidden_source_uses(),
    )


def _plan(
    case_seed: dict[str, Any],
    source_needs: list[dict[str, Any]],
    search_queries: list[dict[str, Any]],
    retrieval_targets: list[dict[str, Any]],
    source_priority_rules: list[str],
    forbidden_source_uses: list[str],
) -> dict[str, Any]:
    return {
        "case_id": case_seed["case_id"],
        "seed_id": case_seed["seed_id"],
        "generated_artifact": "source_discovery_plan.json",
        "discovery_scope": "Find authoritative buyer-side acquisition sources. Case seed is a lead source only and cannot directly support high-confidence evidence.",
        "source_needs": source_needs,
        "search_queries": search_queries,
        "retrieval_targets": retrieval_targets,
        "source_priority_rules": source_priority_rules,
        "forbidden_source_uses": forbidden_source_uses,
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


def _default_source_priority_rules() -> list[str]:
    return [
        "Tier 1 sources are preferred for transaction economics, signed agreements, regulatory filings, patent, clinical, and stock-exchange evidence.",
        "Tier 2 official company sources may support pipeline and company identity facts when Tier 1 is unavailable.",
        "Tier 3 reputable secondary sources may provide leads or context but should not replace official sources for deal economics.",
        "Tier 4 case briefs can generate leads but cannot alone support high-confidence transaction economics.",
        "Personal proceeds require direct evidence or remain unverified.",
    ]


def _default_forbidden_source_uses() -> list[str]:
    return [
        "Do not use model memory as evidence.",
        "Do not use case_seed facts as source-backed evidence.",
        "Do not cite web search results unless the retrieved source is logged in retrieved_sources_manifest.json.",
        "Do not resolve source conflicts in M2; record them for later certification.",
    ]


def _all_ids(items: list[dict[str, Any]]) -> list[str]:
    return [item.get("id") or item.get("source_need_id") for item in items if item.get("id") or item.get("source_need_id")]
