from __future__ import annotations

from typing import Any


class SourceDiscoveryPlanValidationError(ValueError):
    pass


def build_source_discovery_plan(case_seed: dict[str, Any], research_plan: dict[str, Any]) -> dict[str, Any]:
    if case_seed["case_id"] != research_plan["case_id"]:
        raise SourceDiscoveryPlanValidationError("case_seed and research_plan case_id values must match.")

    is_fronthera_case = "fronthera" in _context_text(case_seed, research_plan).lower()
    if is_fronthera_case:
        plan = _build_fronthera_source_discovery_plan(case_seed, research_plan)
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


def _build_fronthera_source_discovery_plan(case_seed: dict[str, Any], research_plan: dict[str, Any]) -> dict[str, Any]:
    source_needs = [
        _source_need("SN-001", "Confirm transaction agreement", "SEC stock purchase agreement dated March 5, 2021 for FronThera acquisition", ["SEC filings", "signed transaction agreements"], "Tier 1", ["WS-001", "WS-005"], ["ER-001", "ER-006"], ["VT-001", "VT-002", "VT-003"]),
        _source_need("SN-002", "Confirm consideration structure", "$60M base initial consideration, up to $120M milestone consideration, and $180M maximum aggregate deal value", ["SEC filings", "signed transaction agreements"], "Tier 1", ["WS-005", "WS-006"], ["ER-001", "ER-006"], ["VT-001", "VT-003"]),
        _source_need("SN-003", "Confirm later milestone payments", "Alumis filing support for $37M 2022 milestone and $23M 2024 milestone", ["SEC filings", "annual reports", "prospectus"], "Tier 1", ["WS-006"], ["ER-002", "ER-006"], ["VT-001", "VT-002"]),
        _source_need("SN-004", "Confirm entity lineage", "FL2021-001 -> Esker Therapeutics -> Alumis name and entity history", ["SEC filings", "company filings", "company press releases"], "Tier 1", ["WS-001", "WS-003"], ["ER-002"], ["VT-005"]),
        _source_need("SN-005", "Confirm Bohan Jin role and ownership lead", "Haisco disclosure on FronThera ownership, Bohan Jin role, director status, and 2017 11.12% shareholding", ["stock exchange announcements", "company filings"], "Tier 1", ["WS-004"], ["ER-003", "ER-007"], ["VT-004", "VT-007"]),
        _source_need("SN-006", "Confirm patent and asset lineage", "TYK2 inhibitor patents related to FronThera / Esker / Alumis", ["official patent databases", "regulator filings"], "Tier 1", ["WS-002", "WS-003", "WS-004"], ["ER-004", "ER-005"], ["VT-006"]),
        _source_need("SN-007", "Confirm official pipeline identity", "ESK-001 / envudeucitinib official Alumis pipeline or clinical source", ["official company pipeline pages", "clinical trial databases", "regulatory filings"], "Tier 1", ["WS-002", "WS-003", "WS-008"], ["ER-005"], ["VT-006"]),
        _source_need("SN-008", "Identify source gap", "Direct evidence for Bohan Jin personal proceeds and FronThera cap table immediately before 2021 transaction", ["SEC filings", "company filings", "stock exchange announcements"], "Tier 1", ["WS-004", "WS-009"], ["ER-003", "ER-007"], ["VT-004", "VT-007"]),
    ]
    search_queries = [
        _search_query("SQ-001", "FronThera stock purchase agreement March 5 2021 Exhibit 10.22 SEC", "Find Tier 1 agreement exhibit", "SEC filing", "Tier 1", ["SN-001", "SN-002"], ["WS-001", "WS-005"], ["VT-001", "VT-003"]),
        _search_query("SQ-002", "Alumis FronThera acquisition $60 million $120 million milestone $180 million", "Find filing support for consideration structure", "SEC filing", "Tier 1", ["SN-002"], ["WS-005", "WS-006"], ["VT-001", "VT-003"]),
        _search_query("SQ-003", "Alumis 10-K 2024 FronThera $37 million 2022 $23 million 2024 milestone", "Find filing support for paid milestones", "SEC filing", "Tier 1", ["SN-003"], ["WS-006"], ["VT-001", "VT-002"]),
        _search_query("SQ-004", "FL2021-001 Esker Therapeutics Alumis name history SEC", "Find entity/name history", "SEC filing", "Tier 1", ["SN-004"], ["WS-001", "WS-003"], ["VT-005"]),
        _search_query("SQ-005", "Haisco FronThera Bohan Jin 11.12% VP Chemistry director", "Find direct ownership and role disclosure", "stock exchange announcement", "Tier 1", ["SN-005", "SN-008"], ["WS-004"], ["VT-004", "VT-007"]),
        _search_query("SQ-006", "FronThera Esker Alumis TYK2 inhibitor patent ESK-001 envudeucitinib", "Find patent and asset lineage support", "patent database", "Tier 1", ["SN-006"], ["WS-002", "WS-003"], ["VT-006"]),
        _search_query("SQ-007", "Alumis ESK-001 envudeucitinib pipeline TYK2 official", "Find official pipeline evidence", "official company pipeline page", "Tier 2", ["SN-007"], ["WS-002", "WS-003", "WS-008"], ["VT-006"]),
    ]
    retrieval_targets = [
        _retrieval_target("RT-001", "SEC filing or exhibit containing FronThera stock purchase agreement Exhibit 10.22", "SEC / Alumis", "SEC filing", "high", ["SN-001", "SN-002"]),
        _retrieval_target("RT-002", "Alumis annual report, S-1, prospectus, or 10-K showing milestone payments", "SEC / Alumis", "SEC filing", "high", ["SN-003"]),
        _retrieval_target("RT-003", "SEC or company filing showing FL2021-001 to Esker Therapeutics to Alumis history", "SEC / Alumis", "SEC filing", "high", ["SN-004"]),
        _retrieval_target("RT-004", "Haisco disclosure for FronThera ownership and Bohan Jin role / 11.12% shareholding", "Haisco / stock exchange", "stock exchange announcement", "high", ["SN-005", "SN-008"]),
        _retrieval_target("RT-005", "Official patent database records for TYK2 inhibitor chemistry related to FronThera / Esker / Alumis", "Official patent database", "patent database", "medium", ["SN-006"]),
        _retrieval_target("RT-006", "Official Alumis pipeline page or clinical database entry for ESK-001 / envudeucitinib", "Alumis / clinical trial database", "official pipeline or clinical database", "medium", ["SN-007"]),
    ]

    return _plan(case_seed, source_needs, search_queries, retrieval_targets)


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
        _retrieval_target("RT-001", "Authoritative documents for transaction terms and buyer-side diligence", "Official source owner", "official source", "high", _all_ids(source_needs)),
    ]
    return _plan(case_seed, source_needs, search_queries, retrieval_targets)


