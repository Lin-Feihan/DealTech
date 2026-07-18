from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from agents.buyer_side_acquisition_loop_agent import calculations as calculation_module
from agents.buyer_side_acquisition_loop_agent.business_contracts import (
    load_module_contracts,
    load_prompt_registry,
    validate_contract_prompt_links,
)
from agents.buyer_side_acquisition_loop_agent.business_gates import evaluate_business_gate
from agents.buyer_side_acquisition_loop_agent.business_loop import enter_unified_loop
from agents.buyer_side_acquisition_loop_agent.business_models import (
    BusinessGateStatus,
    CalculationGapType,
    CalculationInput,
    CriterionOutcome,
    DecisionStateValue,
    ReplayStatus,
)
from agents.buyer_side_acquisition_loop_agent.runtime import run_case


AGENT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "buyer_side_acquisition_loop_agent"
CASE_PATH = AGENT_ROOT / "06_examples" / "synthetic_complete_acquisition_case" / "case.yaml"
EXPECTED_MODULES = ["A1","A2","A3","A4","A5","A6","A7","B1","B2","B3","B4","B5","C1","C2","C3","C4","C5"]
EXPECTED_CALCULATIONS = {
    "enterprise_value", "equity_value", "ev_revenue", "ev_ebitda",
    "purchase_premium", "net_debt_adjustment", "total_consideration",
    "synergy_by_period", "probability_adjusted_synergy", "invested_capital",
    "roic", "payback_period", "irr", "pro_forma_leverage", "closing_liquidity",
}


@pytest.fixture(scope="module")
def completed_business_run(tmp_path_factory):
    output = tmp_path_factory.mktemp("milestone_3") / "run"
    return run_case(CASE_PATH, output), output


def _input(name, value, *, unit="USD million", currency="USD"):
    return CalculationInput(
        name=name, value=value, unit=unit, currency=currency,
        source_ids=["SRC-TEST"], evidence_ids=["EV-TEST"], assumption_ids=[],
    )


def _calculation(**overrides):
    values = {
        "calculation_id": "CAL-TEST", "calculation_type": "enterprise_value",
        "owning_module": "B3", "scenario": "base",
        "inputs": [_input("equity_value", "480"), _input("net_debt", "20")],
        "output_unit": "USD million", "linked_claim_ids": ["CL-TEST"],
        "required_reviewer": "finance reviewer",
    }
    values.update(overrides)
    return calculation_module.run_calculation(**values)


def test_01_exactly_17_professional_module_contracts_load():
    contracts = load_module_contracts()
    assert [item.module_id for item in contracts] == EXPECTED_MODULES
    assert len({item.professional_name for item in contracts}) == 17
    assert all(item.required_claims and item.counterevidence_requirements for item in contracts)
    assert all(item.assumption_requirements and item.explicit_unknown_requirements for item in contracts)


def test_02_exactly_35_complete_prompts_load_and_link():
    contracts = load_module_contracts()
    prompts = load_prompt_registry()
    validate_contract_prompt_links(contracts, prompts)
    assert len(prompts) == 35
    assert {item.rsplit("#", 1)[-1] for item in (contract.prompt_reference for contract in contracts)} <= set(prompts)
    assert all(prompt["authority_limits"] and prompt["invention_prohibition"] for prompt in prompts.values())


def test_03_end_to_end_run_reaches_all_gates(completed_business_run):
    result, _ = completed_business_run
    assert result["terminal_state"].modules_executed == EXPECTED_MODULES
    assert [gate.status for gate in result["gates"]] == [
        BusinessGateStatus.PASS,
        BusinessGateStatus.CONDITIONAL_PASS,
        BusinessGateStatus.CONDITIONAL_PASS,
    ]
    assert result["decision_state"].state == DecisionStateValue.PROCEED_WITH_CONDITIONS


