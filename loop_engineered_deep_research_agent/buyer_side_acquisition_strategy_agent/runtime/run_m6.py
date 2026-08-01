from __future__ import annotations

import argparse
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.artifact_store import write_json_artifact
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.deal_analysis_builder import (
    DealAnalysisError,
    build_analysis_package,
    load_json_artifact,
)


class M6FailClosed(RuntimeError):
    pass


def run_m6_pipeline(
    certification_result_path: Path,
    claim_evidence_graph_path: Path,
    evidence_repository_path: Path,
    research_gaps_path: Path,
    repair_plan_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    try:
        certification_result = load_json_artifact(certification_result_path)
        claim_evidence_graph = load_json_artifact(claim_evidence_graph_path)
        evidence_repository = load_json_artifact(evidence_repository_path)
        research_gaps = load_json_artifact(research_gaps_path)
        repair_plan = load_json_artifact(repair_plan_path)
        analysis_package = build_analysis_package(
            certification_result=certification_result,
            claim_evidence_graph=claim_evidence_graph,
            evidence_repository=evidence_repository,
            research_gaps=research_gaps,
            repair_plan=repair_plan,
        )
        analysis_package_path = write_json_artifact(output_dir, "analysis_package.json", analysis_package)
    except DealAnalysisError as exc:
        raise M6FailClosed(f"M6 failed closed: {exc}") from exc

    return {"analysis_package": analysis_package_path}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Buyer-Side Acquisition Strategy Agent M6 evidence-bounded deal analysis package generation.")
    parser.add_argument("--certification-result", required=True, type=Path)
    parser.add_argument("--claim-evidence-graph", required=True, type=Path)
    parser.add_argument("--evidence-repository", required=True, type=Path)
    parser.add_argument("--research-gaps", required=True, type=Path)
    parser.add_argument("--repair-plan", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        artifacts = run_m6_pipeline(
            certification_result_path=args.certification_result,
            claim_evidence_graph_path=args.claim_evidence_graph,
            evidence_repository_path=args.evidence_repository,
            research_gaps_path=args.research_gaps,
            repair_plan_path=args.repair_plan,
            output_dir=args.output_dir,
        )
    except M6FailClosed as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print("Buyer-Side Acquisition Strategy Agent M6 completed.")
    for name, path in artifacts.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
