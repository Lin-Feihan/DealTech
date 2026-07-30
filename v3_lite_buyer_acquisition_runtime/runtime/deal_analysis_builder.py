from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v3_lite_buyer_acquisition_runtime.runtime.claim_certifier import (
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
ANALYSIS_SECTION_IDS = {
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
}


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


def build_analysis_package(
    certification_result: dict[str, Any],
    claim_evidence_graph: dict[str, Any],
    evidence_repository: dict[str, Any],
    research_gaps: dict[str, Any],
    repair_plan: dict[str, Any],
) -> dict[str, Any]:
    validate_m6_inputs(certification_result, claim_evidence_graph, evidence_repository, research_gaps, repair_plan)
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
    gate_allows_analysis = certification_result["overall_certification_status"] != "repair_required" and analysis_readiness_status == "ready_for_limited_analysis"
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
        "recommendation_allowed": gate_allows_analysis,
        "final_report_allowed": gate_allows_analysis,
        "analysis_sections": _analysis_sections(claim_certs_by_id, claims_by_id, records_by_id, research_gaps, repair_plan),
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
        if package["recommendation_allowed"] is not False or package["final_report_allowed"] is not False:
            raise DealAnalysisError("repair_required certification cannot allow recommendation or final report.")
    section_ids = {section.get("section_id") for section in package["analysis_sections"]}
    if section_ids != ANALYSIS_SECTION_IDS:
        raise DealAnalysisError("analysis_sections must include exactly the required generic M6 sections.")
    for section in package["analysis_sections"]:
        _validate_section(section)
    for item in package["blocked_analysis_items"]:
        for field in ("blocked_item_id", "blocked_topic", "reason", "related_research_gap_ids", "required_repair_target", "can_appear_in_final_report"):
            if field not in item:
                raise DealAnalysisError(f"blocked_analysis_item missing {field}.")
        if item["can_appear_in_final_report"] is not False:
            raise DealAnalysisError("blocked_analysis_items cannot appear in final report unless repaired or caveated.")


def _analysis_sections(
    claim_certs_by_id: dict[str, dict[str, Any]],
    claims_by_id: dict[str, dict[str, Any]],
    records_by_id: dict[str, dict[str, Any]],
    research_gaps: dict[str, Any],
    repair_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    sections = []
    for section_id in [section for section in ANALYSIS_SECTION_IDS if section not in {"source_gaps_and_human_review", "decision_readiness"}]:
        sections.append(_claim_based_section(section_id, claim_certs_by_id, claims_by_id, records_by_id))
    sections.append(_gap_section(research_gaps, repair_plan))
    sections.append(_decision_readiness_section(claim_certs_by_id))
    return sorted(sections, key=lambda section: _section_order(section["section_id"]))


def _claim_based_section(
    section_id: str,
    claim_certs_by_id: dict[str, dict[str, Any]],
    claims_by_id: dict[str, dict[str, Any]],
    records_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    included_claims = []
    excluded_claims = []
    findings = []
    caveats = []
    evidence_record_ids = []
    for claim_id, cert in claim_certs_by_id.items():
        claim = claims_by_id.get(claim_id, {})
        if _section_for_claim(cert, claim) != section_id:
            continue
        if cert["certification_status"] not in ALLOWED_FACT_STATUSES:
            excluded_claims.append(claim_id)
            continue
        evidence_record_ids.extend(cert["supporting_evidence_record_ids"])
        findings.append(
            {
                "finding_id": f"F-{section_id}-{len(findings) + 1:03d}",
                "related_claim_ids": [claim_id],
                "finding_text": _finding_text_for_claim(cert, claim),
                "certification_status": cert["certification_status"],
                "supporting_evidence_record_ids": cert["supporting_evidence_record_ids"],
                "caveated": cert["certification_status"] == "certified_with_caveat" or bool(cert.get("caveats")),
            }
        )
        included_claims.append(claim_id)
        caveats.extend(cert.get("caveats", []))
        for record_id in cert["supporting_evidence_record_ids"]:
            record = records_by_id.get(record_id)
            if record and record.get("evidence_time_relation_to_decision_date") in {"post_decision", "retrospective"}:
                caveats.append(f"{record_id} is {record['evidence_time_relation_to_decision_date']} evidence; use only with retrospective/source-limit caveat.")
    return {
        "section_id": section_id,
        "title": section_id.replace("_", " ").title(),
        "section_status": "limited_analysis" if findings else "no_certified_claims",
        "summary": f"Generic source-bounded analysis section for {section_id}; no recommendation or case conclusion is generated.",
        "included_claim_ids": included_claims,
        "excluded_claim_ids": excluded_claims,
        "supporting_evidence_record_ids": sorted(set(evidence_record_ids)),
        "findings": findings,
        "caveats": sorted(set(caveats)),
    }


def _gap_section(research_gaps: dict[str, Any], repair_plan: dict[str, Any]) -> dict[str, Any]:
    repair_steps_by_gap_id = {
        gap_id: step
        for step in repair_plan["repair_steps"]
        for gap_id in step["related_research_gap_ids"]
    }
    findings = []
    for gap in research_gaps["research_gaps"]:
        repair_step = repair_steps_by_gap_id.get(gap["research_gap_id"])
        findings.append(
            {
                "finding_id": f"F-source_gaps_and_human_review-{len(findings) + 1:03d}",
                "related_claim_ids": gap["related_claim_ids"],
                "finding_text": f"Open generic research gap {gap['research_gap_id']} with type {gap['gap_type']} remains unresolved.",
                "certification_status": "gap_tracking_only",
                "supporting_evidence_record_ids": [],
                "caveated": True,
                "required_repair_target": repair_step["target_state"] if repair_step else gap["recommended_repair_target"],
            }
        )
    return {
        "section_id": "source_gaps_and_human_review",
        "title": "Source Gaps And Human Review",
        "section_status": "gap_tracking_only",
        "summary": "Research gaps, unsupported claims, and human-review requirements are tracked as limits, not as factual findings.",
        "included_claim_ids": [],
        "excluded_claim_ids": sorted({claim_id for gap in research_gaps["research_gaps"] for claim_id in gap["related_claim_ids"]}),
        "supporting_evidence_record_ids": [],
        "findings": findings,
        "caveats": ["Unsupported and source-gap-blocked claims are not treated as facts in M6."],
    }


def _decision_readiness_section(claim_certs_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    blocked_claim_ids = sorted(
        claim_id
        for claim_id, claim in claim_certs_by_id.items()
        if claim["certification_status"] in BLOCKED_FACT_STATUSES
    )
    return {
        "section_id": "decision_readiness",
        "title": "Decision Readiness",
        "section_status": "limited_by_repair_required" if blocked_claim_ids else "ready_for_limited_analysis",
        "summary": "Recommendation and final report generation depend on certification status, source gaps, numeric checks, and human review.",
        "included_claim_ids": [],
        "excluded_claim_ids": blocked_claim_ids,
        "supporting_evidence_record_ids": [],
        "findings": [
            {
                "finding_id": "F-decision_readiness-001",
                "related_claim_ids": blocked_claim_ids,
                "finding_text": "Recommendation and final report generation are not allowed until targeted source repair or human review resolves blocking gaps.",
                "certification_status": "repair_required" if blocked_claim_ids else "ready_for_limited_analysis",
                "supporting_evidence_record_ids": [],
                "caveated": True,
            }
        ],
        "caveats": ["recommendation_allowed and final_report_allowed must remain false while certification or repair gates are unresolved."],
    }


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


def _finding_text_for_claim(cert: dict[str, Any], claim: dict[str, Any]) -> str:
    claim_type = _claim_type(cert, claim)
    return f"Certified source-bounded {claim_type} claim {cert['claim_id']} may be used only with preserved caveats and permitted-use limits."


def _excluded_claims_for_section(claim_ids: list[str], claim_certs_by_id: dict[str, dict[str, Any]]) -> list[str]:
    return [
        claim_id
        for claim_id in claim_ids
        if claim_certs_by_id[claim_id]["certification_status"] not in ALLOWED_FACT_STATUSES
    ]


def _validate_section(section: dict[str, Any]) -> None:
    for field in (
        "section_id",
        "title",
        "section_status",
        "summary",
        "included_claim_ids",
        "excluded_claim_ids",
        "supporting_evidence_record_ids",
        "findings",
        "caveats",
    ):
        if field not in section:
            raise DealAnalysisError(f"analysis_section missing {field}.")
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
