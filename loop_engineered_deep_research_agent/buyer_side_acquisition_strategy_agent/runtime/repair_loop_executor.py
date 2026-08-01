from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RepairLoopError(ValueError):
    pass


ALLOWED_REPAIR_TARGET_STATES = {
    "M2_source_retrieval",
    "M4_claim_evidence_graph_update",
    "M5_numeric_verification",
}
FORBIDDEN_OUTPUT_MARKERS = {"final_report.md", "analysis_package.json", "final_report", "analysis_package"}
MUST_NOT_USE_SOURCES = ["case_seed", "mandate_notes", "model memory", "test fixtures", "unverified local notes"]
REPAIR_STEP_REQUIRED_FIELDS = {
    "repair_step_id",
    "target_state",
    "target_artifact",
    "reason",
    "priority",
    "related_claim_ids",
    "related_research_gap_ids",
}


def load_json_artifact(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise RepairLoopError(f"Artifact not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RepairLoopError(f"Invalid JSON artifact at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RepairLoopError(f"Artifact at {path} must be a JSON object.")
    return payload


def repair_plan_source_id(repair_plan: dict[str, Any]) -> str:
    return f"REPAIR-{repair_plan['case_id']}-{repair_plan['created_from_certification_result_id']}"


def targeted_source_discovery_plan_source_id(plan: dict[str, Any]) -> str:
    return f"TSDP-{plan['case_id']}-{plan['created_at']}"


def build_m5_1_artifacts(
    certification_result: dict[str, Any],
    research_gaps: dict[str, Any],
    repair_plan: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_m5_1_inputs(certification_result, research_gaps, repair_plan)
    targeted_plan = build_targeted_source_discovery_plan(certification_result, research_gaps, repair_plan)
    attempt_log = build_repair_attempt_log(targeted_plan, repair_plan)
    validate_targeted_source_discovery_plan(targeted_plan)
    validate_repair_attempt_log(attempt_log)
    return targeted_plan, attempt_log


def validate_m5_1_inputs(certification_result: Any, research_gaps: Any, repair_plan: Any) -> None:
    if not isinstance(certification_result, dict):
        raise RepairLoopError("certification_result must be an object.")
    if not isinstance(research_gaps, dict):
        raise RepairLoopError("research_gaps must be an object.")
    if not isinstance(repair_plan, dict):
        raise RepairLoopError("repair_plan must be an object.")
    if certification_result.get("generated_artifact") != "certification_result.json":
        raise RepairLoopError("M5.1 requires certification_result.json input.")
    if research_gaps.get("generated_artifact") != "research_gaps.json":
        raise RepairLoopError("M5.1 requires research_gaps.json input.")
    if repair_plan.get("generated_artifact") != "repair_plan.json":
        raise RepairLoopError("M5.1 requires repair_plan.json input.")
    if not repair_plan.get("next_action"):
        raise RepairLoopError("repair_plan.next_action is required.")
    if not isinstance(repair_plan.get("repair_steps"), list) or not repair_plan["repair_steps"]:
        raise RepairLoopError("repair_plan.repair_steps must be a non-empty array.")
    case_ids = {certification_result.get("case_id"), research_gaps.get("case_id"), repair_plan.get("case_id")}
    if len(case_ids) != 1:
        raise RepairLoopError("M5.1 input case_id values must match.")

    research_gap_ids = {gap["research_gap_id"] for gap in research_gaps.get("research_gaps", [])}
    claim_ids = {claim["claim_id"] for claim in certification_result.get("claim_certifications", [])}
    for step in repair_plan["repair_steps"]:
        missing = sorted(field for field in REPAIR_STEP_REQUIRED_FIELDS if field not in step)
        if missing:
            raise RepairLoopError(f"repair_step missing required field(s): {', '.join(missing)}")
        if step["target_state"] not in ALLOWED_REPAIR_TARGET_STATES:
            raise RepairLoopError(f"repair_step target_state not allowed: {step['target_state']}")
        if _requests_forbidden_output(step):
            raise RepairLoopError(f"repair_step requests forbidden report or analysis output: {step['repair_step_id']}")
        unknown_claims = sorted(set(step["related_claim_ids"]) - claim_ids)
        if unknown_claims:
            raise RepairLoopError(f"repair_step cites unknown claim_id(s): {step['repair_step_id']} -> {', '.join(unknown_claims)}")
        unknown_gaps = sorted(set(step["related_research_gap_ids"]) - research_gap_ids)
        if unknown_gaps:
            raise RepairLoopError(f"repair_step cites unknown research_gap_id(s): {step['repair_step_id']} -> {', '.join(unknown_gaps)}")


def build_targeted_source_discovery_plan(
    certification_result: dict[str, Any],
    research_gaps: dict[str, Any],
    repair_plan: dict[str, Any],
) -> dict[str, Any]:
    gaps_by_id = {gap["research_gap_id"]: gap for gap in research_gaps["research_gaps"]}
    certs_by_id = {cert["claim_id"]: cert for cert in certification_result["claim_certifications"]}
    case_context = _case_context(certification_result)
    targeted_source_needs = []
    blocked_or_deferred_repairs = []
    for step in repair_plan["repair_steps"]:
        if step["target_state"] in {"M2_source_retrieval", "M5_numeric_verification"}:
            related_gap = _first_related_gap(step, gaps_by_id)
            targeted_source_needs.append(_targeted_source_need(len(targeted_source_needs) + 1, step, related_gap, certs_by_id, case_context))
        else:
            blocked_or_deferred_repairs.append(_blocked_or_deferred_repair(step, "non_m2_repair_target_deferred"))
    targeted_search_queries = []
    for need in targeted_source_needs:
        for query_text in _query_texts_for_need(need, case_context):
            targeted_search_queries.append(
                {
                    "query_id": f"TSQ-{len(targeted_search_queries) + 1:03d}",
                    "query_text": query_text,
                    "target_source_need_id": need["targeted_source_need_id"],
                    "intended_provider": _intended_provider_for_need(need),
                    "expected_source_owner": need["preferred_source_owners"][0],
                    "expected_source_tier": need["source_tier_required"],
                    "must_not_use_sources": MUST_NOT_USE_SOURCES,
                }
            )
    plan = {
        "case_id": certification_result["case_id"],
        "generated_artifact": "targeted_source_discovery_plan.json",
        "stage": "M5_1_repair_loop_execution",
        "created_from_repair_plan_id": repair_plan_source_id(repair_plan),
        "created_at": _now_utc_iso(),
        "target_state": "M2_source_retrieval",
        "targeted_source_needs": targeted_source_needs,
        "targeted_search_queries": targeted_search_queries,
        "expected_retrieval_outputs": [
            "retrieved_sources_manifest.json only after real authoritative sources are supplied or a configured retrieval provider returns source-bounded documents",
            "cache files for retrieved authoritative source documents when available",
            "no raw_evidence.json in M5.1 dry run without real manifest-backed authoritative sources",
        ],
        "blocked_or_deferred_repairs": blocked_or_deferred_repairs,
    }
    return plan


def build_repair_attempt_log(targeted_plan: dict[str, Any], repair_plan: dict[str, Any]) -> dict[str, Any]:
    attempts = []
    targeted_need_ids_by_claim = {
        claim_id: need["targeted_source_need_id"]
        for need in targeted_plan["targeted_source_needs"]
        for claim_id in need["related_claim_ids"]
    }
    unresolved = []
    for step in repair_plan["repair_steps"]:
        is_source_or_numeric = step["target_state"] in {"M2_source_retrieval", "M5_numeric_verification"}
        status = "deferred_provider_unavailable" if is_source_or_numeric else "planned"
        reason = (
            "Dry run only: no retrieval provider was invoked and no authoritative source manifest was supplied."
            if is_source_or_numeric
            else "Repair step is not executable as targeted M2 source retrieval in M5.1 dry run."
        )
        next_action = (
            "Supply manual authoritative sources or configure a retrieval provider, then rerun M2 source retrieval."
            if is_source_or_numeric
            else "Handle after source repair, claim graph update, or human review decision."
        )
        attempts.append(
            {
                "repair_attempt_id": f"RA-{len(attempts) + 1:03d}",
                "related_repair_step_id": step["repair_step_id"],
                "target_state": step["target_state"],
                "intended_provider": "manual_authoritative_source_supply_or_configured_retrieval_provider" if is_source_or_numeric else "not_invoked_in_m5_1",
                "status": status,
                "reason": reason,
                "output_artifact_generated": False,
                "next_recommended_action": next_action,
            }
        )
        unresolved.append(
            {
                "related_repair_step_id": step["repair_step_id"],
                "related_claim_ids": step["related_claim_ids"],
                "targeted_source_need_ids": sorted({targeted_need_ids_by_claim[claim_id] for claim_id in step["related_claim_ids"] if claim_id in targeted_need_ids_by_claim}),
                "unresolved_reason": reason,
                "next_recommended_action": next_action,
            }
        )
    return {
        "case_id": targeted_plan["case_id"],
        "generated_artifact": "repair_attempt_log.json",
        "stage": "M5_1_repair_attempt_log",
        "created_from_targeted_source_discovery_plan_id": targeted_source_discovery_plan_source_id(targeted_plan),
        "created_at": _now_utc_iso(),
        "repair_attempts": attempts,
        "unresolved_repairs": unresolved,
        "next_action": "supply_manual_authoritative_sources_or_configure_retrieval_provider_before_running_M2_repair",
    }


def validate_targeted_source_discovery_plan(plan: Any) -> None:
    if not isinstance(plan, dict):
        raise RepairLoopError("targeted_source_discovery_plan must be an object.")
    required = {
        "case_id",
        "generated_artifact",
        "stage",
        "created_from_repair_plan_id",
        "created_at",
        "target_state",
        "targeted_source_needs",
        "targeted_search_queries",
        "expected_retrieval_outputs",
        "blocked_or_deferred_repairs",
    }
    missing = sorted(field for field in required if field not in plan)
    if missing:
        raise RepairLoopError(f"targeted_source_discovery_plan missing field(s): {', '.join(missing)}")
    if plan["generated_artifact"] != "targeted_source_discovery_plan.json":
        raise RepairLoopError("generated_artifact must be targeted_source_discovery_plan.json.")
    if plan["stage"] != "M5_1_repair_loop_execution":
        raise RepairLoopError("stage must be M5_1_repair_loop_execution.")
    if plan["target_state"] != "M2_source_retrieval":
        raise RepairLoopError("targeted_source_discovery_plan target_state must be M2_source_retrieval.")
    need_ids = {need["targeted_source_need_id"] for need in plan["targeted_source_needs"]}
    for need in plan["targeted_source_needs"]:
        for field in (
            "targeted_source_need_id",
            "original_research_gap_id",
            "related_claim_ids",
            "missing_source_need_ids",
            "missing_source_description",
            "required_source_types",
            "preferred_source_owners",
            "source_tier_required",
            "priority",
            "purpose",
            "expected_downstream_update",
        ):
            if field not in need:
                raise RepairLoopError(f"targeted_source_need missing {field}.")
    for query in plan["targeted_search_queries"]:
        if query["target_source_need_id"] not in need_ids:
            raise RepairLoopError(f"targeted_search_query cites unknown need: {query['query_id']}")
        if set(MUST_NOT_USE_SOURCES) - set(query["must_not_use_sources"]):
            raise RepairLoopError(f"targeted_search_query missing forbidden source controls: {query['query_id']}")


def validate_repair_attempt_log(log: Any) -> None:
    if not isinstance(log, dict):
        raise RepairLoopError("repair_attempt_log must be an object.")
    required = {
        "case_id",
        "generated_artifact",
        "stage",
        "created_from_targeted_source_discovery_plan_id",
        "created_at",
        "repair_attempts",
        "unresolved_repairs",
        "next_action",
    }
    missing = sorted(field for field in required if field not in log)
    if missing:
        raise RepairLoopError(f"repair_attempt_log missing field(s): {', '.join(missing)}")
    if log["generated_artifact"] != "repair_attempt_log.json":
        raise RepairLoopError("generated_artifact must be repair_attempt_log.json.")
    if log["stage"] != "M5_1_repair_attempt_log":
        raise RepairLoopError("stage must be M5_1_repair_attempt_log.")
    allowed_statuses = {"planned", "attempted", "failed_closed", "deferred_provider_unavailable", "completed"}
    for attempt in log["repair_attempts"]:
        for field in (
            "repair_attempt_id",
            "related_repair_step_id",
            "target_state",
            "intended_provider",
            "status",
            "reason",
            "output_artifact_generated",
            "next_recommended_action",
        ):
            if field not in attempt:
                raise RepairLoopError(f"repair_attempt missing {field}.")
        if attempt["status"] not in allowed_statuses:
            raise RepairLoopError(f"invalid repair_attempt status: {attempt['status']}")
        if attempt["output_artifact_generated"] is not False:
            raise RepairLoopError("M5.1 dry run must not mark retrieval output artifacts as generated.")


def _targeted_source_need(
    index: int,
    step: dict[str, Any],
    research_gap: dict[str, Any] | None,
    certs_by_id: dict[str, dict[str, Any]],
    case_context: dict[str, str],
) -> dict[str, Any]:
    gap_id = research_gap["research_gap_id"] if research_gap else _claim_level_gap_id(step)
    fact_types = _fact_types_for_step(step, research_gap, certs_by_id)
    target_question = _target_fact_or_question(step, research_gap, fact_types)
    required_source_types = _required_source_types(step, research_gap, fact_types)
    return {
        "targeted_source_need_id": f"TSN-{index:03d}",
        "original_research_gap_id": gap_id,
        "related_claim_ids": step["related_claim_ids"],
        "missing_source_need_ids": research_gap.get("missing_source_need_ids", []) if research_gap else [],
        "missing_source_description": target_question,
        "target_fact_or_question": target_question,
        "affected_fact_types": fact_types,
        "required_source_types": required_source_types,
        "preferred_source_owners": _preferred_source_owners(required_source_types, case_context),
        "source_tier_required": "Tier 1" if step["priority"] == "high" else "Tier 1 preferred",
        "priority": step["priority"],
        "purpose": _purpose_for_need(fact_types),
        "expected_downstream_update": _expected_downstream_update(step),
    }


def _blocked_or_deferred_repair(step: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "repair_step_id": step["repair_step_id"],
        "target_state": step["target_state"],
        "reason": reason,
        "related_claim_ids": step["related_claim_ids"],
    }


def _claim_level_gap_id(step: dict[str, Any]) -> str:
    if step.get("related_research_gap_ids"):
        return step["related_research_gap_ids"][0]
    if step.get("related_claim_ids"):
        return f"claim_level_repair:{step['related_claim_ids'][0]}"
    return f"claim_level_repair:{step['repair_step_id']}"


def _first_related_gap(step: dict[str, Any], gaps_by_id: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for gap_id in step["related_research_gap_ids"]:
        if gap_id in gaps_by_id:
            return gaps_by_id[gap_id]
    return None


def _query_texts_for_need(need: dict[str, Any], case_context: dict[str, str]) -> list[str]:
    query_parts = [
        case_context.get("buyer", "buyer"),
        case_context.get("target", "target"),
        case_context.get("transaction_type", "acquisition"),
        " ".join(need.get("affected_fact_types", [])),
        " ".join(need.get("required_source_types", [])),
    ]
    base = _clean_query(" ".join(part for part in query_parts if part))
    if not base:
        base = "buyer target acquisition authoritative source"
    return [base, _clean_query(f"{base} official filing source")]


def _intended_provider_for_need(need: dict[str, Any]) -> str:
    text = " ".join(need["required_source_types"] + need["preferred_source_owners"]).lower()
    if "intellectual" in text or "assignment" in text:
        return "official_ip_record_provider_or_manual_authoritative_source_supply"
    if "filing" in text or "official" in text:
        return "official_filing_provider_or_manual_authoritative_source_supply"
    if "clinical" in text or "regulatory" in text:
        return "regulatory_or_clinical_provider_or_manual_authoritative_source_supply"
    return "manual_authoritative_source_supply_or_configured_retrieval_provider"


def _preferred_source_owners(required_source_types: list[str], case_context: dict[str, str]) -> list[str]:
    buyer = case_context.get("buyer")
    target = case_context.get("target")
    if buyer and target:
        return [f"{buyer} or {target} authoritative source owner"]
    if buyer:
        return [f"{buyer} authoritative source owner"]
    if target:
        return [f"{target} authoritative source owner"]
    if any("regulatory" in item or "clinical" in item for item in required_source_types):
        return ["official regulatory or clinical source owner"]
    if any("intellectual" in item or "assignment" in item for item in required_source_types):
        return ["official intellectual property source owner"]
    return ["authoritative primary source owner"]


def _purpose_for_need(fact_types: list[str]) -> str:
    fact_text = ", ".join(fact_types) if fact_types else "generic acquisition fact"
    return f"Retrieve authoritative source support for unresolved {fact_text} repair need."


def _expected_downstream_update(step: dict[str, Any]) -> str:
    if step["target_state"] == "M5_numeric_verification":
        return "Update M5 numeric verification inputs, then rerun downstream certification."
    return "If authoritative sources are supplied, rerun M2 then M3/M4/M5 to update evidence and certification state."


def _requests_forbidden_output(step: dict[str, Any]) -> bool:
    text = " ".join(str(step.get(field, "")) for field in ("target_artifact", "reason", "expected_output", "target_state")).lower()
    return any(marker in text for marker in FORBIDDEN_OUTPUT_MARKERS)


def _fact_types_for_step(step: dict[str, Any], research_gap: dict[str, Any] | None, certs_by_id: dict[str, dict[str, Any]]) -> list[str]:
    if research_gap and research_gap.get("affected_fact_types"):
        return [_safe_key(str(value)) for value in research_gap["affected_fact_types"]]
    claim_types = []
    for claim_id in step["related_claim_ids"]:
        cert = certs_by_id.get(claim_id)
        if cert and cert.get("claim_type"):
            claim_types.append(_safe_key(str(cert["claim_type"])))
    if claim_types:
        return sorted(set(claim_types))
    return [_safe_key(str(step.get("repair_action") or "generic_fact"))]


def _target_fact_or_question(step: dict[str, Any], research_gap: dict[str, Any] | None, fact_types: list[str]) -> str:
    explicit = step.get("target_fact_or_question") or (research_gap or {}).get("target_fact_or_question")
    if isinstance(explicit, str) and explicit.strip():
        return _neutral_text(explicit)
    fact_text = ", ".join(fact_types) if fact_types else "generic acquisition fact"
    status_reason = _neutral_text(str((research_gap or {}).get("failed_verification_reason") or step.get("repair_action") or "repair required"))
    return f"Find authoritative source support for {fact_text}; repair context: {status_reason}."


def _required_source_types(step: dict[str, Any], research_gap: dict[str, Any] | None, fact_types: list[str]) -> list[str]:
    candidates = step.get("required_source_types") or (research_gap or {}).get("suggested_source_types") or []
    cleaned = [_neutral_text(str(item)) for item in candidates if str(item).strip()]
    if cleaned:
        return cleaned
    fact_text = " ".join(fact_types)
    if any(term in fact_text for term in ("numeric", "consideration", "valuation", "payment")):
        return ["transaction agreement", "official transaction announcement", "audited filing or authoritative financial disclosure"]
    if any(term in fact_text for term in ("ownership", "governance")):
        return ["ownership disclosure", "capitalization schedule", "transaction disclosure schedule"]
    if any(term in fact_text for term in ("intellectual", "asset")):
        return ["official intellectual property record", "assignment record", "authoritative asset disclosure"]
    return ["authoritative primary source", "official filing", "signed transaction document"]


def _case_context(certification_result: dict[str, Any]) -> dict[str, str]:
    context = certification_result.get("case_context") or certification_result.get("transaction_context") or {}
    if not isinstance(context, dict):
        return {}
    return {
        key: _clean_query(str(context[key]))
        for key in ("buyer", "target", "transaction_type")
        if key in context and isinstance(context[key], str) and context[key].strip()
    }


def _neutral_text(text: str) -> str:
    words = []
    for token in text.replace("/", " ").replace("%", " ").split():
        stripped = token.strip(",.;:()[]{}")
        if not stripped or any(character.isupper() or character.isdigit() for character in stripped):
            continue
        safe = _safe_key(stripped)
        if safe and not _looks_case_specific(safe):
            words.append(stripped)
    return " ".join(words) or "generic source repair requirement"


def _clean_query(text: str) -> str:
    return " ".join(_neutral_text(text).split())


def _looks_case_specific(token: str) -> bool:
    forbidden_tokens = {
        "specific_pdf",
        "local_fixture",
    }
    return token in forbidden_tokens or token.startswith("pct_us")


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
