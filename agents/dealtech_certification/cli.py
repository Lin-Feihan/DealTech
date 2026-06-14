from __future__ import annotations

import argparse
import json
from .engine import run_agent_case, format_cli_result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Run a certified DealTech agent case workflow.')
    parser.add_argument('--agent', required=True, help='Agent slug, e.g. shell-company-screening')
    parser.add_argument('--case', dest='case_id', help='Case id under the agent 07_case_studies directory')
    parser.add_argument('--view', choices=['buyer_side', 'target_side'], help='Perspective for acquisition-strategy')
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON')
    args = parser.parse_args(argv)
    result = run_agent_case(args.agent, args.case_id, args.view)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_cli_result(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
