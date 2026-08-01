from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.artifact_store import write_json_artifact
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.case_seed_loader import CaseSeedValidationError, load_case_seed
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.deep_research_output_normalizer import (
    DeepResearchNormalizationError,
    normalize_deep_research_output,
)
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.deep_research_provider import (
    DEEP_RESEARCH_MODES,
    DeepResearchProviderError,
    OPENAI_API_KEY_ENV,
    OPENAI_MODEL_ENV,
    OPENAI_TOOL_MODE_ENV,
    build_deep_research_request,
    call_openai_deep_research,
    extract_normalized_response,
    load_replay_response,
    validate_deep_research_response,
)
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.mandate_intake import MandateValidationError, load_mandate
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.research_planning import ResearchPlanValidationError, validate_research_plan
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.source_discovery import SourceDiscoveryPlanValidationError, validate_source_discovery_plan


class M2DeepResearchFailClosed(RuntimeError):
    pass


def run_m2_deep_research_pipeline(
    mandate_path: Path,
    research_plan_path: Path,
    case_seed_path: Path,
    source_discovery_plan_path: Path,
    output_dir: Path,
    mode: str,
    replay_response_path: Path | None = None,
    model: str | None = None,
    tool_mode: str | None = None,
    targeted_source_discovery_plan_path: Path | None = None,
    repair_plan_path: Path | None = None,
) -> dict[str, Path]:
    if mode not in DEEP_RESEARCH_MODES:
        raise M2DeepResearchFailClosed(f"Unsupported Deep Research mode: {mode}")

    mandate = load_mandate(mandate_path)
    research_plan = _load_json_artifact(research_plan_path, validate_research_plan, "research_plan")
    case_seed = load_case_seed(case_seed_path)
    source_discovery_plan = _load_json_artifact(source_discovery_plan_path, validate_source_discovery_plan, "source_discovery_plan")

    if not (
        mandate["case_id"] == research_plan["case_id"] == case_seed["case_id"] == source_discovery_plan["case_id"]
    ):
        raise M2DeepResearchFailClosed("mandate, research_plan, case_seed, and source_discovery_plan case_id values must match.")

    targeted_source_discovery_plan = _load_optional_json(targeted_source_discovery_plan_path)
    repair_plan = _load_optional_json(repair_plan_path)
    try:
        if mode == "live_openai_deep_research":
            model_value = (model or os.getenv(OPENAI_MODEL_ENV, "")).strip() or "model_not_configured"
            request_artifact = build_deep_research_request(
                mandate=mandate,
                research_plan=research_plan,
                case_seed=case_seed,
                source_discovery_plan=source_discovery_plan,
                model=model_value,
                targeted_source_discovery_plan=targeted_source_discovery_plan,
                repair_plan=repair_plan,
            )
            request_path = write_json_artifact(output_dir, "deep_research_request.json", request_artifact)
            raw_response = call_openai_deep_research(
                request_artifact=request_artifact,
                api_key=os.getenv(OPENAI_API_KEY_ENV),
                model=model,
                tool_mode=tool_mode or os.getenv(OPENAI_TOOL_MODE_ENV),
            )
            raw_response_path = write_json_artifact(output_dir, "deep_research_response.raw.json", raw_response)
            normalized_response = extract_normalized_response(raw_response, expected_case_id=mandate["case_id"])
            retrieved_by = f"openai_deep_research_provider:{mode}"
        else:
            if replay_response_path is None:
                raise M2DeepResearchFailClosed("replay_deep_research_response mode requires --replay-response.")
            raw_response = load_replay_response(replay_response_path)
            validate_deep_research_response(raw_response)
            if raw_response["case_id"] != mandate["case_id"]:
                raise M2DeepResearchFailClosed("Deep Research response case_id must match request case_id.")
            normalized_response = raw_response
            request_path = None
            raw_response_path = None
            retrieved_by = "external_deep_research_package:replay_deep_research_response"

        retrieved_sources_manifest, raw_evidence = normalize_deep_research_output(
            deep_research_response=normalized_response,
            source_discovery_plan=source_discovery_plan,
            decision_date_text=mandate["decision_date"],
            retrieved_by=retrieved_by,
        )
        manifest_path = write_json_artifact(output_dir, "retrieved_sources_manifest.json", retrieved_sources_manifest)
        raw_evidence_path = write_json_artifact(output_dir, "raw_evidence.json", raw_evidence)
    except (DeepResearchProviderError, DeepResearchNormalizationError) as exc:
        raise M2DeepResearchFailClosed(str(exc)) from exc

    artifacts = {
        "retrieved_sources_manifest": manifest_path,
        "raw_evidence": raw_evidence_path,
    }
    if request_path is not None:
        artifacts["deep_research_request"] = request_path
    if raw_response_path is not None:
        artifacts["deep_research_response_raw"] = raw_response_path
    return artifacts


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Buyer-Side Acquisition Strategy Agent M2 Deep Research provider integration.")
    parser.add_argument("--mandate", required=True, type=Path)
    parser.add_argument("--research-plan", required=True, type=Path)
    parser.add_argument("--case-seed", required=True, type=Path)
    parser.add_argument("--source-discovery-plan", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=sorted(DEEP_RESEARCH_MODES))
    parser.add_argument("--replay-response", type=Path)
    parser.add_argument("--model", type=str)
    parser.add_argument("--tool-mode", type=str)
    parser.add_argument("--targeted-source-discovery-plan", type=Path)
    parser.add_argument("--repair-plan", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        artifacts = run_m2_deep_research_pipeline(
            mandate_path=args.mandate,
            research_plan_path=args.research_plan,
            case_seed_path=args.case_seed,
            source_discovery_plan_path=args.source_discovery_plan,
            output_dir=args.output_dir,
            mode=args.mode,
            replay_response_path=args.replay_response,
            model=args.model,
            tool_mode=args.tool_mode,
            targeted_source_discovery_plan_path=args.targeted_source_discovery_plan,
            repair_plan_path=args.repair_plan,
        )
    except (
        M2DeepResearchFailClosed,
        MandateValidationError,
        ResearchPlanValidationError,
        CaseSeedValidationError,
        SourceDiscoveryPlanValidationError,
    ) as exc:
        print(f"Buyer-Side Acquisition Strategy Agent M2 Deep Research failed closed: {exc}", file=sys.stderr)
        return 2

    print("Buyer-Side Acquisition Strategy Agent M2 Deep Research completed.")
    for name, path in artifacts.items():
        print(f"{name}: {path}")
    return 0


def _load_json_artifact(path: Path, validator: Any, name: str) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise M2DeepResearchFailClosed(f"{name} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise M2DeepResearchFailClosed(f"{name} is invalid JSON: {exc}") from exc
    validator(payload)
    return payload


def _load_optional_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise M2DeepResearchFailClosed(f"Optional input not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise M2DeepResearchFailClosed(f"Optional input is invalid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise M2DeepResearchFailClosed(f"Optional input must be a JSON object: {path}")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
