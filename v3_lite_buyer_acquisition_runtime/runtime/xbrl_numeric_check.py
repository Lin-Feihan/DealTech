from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Callable


XBRL_REQUIRED_FIELDS = ("cik", "taxonomy_tag", "period", "unit", "expected_value")
XBRL_STATUSES = {"verified", "mismatch", "not_found", "provider_unavailable", "not_applicable"}


class XbrlNumericCheckError(ValueError):
    pass


XbrlProvider = Callable[[str, str, str, str], dict[str, Any]]


def run_xbrl_numeric_check(evidence_repository: dict[str, Any], provider: XbrlProvider | None = None) -> list[dict[str, Any]]:
    _validate_repository_shape(evidence_repository)
    effective_provider = provider or _provider_unavailable
    results = []
    for record in evidence_repository["evidence_records"]:
        metadata = _xbrl_metadata_from(record)
        if metadata is None:
            results.append(_not_applicable_result(record))
            continue
        results.append(_check_xbrl_metadata(record, metadata, effective_provider))
    return results


def xbrl_results_by_record_id(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        grouped.setdefault(result["evidence_record_id"], []).append(result)
    return grouped


def _validate_repository_shape(evidence_repository: dict[str, Any]) -> None:
    if evidence_repository.get("generated_artifact") != "evidence_repository.json":
        raise XbrlNumericCheckError("XBRL Numeric Check requires evidence_repository.json.")
    if not isinstance(evidence_repository.get("evidence_records"), list):
        raise XbrlNumericCheckError("XBRL Numeric Check requires evidence_records array.")


def _check_xbrl_metadata(record: dict[str, Any], metadata: dict[str, Any], provider: XbrlProvider) -> dict[str, Any]:
    provider_result = provider(metadata["cik"], metadata["taxonomy_tag"], metadata["period"], metadata["unit"])
    status = str(provider_result.get("status") or "")
    if status == "not_found":
        reason = "XBRL fact was not found for explicit CIK, taxonomy tag, period, and unit."
        return _result(record, metadata, None, "not_found", [reason], [_repair_action("M2_source_retrieval", "repair_xbrl_source_metadata_or_source", reason)])
    if status == "provider_unavailable":
        reason = "XBRL provider unavailable; numeric claim cannot be treated as verified."
        return _result(
            record,
            metadata,
            None,
            "provider_unavailable",
            [reason],
            [_repair_action("block_pipeline_until_structure_repaired", "retry_or_document_xbrl_provider_unavailable", reason)],
        )

    observed_value = provider_result.get("observed_value")
    observed_decimal = _canonical_decimal(observed_value)
    if observed_decimal is None:
        reason = "XBRL provider returned no canonical numeric observed_value."
        return _result(
            record,
            metadata,
            observed_value,
            "provider_unavailable",
            [reason],
            [_repair_action("block_pipeline_until_structure_repaired", "retry_or_document_xbrl_provider_unavailable", reason)],
        )
    expected_decimal = metadata["expected_decimal"]
    if observed_decimal == expected_decimal:
        return _result(record, metadata, observed_value, "verified", [], [])
    reason = "XBRL observed value does not match expected canonical value."
    return _result(record, metadata, observed_value, "mismatch", [reason], [_repair_action("M5_numeric_verification", "repair_xbrl_numeric_value", reason)])


def _xbrl_metadata_from(record: dict[str, Any]) -> dict[str, Any] | None:
    nested = record.get("structured_attributes", {})
    nested_xbrl = nested.get("xbrl", {}) if isinstance(nested, dict) else {}
    if not isinstance(nested_xbrl, dict):
        nested_xbrl = {}
    raw = {field: record.get(field, nested_xbrl.get(field)) for field in XBRL_REQUIRED_FIELDS}
    if any(_is_missing(raw[field]) for field in XBRL_REQUIRED_FIELDS):
        return None
    expected_decimal = _canonical_decimal(raw["expected_value"])
    if expected_decimal is None:
        return None
    return {
        "cik": str(raw["cik"]).strip(),
        "taxonomy_tag": str(raw["taxonomy_tag"]).strip(),
        "period": str(raw["period"]).strip(),
        "unit": str(raw["unit"]).strip(),
        "expected_value": raw["expected_value"],
        "expected_decimal": expected_decimal,
    }


def _canonical_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned or any(char in cleaned for char in "$,%"):
            return None
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None
    return None


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _provider_unavailable(cik: str, taxonomy_tag: str, period: str, unit: str) -> dict[str, Any]:
    return {"status": "provider_unavailable"}


def _not_applicable_result(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_record_id": record["evidence_record_id"],
        "cik": "",
        "taxonomy_tag": "",
        "period": "",
        "unit": "",
        "expected_value": None,
        "observed_value": None,
        "xbrl_check_status": "not_applicable",
        "blocking_reasons": [],
        "repair_actions": [],
    }


def _result(
    record: dict[str, Any],
    metadata: dict[str, Any],
    observed_value: Any,
    status: str,
    blocking_reasons: list[str],
    repair_actions: list[dict[str, str]],
) -> dict[str, Any]:
    if status not in XBRL_STATUSES:
        raise XbrlNumericCheckError(f"Invalid XBRL check status: {status}")
    return {
        "evidence_record_id": record["evidence_record_id"],
        "cik": metadata["cik"],
        "taxonomy_tag": metadata["taxonomy_tag"],
        "period": metadata["period"],
        "unit": metadata["unit"],
        "expected_value": metadata["expected_value"],
        "observed_value": observed_value,
        "xbrl_check_status": status,
        "blocking_reasons": _ordered_unique(blocking_reasons),
        "repair_actions": _dedupe_actions(repair_actions),
    }


def _repair_action(target: str, action: str, reason: str) -> dict[str, str]:
    return {"target": target, "action": action, "reason": reason}


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
