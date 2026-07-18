from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from agents.buyer_side_acquisition_loop_agent.business_contracts import load_reporting_prompts
from agents.buyer_side_acquisition_loop_agent.reporting import SECTION_TITLES, verify_final_delivery
from agents.buyer_side_acquisition_loop_agent.review_models import (
    DeliveryOutcome,
    HumanReviewResponse,
    ResponseValidationStatus,
)
from agents.buyer_side_acquisition_loop_agent.review_runtime import resume_human_review_case
from agents.buyer_side_acquisition_loop_agent.review_validation import validate_human_review_response
from agents.buyer_side_acquisition_loop_agent.runtime import run_case
from agents.buyer_side_acquisition_loop_agent.storage import to_primitive


AGENT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "buyer_side_acquisition_loop_agent"
COMPLETE_CASE = AGENT_ROOT / "06_examples" / "synthetic_complete_acquisition_case" / "case.yaml"
HUMAN_CASE = AGENT_ROOT / "06_examples" / "synthetic_human_only_information_case" / "case.yaml"
VALID_RESPONSE = HUMAN_CASE.parent / "valid_human_review_response.json"
INVALID_RESPONSE = HUMAN_CASE.parent / "invalid_unauthorized_response.json"


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def complete_run(tmp_path_factory):
    output = tmp_path_factory.mktemp("m4_complete") / "run"
    result = run_case(COMPLETE_CASE, output)
    return result, output


@pytest.fixture(scope="module")
def valid_resume(tmp_path_factory):
    output = tmp_path_factory.mktemp("m4_valid_resume") / "run"
    run_case(HUMAN_CASE, output)
    before_claims = _read(output / "claims.json")
    before_evidence = _read(output / "evidence.json")
    result = resume_human_review_case(case_path=HUMAN_CASE, response_path=VALID_RESPONSE, output_dir=output)
    return result, output, before_claims, before_evidence


@pytest.fixture(scope="module")
def invalid_resume(tmp_path_factory):
    output = tmp_path_factory.mktemp("m4_invalid_resume") / "run"
    run_case(HUMAN_CASE, output)
    result = resume_human_review_case(case_path=HUMAN_CASE, response_path=INVALID_RESPONSE, output_dir=output)
    return result, output


def _response_and_item(tmp_path):
    output = tmp_path / "initial"
    run_case(HUMAN_CASE, output)
    item = _read(output / "human_review" / "human_review_items.json")[0]
    response = HumanReviewResponse.from_dict(_read(VALID_RESPONSE))
    return response, item


def _verify_again(result, **overrides):
    package = result["reporting_package"]
    values = {
        "report_text": package["report_path"].read_text(encoding="utf-8"),
        "sections": copy.deepcopy(package["sections"]),
        "manifest": copy.deepcopy(package["manifest"]),
        "claims": to_primitive(result["claims"]),
        "sources": to_primitive(result["sources"]),
        "evidence": to_primitive(result["evidence"]),
        "calculations": to_primitive(result["calculations"]),
        "counterevidence": to_primitive(result["counterevidence"]),
        "open_gaps": to_primitive(result["calculation_gaps"]),
        "human_reviews": list(_read(COMPLETE_CASE).get("human_review_items", [])),
        "gates": to_primitive(result["gates"]),
        "decision": to_primitive(result["decision_state"]),
        "pce_result": result["certification"]["pce_result"],
    }
    values.update(overrides)
    return verify_final_delivery(**values)


def test_01_authorized_role_is_accepted(tmp_path):
    response, item = _response_and_item(tmp_path)
    result = validate_human_review_response(response=response, item=item, current_state="OPEN", validated_at=response.submitted_at)
    assert result.status == ResponseValidationStatus.ACCEPTED
    assert result.may_resume is True


def test_02_unauthorized_role_is_rejected(tmp_path):
    _, item = _response_and_item(tmp_path)
    response = HumanReviewResponse.from_dict(_read(INVALID_RESPONSE))
    result = validate_human_review_response(response=response, item=item, current_state="OPEN", validated_at=response.submitted_at)
    assert result.status == ResponseValidationStatus.REJECTED
    assert any("not authorized" in value for value in result.errors)


def test_03_wrong_case_id_is_rejected(tmp_path):
    response, item = _response_and_item(tmp_path)
    response = replace(response, case_id="wrong-case")
    result = validate_human_review_response(response=response, item=item, current_state="OPEN", validated_at=response.submitted_at)
    assert result.status == ResponseValidationStatus.REJECTED
    assert result.checks["case_id_matches"] is False


