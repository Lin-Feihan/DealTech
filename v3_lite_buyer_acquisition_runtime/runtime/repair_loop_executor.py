from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RepairLoopError(ValueError):
    pass


ALLOWED_REPAIR_TARGET_STATES = {
    "M2_source_retrieval",
    "M2_source_retrieval_or_M5_numeric_verification",
    "M4_claim_evidence_graph_update",
}
FORBIDDEN_OUTPUT_MARKERS = {"final_report.md", "analysis_package.json", "final_report", "analysis_package"}
MUST_NOT_USE_SOURCES = ["case_seed", "mandate_notes", "Bohan PDF", "model memory", "test fixtures"]
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
    targeted_source_needs = []
    blocked_or_deferred_repairs = []
    for step in repair_plan["repair_steps"]:
        if "M2_source_retrieval" in step["target_state"]:
            related_gap = _first_related_gap(step, gaps_by_id)
            targeted_source_needs.append(_targeted_source_need(len(targeted_source_needs) + 1, step, related_gap))
        else:
            blocked_or_deferred_repairs.append(_blocked_or_deferred_repair(step, "non_m2_repair_target_deferred"))
    targeted_search_queries = []
    for need in targeted_source_needs:
        for query_text in _query_texts_for_need(need):
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
        is_m2 = "M2_source_retrieval" in step["target_state"]
        status = "deferred_provider_unavailable" if is_m2 else "planned"
        reason = (
            "Dry run only: no retrieval provider was invoked and no authoritative source manifest was supplied."
            if is_m2
            else "Repair step is not executable as targeted M2 source retrieval in M5.1 dry run."
        )
        next_action = (
            "Supply manual authoritative sources or configure a retrieval provider, then rerun M2 source retrieval."
            if is_m2
            else "Handle after source repair or claim graph update decision."
        )
        attempts.append(
            {
                "repair_attempt_id": f"RA-{len(attempts) + 1:03d}",
                "related_repair_step_id": step["repair_step_id"],
                "target_state": step["target_state"],
                "intended_provider": "manual_authoritative_source_supply_or_configured_retrieval_provider" if is_m2 else "not_invoked_in_m5_1",
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


def _targeted_source_need(index: int, step: dict[str, Any], research_gap: dict[str, Any] | None) -> dict[str, Any]:
    gap_id = research_gap["research_gap_id"] if research_gap else step["related_research_gap_ids"][0]
    description = research_gap["gap_description"] if research_gap else step["reason"]
    return {
        "targeted_source_need_id": f"TSN-{index:03d}",
        "original_research_gap_id": gap_id,
        "related_claim_ids": step["related_claim_ids"],
        "missing_source_need_ids": research_gap.get("missing_source_need_ids", []) if research_gap else [],
        "missing_source_description": description,
        "required_source_types": step.get("required_source_types", research_gap.get("suggested_source_types", []) if research_gap else []),
        "preferred_source_owners": _preferred_source_owners(description, step.get("required_source_types", [])),
        "source_tier_required": "Tier 1" if step["priority"] == "high" else "Tier 1 preferred",
        "priority": step["priority"],
        "purpose": _purpose_for_need(description),
        "expected_downstream_update": _expected_downstream_update(step),
    }


def _blocked_or_deferred_repair(step: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "repair_step_id": step["repair_step_id"],
        "target_state": step["target_state"],
        "reason": reason,
        "related_claim_ids": step["related_claim_ids"],
    }


def _first_related_gap(step: dict[str, Any], gaps_by_id: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for gap_id in step["related_research_gap_ids"]:
        if gap_id in gaps_by_id:
            return gaps_by_id[gap_id]
    return None


def _query_texts_for_need(need: dict[str, Any]) -> list[str]:
    text = need["missing_source_description"].lower()
    if "cninfo" in text or "haisco" in text or "11.12" in text:
        return [
            "CNINFO SZSE Haisco FronThera Bohan Jin 11.12 disclosure",
            "Haisco disclosure FronThera Bohan Jin VP Chemistry director 11.12%",
        ]
    if "patent" in text or "tyk2" in text:
        return [
            "WIPO USPTO PCT/US2019/057485 TYK2 FronThera",
            "WIPO USPTO PCT/US2020/021850 TYK2 FronThera",
        ]
    if "personal realized proceeds" in text or "personal proceeds" in text:
        return ["official source Bohan Jin personal proceeds FronThera acquisition"]
    if "cap table" in text:
        return ["official source FronThera pre-2021 cap table ownership"]
    if "$180" in text or "180m" in text:
        return ["SEC FronThera acquisition $180 million maximum aggregate value"]
    return [need["missing_source_description"]]


def _intended_provider_for_need(need: dict[str, Any]) -> str:
    owners = " ".join(need["preferred_source_owners"]).lower()
    if "patent" in owners or "wipo" in owners or "uspto" in owners:
        return "patent_provider_or_manual_authoritative_source_supply"
    if "sec" in owners:
        return "sec_edgar_provider_or_manual_authoritative_source_supply"
    if "cninfo" in owners or "szse" in owners:
        return "stock_exchange_disclosure_provider_or_manual_authoritative_source_supply"
    return "manual_authoritative_source_supply_or_configured_retrieval_provider"


def _preferred_source_owners(description: str, required_source_types: list[str]) -> list[str]:
    text = " ".join([description, " ".join(required_source_types)]).lower()
    if "cninfo" in text or "szse" in text or "haisco" in text:
        return ["Haisco / CNINFO / SZSE"]
    if "patent" in text or "tyk2" in text:
        return ["WIPO / USPTO / official patent office"]
    if "sec" in text or "$180" in text:
        return ["SEC / Alumis / official transaction parties"]
    if "cap table" in text or "ownership" in text:
        return ["FronThera / Haisco / transaction disclosure schedule owner"]
    return ["authoritative primary source owner"]


def _purpose_for_need(description: str) -> str:
    if "180" in description:
        return "Determine whether direct headline maximum value wording exists; otherwise preserve numeric caveat."
    return "Retrieve authoritative source support for unresolved certification-blocking repair gap."


def _expected_downstream_update(step: dict[str, Any]) -> str:
    if step["target_state"] == "M2_source_retrieval_or_M5_numeric_verification":
        return "Either update M2 retrieved sources if a direct source exists, or keep M5 numeric verification caveat unchanged."
    return "If authoritative sources are supplied, rerun M2 then M3/M4/M5 to update evidence and certification state."


def _requests_forbidden_output(step: dict[str, Any]) -> bool:
    text = " ".join(str(step.get(field, "")) for field in ("target_artifact", "reason", "expected_output", "target_state")).lower()
    return any(marker in text for marker in FORBIDDEN_OUTPUT_MARKERS)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
