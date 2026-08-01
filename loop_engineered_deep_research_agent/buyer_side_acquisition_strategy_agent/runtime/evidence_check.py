from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


class EvidenceCheckError(ValueError):
    pass


RECOGNIZED_SOURCE_TIERS = {"Tier 1", "Tier 2", "Tier 3", "Tier 4"}
STRONG_SOURCE_TIERS = {"Tier 1", "Tier 2"}
NUMERIC_OR_TRANSACTION_FACT_TYPES = {
    "transaction_consideration",
    "contingent_consideration",
    "milestone_payment",
    "financing_or_payment_mechanics",
    "financial_performance",
    "valuation_input",
    "derived_numeric_candidate",
}
POST_DECISION_RELATIONS = {"post_decision", "retrospective"}


def run_evidence_check(evidence_repository: dict[str, Any]) -> list[dict[str, Any]]:
    _validate_repository_shape(evidence_repository)
    return [_check_evidence_record(index, record) for index, record in enumerate(evidence_repository["evidence_records"], start=1)]


def evidence_results_by_record_id(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {result["evidence_record_id"]: result for result in results}


def _validate_repository_shape(evidence_repository: dict[str, Any]) -> None:
    if evidence_repository.get("generated_artifact") != "evidence_repository.json":
        raise EvidenceCheckError("Evidence Check requires evidence_repository.json.")
    if evidence_repository.get("source_bounded") is not True:
        raise EvidenceCheckError("Evidence Check requires source_bounded evidence_repository.")
    if not isinstance(evidence_repository.get("evidence_records"), list):
        raise EvidenceCheckError("Evidence Check requires evidence_records array.")


def _check_evidence_record(index: int, record: dict[str, Any]) -> dict[str, Any]:
    evidence_record_id = record.get("evidence_record_id")
    if not evidence_record_id:
        raise EvidenceCheckError("evidence_record_id is required for every evidence record.")

    failures: list[str] = []
    caveats: list[str] = []
    repair_actions: list[dict[str, Any]] = []

    provenance_status = _provenance_status(record, failures, repair_actions)
    source_authority_status = _source_authority_status(record, caveats, repair_actions)
    numeric_check = _numeric_status(record, failures, caveats, repair_actions)
    temporal_status = _temporal_status(record, failures, caveats, repair_actions)
    gap_status = _gap_status(record, failures, repair_actions)

    if failures:
        check_status = "failed"
    elif repair_actions:
        check_status = "repair_required"
    elif caveats:
        check_status = "passed_with_caveat"
    else:
        check_status = "passed"

    return {
        "evidence_check_id": f"EC-{index:03d}",
        "evidence_record_id": evidence_record_id,
        "canonical_fact_key": record.get("canonical_fact_key", ""),
        "canonical_fact_type": record.get("canonical_fact_type", "generic_fact"),
        "check_status": check_status,
        "provenance_check_status": provenance_status,
        "source_authority_check_status": source_authority_status,
        "numeric_check_status": numeric_check["status"],
        "source_time_check_status": temporal_status,
        "evidence_gap_check_status": gap_status,
        "source_ids": list(record.get("source_ids") or []),
        "source_tiers": list(record.get("source_tiers") or []),
        "raw_evidence_ids": list(record.get("raw_evidence_ids") or []),
        "permitted_use": record.get("permitted_use", ""),
        "evidence_time_relation_to_decision_date": record.get("evidence_time_relation_to_decision_date", ""),
        "computed_numeric_result": numeric_check.get("computed_result"),
        "required_caveats": _ordered_unique(caveats),
        "blocking_reasons": _ordered_unique(failures),
        "repair_actions": _dedupe_actions(repair_actions),
    }


def _provenance_status(record: dict[str, Any], failures: list[str], repair_actions: list[dict[str, Any]]) -> str:
    missing = []
    for field in ("source_ids", "source_tiers", "raw_evidence_ids"):
        if not record.get(field):
            missing.append(field)
    for field in ("canonical_fact_key", "canonical_fact_type"):
        if not record.get(field):
            missing.append(field)
    if missing:
        reason = f"Missing evidence provenance field(s): {', '.join(missing)}."
        failures.append(reason)
        repair_actions.append(_repair_action("M2_source_retrieval", "repair_evidence_provenance", reason))
        return "failed"
    return "passed"


def _source_authority_status(record: dict[str, Any], caveats: list[str], repair_actions: list[dict[str, Any]]) -> str:
    tiers = set(record.get("source_tiers") or [])
    unknown = sorted(tier for tier in tiers if tier not in RECOGNIZED_SOURCE_TIERS)
    if unknown:
        reason = f"Unrecognized source tier label(s): {', '.join(unknown)}."
        repair_actions.append(_repair_action("M2_source_retrieval", "repair_source_authority_label", reason))
        return "repair_required"

    fact_type = str(record.get("canonical_fact_type") or "generic_fact")
    if fact_type in NUMERIC_OR_TRANSACTION_FACT_TYPES and not tiers.intersection(STRONG_SOURCE_TIERS):
        reason = f"{fact_type} requires Tier 1 or Tier 2 support; current source tier is weaker."
        caveats.append(reason)
        repair_actions.append(_repair_action("M2_source_retrieval", "retrieve_stronger_authoritative_source", reason))
        return "repair_required"
    return "passed"


def _numeric_status(
    record: dict[str, Any],
    failures: list[str],
    caveats: list[str],
    repair_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    formula = _formula_from(record)
    if formula is None:
        return {"status": "not_applicable"}
    result = replay_numeric_formula(formula, [record])
    if result["verification_status"] == "failed":
        failures.append(result["caveat"])
        repair_actions.append(_repair_action("M5_numeric_verification", "repair_numeric_formula_or_inputs", result["caveat"]))
    else:
        caveats.append("Numeric formula was replayed deterministically; this verifies arithmetic only, not valuation quality or recommendation use.")
    return {"status": result["verification_status"], "computed_result": result.get("computed_result")}


def _temporal_status(record: dict[str, Any], failures: list[str], caveats: list[str], repair_actions: list[dict[str, Any]]) -> str:
    relation = record.get("evidence_time_relation_to_decision_date")
    permitted_use = record.get("permitted_use")
    if not relation:
        reason = "evidence_time_relation_to_decision_date is required."
        failures.append(reason)
        repair_actions.append(_repair_action("M2_source_retrieval", "repair_evidence_temporal_metadata", reason))
        return "failed"
    if not permitted_use:
        reason = "permitted_use is required."
        failures.append(reason)
        repair_actions.append(_repair_action("M2_source_retrieval", "repair_evidence_use_metadata", reason))
        return "failed"
    if relation in POST_DECISION_RELATIONS and permitted_use == "ex_ante_deal_evaluation":
        reason = "post_decision or retrospective evidence cannot be used as ex_ante_deal_evaluation."
        failures.append(reason)
        repair_actions.append(_repair_action("M4_claim_evidence_graph", "correct_temporal_use", reason))
        return "failed"
    if relation in POST_DECISION_RELATIONS and not record.get("hindsight_leakage_warning"):
        reason = "Missing hindsight warning for post_decision or retrospective evidence."
        caveats.append(reason)
        repair_actions.append(_repair_action("M4_claim_evidence_graph", "add_hindsight_warning", reason))
        return "repair_required"
    if relation in POST_DECISION_RELATIONS:
        caveats.append("Evidence is post_decision or retrospective and can be used only with hindsight caveats.")
        return "passed_with_caveat"
    return "passed"


def _gap_status(record: dict[str, Any], failures: list[str], repair_actions: list[dict[str, Any]]) -> str:
    if record.get("support_status") != "source_gap":
        return "not_applicable"
    reason = "source_gap evidence is a repair target and cannot support report assertions."
    failures.append(reason)
    repair_actions.append(_repair_action("M2_source_retrieval", "repair_source_gap", reason))
    return "failed"


def replay_numeric_formula(formula: Any, records: list[dict[str, Any]]) -> dict[str, Any]:
    parsed = _normalize_formula(formula)
    if parsed is None:
        return {"verification_status": "failed", "computed_result": None, "caveat": "numeric_formula metadata is invalid or missing."}
    values = _numeric_inputs(parsed, records)
    if parsed["operation"] == "sum":
        if not values:
            return {"verification_status": "failed", "computed_result": None, "caveat": "sum numeric_formula has no numeric inputs."}
        computed = sum(values, Decimal("0"))
    else:
        return {"verification_status": "failed", "computed_result": None, "caveat": f"unsupported numeric_formula operation: {parsed['operation']}"}
    expected = _to_decimal(parsed.get("expected_result"))
    status = "passed_with_caveat" if expected is None or computed == expected else "failed"
    caveat = "sum numeric_formula replayed from explicit metadata."
    if expected is None:
        caveat = "sum numeric_formula replayed, but no expected_result was provided."
    if expected is not None and computed != expected:
        caveat = "sum numeric_formula computed_result does not match expected_result."
    return {"verification_status": status, "computed_result": _format_decimal(computed), "caveat": caveat}


def _formula_from(record: dict[str, Any]) -> Any:
    attributes = record.get("structured_attributes") or {}
    return record.get("numeric_formula") or attributes.get("numeric_formula") or attributes.get("calculation_formula") or attributes.get("formula")


def _normalize_formula(formula: Any) -> dict[str, Any] | None:
    if not isinstance(formula, dict):
        return None
    operation = str(formula.get("operation") or formula.get("formula_type") or "").lower()
    if not operation and str(formula.get("expression") or "").strip().lower() == "sum":
        operation = "sum"
    if operation != "sum":
        return None
    return dict(formula, operation="sum")


def _numeric_inputs(formula: dict[str, Any], records: list[dict[str, Any]]) -> list[Decimal]:
    values = []
    explicit_inputs = formula.get("inputs") or formula.get("operands") or formula.get("values")
    if isinstance(explicit_inputs, list):
        for value in explicit_inputs:
            if isinstance(value, dict):
                number = _to_decimal(value.get("amount") or value.get("value"))
            else:
                number = _to_decimal(value)
            if number is not None:
                values.append(number)
    if values:
        return values
    for record in records:
        attributes = record.get("structured_attributes") or {}
        for amount in attributes.get("amounts", []):
            number = _parse_amount(amount)
            if number is not None:
                values.append(number)
    return values


def _parse_amount(value: Any) -> Decimal | None:
    if isinstance(value, (int, float, Decimal)):
        return _to_decimal(value)
    if not isinstance(value, str):
        return None
    text = value.replace(",", "").replace("$", "").strip().lower()
    if not text:
        return None
    parts = text.split()
    number = _to_decimal(parts[0])
    if number is None:
        return None
    multiplier = Decimal("1")
    if len(parts) > 1:
        unit = parts[1]
        if unit.startswith("thousand"):
            multiplier = Decimal("1000")
        elif unit.startswith("million") or unit in {"m", "mm"}:
            multiplier = Decimal("1000000")
        elif unit.startswith("billion") or unit == "bn":
            multiplier = Decimal("1000000000")
    return number * multiplier


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(",", "").replace("$", ""))
    except (InvalidOperation, ValueError):
        return None


def _format_decimal(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _repair_action(target: str, action: str, reason: str) -> dict[str, str]:
    return {"target": target, "action": action, "reason": reason}


def _dedupe_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
