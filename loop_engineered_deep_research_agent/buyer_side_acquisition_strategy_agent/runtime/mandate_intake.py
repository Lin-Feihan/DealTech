from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class MandateValidationError(ValueError):
    pass


REQUIRED_MANDATE_FIELDS = (
    "case_id",
    "buyer",
    "target",
    "transaction_context",
    "decision_date",
    "requested_scope",
    "source_pack_reference",
    "constraints",
    "output_requirements",
)


def load_mandate(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            mandate = json.load(handle)
    except json.JSONDecodeError as exc:
        raise MandateValidationError(f"Invalid JSON mandate: {exc}") from exc

    validate_mandate(mandate)
    return mandate


def validate_mandate(mandate: Any) -> None:
    if not isinstance(mandate, dict):
        raise MandateValidationError("Mandate must be a JSON object.")

    missing = [field for field in REQUIRED_MANDATE_FIELDS if field not in mandate]
    if missing:
        raise MandateValidationError(f"Missing required mandate field(s): {', '.join(missing)}")

    _require_non_empty_string(mandate["case_id"], "case_id")
    _validate_named_entity(mandate["buyer"], "buyer")
    _validate_named_entity(mandate["target"], "target")
    _validate_transaction_context(mandate["transaction_context"])
    _validate_decision_date(mandate["decision_date"])
    _validate_string_list(mandate["requested_scope"], "requested_scope")
    _validate_source_pack_reference(mandate["source_pack_reference"])
    _validate_constraints(mandate["constraints"])
    _validate_output_requirements(mandate["output_requirements"])


def _require_non_empty_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise MandateValidationError(f"{field} must be a non-empty string.")


def _validate_named_entity(value: Any, field: str) -> None:
    if not isinstance(value, dict):
        raise MandateValidationError(f"{field} must be an object.")
    _require_non_empty_string(value.get("name"), f"{field}.name")


def _validate_transaction_context(value: Any) -> None:
    if not isinstance(value, dict):
        raise MandateValidationError("transaction_context must be an object.")
    for field in ("transaction_type", "stage", "decision_need"):
        _require_non_empty_string(value.get(field), f"transaction_context.{field}")


def _validate_decision_date(value: Any) -> None:
    _require_non_empty_string(value, "decision_date")
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise MandateValidationError("decision_date must use YYYY-MM-DD format.")


def _validate_string_list(value: Any, field: str) -> None:
    if not isinstance(value, list) or not value:
        raise MandateValidationError(f"{field} must be a non-empty array.")
    for index, item in enumerate(value):
        _require_non_empty_string(item, f"{field}[{index}]")


def _validate_source_pack_reference(value: Any) -> None:
    if not isinstance(value, dict):
        raise MandateValidationError("source_pack_reference must be an object.")
    _require_non_empty_string(value.get("reference_id"), "source_pack_reference.reference_id")
    _require_non_empty_string(value.get("description"), "source_pack_reference.description")


def _validate_constraints(value: Any) -> None:
    if not isinstance(value, dict):
        raise MandateValidationError("constraints must be an object.")
    for field in ("no_web_search", "no_evidence_generation", "no_report_generation"):
        if value.get(field) is not True:
            raise MandateValidationError(f"constraints.{field} must be true for Milestone 1.")


def _validate_output_requirements(value: Any) -> None:
    if not isinstance(value, dict):
        raise MandateValidationError("output_requirements must be an object.")
    artifacts = value.get("expected_artifacts")
    _validate_string_list(artifacts, "output_requirements.expected_artifacts")
    allowed = {"mandate.json", "research_plan.json"}
    unexpected = [artifact for artifact in artifacts if artifact not in allowed]
    if unexpected:
        raise MandateValidationError(f"Unsupported Milestone 1 artifact(s): {', '.join(unexpected)}")
    _require_non_empty_string(value.get("language"), "output_requirements.language")

