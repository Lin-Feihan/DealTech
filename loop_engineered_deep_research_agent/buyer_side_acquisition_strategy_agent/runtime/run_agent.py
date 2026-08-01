from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loop_engineered_deep_research_agent.buyer_side_acquisition_strategy_agent.runtime.loop_controller import LoopController


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Buyer-Side Acquisition Strategy Agent.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Start a case and generate research_request.json.")
    start.add_argument("--case", required=True, type=Path, help="Path to case.json or an existing mandate JSON file.")
    start.add_argument("--output-dir", required=True, type=Path, help="Run directory for artifacts.")

    resume = subparsers.add_parser("resume", help="Resume a run from an external Deep Research response.")
    resume.add_argument("--run-dir", required=True, type=Path, help="Existing run directory containing run_state.json.")
    resume.add_argument("--research-response", required=True, type=Path, help="Structured deep_research_response.json from external research.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "start":
        state = LoopController(args.output_dir).start(args.case)
    else:
        state = LoopController(args.run_dir).resume(args.research_response)
    print(json.dumps(_public_result(state), indent=2, sort_keys=True))
    return 0 if state["status"] != "failed" else 2


def _public_result(state: dict) -> dict:
    return {
        "case_id": state.get("case_id", ""),
        "status": state.get("status"),
        "current_stage": state.get("current_stage"),
        "iteration": state.get("iteration"),
        "next_action": state.get("next_action"),
        "last_error": state.get("last_error"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
