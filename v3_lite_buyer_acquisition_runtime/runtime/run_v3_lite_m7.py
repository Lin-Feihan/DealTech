from __future__ import annotations

import argparse
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from v3_lite_buyer_acquisition_runtime.runtime.artifact_store import write_json_artifact
from v3_lite_buyer_acquisition_runtime.runtime.report_rendering_gate import (
    ReportRenderingGateError,
    build_report_manifest,
    load_json_artifact,
)


class M7FailClosed(RuntimeError):
    pass


def run_m7_pipeline(
    analysis_package_path: Path,
    certification_result_path: Path,
    repair_plan_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    try:
        analysis_package = load_json_artifact(analysis_package_path)
        certification_result = load_json_artifact(certification_result_path)
        repair_plan = load_json_artifact(repair_plan_path)
        report_manifest = build_report_manifest(analysis_package, certification_result, repair_plan)
        report_manifest_path = write_json_artifact(output_dir, "report_manifest.json", report_manifest)
    except ReportRenderingGateError as exc:
        raise M7FailClosed(f"M7 failed closed: {exc}") from exc

    return {"report_manifest": report_manifest_path}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run V3-Lite M7 report rendering gate.")
    parser.add_argument("--analysis-package", required=True, type=Path)
    parser.add_argument("--certification-result", required=True, type=Path)
    parser.add_argument("--repair-plan", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        artifacts = run_m7_pipeline(
            analysis_package_path=args.analysis_package,
            certification_result_path=args.certification_result,
            repair_plan_path=args.repair_plan,
            output_dir=args.output_dir,
        )
    except M7FailClosed as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print("V3-Lite M7 completed.")
    for name, path in artifacts.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
