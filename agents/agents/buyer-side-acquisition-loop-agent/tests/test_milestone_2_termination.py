from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agents.buyer_side_acquisition_loop_agent.runtime import run_case


AGENT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "buyer_side_acquisition_loop_agent"
EXAMPLE_ROOT = AGENT_ROOT / "06_examples"
CASE_PATHS = {
    "success": EXAMPLE_ROOT / "synthetic_minimal_loop_case" / "case.yaml",
    "repeated": EXAMPLE_ROOT / "synthetic_repeated_evidence_failure_case" / "case.yaml",
    "no_progress": EXAMPLE_ROOT / "synthetic_no_progress_case" / "case.yaml",
    "budget": EXAMPLE_ROOT / "synthetic_iteration_budget_case" / "case.yaml",
    "human": EXAMPLE_ROOT / "synthetic_human_only_information_case" / "case.yaml",
}
LEGACY_ROOTS = (
    Path(__file__).resolve().parents[2] / "acquisition-strategy-agent",
    Path(__file__).resolve().parents[2] / "acquisition_strategy_agent",
)


def _tree_digest(roots: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for root in roots:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            digest.update(str(path.relative_to(root)).encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _load_outputs(output_dir: Path) -> dict[str, object]:
    return {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in output_dir.glob("*.json")
    }


@pytest.fixture(scope="module")
def scenario_runs(tmp_path_factory):
    legacy_before = _tree_digest(LEGACY_ROOTS)
    runs = {}
    for name, case_path in CASE_PATHS.items():
        output_dir = tmp_path_factory.mktemp(f"milestone_2_{name}") / "run"
        result = run_case(case_path, output_dir)
        runs[name] = {
            "result": result,
            "output_dir": output_dir,
            "files": _load_outputs(output_dir),
        }
    legacy_after = _tree_digest(LEGACY_ROOTS)
    return runs, legacy_before, legacy_after


def test_01_milestone_1_repair_success_remains_intact(scenario_runs):
    runs, _, _ = scenario_runs
    files = runs["success"]["files"]
    assert [item["status"] for item in files["gate_a_results.json"]] == [
        "FAIL_RESEARCH_GAP",
        "PASS",
    ]
    assert files["terminal_state.json"]["status"] == "COMPLETED_STRATEGIC_THESIS"


def test_02_repeated_insufficient_evidence_is_not_certified(scenario_runs):
    runs, _, _ = scenario_runs
    files = runs["repeated"]["files"]
    assert files["claims.json"][0]["pce_status"] != "Certified"
    assert all(item["status"] == "FAIL_RESEARCH_GAP" for item in files["gate_a_results.json"])


def test_03_historical_failed_gate_results_are_preserved(scenario_runs):
    runs, _, _ = scenario_runs
    files = runs["repeated"]["files"]
    assert [item["iteration"] for item in files["gate_a_results.json"]] == [1, 2, 3]
    assert files["gate_a_iteration_1.json"]["gate_result"]["status"] == "FAIL_RESEARCH_GAP"
    assert files["gate_a_iteration_2.json"]["gate_result"]["status"] == "FAIL_RESEARCH_GAP"


def test_04_research_attempts_are_append_only(scenario_runs):
    runs, _, _ = scenario_runs
    attempts = runs["repeated"]["files"]["research_attempts.json"]
    attempt_ids = [item["attempt_id"] for item in attempts]
    assert attempt_ids == ["ATTEMPT-A-01", "ATTEMPT-REPEATED-02", "ATTEMPT-REPEATED-03"]
    assert len(attempt_ids) == len(set(attempt_ids))


def test_05_no_progress_compares_current_and_prior_iterations(scenario_runs):
    runs, _, _ = scenario_runs
    assessments = runs["no_progress"]["files"]["no_progress_assessment.json"][
        "assessments"
    ]
    assert len(assessments) == 1
    assert assessments[0]["current_iteration"] == 2
    assert assessments[0]["compared_to_iteration"] == 1
    assert assessments[0]["material_progress"] is False


def test_06_identical_failed_action_cannot_repeat_indefinitely(scenario_runs):
    runs, _, _ = scenario_runs
    files = runs["no_progress"]["files"]
    attempts = files["research_attempts.json"]
    assert [item["action_key"] for item in attempts] == [
        "REPEATED_PUBLIC_CAPABILITY_SEARCH",
        "REPEATED_PUBLIC_CAPABILITY_SEARCH",
    ]
    assessment = files["no_progress_assessment.json"]["assessments"][0]
    assert assessment["identical_action_repeated"] is True
    assert len(attempts) == 2


def test_07_loop_stops_at_no_progress_limit(scenario_runs):
    runs, _, _ = scenario_runs
    state = runs["no_progress"]["files"]["loop_state.json"]
    assert state["status"] == "STOPPED_NO_PROGRESS"
    assert state["no_progress_count"] == state["maximum_no_progress_iterations"]


def test_08_loop_stops_at_iteration_budget(scenario_runs):
    runs, _, _ = scenario_runs
    terminal = runs["budget"]["files"]["terminal_state.json"]
    assert terminal["status"] == "STOPPED_ITERATION_BUDGET"
    assert terminal["iterations_used"] == 2


def test_09_no_iteration_begins_after_budget_exhaustion(scenario_runs):
    runs, _, _ = scenario_runs
    files = runs["budget"]["files"]
    assert [item["iteration"] for item in files["iteration_records.json"]] == [1, 2]
    assert "gate_a_iteration_3.json" not in files
    assert files["loop_state.json"]["current_iteration"] == 2


def test_10_human_only_information_creates_review_item(scenario_runs):
    runs, _, _ = scenario_runs
    items = runs["human"]["files"]["human_review_items.json"]
    assert len(items) == 1
    assert items[0]["issue_type"] == "HUMAN_ONLY_INFORMATION"
    assert items[0]["status"] == "OPEN"


def test_11_human_only_information_does_not_retry_public_research(scenario_runs):
    runs, _, _ = scenario_runs
    files = runs["human"]["files"]
    attempts = files["research_attempts.json"]
    assert len([item for item in attempts if item["iteration"] > 1]) == 0
    assert [item["decision"] for item in files["controller_decisions.json"]] == [
        "ESCALATE_HUMAN_REVIEW"
    ]


def test_12_human_only_information_awaits_human_review(scenario_runs):
    runs, _, _ = scenario_runs
    terminal = runs["human"]["files"]["terminal_state.json"]
    assert terminal["status"] == "AWAITING_HUMAN_REVIEW"
    assert terminal["final_pce_status"] == "Not Certified"


def test_13_reviewer_role_and_exact_question_are_persisted(scenario_runs):
    runs, _, _ = scenario_runs
    item = runs["human"]["files"]["human_review_items.json"][0]
    assert item["required_reviewer_role"] == (
        "Authorized target CFO or financial diligence lead"
    )
    assert item["exact_question_for_reviewer"].startswith(
        "Please provide the private target's customer concentration"
    )
    assert len(item["required_documents_or_information"]) == 4


def test_14_paused_case_keeps_claim_and_gap_unresolved(scenario_runs):
    runs, _, _ = scenario_runs
    files = runs["human"]["files"]
    terminal = files["terminal_state.json"]
    assert terminal["unresolved_claims"] == ["CLM-HUMAN-001"]
    assert terminal["open_gaps"]
    assert files["resolved_and_open_gaps.json"]["open_gaps"]
    assert files["resolved_and_open_gaps.json"]["resolved_gaps"] == []


def test_15_stopped_or_paused_cases_have_no_full_deal_recommendation(scenario_runs):
    runs, _, _ = scenario_runs
    for name in ("repeated", "no_progress", "budget", "human"):
        summary = runs[name]["files"]["run_summary.json"]
        assert summary["full_deal_recommendation_generated"] is False


def test_16_pce_gate_controller_and_terminal_statuses_are_separate(scenario_runs):
    runs, _, _ = scenario_runs
    files = runs["budget"]["files"]
    assert files["gate_a_iteration_2.json"]["pce_precheck"]["status"] == (
        "Needs Human Review"
    )
    assert files["gate_a_iteration_2.json"]["gate_result"]["status"] == (
        "FAIL_RESEARCH_GAP"
    )
    assert files["controller_decisions.json"][-1]["decision"] == (
        "STOP_ITERATION_BUDGET"
    )
    assert files["terminal_state.json"]["status"] == "STOPPED_ITERATION_BUDGET"


def test_17_new_agent_contains_no_legacy_case_content(scenario_runs):
    forbidden = ("app" + "le", "darwin" + "ai")
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore").lower()
        for root in (AGENT_ROOT, PACKAGE_ROOT)
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    for term in forbidden:
        assert term not in text


def test_18_legacy_v0_directories_are_untouched(scenario_runs):
    _, legacy_before, legacy_after = scenario_runs
    assert legacy_before == legacy_after
