from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from agents.buyer_side_acquisition_loop_agent.block_c_evaluation import dependent_block_c_modules
from agents.buyer_side_acquisition_loop_agent.block_c_models import DownsideScenario, IntegrationRisk
from agents.buyer_side_acquisition_loop_agent.block_c_runtime import (
    _parse_records,
    check_block_c_configuration,
    run_block_c_case,
    validate_block_c_input_bundle,
)
from agents.buyer_side_acquisition_loop_agent.live_research_models import (
    ProviderConfigurationError,
    ProviderValidationStatus,
)
from agents.buyer_side_acquisition_loop_agent.provider_validation import validate_provider_output


AGENT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "buyer_side_acquisition_loop_agent"
CASE_ROOT = AGENT_ROOT / "06_examples" / "recorded_block_c_case"
CASE_PATH = CASE_ROOT / "case.yaml"
LIVE_TEMPLATE = AGENT_ROOT / "06_examples" / "live_block_c_provider_case_template" / "case.yaml"


@pytest.fixture(scope="module")
def block_c_run(tmp_path_factory):
    output = tmp_path_factory.mktemp("milestone_8") / "run"
    result = run_block_c_case(CASE_PATH, output, provider="recorded", module="BLOCK_C")
    return result, output


def _json(output: Path, relative: str):
    return json.loads(output.joinpath(relative).read_text(encoding="utf-8"))


def test_01_c1_c5_execute_with_approved_prompts(block_c_run):
    _, output = block_c_run
    rows = _json(output, "02_modules/module_executions.json")
    assert [row["module_id"] for row in rows] == ["C1", "C2", "C3", "C4", "C5", "C2", "C4", "C5"]
    assert all(row["prompt_reference"].startswith("03_prompts/block_c_prompts.json#") for row in rows)
    assert {row["module_id"] for row in rows} == {"C1", "C2", "C3", "C4", "C5"}


def test_02_selected_workstreams_are_respected(block_c_run):
    _, output = block_c_run
    plan = _json(output, "00_input/block_c_research_plan.json")
    findings = _json(output, "03_risk_records/latest_diligence_findings.json")
    selected = {"financial", "technology", "cybersecurity"}
    assert set(plan["selected_diligence_workstreams"]) == selected
    assert {row["workstream"] for row in findings} == selected


def test_03_unselected_workstream_cannot_be_marked_complete():
    row = {
        "finding_id": "DF-X", "workstream": "tax", "issue": "test", "finding_type": "test",
        "severity": "low", "materiality": "immaterial", "source_ids": [], "evidence_ids": [],
        "affected_claim_ids": [], "counterevidence_ids": [], "classification": "unknown",
        "supported_impact": "none", "required_follow_up": "none", "mitigation": "monitor",
        "human_review_required": False, "confidentiality": "public", "status": "OPEN",
        "version": 1, "provider_attempt_id": "ATTEMPT-X",
    }
    with pytest.raises(ProviderConfigurationError, match="unselected"):
        _parse_records("C1", {"diligence_findings": [row]}, ["financial"])


@pytest.mark.parametrize("field", ["gate_c_result", "decision_state", "delivery_permission", "final_human_transaction_approval"])
def test_04_provider_cannot_select_reserved_outcomes(block_c_run, field):
    _, output = block_c_run
    payload = _json(output, "provider/C1/attempt_01/admitted_objects.json")
    raw = _json(output, "provider/C1/attempt_01/provider_response_raw.json")["recorded_response"]
    assert payload["claims"]
    raw[field] = {"status": "PASS"}
    validation = validate_provider_output(
        raw, expected_module_id="C1", expected_module_name="Due Diligence", require_counterevidence=True,
    )
    assert validation.status == ProviderValidationStatus.REJECTED
    assert any(item["type"] == "PROVIDER_GATE_AUTHORITY_VIOLATION" for item in validation.errors)


def test_05_provider_c5_decision_field_must_remain_empty(block_c_run):
    _, output = block_c_run
    payload = _json(output, "provider/C5/attempt_01/provider_response_raw.json")["recorded_response"]
    assert payload["module_assessment"]["structured_output"]["decision_state"] == []
    payload["module_assessment"]["structured_output"]["decision_state"] = ["PROCEED"]
    validation = validate_provider_output(
        payload, expected_module_id="C5", expected_module_name="Decision State", require_counterevidence=True,
    )
    assert any(item["type"] == "PROVIDER_GATE_AUTHORITY_VIOLATION" for item in validation.errors)


def test_06_uncertain_legal_interpretation_requires_human_review(block_c_run):
    _, output = block_c_run
    row = _json(output, "03_risk_records/latest_regulatory_risks.json")[0]
    row["legal_adviser_review_required"] = False
    with pytest.raises(ProviderConfigurationError, match="Human Review"):
        _parse_records("C2", {"regulatory_risks": [row]}, [])


