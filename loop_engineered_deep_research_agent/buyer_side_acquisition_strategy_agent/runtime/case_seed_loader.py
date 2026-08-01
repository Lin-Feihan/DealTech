from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CaseSeedValidationError(ValueError):
    pass


REQUIRED_CASE_SEED_FIELDS = (
    "case_id",
    "seed_id",
    "seed_type",
    "source_description",
    "case_parties",
    "transaction_leads",
    "key_assets_or_topics",
    "known_dates",
    "known_amounts",
    "source_leads",
    "uncertainty_warnings",
)


def load_case_seed(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            case_seed = json.load(handle)
    except json.JSONDecodeError as exc:
        raise CaseSeedValidationError(f"Invalid JSON case seed: {exc}") from exc

    validate_case_seed(case_seed)
    return case_seed


def validate_case_seed(case_seed: Any) -> None:
    if not isinstance(case_seed, dict):
        raise CaseSeedValidationError("case_seed must be a JSON object.")
    missing = [field for field in REQUIRED_CASE_SEED_FIELDS if field not in case_seed]
    if missing:
        raise CaseSeedValidationError(f"Missing case_seed field(s): {', '.join(missing)}")

    for field in ("case_id", "seed_id", "seed_type", "source_description"):
        _require_non_empty_string(case_seed[field], field)

    parties = case_seed["case_parties"]
    if not isinstance(parties, dict):
        raise CaseSeedValidationError("case_parties must be an object.")
    _require_non_empty_string_list(parties.get("buyer_or_acquiring_vehicle"), "case_parties.buyer_or_acquiring_vehicle")
    _require_non_empty_string_list(parties.get("target"), "case_parties.target")
    if "people" in parties:
        _require_string_list(parties["people"], "case_parties.people")

    for field in (
        "transaction_leads",
        "key_assets_or_topics",
        "known_dates",
        "known_amounts",
        "source_leads",
        "uncertainty_warnings",
    ):
        _require_non_empty_string_list(case_seed[field], field)


def _require_non_empty_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CaseSeedValidationError(f"{field} must be a non-empty string.")


def _require_string_list(value: Any, field: str) -> None:
    if not isinstance(value, list):
        raise CaseSeedValidationError(f"{field} must be an array.")
    for index, item in enumerate(value):
        _require_non_empty_string(item, f"{field}[{index}]")


def _require_non_empty_string_list(value: Any, field: str) -> None:
    _require_string_list(value, field)
    if not value:
        raise CaseSeedValidationError(f"{field} must be non-empty.")