def _plan(case_seed: dict[str, Any], source_needs: list[dict[str, Any]], search_queries: list[dict[str, Any]], retrieval_targets: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_id": case_seed["case_id"],
        "seed_id": case_seed["seed_id"],
        "generated_artifact": "source_discovery_plan.json",
        "discovery_scope": "Find authoritative buyer-side acquisition sources. Case seed is a lead source only and cannot directly support high-confidence evidence.",
        "source_needs": source_needs,
        "search_queries": search_queries,
        "retrieval_targets": retrieval_targets,
        "source_priority_rules": [
            "Tier 1 sources are preferred for transaction economics, signed agreements, regulatory filings, patent, clinical, and stock-exchange evidence.",
            "Tier 2 official company sources may support pipeline and company identity facts when Tier 1 is unavailable.",
            "Tier 3 reputable secondary sources may provide leads or context but should not replace official sources for deal economics.",
            "Tier 4 case briefs can generate leads but cannot alone support high-confidence transaction economics.",
            "Personal proceeds require direct evidence or remain unverified."
        ],
        "forbidden_source_uses": [
            "Do not use model memory as evidence.",
            "Do not use case_seed facts as source-backed evidence.",
            "Do not cite web search results unless the retrieved source is logged in retrieved_sources_manifest.json.",
            "Do not resolve source conflicts in M2; record them for later certification."
        ]
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


def _all_ids(items: list[dict[str, Any]]) -> list[str]:
    return [item.get("id") or item.get("source_need_id") for item in items if item.get("id") or item.get("source_need_id")]


def _context_text(case_seed: dict[str, Any], research_plan: dict[str, Any]) -> str:
    return "\n".join([
        case_seed.get("case_id", ""),
        " ".join(case_seed.get("case_parties", {}).get("target", [])),
        " ".join(case_seed.get("transaction_leads", [])),
        " ".join(case_seed.get("key_assets_or_topics", [])),
        research_plan.get("research_objective", ""),
    ])

