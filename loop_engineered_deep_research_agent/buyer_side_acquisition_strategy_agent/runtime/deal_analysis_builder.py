from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.claim_certifier import (
    certification_result_source_id,
    evidence_repository_source_id,
    graph_source_id,
)


class DealAnalysisError(ValueError):
    pass


ALLOWED_FACT_STATUSES = {"certified", "certified_with_caveat"}
BLOCKED_FACT_STATUSES = {"unsupported", "blocked_by_source_gap", "failed", "requires_numeric_verification"}
ANALYSIS_READINESS_STATUSES = {
    "ready_for_limited_analysis",
    "limited_by_repair_required",
    "blocked_by_certification_failure",
    "human_review_required",
}
REQUIRED_ANALYSIS_SECTION_IDS = [
    "transaction_logic",
    "buyer_strategic_objectives",
    "target_business_quality",
    "industry_and_competitive_position",
    "strategic_fit",
    "standalone_financial_analysis",
    "valuation_and_acceptable_price",
    "synergy_and_value_creation",
    "deal_structure",
    "financing_and_capital_structure",
    "return_analysis",
    "due_diligence_priorities",
    "regulatory_integration_and_downside_risks",
    "decision_recommendation_readiness",
]
ANALYSIS_SECTION_IDS = set(REQUIRED_ANALYSIS_SECTION_IDS)
ANALYSIS_SECTION_STATUSES = {
    "ready",
    "limited",
    "blocked_by_missing_evidence",
    "not_assessable_due_to_missing_evidence",
    "human_review_required",
    "not_applicable",
    "blocked_by_certification_failure",
}
CONFIDENCE_VALUES = {"high", "medium", "low", "not_assessable"}
OPTIONAL_EXHIBIT_STATUSES = {"ready", "skeleton_only", "blocked_by_missing_inputs", "not_applicable"}
FRAMEWORK_PATH = Path(__file__).resolve().parents[1] / "config" / "buyer_acquisition_analysis_framework.json"
FINAL_RECOMMENDATION_TERMS = ("Proceed", "Proceed with Conditions", "Renegotiate", "Defer", "Walk Away")