def test_04_closed_item_cannot_be_silently_answered(tmp_path):
    response, item = _response_and_item(tmp_path)
    result = validate_human_review_response(response=response, item=item, current_state="RESOLVED", validated_at=response.submitted_at)
    assert result.status == ResponseValidationStatus.REJECTED
    assert result.checks["item_answerable"] is False


def test_05_missing_direct_answer_is_rejected(tmp_path):
    response, item = _response_and_item(tmp_path)
    response = replace(response, direct_answer="")
    result = validate_human_review_response(response=response, item=item, current_state="OPEN", validated_at=response.submitted_at)
    assert result.status == ResponseValidationStatus.REJECTED
    assert result.checks["direct_answer_supplied"] is False


def test_06_expired_response_is_rejected(tmp_path):
    response, item = _response_and_item(tmp_path)
    response = replace(response, effective_until="2026-01-01T00:00:00Z")
    result = validate_human_review_response(response=response, item=item, current_state="OPEN", validated_at=response.submitted_at)
    assert result.status == ResponseValidationStatus.REJECTED
    assert result.checks["response_not_expired"] is False


def test_07_response_cannot_self_certify_evidence(tmp_path):
    response, item = _response_and_item(tmp_path)
    rows = copy.deepcopy(response.supplied_evidence_records)
    rows[0]["PCE_status"] = "Certified"
    response = replace(response, supplied_evidence_records=rows)
    result = validate_human_review_response(response=response, item=item, current_state="OPEN", validated_at=response.submitted_at)
    assert result.status == ResponseValidationStatus.REJECTED
    assert result.checks["response_does_not_self_certify"] is False


def test_08_invalid_response_remains_in_history(invalid_resume):
    result, output = invalid_resume
    responses = _read(output / "human_review" / "human_review_responses.json")
    validations = _read(output / "human_review" / "response_validation_results.json")
    assert responses[-1]["response_id"] == "HR-RESPONSE-INVALID-001"
    assert validations[-1]["status"] == "REJECTED"
    assert result["resume_summary"]["resumed"] is False


def test_09_invalid_response_keeps_gap_and_item_open(invalid_resume):
    _, output = invalid_resume
    assert _read(output / "research_gap.json")["status"] == "OPEN"
    assert _read(output / "human_review" / "review_item_history.json")[-1]["state"] == "OPEN"
    assert _read(output / "human_review" / "gap_resolution_history.json") == []


def test_10_invalid_response_does_not_change_certification_or_terminal(invalid_resume):
    result, output = invalid_resume
    assert _read(output / "claims.json")[0]["pce_status"] == "Not Certified"
    terminal_history = _read(output / "state" / "terminal_state_history.json")
    assert len(terminal_history) == 1
    assert result["terminal_state_before"] == result["terminal_state_after"]


def test_11_original_review_item_remains_append_only(valid_resume):
    _, output, _, _ = valid_resume
    history = _read(output / "human_review" / "review_item_history.json")
    assert [row["state"] for row in history] == ["OPEN", "RESPONSE_RECEIVED", "CONDITIONALLY_RESOLVED"]
    assert history[0]["version_id"] == "HR-HUMAN-001-V1"


def test_12_original_paused_terminal_state_remains(valid_resume):
    _, output, _, _ = valid_resume
    history = _read(output / "state" / "terminal_state_history.json")
    assert [row["sequence_number"] for row in history] == [1, 2]
    assert history[0]["status"] == "AWAITING_HUMAN_REVIEW"
    assert history[1]["supersedes_terminal_state_id"] == history[0]["terminal_state_id"]


def test_13_original_claim_and_evidence_versions_remain(valid_resume):
    _, output, before_claims, before_evidence = valid_resume
    claim_history = _read(output / "resume" / "claim_version_history.json")
    evidence_after = _read(output / "evidence.json")
    assert claim_history[0] == before_claims[0]
    assert before_evidence[0] in evidence_after
    assert claim_history[1]["previous_claim_version"] == "CLM-HUMAN-001-V1"


def test_14_accepted_response_appends_management_source_and_evidence(valid_resume):
    _, output, _, _ = valid_resume
    source = next(row for row in _read(output / "sources.json") if row["source_id"] == "SRC-HR-MGMT-001")
    evidence = next(row for row in _read(output / "evidence.json") if row["evidence_id"] == "EV-HR-MGMT-001")
    assert source["source_type"] == "confidential management representation"
    assert "not independent public evidence" in source["limitations"]
    assert evidence["claim_id"] == "CLM-HUMAN-001"