def test_07_integration_risk_needs_independent_lineage():
    with pytest.raises(ValueError, match="Strategic Fit"):
        IntegrationRisk(
            risk_id="IR-X", integration_domain="technology", dependency="Strategic Fit only",
            severity="high", likelihood="unknown", timing="unknown",
            affected_synergy_or_claim_ids=["A7"], expected_impact="unknown", mitigation="review",
            responsible_owner="integration leader", leading_indicator="unknown",
            human_review_required=True, source_ids=[], evidence_ids=[], assumption_ids=[],
            limitations=["No evidence"], residual_risk="high", status="OPEN", version=1,
            provider_attempt_id="ATTEMPT-X",
        )


def test_08_downside_values_are_not_invented():
    with pytest.raises(ValueError, match="qualitative downside"):
        DownsideScenario(
            scenario_id="DS-X", scenario_name="Unquantified risk", trigger="unknown",
            probability_classification="not quantified", affected_claim_ids=[],
            affected_calculation_ids=[], changed_assumption_ids=[], financial_inputs={},
            resulting_metrics={}, source_ids=[], evidence_ids=[], assumption_ids=[], mitigation="review",
            residual_risk="material", monitoring_indicators=[], human_review_required=True,
            limitations=[], status="OPEN", version=1, provider_attempt_id="ATTEMPT-X",
        )


@pytest.mark.parametrize(
    "module_id,expected",
    [("C1", ["C4", "C5"]), ("C2", ["C4", "C5"]), ("C3", ["C4", "C5"]), ("C4", ["C5"]), ("C5", [])],
)
def test_09_dependency_graph_is_smallest(module_id, expected):
    assert dependent_block_c_modules(module_id) == expected


def test_10_initial_gap_is_precise_and_resolved(block_c_run):
    _, output = block_c_run
    gaps = _json(output, "09_loop/research_gap_history.json")
    assert len(gaps) == 1
    assert gaps[0]["gap_type"] == "EVIDENCE_MISSING"
    assert gaps[0]["owning_module"] == "C2"
    assert gaps[0]["status"] == "RESOLVED" and gaps[0]["resolved_iteration"] == 2


def test_11_repair_reruns_only_c2_c4_c5(block_c_run):
    _, output = block_c_run
    rows = _json(output, "09_loop/iteration_records.json")
    assert len(rows) == 2
    assert rows[1]["modules_executed"] == ["C2", "C4", "C5"]
    assert rows[1]["block_a_modules_executed"] == []
    assert rows[1]["block_b_modules_executed"] == []


def test_12_block_a_and_block_b_are_never_executed(block_c_run):
    _, output = block_c_run
    summary = _json(output, "run_summary.json")
    assert summary["block_a_research_executed"] is False
    assert summary["block_b_research_executed"] is False
    assert all(row["module_id"].startswith("C") for row in _json(output, "02_modules/module_executions.json"))


def test_13_gate_a_and_gate_b_histories_are_immutable(block_c_run):
    _, output = block_c_run
    after = _json(output, "00_input/upstream_integrity_after.json")
    original = json.loads(CASE_PATH.read_text(encoding="utf-8"))["block_c_input_bundle"]
    copied = _json(output, "00_input/block_c_input_bundle.json")
    assert after["fingerprint_unchanged"] is True
    assert copied["gate_a_history"] == original["gate_a_history"]
    assert copied["gate_b_history"] == original["gate_b_history"]


def test_14_modified_upstream_artifact_is_rejected():
    case = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    case["block_c_input_bundle"]["calculations"][0]["output"] = "499"
    with pytest.raises(ProviderConfigurationError, match="Modified or invalid"):
        validate_block_c_input_bundle(case)


def test_15_mismatched_case_id_and_missing_gate_provenance_are_rejected():
    case = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    mismatched = copy.deepcopy(case)
    mismatched["block_c_input_bundle"]["case_id"] = "OTHER"
    with pytest.raises(ProviderConfigurationError, match="mismatched case IDs"):
        validate_block_c_input_bundle(mismatched)
    missing = copy.deepcopy(case)
    missing["block_c_input_bundle"]["gate_a_history"][0].pop("provenance")
    with pytest.raises(ProviderConfigurationError, match="missing Gate provenance"):
        validate_block_c_input_bundle(missing)


def test_16_incomplete_replay_reference_is_rejected():
    case = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    bundle = case["block_c_input_bundle"]
    bundle["calculation_replays"].pop()
    from agents.buyer_side_acquisition_loop_agent.block_c_runtime import canonical_artifact_hash
    bundle["artifact_hashes"]["calculation_replays"] = canonical_artifact_hash(bundle["calculation_replays"])
    with pytest.raises(ProviderConfigurationError, match="Incomplete replay references"):
        validate_block_c_input_bundle(case)


def test_17_gate_c_and_decision_state_are_separate(block_c_run):
    result, output = block_c_run
    gate = _json(output, "05_gate_c/gate_c_result.json")
    decision = _json(output, "05_gate_c/decision_state.json")
    assert gate["gate_id"] == "GATE_C" and gate["status"] == "RENEGOTIATE"
    assert decision["decision_id"].startswith("DECISION-") and decision["state"] == "RENEGOTIATE"
    assert result.gate_c_result != result.decision_state


