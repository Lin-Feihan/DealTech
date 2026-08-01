from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.artifact_store import write_run_artifacts
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.mandate_intake import MandateValidationError, load_mandate
from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.research_planning import ResearchPlanValidationError, build_research_plan


def run_pipeline(mandate_path: Path, output_dir: Path) -> dict[str, Path]:
    mandate = load_mandate(mandate_path)
    research_plan = build_research_plan(mandate)
    return write_run_artifacts(output_dir, mandate, research_plan)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Buyer-Side Acquisition Strategy Agent Milestone 1 mandate-to-research-plan runtime.")
    parser.add_argument("--mandate", required=True, type=Path, help="Path to mandate.json input.")
    parser.add_argument("--output-dir", required=True, type=Path, help="Output directory for Milestone 1 artifacts.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        artifacts = run_pipeline(args.mandate, args.output_dir)
    except (MandateValidationError, ResearchPlanValidationError) as exc:
        print(f"Buyer-Side Acquisition Strategy Agent Milestone 1 failed closed: {exc}", file=sys.stderr)
        return 2

    print("Buyer-Side Acquisition Strategy Agent Milestone 1 completed.")
    for name, path in artifacts.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
