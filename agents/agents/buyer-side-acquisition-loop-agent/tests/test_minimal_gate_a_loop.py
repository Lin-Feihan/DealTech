from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.buyer_side_acquisition_loop_agent.runtime import run_case


CASE_PATH = (
    Path(__file__).resolve().parents[1]
    / "06_examples"
    / "synthetic_minimal_loop_case"
    / "case.yaml"
)


def _read(output_dir: Path, filename: str):
    return json.loads(output_dir.joinpath(filename).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def completed_run(tmp_path_factory):
    output_dir = tmp_path_factory.mktemp("gate_a_loop") / "run"
    result = run_case(CASE_PATH, output_dir)
    files = {path.name: _read(output_dir, path.name) for path in output_dir.glob("*.json")}
    return result, output_dir, files


def test_01_first_gate_fails_for_missing_evidence(completed_run):
    _, _, files = completed_run
    first = files["gate_a_iteration_1.json"]
    assert first["gate_result"]["status"] == "FAIL_RESEARCH_GAP"
    assert first["pce_precheck"]["selected_evidence_id"] is None


def test_02_gap_is_evidence_missing(completed_run):
    _, _, files = completed_run
    assert files["research_gap.json"]["gap_type"] == "EVIDENCE_MISSING"


def test_03_return_target_is_only_target_capability_and_business_quality(completed_run):
    result, _, files = completed_run
    expected = "Target Capability & Business Quality"
    assert result["controller_decision"]["return_target"] == expected
    assert files["research_gap.json"]["return_target"] == expected


def test_04_unrelated_block_a_modules_are_not_rerun(completed_run):
    _, _, files = completed_run
    records = files["iteration_records.json"]
    assert records[1]["modules_executed"] == ["Target Capability & Business Quality"]
    unrelated = {
        "Transaction Context",
        "Buyer Strategic Need",
        "Strategic Rationale",
        "Target Attractiveness",
        "Industry / Competitive Position",
        "Strategic Fit",
    }
    assert unrelated.isdisjoint(records[1]["modules_executed"])


def test_05_original_failed_gate_history_is_preserved(completed_run):
    _, _, files = completed_run
    assert files["gate_a_iteration_1.json"]["gate_result"]["status"] == "FAIL_RESEARCH_GAP"
    assert files["loop_state.json"]["gate_history"] == ["FAIL_RESEARCH_GAP", "PASS"]


def test_06_new_evidence_does_not_overwrite_old_evidence(completed_run):
    _, _, files = completed_run
    evidence_ids = [item["evidence_id"] for item in files["evidence.json"]]
    assert evidence_ids == ["EV-MISSING-001", "EV-A-REPAIR-001"]
    assert files["claims.json"][0]["evidence_ids"] == evidence_ids


def test_07_source_evidence_claim_lineage_is_intact(completed_run):
    _, _, files = completed_run
    source = files["sources.json"][0]
    repaired = next(item for item in files["evidence.json"] if item["status"] == "AVAILABLE")
    claim = files["claims.json"][0]
    assert repaired["source_id"] == source["source_id"]
    assert repaired["claim_id"] == claim["claim_id"]
    assert repaired["evidence_id"] in claim["evidence_ids"]
    assert source["source_id"] in claim["source_ids"]


def test_08_pce_status_and_gate_status_are_separate(completed_run):
    _, _, files = completed_run
    first = files["gate_a_iteration_1.json"]
    second = files["gate_a_iteration_2.json"]
    assert first["pce_precheck"]["status"] == "Not Certified"
    assert first["gate_result"]["status"] == "FAIL_RESEARCH_GAP"
    assert second["pce_precheck"]["status"] == "Certified"
    assert second["gate_result"]["status"] == "PASS"


def test_09_exactly_two_iteration_records_exist(completed_run):
    _, _, files = completed_run
    assert [item["iteration"] for item in files["iteration_records.json"]] == [1, 2]


def test_10_loop_stops_within_budget(completed_run):
    _, _, files = completed_run
    state = files["loop_state.json"]
    assert state["status"] == "COMPLETED_STRATEGIC_THESIS"
    assert state["completed_iterations"] == 2
    assert state["completed_iterations"] <= state["maximum_iterations"]
    assert state["final_gate_status"] == "PASS"


def test_11_no_legacy_case_or_v0_package_content_is_imported(completed_run):
    _, output_dir, _ = completed_run
    output_text = "\n".join(
        path.read_text(encoding="utf-8").lower() for path in output_dir.glob("*.json")
    )
    forbidden_terms = ("app" + "le", "darwin" + "ai", "acquisition_strategy_agent")
    for forbidden in forbidden_terms:
        assert forbidden not in output_text

    package_dir = Path(__file__).resolve().parents[2] / "buyer_side_acquisition_loop_agent"
    package_text = "\n".join(
        path.read_text(encoding="utf-8") for path in package_dir.glob("*.py")
    )
    assert "from agents.acquisition_strategy_agent" not in package_text
    assert "from agents.acquisition-strategy-agent" not in package_text


def test_12_no_full_deal_recommendation_is_generated(completed_run):
    _, _, files = completed_run
    assert files["run_summary.json"]["full_deal_recommendation_generated"] is False
    assert files["loop_state.json"]["final_gate_status"] == "PASS"
    assert files["gate_a_iteration_2.json"]["gate_result"]["decision_scope"] == (
        "Block A strategic thesis only"
    )