def load_json_artifact(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise DealAnalysisError(f"Artifact not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DealAnalysisError(f"Invalid JSON artifact at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DealAnalysisError(f"Artifact at {path} must be a JSON object.")
    return payload


def load_analysis_framework(path: Path = FRAMEWORK_PATH) -> dict[str, Any]:
    framework = load_json_artifact(path)
    validate_analysis_framework(framework)
    return framework


def validate_analysis_framework(framework: Any) -> None:
    if not isinstance(framework, dict):
        raise DealAnalysisError("analysis framework must be an object.")
    sections = framework.get("sections")
    if not isinstance(sections, list):
        raise DealAnalysisError("analysis framework must include sections array.")
    section_ids = [section.get("section_id") for section in sections if isinstance(section, dict)]
    if section_ids != REQUIRED_ANALYSIS_SECTION_IDS:
        raise DealAnalysisError("analysis framework must contain exactly the 14 required M6B sections in order.")
    for section in sections:
        if not isinstance(section, dict):
            raise DealAnalysisError("analysis framework sections must be objects.")
        for field in (
            "section_id",
            "section_title",
            "business_question",
            "analyst_lens",
            "interpretation_rules",
            "buyer_implication_rules",
            "decision_impact_rules",
            "analysis_boundary_rules",
            "relevant_claim_types",
            "optional_exhibits",
        ):
            if field not in section:
                raise DealAnalysisError(f"analysis framework section missing {field}.")
        if not isinstance(section["optional_exhibits"], list):
            raise DealAnalysisError("analysis framework optional_exhibits must be arrays.")


def build_analysis_package(
    certification_result: dict[str, Any],
    claim_evidence_graph: dict[str, Any],
    evidence_repository: dict[str, Any],
    research_gaps: dict[str, Any],
    repair_plan: dict[str, Any],
) -> dict[str, Any]:
    validate_m6_inputs(certification_result, claim_evidence_graph, evidence_repository, research_gaps, repair_plan)
    analysis_framework = load_analysis_framework()
    claim_certs_by_id = {claim["claim_id"]: claim for claim in certification_result["claim_certifications"]}
    claims_by_id = {claim["claim_id"]: claim for claim in claim_evidence_graph["claim_nodes"]}
    records_by_id = {record["evidence_record_id"]: record for record in evidence_repository["evidence_records"]}
    research_gaps_by_id = {gap["research_gap_id"]: gap for gap in research_gaps["research_gaps"]}
    repair_steps_by_gap_id = {
        gap_id: step
        for step in repair_plan["repair_steps"]
        for gap_id in step["related_research_gap_ids"]
    }
    analysis_readiness_status = _analysis_readiness_status(certification_result)
    analysis_gate = certification_result["analysis_gate_summary"]
    report_gate = certification_result["report_gate_summary"]
    recommendation_gate = certification_result["recommendation_gate_summary"]
    consumed_certified_claim_ids = list(analysis_gate["analysis_allowed_claim_ids"])
    consumed_caveated_claim_ids = list(analysis_gate["analysis_caveated_claim_ids"])
    excluded_claim_ids = list(analysis_gate["analysis_blocked_claim_ids"])
    package = {
        "case_id": certification_result["case_id"],
        "generated_artifact": "analysis_package.json",
        "stage": "M6_evidence_bounded_deal_analysis",
        "source_bounded": True,
        "evidence_coverage_status": certification_result["evidence_coverage_status"],
        "created_from_certification_result_id": certification_result_source_id(certification_result),
        "created_from_claim_evidence_graph_id": graph_source_id(claim_evidence_graph),
        "created_from_evidence_repository_id": evidence_repository_source_id(evidence_repository),
        "created_at": _now_utc_iso(),
        "analysis_readiness_status": analysis_readiness_status,
        "recommendation_allowed": recommendation_gate["recommendation_allowed"],
        "final_report_allowed": not bool(report_gate["report_blocked_claim_ids"]),
        "supporting_claim_ids": consumed_certified_claim_ids + consumed_caveated_claim_ids,
        "consumed_certified_claim_ids": consumed_certified_claim_ids,
        "consumed_caveated_claim_ids": consumed_caveated_claim_ids,
        "excluded_claim_ids": excluded_claim_ids,
        "exclusion_reasons": _exclusion_reasons(certification_result),
        "preserved_caveats": _preserved_caveats(claim_certs_by_id, consumed_caveated_claim_ids),
        "recommendation_gate_status": _recommendation_gate_status(recommendation_gate),
        "report_gate_status": _report_gate_status(report_gate),
        "analysis_sections": _analysis_sections(
            analysis_framework,
            certification_result,
            claim_certs_by_id,
            claims_by_id,
            records_by_id,
            research_gaps,
            repair_plan,
            analysis_gate,
        ),
        "blocked_analysis_items": _blocked_analysis_items(claim_certs_by_id, claims_by_id, research_gaps_by_id, repair_steps_by_gap_id),
        "caveats": _package_caveats(certification_result),
        "human_review_items": certification_result["human_review_items"],
        "next_action": _next_action(certification_result),
    }
    validate_analysis_package(package, certification_result)
    return package


def validate_m6_inputs(
    certification_result: Any,
    claim_evidence_graph: Any,
    evidence_repository: Any,
    research_gaps: Any,
    repair_plan: Any,
) -> None:
    artifacts = {
        "certification_result": certification_result,
        "claim_evidence_graph": claim_evidence_graph,
        "evidence_repository": evidence_repository,
        "research_gaps": research_gaps,
        "repair_plan": repair_plan,
    }
    for name, payload in artifacts.items():
        if not isinstance(payload, dict):
            raise DealAnalysisError(f"{name} must be an object.")
    expected_metadata = {
        "certification_result": ("certification_result.json", "M5_loop_certification"),
        "claim_evidence_graph": ("claim_evidence_graph.json", "M4_claim_evidence_graph"),
        "evidence_repository": ("evidence_repository.json", "M3_evidence_repository"),
        "research_gaps": ("research_gaps.json", "M5_research_gaps"),
        "repair_plan": ("repair_plan.json", "M5_repair_plan"),
    }
    for name, (artifact, stage) in expected_metadata.items():
        payload = artifacts[name]
        if payload.get("generated_artifact") != artifact:
            raise DealAnalysisError(f"M6 requires {artifact} input for {name}.")
        if payload.get("stage") != stage:
            raise DealAnalysisError(f"M6 requires {name}.stage == {stage}.")
    if certification_result.get("source_bounded") is not True:
        raise DealAnalysisError("M6 requires source_bounded certification_result.")
    if claim_evidence_graph.get("source_bounded") is not True:
        raise DealAnalysisError("M6 requires source_bounded claim_evidence_graph.")
    if evidence_repository.get("source_bounded") is not True:
        raise DealAnalysisError("M6 requires source_bounded evidence_repository.")
    case_ids = {payload.get("case_id") for payload in artifacts.values()}
    if len(case_ids) != 1:
        raise DealAnalysisError("M6 input case_id values must match.")
    if not isinstance(certification_result.get("claim_certifications"), list):
        raise DealAnalysisError("certification_result must include claim_certifications array.")
    for field in ("analysis_gate_summary", "report_gate_summary", "recommendation_gate_summary"):
        if not isinstance(certification_result.get(field), dict):
            raise DealAnalysisError(f"certification_result must include {field} object.")
    _validate_m5_gate_summaries(certification_result)
    if not isinstance(certification_result.get("human_review_items"), list):
        raise DealAnalysisError("certification_result must include human_review_items array.")
    if not isinstance(certification_result.get("numeric_verification_results"), list):
        raise DealAnalysisError("certification_result must include numeric_verification_results array.")
    if not isinstance(claim_evidence_graph.get("claim_nodes"), list):
        raise DealAnalysisError("claim_evidence_graph must include claim_nodes array.")
    if not isinstance(research_gaps.get("research_gaps"), list):
        raise DealAnalysisError("research_gaps must include research_gaps array.")
    if not isinstance(repair_plan.get("repair_steps"), list):
        raise DealAnalysisError("repair_plan must include repair_steps array.")


def validate_analysis_package(package: Any, certification_result: dict[str, Any] | None = None) -> None:
    if not isinstance(package, dict):
        raise DealAnalysisError("analysis_package must be an object.")
    required = {
        "case_id",
        "generated_artifact",
        "stage",
        "source_bounded",
        "evidence_coverage_status",
        "created_from_certification_result_id",
        "created_from_claim_evidence_graph_id",
        "created_from_evidence_repository_id",
        "analysis_readiness_status",
        "recommendation_allowed",
        "final_report_allowed",
        "supporting_claim_ids",
        "consumed_certified_claim_ids",
        "consumed_caveated_claim_ids",
        "excluded_claim_ids",
        "exclusion_reasons",
        "preserved_caveats",
        "recommendation_gate_status",
        "report_gate_status",
        "analysis_sections",
        "blocked_analysis_items",
        "caveats",
        "human_review_items",
        "next_action",
    }
    missing = sorted(field for field in required if field not in package)
    if missing:
        raise DealAnalysisError(f"analysis_package missing field(s): {', '.join(missing)}")
    if package["generated_artifact"] != "analysis_package.json":
        raise DealAnalysisError("generated_artifact must be analysis_package.json.")
    if package["stage"] != "M6_evidence_bounded_deal_analysis":
        raise DealAnalysisError("stage must be M6_evidence_bounded_deal_analysis.")
    if package["source_bounded"] is not True:
        raise DealAnalysisError("analysis_package must be source_bounded.")
    if package["analysis_readiness_status"] not in ANALYSIS_READINESS_STATUSES:
        raise DealAnalysisError("invalid analysis_readiness_status.")
    if certification_result and certification_result["overall_certification_status"] == "repair_required":
        if package["analysis_readiness_status"] != "limited_by_repair_required":
            raise DealAnalysisError("repair_required certification must produce limited_by_repair_required analysis readiness.")
    if certification_result:
        if package["recommendation_allowed"] != certification_result["recommendation_gate_summary"]["recommendation_allowed"]:
            raise DealAnalysisError("recommendation_allowed must match M5 recommendation_gate_summary.")
        expected_final_report_allowed = not bool(certification_result["report_gate_summary"]["report_blocked_claim_ids"])
        if package["final_report_allowed"] != expected_final_report_allowed:
            raise DealAnalysisError("final_report_allowed must match M5 report_gate_summary.")
        if set(package["supporting_claim_ids"]) != set(certification_result["analysis_gate_summary"]["analysis_allowed_claim_ids"] + certification_result["analysis_gate_summary"]["analysis_caveated_claim_ids"]):
            raise DealAnalysisError("supporting_claim_ids must consume only M5 analysis gate allowed and caveated claims.")
        if set(package["supporting_claim_ids"]).intersection(certification_result["analysis_gate_summary"]["analysis_blocked_claim_ids"]):
            raise DealAnalysisError("analysis_blocked_claim_ids cannot appear in supporting_claim_ids.")
    section_ids = [section.get("section_id") for section in package["analysis_sections"]]
    if section_ids != REQUIRED_ANALYSIS_SECTION_IDS:
        raise DealAnalysisError("analysis_sections must include exactly the required M6B professional buyer-side sections in order.")
    for section in package["analysis_sections"]:
        _validate_section(section)
    for item in package["blocked_analysis_items"]:
        for field in ("blocked_item_id", "blocked_topic", "reason", "related_research_gap_ids", "required_repair_target", "can_appear_in_final_report"):
            if field not in item:
                raise DealAnalysisError(f"blocked_analysis_item missing {field}.")
        if item["can_appear_in_final_report"] is not False:
            raise DealAnalysisError("blocked_analysis_items cannot appear in final report unless repaired or caveated.")


def _analysis_sections(
    analysis_framework: dict[str, Any],
    certification_result: dict[str, Any],
    claim_certs_by_id: dict[str, dict[str, Any]],
    claims_by_id: dict[str, dict[str, Any]],
    records_by_id: dict[str, dict[str, Any]],
    research_gaps: dict[str, Any],
    repair_plan: dict[str, Any],
    analysis_gate: dict[str, Any],
) -> list[dict[str, Any]]:
    supporting_claim_ids = set(analysis_gate["analysis_allowed_claim_ids"] + analysis_gate["analysis_caveated_claim_ids"])
    blocked_claim_ids = set(analysis_gate["analysis_blocked_claim_ids"])
    sections = []
    for framework_section in analysis_framework["sections"]:
        sections.append(
            _framework_section(
                framework_section,
                certification_result,
                claim_certs_by_id,
                claims_by_id,
                records_by_id,
                research_gaps,
                repair_plan,
                supporting_claim_ids,
                blocked_claim_ids,
            )
        )
    return sections


def _framework_section(
    framework_section: dict[str, Any],
    certification_result: dict[str, Any],
    claim_certs_by_id: dict[str, dict[str, Any]],
    claims_by_id: dict[str, dict[str, Any]],
    records_by_id: dict[str, dict[str, Any]],
    research_gaps: dict[str, Any],
    repair_plan: dict[str, Any],
    supporting_claim_ids: set[str],
    blocked_claim_ids: set[str],
) -> dict[str, Any]:
    section_id = framework_section["section_id"]
    included_claims, excluded_claims, evidence_record_ids, caveats, findings = _section_claim_material(
        framework_section,
        claim_certs_by_id,
        claims_by_id,
        records_by_id,
        supporting_claim_ids,
        blocked_claim_ids,
    )
    related_gaps = _related_gaps_for_section(section_id, framework_section, research_gaps)
    pending_diligence_items = _pending_diligence_items(section_id, related_gaps, repair_plan)
    missing_inputs = _missing_inputs(framework_section, related_gaps, included_claims)
    if section_id in {"due_diligence_priorities", "decision_recommendation_readiness"}:
        pending_diligence_items = _dedupe_dicts(pending_diligence_items + _pending_diligence_items(section_id, research_gaps["research_gaps"], repair_plan))
        missing_inputs = sorted(set(missing_inputs + [gap["gap_type"] for gap in research_gaps["research_gaps"]]))
    status = _section_status(section_id, certification_result, included_claims, pending_diligence_items)
    confidence = _section_confidence(status, included_claims, pending_diligence_items)
    usable_fact_profile = _usable_fact_profile(included_claims, claim_certs_by_id, claims_by_id)
    imported_limitations = _imported_limitations_from_m5(section_id, related_gaps, pending_diligence_items, certification_result)
    analyst_interpretation = _analyst_interpretation(section_id, framework_section, usable_fact_profile, imported_limitations)
    buyer_implication = _buyer_implication(section_id, framework_section, usable_fact_profile, imported_limitations)
    decision_impact = _decision_impact(section_id, framework_section, status, usable_fact_profile, imported_limitations, certification_result)
    analysis_boundary = _analysis_boundary(section_id, framework_section, usable_fact_profile, imported_limitations, certification_result)
    key_takeaway = _key_takeaway(analyst_interpretation, buyer_implication)
    optional_exhibits = _optional_exhibits(framework_section, included_claims, pending_diligence_items)
    section = {
        "section_id": section_id,
        "section_title": framework_section["section_title"],
        "analysis_status": status,
        "business_question": framework_section["business_question"],
        "analyst_interpretation": analyst_interpretation,
        "buyer_implication": buyer_implication,
        "key_takeaway": key_takeaway,
        "decision_impact": decision_impact,
        "analysis_boundary": analysis_boundary,
        "supporting_claim_ids": included_claims,
        "supporting_evidence_record_ids": sorted(set(evidence_record_ids)),
        "imported_limitations_from_m5": imported_limitations,
        "missing_inputs": missing_inputs,
        "pending_diligence_items": pending_diligence_items,
        "caveats": sorted(set(caveats)),
        "confidence": confidence,
        "optional_exhibits": optional_exhibits,
        "title": framework_section["section_title"],
        "section_status": status,
        "summary": key_takeaway,
        "included_claim_ids": included_claims,
        "excluded_claim_ids": excluded_claims,
        "findings": findings,
    }
    _assert_no_final_recommendation_terms(section)
    return section


def _section_claim_material(
    framework_section: dict[str, Any],
    claim_certs_by_id: dict[str, dict[str, Any]],
    claims_by_id: dict[str, dict[str, Any]],
    records_by_id: dict[str, dict[str, Any]],
    supporting_claim_ids: set[str],
    blocked_claim_ids: set[str],
) -> tuple[list[str], list[str], list[str], list[str], list[dict[str, Any]]]:
    included_claims = []
    excluded_claims = []
    evidence_record_ids = []
    caveats = []
    findings = []
    for claim_id, cert in claim_certs_by_id.items():
        claim = claims_by_id.get(claim_id, {})
        if not _claim_relevant_to_section(framework_section, cert, claim):
            continue
        if claim_id in blocked_claim_ids or claim_id not in supporting_claim_ids:
            excluded_claims.append(claim_id)
            continue
        included_claims.append(claim_id)
        evidence_record_ids.extend(cert["supporting_evidence_record_ids"])
        claim_caveats = _claim_caveats(cert)
        caveats.extend(claim_caveats)
        caveats.extend(_temporal_record_caveats(cert, records_by_id))
        findings.append(
            {
                "finding_id": f"F-{framework_section['section_id']}-{len(findings) + 1:03d}",
                "related_claim_ids": [claim_id],
                "finding_text": _finding_text_for_claim(framework_section["section_id"], cert, claim),
                "certification_status": cert["certification_status"],
                "supporting_evidence_record_ids": cert["supporting_evidence_record_ids"],
                "caveated": cert["certification_status"] == "certified_with_caveat" or bool(claim_caveats),
                "preserved_caveats": claim_caveats,
            }
        )
    return included_claims, excluded_claims, evidence_record_ids, caveats, findings


def _claim_relevant_to_section(framework_section: dict[str, Any], cert: dict[str, Any], claim: dict[str, Any]) -> bool:
    section_id = framework_section["section_id"]
    claim_type = _claim_type(cert, claim)
    claim_text = _safe_key(str(claim.get("claim_statement", "")))
    relevant_terms = {_safe_key(str(value)) for value in framework_section["relevant_claim_types"]}
    if any(term and (term in claim_type or term in claim_text) for term in relevant_terms):
        return True
    section_terms = {
        "transaction_logic": ("transaction", "party", "timing", "payment", "consideration", "term"),
        "buyer_strategic_objectives": ("strategic", "rationale", "objective", "alternative"),
        "target_business_quality": ("business", "asset", "product", "lineage", "entity", "scientific", "clinical"),
        "industry_and_competitive_position": ("market", "industry", "competitive", "customer", "growth"),
        "strategic_fit": ("strategic", "synergy", "portfolio", "capability", "technology", "alternative"),
        "standalone_financial_analysis": ("financial", "revenue", "ebitda", "cash", "margin", "xbrl"),
        "valuation_and_acceptable_price": ("valuation", "consideration", "purchase", "price", "milestone", "numeric", "payment"),
        "synergy_and_value_creation": ("synergy", "value_creation", "cost_saving", "revenue_synergy"),
        "deal_structure": ("deal", "structure", "consideration", "milestone", "payment", "condition", "term"),
        "financing_and_capital_structure": ("financing", "capital", "debt", "equity", "cash", "leverage", "payment"),
        "return_analysis": ("return", "irr", "moic", "npv", "payback", "eps", "roic", "numeric"),
        "due_diligence_priorities": ("source_gap", "human_review", "diligence", "legal", "financial", "commercial", "technical"),
        "regulatory_integration_and_downside_risks": ("regulatory", "clinical", "legal", "integration", "operational", "risk", "patent"),
        "decision_recommendation_readiness": ("recommendation", "gate", "source_gap", "human_review", "repair"),
    }
    return any(term in claim_type or term in claim_text for term in section_terms[section_id])


def _related_gaps_for_section(section_id: str, framework_section: dict[str, Any], research_gaps: dict[str, Any]) -> list[dict[str, Any]]:
    if section_id in {"due_diligence_priorities", "decision_recommendation_readiness"}:
        return list(research_gaps["research_gaps"])
    relevant = {_safe_key(str(value)) for value in framework_section["relevant_claim_types"]}
    related = []
    for gap in research_gaps["research_gaps"]:
        gap_terms = {_safe_key(str(gap.get("gap_type", "")))} | {_safe_key(str(value)) for value in gap.get("affected_fact_types", [])}
        if relevant.intersection(gap_terms) or _gap_matches_section(section_id, gap_terms):
            related.append(gap)
    return related


def _gap_matches_section(section_id: str, gap_terms: set[str]) -> bool:
    joined = " ".join(gap_terms)
    section_keywords = {
        "transaction_logic": ("transaction", "term", "payment"),
        "standalone_financial_analysis": ("financial", "numeric"),
        "valuation_and_acceptable_price": ("valuation", "numeric", "transaction_terms"),
        "deal_structure": ("transaction", "terms", "payment"),
        "financing_and_capital_structure": ("financing", "payment", "capital", "ownership"),
        "return_analysis": ("return", "valuation", "numeric", "financial"),
        "regulatory_integration_and_downside_risks": ("regulatory", "clinical", "risk", "ownership"),
        "target_business_quality": ("clinical", "business", "asset"),
    }
    return any(keyword in joined for keyword in section_keywords.get(section_id, ()))


def _pending_diligence_items(section_id: str, related_gaps: list[dict[str, Any]], repair_plan: dict[str, Any]) -> list[dict[str, Any]]:
    repair_steps_by_gap_id = {
        gap_id: step
        for step in repair_plan["repair_steps"]
        for gap_id in step["related_research_gap_ids"]
    }
    items = []
    for gap in related_gaps:
        repair_step = repair_steps_by_gap_id.get(gap["research_gap_id"])
        items.append(
            {
                "diligence_item_id": f"DI-{section_id}-{gap['research_gap_id']}",
                "related_research_gap_id": gap["research_gap_id"],
                "related_claim_ids": gap.get("related_claim_ids", []),
                "diligence_question": gap["gap_description"],
                "required_source_types": gap.get("suggested_source_types", []),
                "repair_target": repair_step["target_state"] if repair_step else gap["recommended_repair_target"],
            }
        )
    return items


def _missing_inputs(framework_section: dict[str, Any], related_gaps: list[dict[str, Any]], included_claims: list[str]) -> list[str]:
    missing = [gap["gap_type"] for gap in related_gaps]
    if not included_claims:
        missing.extend(_rule_terms(framework_section, "analysis_boundary_rules"))
    return sorted(set(missing))


def _section_status(
    section_id: str,
    certification_result: dict[str, Any],
    included_claims: list[str],
    pending_diligence_items: list[dict[str, Any]],
) -> str:
    if certification_result["overall_certification_status"] == "failed":
        return "blocked_by_certification_failure"
    if included_claims:
        return "limited"
    if section_id in {"due_diligence_priorities", "decision_recommendation_readiness"} and pending_diligence_items:
        return "limited"
    return "not_assessable_due_to_missing_evidence"


def _section_confidence(status: str, included_claims: list[str], pending_diligence_items: list[dict[str, Any]]) -> str:
    if status in {"blocked_by_missing_evidence", "not_assessable_due_to_missing_evidence", "blocked_by_certification_failure", "not_applicable"}:
        return "not_assessable"
    if pending_diligence_items:
        return "low" if not included_claims else "medium"
    return "medium" if included_claims else "not_assessable"


def _key_takeaway(analyst_interpretation: str, buyer_implication: str) -> str:
    return f"{analyst_interpretation} {buyer_implication}"


def _decision_impact(
    section_id: str,
    framework_section: dict[str, Any],
    status: str,
    usable_fact_profile: dict[str, Any],
    imported_limitations: list[dict[str, Any]],
    certification_result: dict[str, Any],
) -> str:
    if status == "blocked_by_certification_failure":
        return "M5 certification failed, so this section cannot support buyer underwriting until the failed certification state is repaired."
    if section_id == "decision_recommendation_readiness":
        return _join_rules(framework_section["decision_impact_rules"]) + " Recommendation and report gates remain controlled by M5/M7; M6 records readiness only."
    if not usable_fact_profile["claim_ids"]:
        return _join_rules(framework_section["decision_impact_rules"]) + " Because usable evidence is absent, this section should shape diligence scope rather than price, structure, or approval posture."
    limitation_note = " Imported M5 limitations should be addressed before this section drives final approval." if imported_limitations else ""
    return _join_rules(framework_section["decision_impact_rules"]) + limitation_note


def _usable_fact_profile(
    included_claims: list[str],
    claim_certs_by_id: dict[str, dict[str, Any]],
    claims_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    facts = []
    for claim_id in included_claims:
        cert = claim_certs_by_id[claim_id]
        claim = claims_by_id.get(claim_id, {})
        facts.append(
            {
                "claim_id": claim_id,
                "claim_type": _claim_type(cert, claim),
                "claim_statement": claim.get("claim_statement") or cert.get("claim_statement") or claim_id,
                "certification_status": cert["certification_status"],
            }
        )
    return {
        "claim_ids": included_claims,
        "claim_types": sorted({fact["claim_type"] for fact in facts}),
        "facts": facts,
    }


def _imported_limitations_from_m5(
    section_id: str,
    related_gaps: list[dict[str, Any]],
    pending_diligence_items: list[dict[str, Any]],
    certification_result: dict[str, Any],
) -> list[dict[str, Any]]:
    limitations = []
    for gap in related_gaps:
        limitations.append(
            {
                "limitation_id": f"M5-{gap['research_gap_id']}",
                "source_stage": "M5_loop_certification",
                "limitation_type": gap["gap_type"],
                "related_claim_ids": gap.get("related_claim_ids", []),
                "buyer_analysis_effect": _limitation_effect(section_id, gap),
            }
        )
    if section_id == "decision_recommendation_readiness":
        limitations.append(
            {
                "limitation_id": "M5-recommendation-gate",
                "source_stage": "M5_loop_certification",
                "limitation_type": "recommendation_gate_closed" if not certification_result["recommendation_gate_summary"]["recommendation_allowed"] else "recommendation_gate_open",
                "related_claim_ids": certification_result["recommendation_gate_summary"].get("recommendation_blocked_claim_ids", []),
                "buyer_analysis_effect": "Controls whether M6 analysis can advance toward recommendation drafting; M6 does not override this gate.",
            }
        )
    return _dedupe_dicts(limitations)


def _limitation_effect(section_id: str, gap: dict[str, Any]) -> str:
    if section_id == "due_diligence_priorities":
        return "Converted into a buyer diligence action with source needs and repair target preserved from M5."
    if section_id == "decision_recommendation_readiness":
        return "Limits recommendation readiness until M5 repair or human review resolves the blocking claim set."
    return "Bounds the analysis conclusion; it is not re-certified or repaired inside M6."


def _analyst_interpretation(
    section_id: str,
    framework_section: dict[str, Any],
    usable_fact_profile: dict[str, Any],
    imported_limitations: list[dict[str, Any]],
) -> str:
    if not usable_fact_profile["claim_ids"]:
        return _no_evidence_interpretation(section_id, framework_section, imported_limitations)
    fact_phrase = _fact_phrase(usable_fact_profile)
    if section_id == "transaction_logic":
        return f"The usable evidence establishes a bounded transaction baseline around {fact_phrase}. In buyer-side terms, that frames the deal perimeter before any strategic, valuation, or financing conclusion is added."
    if section_id == "target_business_quality":
        return f"The usable evidence identifies what asset, product, technology, or lineage the buyer may be underwriting: {fact_phrase}. This supports a bounded target-quality discussion, not a full commercial or clinical quality score."
    if section_id == "valuation_and_acceptable_price":
        return f"The usable evidence points to consideration or price mechanics around {fact_phrase}. A buyer-side analyst should separate upfront value transfer, contingent value transfer, and headline economics rather than treating deal consideration as a complete valuation; this evidence does not by itself support a full valuation conclusion."
    if section_id == "deal_structure":
        return f"The usable evidence supports analysis of transaction structure and risk allocation around {fact_phrase}. Contingent or milestone-style mechanics can shift part of economic transfer away from upfront payment and toward future achievement."
    if section_id == "financing_and_capital_structure":
        return f"The usable evidence touches payment or financing mechanics around {fact_phrase}. That can frame affordability questions, but it does not establish a complete Sources and Uses, leverage profile, liquidity conclusion, or capital-structure analysis."
    if section_id == "regulatory_integration_and_downside_risks":
        return f"The usable evidence can inform downside-risk framing around {fact_phrase}. M6 should translate that evidence into risk questions and protections rather than declaring risks cleared."
    return f"The usable evidence ({fact_phrase}) can be interpreted through the section lens: {_join_rules(framework_section['interpretation_rules'])}"


def _buyer_implication(
    section_id: str,
    framework_section: dict[str, Any],
    usable_fact_profile: dict[str, Any],
    imported_limitations: list[dict[str, Any]],
) -> str:
    if section_id == "decision_recommendation_readiness":
        return "For the buyer, the current package can frame readiness limits but cannot create a final buyer recommendation or substitute for the recommendation and report gates controlled by M5 and M7."
    if section_id == "due_diligence_priorities":
        return "For the buyer, M5 limitations become practical diligence actions that identify which unanswered questions matter before advancing price, structure, risk, closing-condition, or recommendation work."
    if not usable_fact_profile["claim_ids"]:
        return f"For the buyer, this means the section cannot yet support underwriting judgment, but it still identifies the analysis that must be completed: {_join_rules(framework_section['buyer_implication_rules'])}"
    if section_id == "transaction_logic":
        return "For the buyer, the practical implication is clarity on what is being evaluated and which certified facts define the transaction perimeter; buyer motive and strategic necessity remain separate questions."
    if section_id == "target_business_quality":
        return "For the buyer, the evidence can support initial underwriting of what is being acquired, while leaving commercial attractiveness, IP freedom-to-operate, competitive strength, and risk-adjusted asset value unresolved."
    if section_id == "valuation_and_acceptable_price":
        return "For the buyer, contingent consideration can reduce upfront capital at risk, but it does not prove the price is attractive without standalone value, probability-adjusted milestones, market benchmarks, and return thresholds."
    if section_id == "deal_structure":
        return "For the buyer, structure is a risk-control tool: milestone or contingent mechanics may protect against paying full headline economics before development, approval, or performance outcomes are achieved."
    if section_id == "synergy_and_value_creation":
        return "For the buyer, synergy matters because it is one possible justification for control premium, but unverified synergy remains a hypothesis rather than a valuation input."
    return _join_rules(framework_section["buyer_implication_rules"])


def _analysis_boundary(
    section_id: str,
    framework_section: dict[str, Any],
    usable_fact_profile: dict[str, Any],
    imported_limitations: list[dict[str, Any]],
    certification_result: dict[str, Any],
) -> str:
    boundary = _join_rules(framework_section["analysis_boundary_rules"])
    if not usable_fact_profile["claim_ids"]:
        return f"No usable M5-certified or caveated claims support this section yet. {boundary}"
    if imported_limitations:
        limitation_ids = ", ".join(item["limitation_id"] for item in imported_limitations)
        return f"M6 may interpret the supporting claims, but it cannot resolve imported M5 limitations ({limitation_ids}). {boundary}"
    return f"M6 may interpret the supporting claims within their caveats. {boundary}"


def _no_evidence_interpretation(section_id: str, framework_section: dict[str, Any], imported_limitations: list[dict[str, Any]]) -> str:
    if section_id == "synergy_and_value_creation":
        return "Synergy remains a diligence hypothesis and cannot be quantified from the current certified evidence, but professionally it remains the bridge between standalone value and any buyer-specific control premium."
    if section_id == "due_diligence_priorities":
        return "This section converts M5 gaps and caveats into buyer diligence actions; unresolved items are not treated as facts or conclusions."
    if section_id == "decision_recommendation_readiness":
        return "This section summarizes whether the certified evidence base can support a buyer decision process; it does not issue the final transaction recommendation."
    return f"The current certified evidence does not support a substantive {framework_section['section_title']} conclusion. A buyer-side analyst would need evidence responsive to this lens: {framework_section['analyst_lens']}"


def _fact_phrase(usable_fact_profile: dict[str, Any]) -> str:
    claim_ids = ", ".join(usable_fact_profile["claim_ids"])
    claim_types = ", ".join(usable_fact_profile["claim_types"])
    return f"{claim_types} claims ({claim_ids})"


def _rule_terms(framework_section: dict[str, Any], field: str) -> list[str]:
    value = framework_section.get(field, [])
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _join_rules(rules: list[str] | str) -> str:
    if isinstance(rules, str):
        return rules
    return " ".join(str(rule).strip() for rule in rules if str(rule).strip())


def _optional_exhibits(
    framework_section: dict[str, Any],
    included_claims: list[str],
    pending_diligence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    available_inputs = _available_inputs(framework_section, included_claims)
    blocked_inputs = {source_type for item in pending_diligence_items for source_type in item.get("required_source_types", [])}
    exhibits = []
    for exhibit in framework_section["optional_exhibits"]:
        required_inputs = exhibit.get("required_inputs", [])
        matched_inputs = [value for value in required_inputs if _input_available(value, available_inputs)]
        if len(matched_inputs) == len(required_inputs) and required_inputs:
            status = "ready"
            reason = "All required exhibit inputs have certified or caveated supporting claims in this M6 package."
        elif matched_inputs:
            status = "skeleton_only"
            reason = "Some exhibit inputs are source-supported, but the exhibit is not complete enough for a full table."
        elif blocked_inputs or pending_diligence_items:
            status = "blocked_by_missing_inputs"
            reason = "Required exhibit inputs are missing or tied to unresolved research gaps."
        else:
            status = "not_applicable"
            reason = "No certified inputs in this package make the optional exhibit applicable."
        exhibits.append(
            {
                "exhibit_id": exhibit["exhibit_id"],
                "status": status,
                "reason": reason,
                "required_inputs": required_inputs,
                "available_inputs": matched_inputs,
            }
        )
    return exhibits


def _available_inputs(framework_section: dict[str, Any], included_claims: list[str]) -> set[str]:
    if not included_claims:
        return set()
    available = {_safe_key(value) for value in _rule_terms(framework_section, "interpretation_rules")}
    available.update(_safe_key(value) for value in framework_section["relevant_claim_types"])
    return available


def _input_available(required_input: str, available_inputs: set[str]) -> bool:
    normalized = _safe_key(required_input)
    return any(normalized in value or value in normalized for value in available_inputs)


def _claim_phrase(included_claims: list[str]) -> str:
    if not included_claims:
        return "does not yet provide a supporting claim set"
    return f"from {', '.join(included_claims)}"


def _gap_phrase(pending_diligence_items: list[dict[str, Any]]) -> str:
    if not pending_diligence_items:
        return "No additional gap is resolved beyond the certified claim set."
    gap_ids = ", ".join(item["related_research_gap_id"] for item in pending_diligence_items)
    return f"Pending diligence remains for {gap_ids}."


def _temporal_record_caveats(cert: dict[str, Any], records_by_id: dict[str, dict[str, Any]]) -> list[str]:
    caveats = []
    for record_id in cert["supporting_evidence_record_ids"]:
        record = records_by_id.get(record_id)
        if record and record.get("evidence_time_relation_to_decision_date") in {"post_decision", "retrospective"}:
            caveats.append(f"{record_id} is {record['evidence_time_relation_to_decision_date']} evidence; use only with retrospective/source-limit caveat.")
    return caveats


def _dedupe_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique = []
    for item in items:
        key = json.dumps(item, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _assert_no_final_recommendation_terms(section: dict[str, Any]) -> None:
    text = json.dumps(section, ensure_ascii=True)
    for term in FINAL_RECOMMENDATION_TERMS:
        if term in text:
            raise DealAnalysisError(f"M6 section contains forbidden final recommendation term: {term}")


def _blocked_analysis_items(
    claim_certs_by_id: dict[str, dict[str, Any]],
    claims_by_id: dict[str, dict[str, Any]],
    research_gaps_by_id: dict[str, dict[str, Any]],
    repair_steps_by_gap_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    items = []
    for gap_id, gap in research_gaps_by_id.items():
        repair_step = repair_steps_by_gap_id.get(gap_id)
        items.append(
            {
                "blocked_item_id": f"BAI-{len(items) + 1:03d}",
                "blocked_topic": f"{gap['gap_type']} unresolved",
                "reason": f"Generic research gap {gap_id} blocks factual use until repaired or explicitly scoped out.",
                "related_research_gap_ids": [gap_id],
                "required_repair_target": repair_step["target_state"] if repair_step else gap["recommended_repair_target"],
                "can_appear_in_final_report": False,
            }
        )
    for claim_id, cert in claim_certs_by_id.items():
        if cert["certification_status"] not in BLOCKED_FACT_STATUSES or cert["related_source_gap_ids"]:
            continue
        claim_type = _claim_type(cert, claims_by_id.get(claim_id, {}))
        items.append(
            {
                "blocked_item_id": f"BAI-{len(items) + 1:03d}",
                "blocked_topic": f"{claim_type} claim not certified",
                "reason": f"Claim {claim_id} has certification status {cert['certification_status']} and cannot support analysis conclusions.",
                "related_research_gap_ids": [],
                "required_repair_target": "M2_source_retrieval_or_M5_numeric_verification",
                "can_appear_in_final_report": False,
            }
        )
    return items


def _package_caveats(certification_result: dict[str, Any]) -> list[dict[str, Any]]:
    caveats = [
        {
            "caveat_id": "CAV-001",
            "caveat_type": "partial_evidence_coverage",
            "caveat_text": f"Evidence coverage is {certification_result['evidence_coverage_status']}; analysis remains bounded by retrieved and certified evidence only.",
            "related_claim_ids": [],
        },
        {
            "caveat_id": "CAV-002",
            "caveat_type": "repair_required",
            "caveat_text": "overall_certification_status is repair_required; recommendations and final report generation are blocked.",
            "related_claim_ids": [],
        },
        {
            "caveat_id": "CAV-003",
            "caveat_type": "human_review_required",
            "caveat_text": "Human review items are carried forward unresolved and must not be resolved in M6.",
            "related_claim_ids": sorted({claim_id for item in certification_result["human_review_items"] for claim_id in item["related_claim_ids"]}),
        },
    ]
    for numeric in certification_result["numeric_verification_results"]:
        caveats.append(
            {
                "caveat_id": f"CAV-NUM-{numeric['related_claim_id']}",
                "caveat_type": "derived_numeric_result",
                "caveat_text": _neutral_numeric_caveat(numeric),
                "related_claim_ids": [numeric["related_claim_id"]],
            }
        )
    retrospective_claim_ids = sorted(
        {
            result["claim_id"]
            for result in certification_result["temporal_verification_results"]
            if result["verification_status"] == "passed_with_caveat"
        }
    )
    caveats.append(
        {
            "caveat_id": "CAV-004",
            "caveat_type": "post_decision_or_retrospective_sources",
            "caveat_text": "Post-decision or retrospective evidence may support retrospective validation only and must not be worded as ex-ante buyer decision support.",
            "related_claim_ids": retrospective_claim_ids,
        }
    )
    return caveats


def _analysis_readiness_status(certification_result: dict[str, Any]) -> str:
    status = certification_result["overall_certification_status"]
    if status == "repair_required":
        return "limited_by_repair_required"
    if status == "failed":
        return "blocked_by_certification_failure"
    if status == "human_review_required":
        return "human_review_required"
    return "ready_for_limited_analysis"


def _next_action(certification_result: dict[str, Any]) -> str:
    if certification_result["overall_certification_status"] == "repair_required":
        return "run_targeted_source_repair_or_human_review_before_recommendation_or_final_report"
    return "human_review_before_recommendation_or_final_report"


def _section_for_claim(cert: dict[str, Any], claim: dict[str, Any]) -> str:
    claim_type = _claim_type(cert, claim)
    if any(term in claim_type for term in ("background", "term", "timing", "party", "document")):
        return "transaction_background_and_terms"
    if any(term in claim_type for term in ("strategic", "alternative", "rationale")):
        return "strategic_rationale_and_alternatives"
    if any(term in claim_type for term in ("business", "asset", "product", "lineage", "entity", "scientific")):
        return "target_business_quality"
    if any(term in claim_type for term in ("market", "competitive")):
        return "market_and_competitive_position"
    if any(term in claim_type for term in ("valuation", "consideration", "return", "milestone", "numeric")):
        return "valuation_deal_structure_and_returns"
    if any(term in claim_type for term in ("synergy", "value_creation")):
        return "synergy_and_value_creation"
    if any(term in claim_type for term in ("financing", "payment", "ownership", "governance")):
        return "financing_payment_mechanics_and_value_transfer"
    if any(term in claim_type for term in ("legal", "regulatory", "clinical", "intellectual", "patent", "risk")):
        return "legal_regulatory_and_diligence_risks"
    if any(term in claim_type for term in ("integration", "operational")):
        return "integration_and_operational_risks"
    return "transaction_background_and_terms"


def _claim_type(cert: dict[str, Any], claim: dict[str, Any]) -> str:
    return _safe_key(str(claim.get("canonical_fact_type") or cert.get("claim_type") or "generic_fact"))


def _finding_text_for_claim(section_id: str, cert: dict[str, Any], claim: dict[str, Any]) -> str:
    claim_type = _claim_type(cert, claim)
    claim_statement = claim.get("claim_statement") or f"source-bounded {claim_type} fact"
    section_meanings = {
        "transaction_logic": "sets part of the transaction fact baseline for buyer analysis",
        "buyer_strategic_objectives": "can frame buyer objectives only where linked to certified evidence",
        "target_business_quality": "can inform bounded target-quality diligence but not a complete quality score",
        "industry_and_competitive_position": "can inform market context only within certified source limits",
        "strategic_fit": "can support a limited fit hypothesis but not a final strategic conclusion",
        "standalone_financial_analysis": "can inform the financial fact base but not unsupported revenue, EBITDA, cash-flow, or forecast conclusions",
        "valuation_and_acceptable_price": "can inform consideration mechanics but not a complete valuation or acceptable-price conclusion",
        "synergy_and_value_creation": "can frame value-creation hypotheses but not quantified synergy value",
        "deal_structure": "can support analysis of risk allocation in the transaction structure",
        "financing_and_capital_structure": "can support limited payment-mechanics discussion but not a full financing model",
        "return_analysis": "can identify return-analysis inputs but not calculate unsupported buyer return metrics",
        "due_diligence_priorities": "helps define diligence priorities rather than resolving open gaps",
        "regulatory_integration_and_downside_risks": "can inform downside-risk framing within certification caveats",
        "decision_recommendation_readiness": "can inform gate readiness but not create a final buyer recommendation",
    }
    return f"Claim {cert['claim_id']} ({claim_type}) {section_meanings[section_id]}: {claim_statement}"


def _validate_m5_gate_summaries(certification_result: dict[str, Any]) -> None:
    analysis_gate = certification_result["analysis_gate_summary"]
    report_gate = certification_result["report_gate_summary"]
    recommendation_gate = certification_result["recommendation_gate_summary"]
    for field in (
        "analysis_allowed_claim_ids",
        "analysis_caveated_claim_ids",
        "analysis_blocked_claim_ids",
        "analysis_blocking_reasons",
    ):
        if field not in analysis_gate:
            raise DealAnalysisError(f"analysis_gate_summary missing {field}.")
    for field in (
        "report_allowed_claim_ids",
        "report_caveated_claim_ids",
        "report_blocked_claim_ids",
        "report_blocking_reasons",
    ):
        if field not in report_gate:
            raise DealAnalysisError(f"report_gate_summary missing {field}.")
    for field in (
        "recommendation_allowed",
        "recommendation_supporting_claim_ids",
        "recommendation_blocked_claim_ids",
        "recommendation_blocking_reasons",
    ):
        if field not in recommendation_gate:
            raise DealAnalysisError(f"recommendation_gate_summary missing {field}.")


def _claim_caveats(cert: dict[str, Any]) -> list[str]:
    caveats = []
    for field in ("required_caveats", "caveats"):
        for caveat in cert.get(field, []):
            if isinstance(caveat, str) and caveat not in caveats:
                caveats.append(caveat)
    return caveats


def _preserved_caveats(claim_certs_by_id: dict[str, dict[str, Any]], claim_ids: list[str]) -> list[dict[str, Any]]:
    preserved = []
    for claim_id in claim_ids:
        claim_caveats = _claim_caveats(claim_certs_by_id[claim_id])
        if not claim_caveats:
            continue
        preserved.append({"claim_id": claim_id, "caveats": claim_caveats})
    return preserved


def _exclusion_reasons(certification_result: dict[str, Any]) -> list[dict[str, str]]:
    claim_certs_by_id = {claim["claim_id"]: claim for claim in certification_result["claim_certifications"]}
    excluded = []
    for claim_id in certification_result["analysis_gate_summary"]["analysis_blocked_claim_ids"]:
        cert = claim_certs_by_id[claim_id]
        reasons = _blocking_reasons_for_claim(cert, "analysis")
        excluded.append({"claim_id": claim_id, "reason": "; ".join(reasons)})
    return excluded


def _blocking_reasons_for_claim(cert: dict[str, Any], downstream_use: str) -> list[str]:
    reasons = []
    for action in cert.get("repair_actions", []):
        reasons.append(action.get("reason", ""))
    if not reasons:
        reasons.append(f"{downstream_use} blocked by {cert['certification_status']} certification status.")
    return [reason for reason in reasons if reason]


def _recommendation_gate_status(recommendation_gate: dict[str, Any]) -> str:
    return "allowed" if recommendation_gate["recommendation_allowed"] else "blocked"


def _report_gate_status(report_gate: dict[str, Any]) -> str:
    return "allowed" if not report_gate["report_blocked_claim_ids"] else "blocked"


def _validate_section(section: dict[str, Any]) -> None:
    for field in (
        "section_id",
        "section_title",
        "analysis_status",
        "business_question",
        "analyst_interpretation",
        "buyer_implication",
        "key_takeaway",
        "decision_impact",
        "analysis_boundary",
        "supporting_claim_ids",
        "supporting_evidence_record_ids",
        "imported_limitations_from_m5",
        "missing_inputs",
        "pending_diligence_items",
        "caveats",
        "confidence",
        "optional_exhibits",
    ):
        if field not in section:
            raise DealAnalysisError(f"analysis_section missing {field}.")
    if section["section_id"] not in ANALYSIS_SECTION_IDS:
        raise DealAnalysisError("invalid analysis section_id.")
    if section["analysis_status"] not in ANALYSIS_SECTION_STATUSES:
        raise DealAnalysisError("invalid analysis_status.")
    if section["confidence"] not in CONFIDENCE_VALUES:
        raise DealAnalysisError("invalid section confidence.")
    for exhibit in section["optional_exhibits"]:
        for field in ("exhibit_id", "status", "reason", "required_inputs", "available_inputs"):
            if field not in exhibit:
                raise DealAnalysisError(f"optional_exhibit missing {field}.")
        if exhibit["status"] not in OPTIONAL_EXHIBIT_STATUSES:
            raise DealAnalysisError("invalid optional_exhibit status.")
    for finding in section["findings"]:
        for field in ("finding_id", "related_claim_ids", "finding_text", "certification_status", "supporting_evidence_record_ids", "caveated"):
            if field not in finding:
                raise DealAnalysisError(f"analysis finding missing {field}.")


def _section_order(section_id: str) -> int:
    ordered = [
        "transaction_background_and_terms",
        "strategic_rationale_and_alternatives",
        "target_business_quality",
        "market_and_competitive_position",
        "valuation_deal_structure_and_returns",
        "synergy_and_value_creation",
        "financing_payment_mechanics_and_value_transfer",
        "legal_regulatory_and_diligence_risks",
        "integration_and_operational_risks",
        "source_gaps_and_human_review",
        "decision_readiness",
    ]
    return ordered.index(section_id)


def _neutral_numeric_caveat(numeric: dict[str, Any]) -> str:
    return f"Numeric check {numeric.get('numeric_check_id', '')} is arithmetic-only and cannot create valuation, recommendation, or final report authority."


def _safe_key(value: str) -> str:
    normalized = []
    previous_separator = False
    for character in value.lower():
        if character.isalnum():
            normalized.append(character)
            previous_separator = False
        elif not previous_separator:
            normalized.append("_")
            previous_separator = True
    return "".join(normalized).strip("_") or "generic_fact"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
