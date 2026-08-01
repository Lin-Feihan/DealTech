from __future__ import annotations

import argparse
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.artifact_store import write_json_artifact
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.claim_evidence_graph_builder import (
    ClaimEvidenceGraphError,
    build_claim_evidence_graph,
    load_json_artifact,
)


class M4FailClosed(RuntimeError):
    pass


def run_m4_pipeline(evidence_repository_path: Path, output_dir: Path) -> dict[str, Path]:
    try:
        evidence_repository = load_json_artifact(evidence_repository_path)
        claim_evidence_graph = build_claim_evidence_graph(evidence_repository)
        claim_evidence_graph_path = write_json_artifact(output_dir, "claim_evidence_graph.json", claim_evidence_graph)
    except ClaimEvidenceGraphError as exc:
        raise M4FailClosed(f"M4 failed closed: {exc}") from exc

    return {"claim_evidence_graph": claim_evidence_graph_path}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Buyer-Side Acquisition Strategy Agent M4 claim-evidence graph construction.")
    parser.add_argument("--evidence-repository", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        artifacts = run_m4_pipeline(evidence_repository_path=args.evidence_repository, output_dir=args.output_dir)
    except M4FailClosed as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print("Buyer-Side Acquisition Strategy Agent M4 completed.")
    for name, path in artifacts.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