def test_18_gate_b_renegotiate_price_cannot_become_proceed(block_c_run):
    _, output = block_c_run
    decision = _json(output, "05_gate_c/decision_state.json")
    assert decision["gate_b_status"] == "RENEGOTIATE_PRICE"
    assert decision["state"] == "RENEGOTIATE"
    assert "current terms" in " ".join(decision["rationale"]).lower()


def test_19_gate_c_has_all_20_criteria_and_no_unconditional_pass(block_c_run):
    _, output = block_c_run
    gate = _json(output, "05_gate_c/gate_c_result.json")
    assert len(gate["criteria"]) == 20
    assert gate["status"] == "RENEGOTIATE"
    assert gate["status"] != "PASS"


def test_20_confidential_management_information_stays_labeled(block_c_run):
    _, output = block_c_run
    sources = _json(output, "01_research/source_registry.json")
    management = next(row for row in sources if row["source_id"] == "SRC-C1-MGMT-001")
    assert management["confidentiality_classification"] == "confidential management information"
    assert "management representation" in management["limitations"].lower()


def test_21_report_contains_block_c_identifiers_and_conditions(block_c_run):
    _, output = block_c_run
    report = (output / "reporting" / "final_acquisition_strategy_report.md").read_text(encoding="utf-8")
    for value in ("DF-C1-CYBER-001", "RR-C2-001", "IR-C3-001", "DS-C4-001", "GATE_C", "RENEGOTIATE"):
        assert value in report
    assert "price and return conditions prevent proceeding at the current terms" in report.lower()
    assert "not final authorized human approval" in report.lower()


def test_22_report_and_delivery_outcome_are_independent(block_c_run):
    result, output = block_c_run
    verification = _json(output, "reporting/final_delivery_verification.json")
    assert verification["business_decision_state"] == "RENEGOTIATE"
    assert verification["delivery_outcome"] == "DELIVERABLE_WITH_CAVEATS"
    assert result.delivery_outcome == "DELIVERABLE_WITH_CAVEATS"
    assert verification["policy_boundary"].startswith("Final delivery verification is separate")


def test_23_report_manifest_and_required_artifacts_are_complete(block_c_run):
    _, output = block_c_run
    manifest = _json(output, "reporting/report_manifest.json")
    assert len(manifest["sections"]) == 28
    required = [
        "reporting/final_acquisition_strategy_report.md",
        "reporting/report_manifest.json",
        "reporting/final_delivery_verification.json",
        "state/final_terminal_state.json",
        "05_gate_c/gate_c_result.json",
        "05_gate_c/decision_state.json",
    ]
    assert all(output.joinpath(name).is_file() for name in required)


def test_24_pce_er_brb_and_frozen_replay_checks_complete(block_c_run):
    _, output = block_c_run
    assert _json(output, "04_controls/pce_results.json")["claim_results"]
    assert _json(output, "04_controls/er_brb_results.json")
    validation = _json(output, "00_input/block_c_input_validation.json")
    assert validation["calculation_replay_references_complete"] is True


def test_25_regulatory_and_integration_human_review_boundaries_remain(block_c_run):
    _, output = block_c_run
    reviews = _json(output, "04_controls/human_review_items.json")
    by_id = {row["review_id"]: row for row in reviews}
    assert by_id["HR-C2-LEGAL-001"]["required_reviewer_role"] == "regulatory counsel"
    assert by_id["HR-C3-INTEGRATION-001"]["status"] == "OPEN"
    assert all(row["blocking"] is False for row in reviews)


def test_26_live_template_is_clean_and_dry_run_never_makes_paid_request():
    text = LIVE_TEMPLATE.read_text(encoding="utf-8").lower()
    assert "api_key" not in text and "credential" in text
    check = check_block_c_configuration(LIVE_TEMPLATE, provider="openai_live", module="BLOCK_C", enable_live=False)
    assert check["ready"] is False
    assert check["paid_request_made"] is False
    assert check["live_execution_enabled"] is False
    assert check["checks"]["explicit_live_enable"] is False
    assert any("Invalid BlockCInputBundle" in issue for issue in check["issues"])


def test_27_new_agent_has_no_legacy_case_content_or_plaintext_credentials():
    forbidden = ("app" + "le", "darwin" + "ai")
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore").lower()
        for root in (AGENT_ROOT, PACKAGE_ROOT)
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".py", ".json", ".yaml", ".md"}
        and "__pycache__" not in path.parts and "run_output" not in path.parts
    )
    assert all(term not in text for term in forbidden)
    case_text = CASE_PATH.read_text(encoding="utf-8").lower() + (CASE_ROOT / "recorded_provider_responses.json").read_text(encoding="utf-8").lower()
    assert re.search(r'"api_key"\s*:', case_text) is None
    assert re.search(r"sk-[a-z0-9]{20,}", case_text) is None
