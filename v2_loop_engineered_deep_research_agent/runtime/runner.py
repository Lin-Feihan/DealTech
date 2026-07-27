from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .acquisition_analysis import (
    build_acquisition_analysis,
    build_recommendation_decision,
    build_report_manifest,
    render_acquisition_report,
)


CERTIFICATION_FILENAMES = ("certification_results.json", "certification_result.json")
OUTPUT_FILENAMES = (
    "case_analysis.json",
    "analysis_package.json",
    "recommendation_decision.json",
    "report_manifest.json",
    "research_gaps.json",
    "human_review_items.json",
    "analysis_quality_control.json",
    "final_report.md",
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Required input does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON input {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def _certification_path(case_dir: Path, explicit_path: Path | None) -> Path:
    if explicit_path is not None:
        return explicit_path
    for name in CERTIFICATION_FILENAMES:
        candidate = case_dir / name
        if candidate.exists():
            return candidate
    expected = " or ".join(str(case_dir / name) for name in CERTIFICATION_FILENAMES)
    raise ValueError(f"Missing certification input; expected {expected}")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _validate_outputs(
    package: dict[str, Any],
    decision: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    sections = package.get("sections")
    if not isinstance(sections, list) or len(sections) != 15:
        raise ValueError("Analysis package must contain exactly 15 analysis-authored sections")
    if not package.get("quality_control", {}).get("passed"):
        raise ValueError("Analysis package must pass analysis-provenance QC")
    if decision.get("disposition") != package.get("recommendation"):
        raise ValueError("Recommendation decision conflicts with authoritative case analysis")
    if len(manifest.get("sections", [])) != 15:
        raise ValueError("Report manifest must map all 15 sections")


def run_case(
    case_dir: Path,
    output_dir: Path,
    case_id: str | None = None,
    certification_path: Path | None = None,
) -> dict[str, Any]:
    case_dir = case_dir.resolve()
    output_dir = output_dir.resolve()
    certification = _load_json(_certification_path(case_dir, certification_path))
    if not certification.get("overall_status"):
        raise ValueError("Certification input must contain overall_status")

    source_analysis_path = case_dir / "supporting_files" / "case_analysis.json"
    source_analysis = _load_json(source_analysis_path)
    effective_case_id = case_id or str(
        source_analysis.get("report_metadata", {}).get("case_id")
        or certification.get("case_id")
        or case_dir.name
    )
    package = build_acquisition_analysis(effective_case_id, case_dir, certification)
    decision = build_recommendation_decision(package)
    manifest = build_report_manifest(package)
    report = render_acquisition_report(package)
    _validate_outputs(package, decision, manifest)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "case_analysis.json", source_analysis)
    _write_json(output_dir / "analysis_package.json", package)
    _write_json(output_dir / "recommendation_decision.json", decision)
    _write_json(output_dir / "report_manifest.json", manifest)
    _write_json(output_dir / "research_gaps.json", package["research_gaps"])
    _write_json(output_dir / "human_review_items.json", package["human_review_items"])
    _write_json(output_dir / "analysis_quality_control.json", package["quality_control"])
    (output_dir / "final_report.md").write_text(report, encoding="utf-8")

    return {
        "case_id": effective_case_id,
        "recommendation": package["recommendation"],
        "certification_status": package["certification_status"],
        "output_dir": str(output_dir),
        "output_files": list(OUTPUT_FILENAMES),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a V2 buyer report from an authoritative case analysis."
    )
    parser.add_argument("--case-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case-id")
    parser.add_argument("--certification", type=Path)
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = run_case(
            case_dir=args.case_dir,
            output_dir=args.output_dir,
            case_id=args.case_id,
            certification_path=args.certification,
        )
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from exc
    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Recommendation: {result['recommendation']}")
        print(f"Certification status: {result['certification_status']}")
        print(f"Output: {result['output_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
