from __future__ import annotations

from typing import Any


class UsageCheckError(ValueError):
    pass


REPORT_ASSERTION = "report_assertion"
FINAL_RECOMMENDATION = "final_recommendation"
EX_ANTE_RECOMMENDATION = "ex_ante_recommendation"
UNCAVEATED_FINANCIAL_CONCLUSION = "uncaveated_financial_conclusion"
RECOMMENDATION_USE = "recommendation_use"
INTERNAL_EVIDENCE_REVIEW = "internal_evidence_review"
RETROSPECTIVE_VALIDATION = "retrospective_validation"
REPAIR_TRACKING = "repair_tracking"

JUDGMENT_DEPENDENCY_GROUPS = {
    "valuation": {"valuation", "consideration", "financial", "return", "price", "payment"},
    "risk": {"risk", "diligence", "regulatory", "legal", "clinical", "integration"},
    "alternatives": {"alternative", "market", "competitive", "strategic", "synergy"},
}


def run_usage_check(claim_evidence_graph: dict[str, Any], evidence_repository: dict[str, Any]) -> list[dict[str, Any]]:
    _validate_inputs(claim_evidence_graph, evidence_repository)
    available_claim_types = {str(claim.get("claim_type", "")).lower() for claim in claim_evidence_graph["claim_nodes"]}
    available_fact_types = {str(record.get("canonical_fact_type", "")).lower() for record in evidence_repository["evidence_records"]}
    available_context = available_claim_types | available_fact_types
    return [_check_claim_usage(index, claim, available_context) for index, claim in enumerate(claim_evidence_graph["claim_nodes"], start=1)]


