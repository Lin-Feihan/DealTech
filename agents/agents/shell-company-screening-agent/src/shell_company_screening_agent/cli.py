from __future__ import annotations
import argparse, json
from pathlib import Path
from .pipeline import run_tuntun_hk_demo, validate_trace
from .trace.calculation_replay import replay_trace_calculations
from .pce.certification_report import certify_example

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='shell-screen-agent')
    parser.add_argument('--repo-root', default='.', help='Repository root')
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('run-tuntun-hk-demo')
    sub.add_parser('validate-trace')
    sub.add_parser('replay-calculations')
    sub.add_parser('certify')
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    example = root / 'examples/tuntun_hk'
    if args.cmd == 'run-tuntun-hk-demo': result = run_tuntun_hk_demo(root)
    elif args.cmd == 'validate-trace': result = validate_trace(example)
    elif args.cmd == 'replay-calculations': result = replay_trace_calculations(example)
    elif args.cmd == 'certify': result = certify_example(example)
    else: raise AssertionError(args.cmd)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
