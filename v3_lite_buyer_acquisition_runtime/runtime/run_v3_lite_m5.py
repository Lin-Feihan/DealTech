from __future__ import annotations

import argparse
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from v3_lite_buyer_acquisition_runtime.runtime.artifact_store import write_json_artifact
from v3_lite_buyer_acquisition_runtime.runtime.claim_certifier import (
    CertificationError,
    build_certification_result,
    load_json_artifact,
)
from v3_lite_buyer_acquisition_runtime.runtime.repair_plan_builder import build_repair_plan, build_research_gaps


class M5FailClosed(RuntimeError):
    pass


def run_m5_pipeline(claim_evidence_graph_path: Path, evidence_repository_path: Path, output_dir: Path) -> dict[str, Path]:
    try:
        claim_evidence_graph = load_json_artifact(claim_evidence_graph_path)
        evidence_repository = load_json_artifact(evidence_repository_path)
        certification_result = build_certification_result(claim_evidence_graph, evidence_repository)
        research_gaps = build_research_gaps(certification_result, claim_evidence_graph)
        repair_plan = build_repair_plan(certification_result, research_gaps)
        certification_result_path = write_json_artifact(output_dir, "certification_result.json", certification_result)
        research_gaps_path = write_json_artifact(output_dir, "research_gaps.json", research_gaps)
        repair_plan_path = write_json_artifact(output_dir, "repair_plan.json", repair_plan)
    except (CertificationError, ValueError) as exc:
        raise M5FailClosed(f"M5 failed closed: {exc}") from exc

    return {
        "certification_result": certification_result_path,
        "research_gaps": research_gaps_path,
        "repair_plan": repair_plan_path,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run V3-Lite M5 loop certification and repair planning.")
    parser.add_argument("--claim-evidence-graph", required=True, type=Path)
    parser.add_argument("--evidence-repository", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        artifacts = run_m5_pipeline(
            claim_evidence_graph_path=args.claim_evidence_graph,
            evidence_repository_path=args.evidence_repository,
            output_dir=args.output_dir,
        )
    except M5FailClosed as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print("V3-Lite M5 completed.")
    for name, path in artifacts.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
