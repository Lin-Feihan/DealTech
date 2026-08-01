from __future__ import annotations

from pathlib import Path
from typing import Any

from v3_lite_buyer_acquisition_runtime.runtime.artifact_store import write_json_artifact
from v3_lite_buyer_acquisition_runtime.runtime.deep_research_provider import build_deep_research_request


DEFAULT_EXTERNAL_RESEARCH_MODEL = "openclaw_external_research"


def write_research_request(
    *,
    mandate: dict[str, Any],
    research_plan: dict[str, Any],
    case_seed: dict[str, Any],
    source_discovery_plan: dict[str, Any],
    output_dir: Path,
    targeted_source_discovery_plan: dict[str, Any] | None = None,
    repair_plan: dict[str, Any] | None = None,
) -> Path:
    request = _external_research_request(
        mandate=mandate,
        research_plan=research_plan,
        case_seed=case_seed,
        source_discovery_plan=source_discovery_plan,
        targeted_source_discovery_plan=targeted_source_discovery_plan,
        repair_plan=repair_plan,
    )
    return write_json_artifact(output_dir, "research_request.json", request)


def write_repair_request(
    *,
    mandate: dict[str, Any],
    research_plan: dict[str, Any],
    case_seed: dict[str, Any],
    source_discovery_plan: dict[str, Any],
    targeted_source_discovery_plan: dict[str, Any],
    repair_plan: dict[str, Any],
    output_dir: Path,
    iteration: int,
) -> Path:
    request = _external_research_request(
        mandate=mandate,
        research_plan=research_plan,
        case_seed=case_seed,
        source_discovery_plan=source_discovery_plan,
        targeted_source_discovery_plan=targeted_source_discovery_plan,
        repair_plan=repair_plan,
    )
    request["generated_artifact"] = "repair_request.json"
    request["stage"] = "M5_repair_external_research_request"
    request["repair_iteration"] = iteration
    request["targeted_source_needs"] = targeted_source_discovery_plan.get("targeted_source_needs", [])
    request["targeted_search_queries"] = targeted_source_discovery_plan.get("targeted_search_queries", [])
    request["repair_steps"] = repair_plan.get("repair_steps", [])
    return write_json_artifact(output_dir, "repair_request.json", request)


def _external_research_request(
    *,
    mandate: dict[str, Any],
    research_plan: dict[str, Any],
    case_seed: dict[str, Any],
    source_discovery_plan: dict[str, Any],
    targeted_source_discovery_plan: dict[str, Any] | None,
    repair_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    request = build_deep_research_request(
        mandate=mandate,
        research_plan=research_plan,
        case_seed=case_seed,
        source_discovery_plan=source_discovery_plan,
        targeted_source_discovery_plan=targeted_source_discovery_plan,
        repair_plan=repair_plan,
        model=DEFAULT_EXTERNAL_RESEARCH_MODEL,
    )
    request["generated_artifact"] = "research_request.json"
    request["provider"] = "openclaw_external_research"
    request["handoff_contract"] = {
        "agent_writes": "research_request.json",
        "external_executor_writes": "deep_research_response.json",
        "resume_command": "python run_agent.py resume --run-dir <run_dir> --research-response <deep_research_response.json>",
        "agent_does_not_control_openclaw_remotely": True,
    }
    return request
