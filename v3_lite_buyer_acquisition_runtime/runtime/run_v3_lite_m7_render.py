from __future__ import annotations

import argparse
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from v3_lite_buyer_acquisition_runtime.runtime.report_renderer import (
    ReportRendererError,
    load_json_artifact,
    render_report_if_allowed,
)


class M7RenderFailClosed(RuntimeError):
    pass


def run_m7_render_pipeline(
    report_manifest_path: Path,
    analysis_package_path: Path,
    certification_result_path: Path,
    output_dir: Path,
    audit_package_path: Path | None = None,
) -> dict:
    try:
        report_manifest = load_json_artifact(report_manifest_path)
        analysis_package = load_json_artifact(analysis_package_path)
        certification_result = load_json_artifact(certification_result_path)
        audit_package = load_json_artifact(audit_package_path) if audit_package_path else None
        return render_report_if_allowed(report_manifest, analysis_package, certification_result, output_dir, audit_package=audit_package)
    except ReportRendererError as exc:
        raise M7RenderFailClosed(f"M7.1 render failed closed: {exc}") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run V3-Lite M7.1 gate-controlled report renderer.")
    parser.add_argument("--report-manifest", required=True, type=Path)
    parser.add_argument("--analysis-package", required=True, type=Path)
    parser.add_argument("--certification-result", required=True, type=Path)
    parser.add_argument("--audit-package", required=False, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run_m7_render_pipeline(
            report_manifest_path=args.report_manifest,
            analysis_package_path=args.analysis_package,
            certification_result_path=args.certification_result,
            audit_package_path=args.audit_package,
            output_dir=args.output_dir,
        )
    except M7RenderFailClosed as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"V3-Lite M7.1 rendering_status: {result['rendering_status']}")
    print(f"final_report_generated: {result['final_report_generated']}")
    if result["final_report_path"]:
        print(f"final_report: {result['final_report_path']}")
    if result["blocked_reasons"]:
        print("blocked_reasons:")
        for reason in result["blocked_reasons"]:
            print(f"- {reason.get('reason', reason)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
