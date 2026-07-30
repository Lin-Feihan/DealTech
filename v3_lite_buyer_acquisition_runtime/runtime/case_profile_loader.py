from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CaseProfileError(ValueError):
    pass


PROFILE_ROOT = Path(__file__).resolve().parents[1] / "case_profiles"

REQUIRED_TOP_LEVEL_FIELDS = (
    "generated_artifact",
    "profile_type",
    "case_id",
    "profile_id",
    "description",
    "planning_profile",
    "source_discovery_profile",
)
REQUIRED_PLANNING_FIELDS = (
    "key_questions",
    "workstreams",
    "evidence_requirements",
    "verification_targets",
    "open_questions",
)
REQUIRED_SOURCE_DISCOVERY_FIELDS = (
    "source_needs",
    "search_queries",
    "retrieval_targets",
    "source_priority_rules",
    "forbidden_source_uses",
)


def load_case_profile_for_case_id(case_id: str) -> dict[str, Any] | None:
    profile_path = PROFILE_ROOT / f"{case_id}.json"
    if not profile_path.exists():
        return None
    return load_case_profile(profile_path, expected_case_id=case_id)


def load_case_profile(path: Path, expected_case_id: str | None = None) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            profile = json.load(handle)
    except json.JSONDecodeError as exc:
        raise CaseProfileError(f"Invalid JSON case profile: {exc}") from exc

    validate_case_profile(profile, expected_case_id=expected_case_id)
    return profile


def validate_case_profile(profile: Any, expected_case_id: str | None = None) -> None:
    if not isinstance(profile, dict):
        raise CaseProfileError("case_profile must be a JSON object.")

    missing = [field for field in REQUIRED_TOP_LEVEL_FIELDS if field not in profile]
    if missing:
        raise CaseProfileError(f"Missing case_profile field(s): {', '.join(missing)}")
    if profile["generated_artifact"] != "case_profile.json":
        raise CaseProfileError("generated_artifact must be case_profile.json.")
    if profile["profile_type"] != "buyer_acquisition_case_profile":
        raise CaseProfileError("profile_type must be buyer_acquisition_case_profile.")
    _require_non_empty_string(profile["case_id"], "case_id")
    _require_non_empty_string(profile["profile_id"], "profile_id")
    _require_non_empty_string(profile["description"], "description")
    if expected_case_id is not None and profile["case_id"] != expected_case_id:
        raise CaseProfileError("case_profile case_id does not match requested case_id.")

    _validate_section(profile["planning_profile"], "planning_profile", REQUIRED_PLANNING_FIELDS)
    _validate_section(
        profile["source_discovery_profile"],
        "source_discovery_profile",
        REQUIRED_SOURCE_DISCOVERY_FIELDS,
    )


def _validate_section(section: Any, section_name: str, required_fields: tuple[str, ...]) -> None:
    if not isinstance(section, dict):
        raise CaseProfileError(f"{section_name} must be an object.")
    missing = [field for field in required_fields if field not in section]
    if missing:
        raise CaseProfileError(f"Missing {section_name} field(s): {', '.join(missing)}")
    for field in required_fields:
        value = section[field]
        if not isinstance(value, list) or not value:
            raise CaseProfileError(f"{section_name}.{field} must be a non-empty array.")


def _require_non_empty_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CaseProfileError(f"{field} must be a non-empty string.")
