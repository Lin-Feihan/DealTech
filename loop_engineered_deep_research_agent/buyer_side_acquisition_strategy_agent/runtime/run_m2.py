from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.artifact_store import write_json_artifact
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.case_seed_loader import CaseSeedValidationError, load_case_seed
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.mandate_intake import MandateValidationError, load_mandate
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.raw_evidence_extraction import RawEvidenceExtractionError, extract_raw_evidence
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.research_planning import ResearchPlanValidationError, validate_research_plan
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.source_discovery import SourceDiscoveryPlanValidationError, build_source_discovery_plan
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.source_retrieval import RETRIEVAL_MODES, SourceRetrievalError, retrieve_sources_with_provider


class M2FailClosed(RuntimeError):
    pass


def run_m2_pipeline(
    mandate_path: Path,
    research_plan_path: Path,
    case_seed_path: Path,
    output_dir: Path,
    retrieval_mode: str,
    retrieved_sources_manifest_path: Path | None = None,
) -> dict[str, Path]:
    mandate = load_mandate(mandate_path)
    research_plan = _load_research_plan(research_plan_path)
    case_seed = load_case_seed(case_seed_path)
    if not (mandate["case_id"] == research_plan["case_id"] == case_seed["case_id"]):
        raise M2FailClosed("mandate, research_plan, and case_seed case_id values must match.")

    source_discovery_plan = build_source_discovery_plan(case_seed, research_plan)
    discovery_path = write_json_artifact(output_dir, "source_discovery_plan.json", source_discovery_plan)

    try:
        retrieved_manifest = retrieve_sources_with_provider(
            retrieval_mode=retrieval_mode,
            source_discovery_plan=source_discovery_plan,
            output_dir=output_dir,
            retrieved_sources_manifest_path=retrieved_sources_manifest_path,
        )
        manifest_path = write_json_artifact(output_dir, "retrieved_sources_manifest.json", retrieved_manifest)
        raw_evidence = extract_raw_evidence(source_discovery_plan, retrieved_manifest, manifest_path=manifest_path)
        raw_evidence_path = write_json_artifact(output_dir, "raw_evidence.json", raw_evidence)
    except SourceRetrievalError as exc:
        raise M2FailClosed(f"M2 failed closed after source_discovery_plan.json: {exc}") from exc

    return {
        "source_discovery_plan": discovery_path,
        "retrieved_sources_manifest": manifest_path,
        "raw_evidence": raw_evidence_path,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Buyer-Side Acquisition Strategy Agent M2 source discovery and raw evidence extraction.")
    parser.add_argument("--mandate", required=True, type=Path)
    parser.add_argument("--research-plan", required=True, type=Path)
    parser.add_argument("--case-seed", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--retrieval-mode", required=True, choices=sorted(RETRIEVAL_MODES))
    parser.add_argument("--retrieved-sources-manifest", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        artifacts = run_m2_pipeline(
            mandate_path=args.mandate,
            research_plan_path=args.research_plan,
            case_seed_path=args.case_seed,
            output_dir=args.output_dir,
            retrieval_mode=args.retrieval_mode,
            retrieved_sources_manifest_path=args.retrieved_sources_manifest,
        )
    except (
        M2FailClosed,
        MandateValidationError,
        ResearchPlanValidationError,
        CaseSeedValidationError,
        SourceDiscoveryPlanValidationError,
        RawEvidenceExtractionError,
    ) as exc:
        print(f"Buyer-Side Acquisition Strategy Agent M2 failed closed: {exc}", file=sys.stderr)
        return 2

    print("Buyer-Side Acquisition Strategy Agent M2 completed.")
    for name, path in artifacts.items():
        print(f"{name}: {path}")
    return 0


def _load_research_plan(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        research_plan = json.load(handle)
    validate_research_plan(research_plan)
    return research_plan


if __name__ == "__main__":
    raise SystemExit(main())