def test_04_output_tree_contains_required_structured_artifacts(completed_business_run):
    _, output = completed_business_run
    required = [
        "00_input/mandate.json", "00_input/research_contract.json",
        "01_research/sources.json", "01_research/evidence.json", "01_research/claims.json",
        "01_research/assumptions.json", "01_research/unknowns.json", "01_research/counterevidence.json",
        "03_gate_a/gate_a_result.json", "04_block_b/calculations.json",
        "04_block_b/calculation_replays.json", "05_gate_b/gate_b_result.json",
        "07_gate_c/gate_c_result.json", "07_gate_c/decision_state.json",
        "08_controls/er_brb_results.json", "08_controls/pce_results.json",
        "09_loop/iteration_records.json", "09_loop/terminal_state.json", "run_summary.json",
    ]
    assert all(output.joinpath(item).is_file() for item in required)
    for path in output.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))


def test_05_all_required_calculations_replay(completed_business_run):
    result, _ = completed_business_run
    assert {item.calculation_type for item in result["calculations"]} == EXPECTED_CALCULATIONS
    assert len(result["calculations"]) == 15
    assert not result["calculation_gaps"]
    assert all(item.replay_status == ReplayStatus.PASS for item in result["calculations"])
    outputs = {item.calculation_type:item.output for item in result["calculations"]}
    assert outputs["enterprise_value"] == Decimal("500")
    assert outputs["equity_value"] == Decimal("480")
    assert outputs["purchase_premium"] == Decimal("0.2")
    assert outputs["probability_adjusted_synergy"] == Decimal("12.60")
    assert outputs["roic"] > Decimal("0.10")
    assert outputs["irr"] > Decimal("0.10")
    assert outputs["pro_forma_leverage"] < Decimal("2.50")
    assert outputs["closing_liquidity"] > Decimal("250")


def test_06_decimal_outputs_are_serialized_as_exact_strings(completed_business_run):
    _, output = completed_business_run
    rows = json.loads((output / "04_block_b" / "calculations.json").read_text(encoding="utf-8"))
    assert all(isinstance(item["output"], str) for item in rows)
    assert next(item for item in rows if item["calculation_type"] == "probability_adjusted_synergy")["output"] == "12.60"


def test_07_assumption_unknown_counterevidence_and_review_remain_visible(completed_business_run):
    _, output = completed_business_run
    assumptions = json.loads((output / "01_research" / "assumptions.json").read_text(encoding="utf-8"))
    unknowns = json.loads((output / "01_research" / "unknowns.json").read_text(encoding="utf-8"))
    counter = json.loads((output / "01_research" / "counterevidence.json").read_text(encoding="utf-8"))
    reviews = json.loads((output / "08_controls" / "human_review_items.json").read_text(encoding="utf-8"))
    assert assumptions[0]["assumption_id"] == "ASM-B2-01"
    assert unknowns[0]["unknown_id"] == "UNK-A5-01"
    assert counter[0]["counterevidence_id"] == "CE-C3-01"
    assert {item["required_reviewer_role"] for item in reviews} == {"qualified regulatory counsel", "integration leader", "investment committee"}


def test_08_pce_and_er_brb_are_controls_not_business_gates(completed_business_run):
    result, output = completed_business_run
    pce = json.loads((output / "08_controls" / "pce_results.json").read_text(encoding="utf-8"))
    boundary = json.loads((output / "08_controls" / "certification_adapter_boundary.json").read_text(encoding="utf-8"))
    assert pce["overall_status"] == "Needs Human Review"
    assert result["gates"][-1].status == BusinessGateStatus.CONDITIONAL_PASS
    assert boundary["read_only"] is True
    assert "Neither substitutes" in boundary["meaning"]