def usage_results_by_claim_id(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {result["claim_id"]: result for result in results}


def _validate_inputs(claim_evidence_graph: dict[str, Any], evidence_repository: dict[str, Any]) -> None:
    if claim_evidence_graph.get("generated_artifact") != "claim_evidence_graph.json":
        raise UsageCheckError("Usage Check requires claim_evidence_graph.json.")
    if evidence_repository.get("generated_artifact") != "evidence_repository.json":
        raise UsageCheckError("Usage Check requires evidence_repository.json.")
    if claim_evidence_graph.get("case_id") != evidence_repository.get("case_id"):
        raise UsageCheckError("Usage Check requires matching case_id values.")
    if not isinstance(claim_evidence_graph.get("claim_nodes"), list):
        raise UsageCheckError("claim_evidence_graph.claim_nodes must be an array.")
    if not isinstance(evidence_repository.get("evidence_records"), list):
        raise UsageCheckError("evidence_repository.evidence_records must be an array.")


def _check_claim_usage(index: int, claim: dict[str, Any], available_context: set[str]) -> dict[str, Any]:
    blocked: list[str] = []
    allowed: list[str] = [INTERNAL_EVIDENCE_REVIEW]
    caveats: list[str] = []
    reasons: list[str] = []
    repair_actions: list[dict[str, str]] = []

    claim_id = claim.get("claim_id")
    if not claim_id:
        raise UsageCheckError("claim_id is required for every claim node.")

    support_level = claim.get("support_level")
    temporal_scope = claim.get("temporal_scope") or claim.get("evidence_time_relation_to_decision_date")
    permitted_use = claim.get("permitted_use")
    claim_type = str(claim.get("claim_type", "generic_fact"))
    statement = str(claim.get("claim_statement", ""))

    if support_level in {"gap_only", "unsupported"} or not claim.get("supporting_evidence_record_ids"):
        _block(blocked, REPORT_ASSERTION, "gap-only or unsupported claim cannot be used as a report assertion", reasons, repair_actions, "M2_source_retrieval")
        _add(allowed, REPAIR_TRACKING)

    if claim.get("created_from_generic_fallback") is True:
        _block(blocked, REPORT_ASSERTION, "generic fallback claim is not directly report-ready", reasons, repair_actions, "M4_claim_evidence_graph")
        caveats.append("Generic fallback wording may support internal review only until rewritten as a specific source-bounded assertion.")

    if temporal_scope in {"retrospective", "post_decision"}:
        _block(blocked, EX_ANTE_RECOMMENDATION, "retrospective or post-decision claim cannot support ex-ante recommendation", reasons, repair_actions, "M4_claim_evidence_graph")
        _add(allowed, RETROSPECTIVE_VALIDATION)
        caveats.append("Use only for retrospective validation or outcome tracking; do not frame as decision-date evidence.")
    elif permitted_use == "retrospective_outcome_validation":
        _block(blocked, EX_ANTE_RECOMMENDATION, "retrospective permitted use cannot support ex-ante recommendation", reasons, repair_actions, "M4_claim_evidence_graph")
        _add(allowed, RETROSPECTIVE_VALIDATION)
        caveats.append("Permitted use is retrospective outcome validation only.")

    if claim.get("requires_numeric_verification") is True or claim_type == "derived_numeric_candidate":
        _block(
            blocked,
            UNCAVEATED_FINANCIAL_CONCLUSION,
            "numeric claim requires deterministic verification before uncaveated financial conclusion",
            reasons,
            repair_actions,
            "M5_numeric_verification",
        )
        caveats.append("Numeric use is blocked until explicit formula inputs are verified and caveats are preserved.")

    if claim.get("requires_human_review") is True:
        _block(blocked, FINAL_RECOMMENDATION, "claim requires human review before final recommendation use", reasons, repair_actions, "human_review")
        caveats.append("Human review is required before final recommendation wording.")

    if _is_judgment_claim(claim_type, statement):
        missing = _missing_judgment_dependencies(available_context)
        if missing:
            reason = "recommendation, valuation, or strategic-fit claim lacks dependency coverage: " + ", ".join(missing)
            _block(blocked, RECOMMENDATION_USE, reason, reasons, repair_actions, "M4_claim_evidence_graph")
            _block(blocked, FINAL_RECOMMENDATION, reason, reasons, repair_actions, "M4_claim_evidence_graph")
            caveats.append("Judgment claim requires valuation, risk, and alternatives dependencies before recommendation use.")

    if not blocked:
        _add(allowed, REPORT_ASSERTION)
    if not any(use in blocked for use in (FINAL_RECOMMENDATION, EX_ANTE_RECOMMENDATION, RECOMMENDATION_USE)):
        _add(allowed, EX_ANTE_RECOMMENDATION)

    status = "blocked" if _has_blocking_report_use(blocked) else "passed_with_caveat" if caveats or blocked else "passed"
    return {
        "usage_check_id": f"UC-{index:03d}",
        "claim_id": claim_id,
        "usage_check_status": status,
        "allowed_downstream_uses": _ordered_unique(allowed),
        "blocked_downstream_uses": _ordered_unique(blocked),
        "required_caveats": _ordered_unique(caveats),
        "blocking_reasons": _ordered_unique(reasons),
        "repair_actions": _dedupe_actions(repair_actions),
    }


def _has_blocking_report_use(blocked: list[str]) -> bool:
    return any(use in blocked for use in (REPORT_ASSERTION, FINAL_RECOMMENDATION, EX_ANTE_RECOMMENDATION, UNCAVEATED_FINANCIAL_CONCLUSION, RECOMMENDATION_USE))


def _is_judgment_claim(claim_type: str, statement: str) -> bool:
    text = f"{claim_type} {statement}".lower()
    return any(term in text for term in ("recommend", "recommendation", "valuation", "strategic_fit", "strategic fit", "attractive", "walk away", "proceed"))


def _missing_judgment_dependencies(available_context: set[str]) -> list[str]:
    missing = []
    joined = " ".join(available_context)
    for group, terms in JUDGMENT_DEPENDENCY_GROUPS.items():
        if not any(term in joined for term in terms):
            missing.append(group)
    return missing


def _block(blocked: list[str], use: str, reason: str, reasons: list[str], repair_actions: list[dict[str, str]], target: str) -> None:
    _add(blocked, use)
    reasons.append(reason)
    repair_actions.append({"target": target, "action": "repair_usage_gate", "reason": reason})


def _add(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _dedupe_actions(actions: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    deduped = []
    for action in actions:
        key = (action.get("target"), action.get("action"), action.get("reason"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped


def _ordered_unique(values: list[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        if value in seen or value in {None, ""}:
            continue
        seen.add(value)
        unique.append(value)
    return unique
