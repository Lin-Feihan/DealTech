from __future__ import annotations

import argparse
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from v3_lite_buyer_acquisition_runtime.runtime.artifact_store import write_json_artifact
from v3_lite_buyer_acquisition_runtime.runtime.audit_package_builder import (
    AuditPackageError,
    build_audit_package,
    load_json_artifact,
)


class Step6AFailClosed(RuntimeError):
    pass


def run_step6a_audit_package_pipeline(
    report_manifest_path: Path,
    analysis_package_path: Path,
    certification_result_path: Path,
    claim_evidence_graph_path: Path,
    evidence_repository_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    try:
        report_manifest = load_json_artifact(report_manifest_path)
        analysis_package = load_json_artifact(analysis_package_path)
        certification_result = load_json_artifact(certification_result_path)
        claim_evidence_graph = load_json_artifact(claim_evidence_graph_path)
        evidence_repository = load_json_artifact(evidence_repository_path)
        audit_package = build_audit_package(
            report_manifest=report_manifest,
            analysis_package=analysis_package,
            certification_result=certification_result,
            claim_evidence_graph=claim_evidence_graph,
            evidence_repository=evidence_repository,
        )
        audit_package_path = write_json_artifact(output_dir, "audit_package.json", audit_package)
    except AuditPackageError as exc:
        raise Step6AFailClosed(f"Step 6A audit package failed closed: {exc}") from exc

    return {"audit_package": audit_package_path}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run V3-Lite Step 6A professional report audit package generation.")
    parser.add_argument("--report-manifest", required=True, type=Path)
    parser.add_argument("--analysis-package", required=True, type=Path)
    parser.add_argument("--certification-result", required=True, type=Path)
    parser.add_argument("--claim-evidence-graph", required=True, type=Path)
    parser.add_argument("--evidence-repository", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        artifacts = run_step6a_audit_package_pipeline(
            report_manifest_path=args.report_manifest,
            analysis_package_path=args.analysis_package,
            certification_result_path=args.certification_result,
            claim_evidence_graph_path=args.claim_evidence_graph,
            evidence_repository_path=args.evidence_repository,
            output_dir=args.output_dir,
        )
    except Step6AFailClosed as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print("V3-Lite Step 6A completed.")
    for name, path in artifacts.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