def test_09_milestone_4_generates_the_registered_final_report(completed_business_run):
    _, output = completed_business_run
    summary = json.loads((output / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["final_narrative_report_generated"] is True
    assert (output / "reporting" / "final_acquisition_strategy_report.md").is_file()


@pytest.mark.parametrize("gate_index,expected_block", [(0,"Block A"),(1,"Block B"),(2,"Block C")])
def test_10_every_gate_failure_uses_one_unified_targeted_loop(completed_business_run, gate_index, expected_block):
    result, _ = completed_business_run
    original = result["gates"][gate_index]
    failed = replace(
        original, status=BusinessGateStatus.FAIL_RESEARCH_GAP,
        failed_criterion_ids=[original.criteria[0].criterion_id],
        criteria=[replace(original.criteria[0], outcome=CriterionOutcome.FAIL)] + original.criteria[1:],
    )
    event = enter_unified_loop(failed, 2)
    assert set(event) == {"gap_diagnosis", "memory_update", "loop_controller", "replan"}
    assert event["loop_controller"]["return_block"] == expected_block
    assert event["replan"]["scope"] == "targeted_only"
    assert len(event["replan"]["return_modules"]) == 1


def test_11_missing_calculation_input_creates_precise_gap():
    record, replay, gap = _calculation(inputs=[_input("equity_value", "480")])
    assert record.output is None
    assert replay.status == ReplayStatus.NOT_RUN
    assert gap.gap_type == CalculationGapType.CALCULATION_INPUT_MISSING
    assert gap.missing_or_conflicting_inputs == ["net_debt"]


def test_12_unit_mismatch_blocks_output():
    record, _, gap = _calculation(inputs=[_input("equity_value","480"), _input("net_debt","20",unit="USD thousand")])
    assert record.output is None
    assert gap.gap_type == CalculationGapType.UNIT_MISMATCH


def test_13_currency_mismatch_blocks_output():
    record, _, gap = _calculation(inputs=[_input("equity_value","480"), _input("net_debt","20",currency="EUR")])
    assert record.output is None
    assert gap.gap_type == CalculationGapType.CURRENCY_MISMATCH


def test_14_unsupported_assumption_blocks_output():
    record, _, gap = _calculation(unsupported_assumptions=["unverified terminal growth"])
    assert record.output is None
    assert gap.gap_type == CalculationGapType.VALUATION_ASSUMPTION_UNSUPPORTED


def test_15_failed_independent_replay_creates_formula_gap(monkeypatch):
    monkeypatch.setattr(calculation_module, "_replay", lambda *_: Decimal("501"))
    record, replay, gap = _calculation()
    assert replay.status == ReplayStatus.FAIL
    assert record.replay_status == ReplayStatus.FAIL
    assert gap.gap_type == CalculationGapType.FORMULA_REPLAY_FAILED


def test_16_purchase_price_boundary_forces_renegotiation(completed_business_run):
    result, _ = completed_business_run
    calculations = [
        replace(item, output=Decimal("501")) if item.calculation_type == "equity_value" else item
        for item in result["calculations"]
    ]
    block_b = [item.module_result for item in result["bundles"] if item.module_result.module_id.startswith("B")]
    gate = evaluate_business_gate(
        gate_id="GATE_B", module_results=block_b, claims=result["claims"],
        mandate=result["mandate"], calculations=calculations, calculation_gaps=[],
        prior_gates=[result["gates"][0]],
    )
    assert gate.status == BusinessGateStatus.RENEGOTIATE_PRICE


def test_17_new_agent_has_no_legacy_case_names():
    forbidden = ("app" + "le", "darwin" + "ai")
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore").lower()
        for root in (AGENT_ROOT, PACKAGE_ROOT)
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    assert all(term not in text for term in forbidden)


def test_18_gate_b_blocks_an_omitted_required_calculation(completed_business_run):
    result, _ = completed_business_run
    calculations = [item for item in result["calculations"] if item.calculation_type != "irr"]
    block_b = [item.module_result for item in result["bundles"] if item.module_result.module_id.startswith("B")]
    gate = evaluate_business_gate(
        gate_id="GATE_B", module_results=block_b, claims=result["claims"],
        mandate=result["mandate"], calculations=calculations, calculation_gaps=[],
        prior_gates=[result["gates"][0]],
    )
    assert gate.status == BusinessGateStatus.FAIL_CALCULATION_GAP
    assert "GAP-MISSING-CALC-irr" in gate.gap_ids


def test_19_gate_status_union_preserves_all_business_decision_paths():
    assert {item.value for item in BusinessGateStatus} == {
        "PASS", "CONDITIONAL_PASS", "FAIL_RESEARCH_GAP", "FAIL_CALCULATION_GAP",
        "FAIL_MANDATE_GAP", "HUMAN_REVIEW_REQUIRED", "FATAL_STRATEGIC_MISMATCH",
        "RENEGOTIATE_PRICE", "FATAL_VALUE_DESTRUCTION", "RENEGOTIATE", "PAUSE",
        "NO_GO", "FATAL_RISK",
    }