def test_15_resume_starts_at_smallest_module_and_reruns_dependency(valid_resume):
    result, _, _, _ = valid_resume
    assert result["resume_summary"]["modules_rerun"] == [
        "Target Capability & Business Quality", "Strategic Fit"
    ]


def test_16_resume_does_not_rerun_unrelated_modules(valid_resume):
    result, _, _, _ = valid_resume
    assert result["resume_summary"]["modules_not_rerun"] == [
        "Buyer Strategic Need", "Strategic Rationale", "Target Attractiveness",
        "Industry / Competitive Position",
    ]


def test_17_only_relevant_gate_and_calculations_rerun(valid_resume):
    result, _, _, _ = valid_resume
    assert [row["gate_name"] for row in result["resume_summary"]["gates_rerun"]] == ["Strategic Thesis Gate"]
    assert result["resume_summary"]["calculations_rerun"] == []
    assert result["resume_summary"]["previous_gate_results_preserved"] is True


def test_18_gap_is_conditionally_closed_after_admissibility_review(valid_resume):
    result, _, _, _ = valid_resume
    gap = result["resume_summary"]["gaps_changed"][0]
    assert gap["status"] == "CONDITIONALLY_CLOSED"
    assert gap["remaining_conditions"]
    assert "receipt alone did not close" in gap["explanation"]


def test_19_pre_and_post_resume_terminal_states_are_distinct(valid_resume):
    result, _, _, _ = valid_resume
    assert result["terminal_state_before"]["status"] == "AWAITING_HUMAN_REVIEW"
    assert result["terminal_state_after"].status.value == "COMPLETED_CONDITIONAL_STRATEGIC_THESIS"
    assert result["terminal_state_before"]["terminal_state_id"] != result["terminal_state_after"].terminal_state_id


def test_20_seven_complete_reporting_prompts_load():
    prompts = load_reporting_prompts()
    assert len(prompts) == 7
    assert "FINAL_ACQUISITION_STRATEGY_REPORT_WRITER" in prompts
    assert all(row["citation_requirements"] and row["blocked_claim_handling"] for row in prompts.values())


def test_21_all_required_reporting_files_exist(complete_run):
    _, output = complete_run
    required = [
        "final_acquisition_strategy_report.md", "executive_decision_summary.md",
        "evidence_appendix.md", "calculation_appendix.md", "human_review_pack.md",
        "report_manifest.json", "final_delivery_verification.json",
        "final_delivery_certificate.json",
    ]
    assert all((output / "reporting" / name).is_file() for name in required)


def test_22_report_contains_exactly_28_required_sections(complete_run):
    _, output = complete_run
    report = (output / "reporting" / "final_acquisition_strategy_report.md").read_text(encoding="utf-8")
    headings = [line.split(". ", 1)[1] for line in report.splitlines() if line.startswith("## ")]
    assert headings == SECTION_TITLES


def test_23_fact_inference_assumption_unknown_categories_remain_distinct(complete_run):
    _, output = complete_run
    report = (output / "reporting" / "final_acquisition_strategy_report.md").read_text(encoding="utf-8")
    for label in ("**Facts**", "**Inferences**", "**Assumptions**", "**Unknowns**"):
        assert label in report
    assert "ASM-B2-01" in report and "UNK-A5-01" in report


def test_24_caveats_counterevidence_and_open_reviews_are_visible(complete_run):
    _, output = complete_run
    report = (output / "reporting" / "final_acquisition_strategy_report.md").read_text(encoding="utf-8")
    assert "CE-C3-01" in report
    assert "HR-C2-01" in report and "HR-C3-01" in report and "HR-C5-01" in report
    assert "Caveats and conditions" in report


def test_25_source_evidence_calculation_and_gate_ids_appear(complete_run):
    _, output = complete_run
    report = (output / "reporting" / "final_acquisition_strategy_report.md").read_text(encoding="utf-8")
    for value in ("CL-B3", "SRC-MODEL", "EV-B3", "CAL-EV", "GATE_A", "GATE_B", "GATE_C"):
        assert value in report


def test_26_decision_state_is_not_human_approval(complete_run):
    _, output = complete_run
    report = (output / "reporting" / "final_acquisition_strategy_report.md").read_text(encoding="utf-8").lower()
    assert "proceed_with_conditions" in report
    assert "not final authorized human approval" in report


