from __future__ import annotations

import argparse
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.artifact_store import write_json_artifact
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.evidence_repository_builder import (
    EvidenceRepositoryError,
    build_evidence_repository,
    load_json_artifact,
)


class M3FailClosed(RuntimeError):
    pass


def run_m3_pipeline(raw_evidence_path: Path, retrieved_sources_manifest_path: Path, output_dir: Path) -> dict[str, Path]:
    try:
        raw_evidence = load_json_artifact(raw_evidence_path)
        retrieved_sources_manifest = load_json_artifact(retrieved_sources_manifest_path)
        evidence_repository = build_evidence_repository(raw_evidence, retrieved_sources_manifest)
        evidence_repository_path = write_json_artifact(output_dir, "evidence_repository.json", evidence_repository)
    except EvidenceRepositoryError as exc:
        raise M3FailClosed(f"M3 failed closed: {exc}") from exc

    return {"evidence_repository": evidence_repository_path}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Buyer-Side Acquisition Strategy Agent M3 evidence repository construction.")
    parser.add_argument("--raw-evidence", required=True, type=Path)
    parser.add_argument("--retrieved-sources-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        artifacts = run_m3_pipeline(
            raw_evidence_path=args.raw_evidence,
            retrieved_sources_manifest_path=args.retrieved_sources_manifest,
            output_dir=args.output_dir,
        )
    except M3FailClosed as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print("Buyer-Side Acquisition Strategy Agent M3 completed.")
    for name, path in artifacts.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
