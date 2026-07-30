from __future__ import annotations

from typing import Any

from v3_lite_buyer_acquisition_runtime.runtime.claim_certifier import certification_result_source_id


def build_research_gaps(certification_result: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    claim_certs_by_id = {cert["claim_id"]: cert for cert in certification_result["claim_certifications"]}
    claims_by_id = {claim["claim_id"]: claim for claim in graph["claim_nodes"]}
    gap_nodes_by_source_gap_id = {gap["source_gap_id"]: gap for gap in graph["gap_nodes"]}
    research_gaps = []

    for gap_node in graph["gap_nodes"]:
        related_claim_ids = [cert["claim_id"] for cert in certification_result["claim_certifications"] if gap_node["source_gap_id"] in cert["related_source_gap_ids"]]
        research_gaps.append(
            {
                "research_gap_id": f"RG-{len(research_gaps) + 1:03d}",
                "gap_type": _gap_type_from_gap_node(gap_node),
                "related_claim_ids": related_claim_ids,
                "related_gap_node_ids": [gap_node["gap_node_id"]],
                "missing_source_need_ids": [gap_node["missing_source_need_id"]],
                "gap_description": gap_node["gap_statement"],
                "severity": _gap_severity(gap_node),
                "blocks_certification": True,
                "recommended_repair_target": "M2_source_retrieval",
                "suggested_source_types": _suggested_source_types(gap_node),
            }
        )

    for claim_id, cert in claim_certs_by_id.items():
        claim = claims_by_id[claim_id]
        if claim["claim_type"] == "derived_numeric_candidate":
            research_gaps.append(
                {
                    "research_gap_id": f"RG-{len(research_gaps) + 1:03d}",
                    "gap_type": "direct_headline_value_source_optional",
                    "related_claim_ids": [claim_id],
                    "related_gap_node_ids": [],
                    "missing_source_need_ids": [],
                    "gap_description": "Optional direct source for headline $180M maximum value if final report wording needs a direct quoted deal value.",
                    "severity": "medium",
                    "blocks_certification": False,
                    "recommended_repair_target": "M2_source_retrieval_or_M5_numeric_verification",
                    "suggested_source_types": ["SEC agreement exhibit", "SEC prospectus or 10-K direct headline value disclosure", "buyer or target transaction announcement"],
                }
            )
        if cert["certification_status"] in {"unsupported", "blocked_by_source_gap"} and not cert["related_source_gap_ids"]:
            research_gaps.append(
                {
                    "research_gap_id": f"RG-{len(research_gaps) + 1:03d}",
                    "gap_type": "unsupported_claim",
                    "related_claim_ids": [claim_id],
                    "related_gap_node_ids": [],
                    "missing_source_need_ids": [],
                    "gap_description": cert["certification_basis"],
                    "severity": "high",
                    "blocks_certification": True,
                    "recommended_repair_target": "M2_source_retrieval",
                    "suggested_source_types": ["authoritative transaction or ownership disclosure"],
                }
            )

    result = {
        "case_id": certification_result["case_id"],
        "generated_artifact": "research_gaps.json",
        "stage": "M5_research_gaps",
        "created_from_certification_result_id": certification_result_source_id(certification_result),
        "research_gaps": research_gaps,
    }
    validate_research_gaps(result)
    return result


def build_repair_plan(certification_result: dict[str, Any], research_gaps: dict[str, Any]) -> dict[str, Any]:
    repair_steps = []
    for gap in research_gaps["research_gaps"]:
        target_state = _repair_target_state(gap)
        repair_steps.append(
            {
                "repair_step_id": f"RP-{len(repair_steps) + 1:03d}",
                "target_state": target_state,
                "target_artifact": _target_artifact(target_state),
                "reason": gap["gap_description"],
                "related_claim_ids": gap["related_claim_ids"],
                "related_research_gap_ids": [gap["research_gap_id"]],
                "required_source_types": gap["suggested_source_types"],
                "priority": "high" if gap["blocks_certification"] else "medium",
                "expected_output": _expected_output(target_state),
            }
        )
    if any(cert["certification_status"] in {"failed", "requires_human_review"} for cert in certification_result["claim_certifications"]):
        repair_steps.append(
            {
                "repair_step_id": f"RP-{len(repair_steps) + 1:03d}",
                "target_state": "M4_claim_evidence_graph_update",
                "target_artifact": "claim_evidence_graph.json",
                "reason": "Downgrade or remap claims if M5 verification failures reveal unsupported claim framing.",
                "related_claim_ids": [cert["claim_id"] for cert in certification_result["claim_certifications"] if cert["certification_status"] in {"failed", "requires_human_review"}],
                "related_research_gap_ids": [],
                "required_source_types": ["updated verified evidence repository records"],
                "priority": "medium",
                "expected_output": "Updated claim evidence graph with unsupported or failed claims downgraded before rerunning M5.",
            }
        )
    result = {
        "case_id": certification_result["case_id"],
        "generated_artifact": "repair_plan.json",
        "stage": "M5_repair_plan",
        "created_from_certification_result_id": certification_result_source_id(certification_result),
        "next_action": certification_result["next_action"],
        "repair_steps": repair_steps,
        "stop_conditions": [
            "Do not generate final_report.md until blocked source gaps are repaired or explicitly excluded from report scope.",
            "Do not use derived $180M wording as direct quoted value unless a direct source is retrieved or wording preserves numeric caveat.",
            "Do not convert post-decision or retrospective evidence into ex-ante buyer decision support.",
        ],
    }
    validate_repair_plan(result)
    return result


def validate_research_gaps(payload: dict[str, Any]) -> None:
    if payload.get("generated_artifact") != "research_gaps.json" or payload.get("stage") != "M5_research_gaps":
        raise ValueError("Invalid research_gaps artifact metadata.")
    for gap in payload["research_gaps"]:
        for field in (
            "research_gap_id",
            "gap_type",
            "related_claim_ids",
            "related_gap_node_ids",
            "missing_source_need_ids",
            "gap_description",
            "severity",
            "blocks_certification",
            "recommended_repair_target",
            "suggested_source_types",
        ):
            if field not in gap:
                raise ValueError(f"research_gap missing {field}.")


def validate_repair_plan(payload: dict[str, Any]) -> None:
    if payload.get("generated_artifact") != "repair_plan.json" or payload.get("stage") != "M5_repair_plan":
        raise ValueError("Invalid repair_plan artifact metadata.")
    for step in payload["repair_steps"]:
        for field in (
            "repair_step_id",
            "target_state",
            "target_artifact",
            "reason",
            "related_claim_ids",
            "related_research_gap_ids",
            "required_source_types",
            "priority",
            "expected_output",
        ):
            if field not in step:
                raise ValueError(f"repair_step missing {field}.")


def _gap_type_from_gap_node(gap_node: dict[str, Any]) -> str:
    affected = set(gap_node["affected_claim_types"])
    if "personal_proceeds" in affected:
        return "personal_proceeds_source_gap"
    if "cap_table" in affected:
        return "pre_sale_cap_table_source_gap"
    if "ownership_or_founder_background" in affected:
        return "founder_ownership_background_source_gap"
    if "scientific_asset" in affected or "asset_lineage" in affected:
        return "official_patent_record_source_gap"
    return "source_gap"


def _gap_severity(gap_node: dict[str, Any]) -> str:
    affected = set(gap_node["affected_claim_types"])
    if affected.intersection({"personal_proceeds", "cap_table", "ownership_or_founder_background"}):
        return "high"
    return "medium"


def _suggested_source_types(gap_node: dict[str, Any]) -> list[str]:
    affected = set(gap_node["affected_claim_types"])
    if "personal_proceeds" in affected:
        return ["direct proceeds disclosure", "transaction proceeds schedule", "authoritative ownership and payout record"]
    if "cap_table" in affected:
        return ["pre-sale cap table", "equity ownership schedule", "transaction disclosure schedule"]
    if "ownership_or_founder_background" in affected:
        return ["Haisco disclosure", "CNINFO filing", "SZSE disclosure", "board or founder-role disclosure"]
    if "scientific_asset" in affected or "asset_lineage" in affected:
        return ["official patent-office record", "patent assignment database", "authoritative chemistry patent family record"]
    return ["authoritative primary source"]


def _repair_target_state(gap: dict[str, Any]) -> str:
    if gap["gap_type"] == "direct_headline_value_source_optional":
        return "M2_source_retrieval_or_M5_numeric_verification"
    return "M2_source_retrieval"


def _target_artifact(target_state: str) -> str:
    if target_state == "M2_source_retrieval_or_M5_numeric_verification":
        return "retrieved_sources_manifest.json or certification_result.json"
    return "retrieved_sources_manifest.json"


def _expected_output(target_state: str) -> str:
    if target_state == "M2_source_retrieval_or_M5_numeric_verification":
        return "Either a direct source for headline $180M wording or a preserved numeric caveat confirming arithmetic only."
    return "Updated retrieved source manifest and raw evidence enabling M3/M4/M5 rerun."
