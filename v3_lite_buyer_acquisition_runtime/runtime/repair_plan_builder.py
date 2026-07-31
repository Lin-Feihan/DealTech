from __future__ import annotations

from typing import Any

from v3_lite_buyer_acquisition_runtime.runtime.claim_certifier import certification_result_source_id


BLOCKING_CERTIFICATION_STATUSES = {"unsupported", "blocked_by_source_gap", "failed", "requires_numeric_verification", "requires_human_review"}
FAILED_NUMERIC_STATUSES = {"failed", "insufficient_numeric_support"}


def build_research_gaps(certification_result: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    claim_certs_by_id = {cert["claim_id"]: cert for cert in certification_result["claim_certifications"]}
    claims_by_id = {claim["claim_id"]: claim for claim in graph["claim_nodes"]}
    research_gaps = []
    seen_gap_keys: set[tuple[Any, ...]] = set()

    for gap_node in graph["gap_nodes"]:
        related_claim_ids = [cert["claim_id"] for cert in certification_result["claim_certifications"] if gap_node["source_gap_id"] in cert["related_source_gap_ids"]]
        research_gaps.append(_research_gap_from_source_gap(len(research_gaps) + 1, gap_node, related_claim_ids))
        seen_gap_keys.add(("source_gap", gap_node["source_gap_id"]))

    for numeric_result in certification_result.get("numeric_verification_results", []):
        if numeric_result.get("verification_status") in FAILED_NUMERIC_STATUSES:
            claim_id = numeric_result["related_claim_id"]
            research_gaps.append(_research_gap_from_numeric_failure(len(research_gaps) + 1, claim_id, claims_by_id.get(claim_id), numeric_result))
            seen_gap_keys.add(("numeric", claim_id))

    for cert in certification_result["claim_certifications"]:
        status = cert["certification_status"]
        if status not in BLOCKING_CERTIFICATION_STATUSES:
            continue
        claim = claims_by_id.get(cert["claim_id"], {})
        if cert["related_source_gap_ids"]:
            for source_gap_id in cert["related_source_gap_ids"]:
                if ("source_gap", source_gap_id) not in seen_gap_keys:
                    research_gaps.append(_research_gap_from_claim(len(research_gaps) + 1, cert, claim, [source_gap_id]))
                    seen_gap_keys.add(("source_gap", source_gap_id))
            continue
        key = ("claim", cert["claim_id"], status)
        if key not in seen_gap_keys:
            research_gaps.append(_research_gap_from_claim(len(research_gaps) + 1, cert, claim, []))
            seen_gap_keys.add(key)

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
    seen_step_keys: set[tuple[Any, ...]] = set()
    for gap in research_gaps["research_gaps"]:
        action = _repair_action(gap)
        _append_repair_step(
            repair_steps,
            seen_step_keys,
            action=action,
            target_state=_repair_target_state(action),
            target_artifact=_target_artifact(action),
            reason=_repair_reason(gap, action),
            related_claim_ids=gap["related_claim_ids"],
            related_research_gap_ids=[gap["research_gap_id"]],
            required_source_types=gap["suggested_source_types"],
            priority="high" if gap["blocks_certification"] else "medium",
            expected_output=_expected_output(action),
        )

    for cert in certification_result["claim_certifications"]:
        for repair_action in cert.get("repair_actions", []):
            if not _should_emit_claim_repair_step(cert, repair_action):
                continue
            mapped = _repair_step_from_claim_action(cert, repair_action)
            _append_repair_step(repair_steps, seen_step_keys, **mapped)

    result = {
        "case_id": certification_result["case_id"],
        "generated_artifact": "repair_plan.json",
        "stage": "M5_repair_plan",
        "created_from_certification_result_id": certification_result_source_id(certification_result),
        "next_action": certification_result["next_action"],
        "repair_steps": repair_steps,
        "stop_conditions": [
            "Do not generate final_report.md until blocking source gaps, failed checks, and human-review requirements are repaired or explicitly excluded from report scope.",
            "Do not convert inferred or partial numeric support into a final value assertion without explicit formula inputs and preserved caveats.",
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


def _append_repair_step(
    repair_steps: list[dict[str, Any]],
    seen_step_keys: set[tuple[Any, ...]],
    *,
    action: str,
    target_state: str,
    target_artifact: str,
    reason: str,
    related_claim_ids: list[str],
    related_research_gap_ids: list[str],
    required_source_types: list[str],
    priority: str,
    expected_output: str,
) -> None:
    key = (action, target_state, target_artifact, reason, tuple(sorted(related_claim_ids)), tuple(sorted(related_research_gap_ids)))
    if key in seen_step_keys:
        return
    seen_step_keys.add(key)
    repair_steps.append(
        {
            "repair_step_id": f"RP-{len(repair_steps) + 1:03d}",
            "repair_action": action,
            "target_state": target_state,
            "target_artifact": target_artifact,
            "reason": reason,
            "related_claim_ids": related_claim_ids,
            "related_research_gap_ids": related_research_gap_ids,
            "required_source_types": required_source_types,
            "priority": priority,
            "expected_output": expected_output,
        }
    )


def _repair_step_from_claim_action(cert: dict[str, Any], repair_action: dict[str, Any]) -> dict[str, Any]:
    target = repair_action.get("target", "block_pipeline_until_structure_repaired")
    action = str(repair_action.get("action") or _default_action_for_target(target))
    reason = f"{action} for {cert['claim_id']}; {repair_action.get('reason', cert.get('certification_basis', 'repair required'))}"
    return {
        "action": _normalized_action_for_target(target, action),
        "target_state": _target_state_for_claim_action(target),
        "target_artifact": _target_artifact_for_claim_action(target),
        "reason": reason,
        "related_claim_ids": [cert["claim_id"]],
        "related_research_gap_ids": [],
        "required_source_types": _required_source_types_for_claim_action(target),
        "priority": "high" if target in {"M2_source_retrieval", "M5_numeric_verification"} else "medium",
        "expected_output": _expected_output_for_claim_action(target),
    }


def _should_emit_claim_repair_step(cert: dict[str, Any], repair_action: dict[str, Any]) -> bool:
    if cert.get("related_source_gap_ids"):
        return False
    if cert.get("certification_status") in {"certified", "certified_with_caveat"}:
        return False
    return bool(repair_action.get("target"))


def _research_gap_from_source_gap(index: int, gap_node: dict[str, Any], related_claim_ids: list[str]) -> dict[str, Any]:
    affected_fact_types = [_safe_key(value) for value in gap_node.get("affected_claim_types", [])]
    gap_type = _gap_type(affected_fact_types, default="source_gap")
    return {
        "research_gap_id": f"RG-{index:03d}",
        "gap_type": gap_type,
        "affected_fact_types": affected_fact_types,
        "related_claim_ids": related_claim_ids,
        "related_gap_node_ids": [gap_node["gap_node_id"]],
        "missing_source_need_ids": [gap_node["missing_source_need_id"]],
        "gap_description": _gap_description(gap_type, affected_fact_types, gap_node.get("missing_source_need_id")),
        "severity": _severity_for_gap(affected_fact_types, blocks_certification=True),
        "blocks_certification": True,
        "recommended_repair_target": "M2_source_retrieval",
        "suggested_source_types": _suggested_source_types(affected_fact_types),
    }


def _research_gap_from_numeric_failure(index: int, claim_id: str, claim: dict[str, Any] | None, numeric_result: dict[str, Any]) -> dict[str, Any]:
    claim_type = _claim_type(claim, fallback="derived_numeric_candidate")
    return {
        "research_gap_id": f"RG-{index:03d}",
        "gap_type": "numeric_formula_or_input_gap",
        "affected_fact_types": [claim_type],
        "related_claim_ids": [claim_id],
        "related_gap_node_ids": [],
        "missing_source_need_ids": [],
        "gap_description": f"Numeric verification for {claim_type} requires explicit formula inputs or corrected expected result.",
        "severity": "high",
        "blocks_certification": True,
        "recommended_repair_target": "M5_numeric_verification",
        "suggested_source_types": ["explicit numeric formula", "source-bounded numeric inputs", "calculation support document"],
        "failed_verification_reason": numeric_result.get("caveat", "numeric verification failed"),
    }


def _research_gap_from_claim(index: int, cert: dict[str, Any], claim: dict[str, Any], related_source_gap_ids: list[str]) -> dict[str, Any]:
    claim_type = _claim_type(claim, cert.get("claim_type", "generic_fact"))
    status = cert["certification_status"]
    return {
        "research_gap_id": f"RG-{index:03d}",
        "gap_type": _gap_type([claim_type], default=status),
        "affected_fact_types": [claim_type],
        "related_claim_ids": [cert["claim_id"]],
        "related_gap_node_ids": [],
        "missing_source_need_ids": [],
        "gap_description": f"Claim {cert['claim_id']} with type {claim_type} is not certified because status is {status}.",
        "severity": "high" if status in {"unsupported", "blocked_by_source_gap", "failed"} else "medium",
        "blocks_certification": status in {"unsupported", "blocked_by_source_gap", "failed", "requires_numeric_verification"},
        "recommended_repair_target": _recommended_target_for_status(status),
        "suggested_source_types": _suggested_source_types([claim_type]),
        "related_source_gap_ids": related_source_gap_ids,
        "failed_verification_reason": cert.get("certification_basis", "claim certification did not pass"),
    }


def _gap_type(affected_fact_types: list[str], default: str) -> str:
    if not affected_fact_types:
        return default
    if any("numeric" in value or "valuation" in value or "consideration" in value for value in affected_fact_types):
        return "numeric_or_transaction_terms_source_gap"
    if any("ownership" in value or "governance" in value or "proceeds" in value or "cap_table" in value for value in affected_fact_types):
        return "ownership_or_value_transfer_source_gap"
    if any("patent" in value or "intellectual" in value or "asset" in value for value in affected_fact_types):
        return "asset_or_intellectual_property_source_gap"
    if any("clinical" in value or "regulatory" in value for value in affected_fact_types):
        return "regulatory_or_clinical_source_gap"
    return f"{affected_fact_types[0]}_source_gap"


def _gap_description(gap_type: str, affected_fact_types: list[str], missing_source_need_id: str | None) -> str:
    affected = ", ".join(affected_fact_types) if affected_fact_types else "generic_fact"
    source_need = missing_source_need_id or "unspecified_source_need"
    return f"Unresolved {gap_type} for {affected}; missing source need {source_need} requires authoritative repair."


def _severity_for_gap(affected_fact_types: list[str], blocks_certification: bool) -> str:
    if blocks_certification and any(value in {"transaction_consideration", "ownership_or_governance", "legal_regulatory_and_diligence_risks"} for value in affected_fact_types):
        return "high"
    return "high" if blocks_certification else "medium"


def _suggested_source_types(affected_fact_types: list[str]) -> list[str]:
    joined = " ".join(affected_fact_types)
    if any(term in joined for term in ("numeric", "consideration", "valuation", "payment", "financing")):
        return ["transaction agreement", "official transaction announcement", "audited filing or authoritative financial disclosure"]
    if any(term in joined for term in ("ownership", "governance", "proceeds", "cap_table")):
        return ["ownership disclosure", "capitalization schedule", "transaction disclosure schedule"]
    if any(term in joined for term in ("patent", "intellectual", "asset")):
        return ["official intellectual property record", "assignment record", "authoritative product or asset disclosure"]
    if any(term in joined for term in ("clinical", "regulatory")):
        return ["regulatory filing", "clinical registry record", "official development-status disclosure"]
    return ["authoritative primary source", "official filing", "signed transaction document"]


def _repair_action(gap: dict[str, Any]) -> str:
    gap_type = gap["gap_type"]
    if "numeric" in gap_type or gap.get("recommended_repair_target") == "M5_numeric_verification":
        return "repair_numeric_formula_or_inputs"
    if "conflict" in gap_type:
        return "resolve_source_conflict"
    if gap.get("missing_source_need_ids"):
        return "rerun_m2_source_retrieval"
    if gap.get("blocks_certification"):
        return "retrieve_authoritative_source"
    return "add_human_review_item"


def _repair_target_state(action: str) -> str:
    if action == "repair_numeric_formula_or_inputs":
        return "M2_source_retrieval_or_M5_numeric_verification"
    if action in {"resolve_source_conflict", "add_human_review_item"}:
        return "M4_claim_evidence_graph_update"
    return "M2_source_retrieval"


def _target_artifact(action: str) -> str:
    if action == "repair_numeric_formula_or_inputs":
        return "retrieved_sources_manifest.json or certification_result.json"
    if action in {"resolve_source_conflict", "add_human_review_item"}:
        return "claim_evidence_graph.json"
    return "retrieved_sources_manifest.json"


def _repair_reason(gap: dict[str, Any], action: str) -> str:
    claim_ids = ", ".join(gap["related_claim_ids"]) if gap["related_claim_ids"] else "no direct claim id"
    return f"{action} for {gap['gap_type']} affecting {claim_ids}; {gap['gap_description']}"


def _expected_output(action: str) -> str:
    if action == "repair_numeric_formula_or_inputs":
        return "Explicit formula inputs or corrected numeric support before rerunning M5 numeric verification."
    if action in {"resolve_source_conflict", "add_human_review_item"}:
        return "Updated claim framing, conflict disposition, or documented human review before rerunning M4/M5."
    return "Updated retrieved source manifest enabling M3/M4/M5 rerun with source-bounded evidence."


def _default_action_for_target(target: str) -> str:
    if target == "M2_source_retrieval":
        return "rerun_m2_source_retrieval"
    if target == "M4_claim_evidence_graph":
        return "repair_claim_rewrite_or_mapping"
    if target == "M5_numeric_verification":
        return "repair_numeric_formula_or_inputs"
    if target == "human_review":
        return "add_human_review_item"
    return "repair_pipeline_structure"


def _normalized_action_for_target(target: str, action: str) -> str:
    if target == "M2_source_retrieval":
        return action if action.startswith(("rerun_m2", "retrieve", "repair_source", "repair_evidence")) else "rerun_m2_source_retrieval"
    if target == "M4_claim_evidence_graph":
        return action if action.startswith(("repair_claim", "repair_overclaim", "resolve_claim", "add_required", "correct_temporal", "add_hindsight")) else "repair_claim_rewrite_or_mapping"
    if target == "M5_numeric_verification":
        return "repair_numeric_formula_or_inputs"
    if target == "human_review":
        return "add_human_review_item"
    return "repair_pipeline_structure"


def _target_state_for_claim_action(target: str) -> str:
    if target == "M2_source_retrieval":
        return "M2_source_retrieval"
    if target == "M4_claim_evidence_graph":
        return "M4_claim_evidence_graph_update"
    if target == "M5_numeric_verification":
        return "M2_source_retrieval_or_M5_numeric_verification"
    if target == "human_review":
        return "M4_claim_evidence_graph_update"
    return "M5_loop_certification"


def _target_artifact_for_claim_action(target: str) -> str:
    if target == "M2_source_retrieval":
        return "retrieved_sources_manifest.json"
    if target == "M4_claim_evidence_graph":
        return "claim_evidence_graph.json"
    if target == "M5_numeric_verification":
        return "certification_result.json"
    if target == "human_review":
        return "human_review_items"
    return "certification_result.json"


def _required_source_types_for_claim_action(target: str) -> list[str]:
    if target == "M2_source_retrieval":
        return ["authoritative primary source", "official filing", "signed transaction document"]
    if target == "M4_claim_evidence_graph":
        return ["rewritten source-bounded claim statement", "claim-evidence edge review", "overclaim or ambiguity repair"]
    if target == "M5_numeric_verification":
        return ["explicit numeric formula", "source-bounded numeric inputs", "calculation support document"]
    if target == "human_review":
        return ["documented human review decision", "approved caveat or exclusion from downstream use"]
    return ["valid certification structure"]


def _expected_output_for_claim_action(target: str) -> str:
    if target == "M2_source_retrieval":
        return "Updated source retrieval inputs before rerunning M3/M4/M5."
    if target == "M4_claim_evidence_graph":
        return "Updated claim wording, support mapping, or caveat metadata before rerunning M5."
    if target == "M5_numeric_verification":
        return "Explicit formula inputs or corrected numeric support before rerunning M5 numeric verification."
    if target == "human_review":
        return "Documented human review disposition before final recommendation or report assertion use."
    return "Repaired M5 certification structure before continuing the pipeline."


def _recommended_target_for_status(status: str) -> str:
    if status == "requires_numeric_verification":
        return "M5_numeric_verification"
    if status in {"failed", "requires_human_review"}:
        return "M4_claim_evidence_graph_update"
    return "M2_source_retrieval"


def _claim_type(claim: dict[str, Any] | None, fallback: str = "generic_fact") -> str:
    if not claim:
        return _safe_key(fallback)
    return _safe_key(str(claim.get("canonical_fact_type") or claim.get("claim_type") or fallback))


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