def test_27_management_representations_are_labeled_not_independent(complete_run, valid_resume):
    _, output = complete_run
    _, resume_output, _, _ = valid_resume
    evidence_appendix = (output / "reporting" / "evidence_appendix.md").read_text(encoding="utf-8")
    resume_pack = (resume_output / "reporting" / "human_review_pack.md").read_text(encoding="utf-8")
    assert "not independent public evidence" in evidence_appendix
    assert "not independent public evidence" in resume_pack


def test_28_manifest_covers_every_section_and_hashes_verify(complete_run):
    _, output = complete_run
    manifest = _read(output / "reporting" / "report_manifest.json")
    verification = _read(output / "reporting" / "final_delivery_verification.json")
    assert len(manifest["sections"]) == 28
    assert {row["section_id"] for row in manifest["sections"]} == {f"section-{index:02d}" for index in range(1,29)}
    assert verification["checks"]["manifest_hashes_match"] is True


def test_29_complete_case_delivery_is_caveated_not_approval(complete_run):
    result, output = complete_run
    verification = _read(output / "reporting" / "final_delivery_verification.json")
    assert verification["delivery_outcome"] == "DELIVERABLE_WITH_CAVEATS"
    assert verification["business_decision_state"] == "PROCEED_WITH_CONDITIONS"
    assert result["run_summary"]["final_narrative_report_generated"] is True


def test_30_calculation_replay_failure_blocks_delivery(complete_run):
    result, _ = complete_run
    calculations = to_primitive(result["calculations"])
    calculations[0]["replay_status"] = "FAIL"
    verification = _verify_again(result, calculations=calculations)
    assert verification["delivery_outcome"] == DeliveryOutcome.NOT_DELIVERABLE
    assert verification["calculation_replay_failures"]


def test_31_delivery_blocking_human_review_requires_human(complete_run):
    result, _ = complete_run
    reviews = list(_read(COMPLETE_CASE)["human_review_items"])
    reviews[0] = {**reviews[0], "delivery_blocking": True}
    verification = _verify_again(result, human_reviews=reviews)
    assert verification["delivery_outcome"] == DeliveryOutcome.HUMAN_REVIEW_REQUIRED


def test_32_missing_lineage_blocks_delivery(complete_run):
    result, _ = complete_run
    claims = to_primitive(result["claims"])
    claims[0]["evidence_ids"] = ["EV-NOT-REGISTERED"]
    verification = _verify_again(result, claims=claims)
    assert verification["delivery_outcome"] == DeliveryOutcome.NOT_DELIVERABLE
    assert any(row["type"] == "MISSING_LINEAGE" for row in verification["blocking_issues"])


def test_33_blocked_claim_cannot_be_presented_as_verified(complete_run):
    result, _ = complete_run
    claims = to_primitive(result["claims"])
    claim = next(row for row in claims if row["claim_id"] == "CL-C2")
    claim["delivery_allowed"] = False
    manifest = copy.deepcopy(result["reporting_package"]["manifest"])
    section = next(row for row in manifest if row["section_id"] == "section-16")
    section["excluded_or_blocked_claim_ids"] = ["CL-C2"]
    verification = _verify_again(result, claims=claims, manifest=manifest)
    assert verification["delivery_outcome"] == DeliveryOutcome.NOT_DELIVERABLE
    assert any(row["type"] == "BLOCKED_CLAIM_PRESENTED_AS_VERIFIED" for row in verification["blocking_issues"])


def test_34_economic_no_go_may_still_be_deliverable(complete_run):
    result, _ = complete_run
    decision = to_primitive(result["decision_state"])
    decision["state"] = "NO_GO"
    report_text = result["reporting_package"]["report_path"].read_text(encoding="utf-8") + "\nNO_GO\n"
    verification = _verify_again(result, decision=decision, report_text=report_text)
    assert verification["delivery_outcome"] == DeliveryOutcome.DELIVERABLE_WITH_CAVEATS


def test_35_gate_pass_does_not_override_delivery_failure(complete_run):
    result, _ = complete_run
    calculations = to_primitive(result["calculations"])
    calculations[0]["replay_status"] = "FAIL"
    gates = to_primitive(result["gates"])
    for gate in gates:
        gate["status"] = "PASS"
    verification = _verify_again(result, calculations=calculations, gates=gates)
    assert verification["delivery_outcome"] == DeliveryOutcome.NOT_DELIVERABLE
    assert verification["business_gate_pass_does_not_grant_delivery"] is True


def test_36_no_legacy_case_content_appears_in_new_agent():
    forbidden = ("app" + "le", "darwin" + "ai")
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore").lower()
        for root in (AGENT_ROOT, PACKAGE_ROOT)
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    assert all(value not in text for value in forbidden)
