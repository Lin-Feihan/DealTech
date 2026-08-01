from __future__ import annotations

import argparse
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.artifact_store import write_json_artifact
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.repair_loop_executor import (
    RepairLoopError,
    build_m5_1_artifacts,
    load_json_artifact,
)


class M51FailClosed(RuntimeError):
    pass


def run_m5_1_pipeline(
    certification_result_path: Path,
    research_gaps_path: Path,
    repair_plan_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    try:
        certification_result = load_json_artifact(certification_result_path)
        research_gaps = load_json_artifact(research_gaps_path)
        repair_plan = load_json_artifact(repair_plan_path)
        targeted_plan, attempt_log = build_m5_1_artifacts(certification_result, research_gaps, repair_plan)
        targeted_plan_path = write_json_artifact(output_dir, "targeted_source_discovery_plan.json", targeted_plan)
        attempt_log_path = write_json_artifact(output_dir, "repair_attempt_log.json", attempt_log)
    except RepairLoopError as exc:
        raise M51FailClosed(f"M5.1 failed closed: {exc}") from exc

    return {
        "targeted_source_discovery_plan": targeted_plan_path,
        "repair_attempt_log": attempt_log_path,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Buyer-Side Acquisition Strategy Agent M5.1 repair loop execution dry run.")
    parser.add_argument("--certification-result", required=True, type=Path)
    parser.add_argument("--research-gaps", required=True, type=Path)
    parser.add_argument("--repair-plan", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        artifacts = run_m5_1_pipeline(
            certification_result_path=args.certification_result,
            research_gaps_path=args.research_gaps,
            repair_plan_path=args.repair_plan,
            output_dir=args.output_dir,
        )
    except M51FailClosed as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print("Buyer-Side Acquisition Strategy Agent M5.1 completed.")
    for name, path in artifacts.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
