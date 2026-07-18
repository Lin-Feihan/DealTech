from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from buyer_side_acquisition_loop_agent.full_pipeline import (
    _write_manifest,
    check_full_pipeline_case,
    resume_full_pipeline,
    run_full_pipeline,
)
from buyer_side_acquisition_loop_agent.live_research_models import ProviderConfigurationError
from buyer_side_acquisition_loop_agent.pipeline_models import validate_block_b_input_bundle
from buyer_side_acquisition_loop_agent.storage import load_case


ASSETS = Path(__file__).resolve().parents[1]
DEMO_CASE = ASSETS / "06_examples" / "recorded_full_pipeline_case" / "case.yaml"
TEACHER_CASE = ASSETS / "06_examples" / "teacher_case_template" / "case.yaml"


@pytest.fixture(scope="module")
def completed_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("rc1") / "run_output"
    result = run_full_pipeline(DEMO_CASE, output)
    assert result["summary"]["status"] == "COMPLETED"
    return output


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_case_check_and_blank_teacher_template() -> None:
    ready = check_full_pipeline_case(DEMO_CASE)
    not_ready = check_full_pipeline_case(TEACHER_CASE)
    assert ready["status"] == "READY_WITH_WARNINGS"
    assert ready["paid_request_made"] is False
    assert not_ready["status"] == "NOT_READY"
    assert any("mandate.buyer_name" in item for item in not_ready["issues"])


def test_continuous_recorded_pipeline_outcomes_and_artifacts(completed_run: Path) -> None:
    summary = read(completed_run / "run_summary.json")
    assert summary["module_counts"] == {"block_a": 7, "block_b": 5, "block_c": 5}
    assert summary["gate_a"] == "CONDITIONAL_PASS"
    assert summary["gate_b"] == "RENEGOTIATE_PRICE"
    assert summary["gate_c"] == "RENEGOTIATE"
    assert summary["decision_state"] == "RENEGOTIATE"
    assert summary["delivery_outcome"] == "DELIVERABLE_WITH_CAVEATS"
    assert summary["paid_request_made"] is False
    assert summary["decision_state_is_final_human_approval"] is False
    required = {
        "final_acquisition_strategy_report.md", "run_summary.json", "gate_a_result.json",
        "gate_b_result.json", "gate_c_result.json", "decision_state.json",
        "final_delivery_verification.json", "run_manifest.json",
        "cross_block_consistency_result.json",
    }
    assert required <= {path.name for path in completed_run.iterdir() if path.is_file()}
    assert read(completed_run / "cross_block_consistency_result.json")["passed"] is True


def test_three_targeted_repair_patterns_are_real(completed_run: Path) -> None:
    a_gaps = read(completed_run / "stages/block_a/loop/gaps.json")
    b_gaps = read(completed_run / "stages/block_b/04_calculations/calculation_gap_history.json")
    c_gaps = read(completed_run / "stages/block_c/09_loop/research_gap_history.json")
    assert [(row["originating_module"], row["status"]) for row in a_gaps] == [("A6", "CONDITIONALLY_RESOLVED")]
    assert {row["owning_module"] for row in b_gaps if row["status"] == "RESOLVED"} == {"B3"}
    assert [(row["gap_type"], row["owning_module"], row["status"]) for row in c_gaps] == [("EVIDENCE_MISSING", "C2", "RESOLVED")]
    summary = read(completed_run / "run_summary.json")
    assert summary["targeted_repairs"]["block_b"] == ["B3", "B5"]
    assert summary["targeted_repairs"]["block_c"] == ["C2", "C4", "C5"]


def test_validated_cross_block_bundles_and_replay(completed_run: Path) -> None:
    case_data = load_case(DEMO_CASE)
    b_bundle = read(completed_run / "stages/block_b/00_input/block_b_input_bundle.json")
    validated = validate_block_b_input_bundle(
        b_bundle, case_id=case_data["case_id"], run_id=case_data["run_id"], as_of_date=case_data["as_of_date"]
    )
    assert validated.gate_a_history[-1]["status"] == "CONDITIONAL_PASS"
    c_validation = read(completed_run / "stages/block_c/00_input/block_c_input_validation.json")
    c_bundle = read(completed_run / "stages/block_c/00_input/block_c_input_bundle.json")
    assert c_validation["validated"] is True
    assert c_bundle["case_id"] == case_data["case_id"]
    assert c_bundle["run_id"] == case_data["run_id"]
    assert c_bundle["schema_version"] == "release-candidate-1"
    assert all(not Path(path).is_absolute() for path in c_bundle["artifact_references"].values())
    assert all(row["status"] == "PASS" for row in c_bundle["calculation_replays"])


def test_completed_resume_skips_valid_stages(completed_run: Path) -> None:
    before = {
        stage: (completed_run / f"stages/{stage}/run_summary.json").stat().st_mtime_ns
        for stage in ("block_a", "block_b", "block_c")
    }
    result = resume_full_pipeline(completed_run)
    after = {
        stage: (completed_run / f"stages/{stage}/run_summary.json").stat().st_mtime_ns
        for stage in ("block_a", "block_b", "block_c")
    }
    assert result["manifest"]["next_stage"] == "COMPLETE"
    assert before == after


def test_reporting_only_resume_does_not_rerun_research(completed_run: Path, tmp_path: Path) -> None:
    output = tmp_path / "reporting_resume"
    shutil.copytree(completed_run, output)
    case_data = load_case(DEMO_CASE)
    before = {
        stage: (output / f"stages/{stage}/run_summary.json").stat().st_mtime_ns
        for stage in ("block_a", "block_b", "block_c")
    }
    (output / "final_acquisition_strategy_report.md").unlink()
    _write_manifest(output, DEMO_CASE.resolve(), case_data, ["BLOCK_A", "BLOCK_B", "BLOCK_C"])
    result = resume_full_pipeline(output)
    after = {
        stage: (output / f"stages/{stage}/run_summary.json").stat().st_mtime_ns
        for stage in ("block_a", "block_b", "block_c")
    }
    assert before == after
    assert (output / "final_acquisition_strategy_report.md").is_file()
    assert result["summary"]["status"] == "COMPLETED"


def test_resume_rejects_tampered_completed_artifact(completed_run: Path, tmp_path: Path) -> None:
    output = tmp_path / "tampered"
    shutil.copytree(completed_run, output)
    path = output / "stages/block_a/run_summary.json"
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ProviderConfigurationError, match="altered or is missing"):
        resume_full_pipeline(output)


def test_new_agent_has_no_legacy_demonstration_parties() -> None:
    forbidden = ("app" + "le", "darwin" + "ai")
    for root in (ASSETS, ASSETS.parent / "buyer_side_acquisition_loop_agent"):
        for path in root.rglob("*"):
            if not path.is_file() or "run_output" in path.parts or path.suffix.lower() not in {".py", ".md", ".json", ".yaml"}:
                continue
            text = path.read_text(encoding="utf-8").lower()
            assert not any(term in text for term in forbidden), path
