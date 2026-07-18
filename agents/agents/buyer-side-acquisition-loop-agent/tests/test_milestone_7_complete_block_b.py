from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.buyer_side_acquisition_loop_agent import calculations as calculation_module
from agents.buyer_side_acquisition_loop_agent.block_b_calculations import (
    mandate_threshold_gaps,
)
from agents.buyer_side_acquisition_loop_agent.block_b_evaluation import (
    dependent_block_b_modules,
    evaluate_block_b_gate,
)
from agents.buyer_side_acquisition_loop_agent.block_b_financials import (
    validate_compatible_financial_points,
)
from agents.buyer_side_acquisition_loop_agent.block_b_models import (
    BLOCK_B_MODULE_NAMES,
    BLOCK_B_ORDER,
    BLOCK_B_REQUIRED_CALCULATIONS,
    BlockBResearchGap,
    BlockBResearchGapType,
    FinancialDataPoint,
    FinancialIntegrityGapType,
    FinancialMetricClass,
    FinancialPeriodClass,
    SynergyRecord,
)
from agents.buyer_side_acquisition_loop_agent.block_b_runtime import run_block_b_case
from agents.buyer_side_acquisition_loop_agent.business_models import (
    BusinessGateStatus,
    BusinessMandate,
    CalculationGap,
    CalculationGapType,
    CalculationInput,
    ReplayStatus,
)
from agents.buyer_side_acquisition_loop_agent.live_research_models import (
    AttachmentValidationError,
    ProviderValidationStatus,
)
from agents.buyer_side_acquisition_loop_agent.provider_validation import validate_provider_output
from agents.buyer_side_acquisition_loop_agent.xlsx_ingestion import extract_xlsx_cells


AGENT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "buyer_side_acquisition_loop_agent"
CASE_ROOT = AGENT_ROOT / "06_examples" / "recorded_block_b_case"
CASE_PATH = CASE_ROOT / "case.yaml"
RECORDING_PATH = CASE_ROOT / "recorded_provider_responses.json"


@pytest.fixture(scope="module")
def block_b_run(tmp_path_factory):
    output = tmp_path_factory.mktemp("milestone_7") / "run"
    result = run_block_b_case(CASE_PATH, output, provider="recorded", module="BLOCK_B")
    return result, output


def _json(output: Path, relative: str):
    return json.loads(output.joinpath(relative).read_text(encoding="utf-8"))


def _point(**overrides) -> FinancialDataPoint:
    values = {
        "data_point_id": "FDP-TEST-01", "owning_module": "B1", "metric": "revenue",
        "value": Decimal("100"), "original_value": Decimal("100"),
        "normalized_value": Decimal("100"), "currency": "USD",
        "unit": "USD million", "scale": "millions", "fiscal_period": "FY2025",
        "period_classification": FinancialPeriodClass.HISTORICAL,
        "metric_classification": FinancialMetricClass.REPORTED,
        "company_perimeter": "target standalone", "source_id": "SRC-TEST",
        "evidence_id": "EV-TEST", "exact_locator": "statement line 1",
        "assumption_ids": [], "limitations": [], "version": 1,
        "provider_attempt_id": "ATTEMPT-TEST-01", "scenario": "base",
    }
    values.update(overrides)
    return FinancialDataPoint(**values)


def _mandate() -> BusinessMandate:
    data = json.loads(CASE_PATH.read_text(encoding="utf-8"))["business_mandate"]
    return BusinessMandate.from_dict(data)


def test_01_all_b1_b5_modules_use_the_approved_prompt(block_b_run):
    _, output = block_b_run
    rows = _json(output, "02_modules/module_executions.json")
    assert [row["module_id"] for row in rows] == ["B1", "B2", "B3", "B4", "B5", "B3", "B5"]
    assert all(row["prompt_reference"].startswith("03_prompts/block_b_prompts.json#") for row in rows)
    assert {row["module_id"] for row in rows} == set(BLOCK_B_MODULE_NAMES)


def test_02_provider_output_cannot_select_gate_b():
    payload = json.loads(RECORDING_PATH.read_text(encoding="utf-8"))["modules"]["B2"]["attempts"][0]["structured_response"]
    payload = json.loads(json.dumps(payload))
    payload["gate_b_result"] = {"status": "PASS"}
    validation = validate_provider_output(
        payload,
        expected_module_id="B2",
        expected_module_name="Synergy Mechanism & Value Creation",
        require_counterevidence=True,
    )
    assert validation.status == ProviderValidationStatus.REJECTED
    assert any(item["type"] == "PROVIDER_GATE_AUTHORITY_VIOLATION" for item in validation.errors)


@pytest.mark.parametrize(
    "module_id,expected",
    [("B1", ["B3", "B5"]), ("B2", ["B3", "B5"]), ("B3", ["B5"]), ("B4", ["B5"]), ("B5", [])],
)
def test_03_dependency_invalidation_is_smallest(module_id, expected):
    assert dependent_block_b_modules(module_id) == expected


@pytest.mark.parametrize("field", ["value", "original_value", "normalized_value"])
def test_04_missing_values_never_become_zero(field):
    row = {
        "data_point_id":"FDP-X", "owning_module":"B1", "metric":"revenue",
        "value":"1", "original_value":"1", "normalized_value":"1",
        "currency":"USD", "unit":"USD million", "scale":"millions",
        "fiscal_period":"FY2025", "period_classification":"historical",
        "metric_classification":"reported", "company_perimeter":"target standalone",
        "source_id":"SRC-X", "evidence_id":"EV-X", "exact_locator":"line 1",
        "assumption_ids":[], "limitations":[], "version":1,
        "provider_attempt_id":"ATTEMPT-X", "scenario":"base",
    }
    row[field] = None
    with pytest.raises(ValueError, match="cannot be missing|never be converted"):
        FinancialDataPoint.from_dict(row)


@pytest.mark.parametrize(
    "changes,gap_type",
    [
        ({"unit": "USD thousand"}, FinancialIntegrityGapType.UNIT_MISMATCH),
        ({"scale": "thousands"}, FinancialIntegrityGapType.SCALE_MISMATCH),
        ({"currency": "EUR"}, FinancialIntegrityGapType.CURRENCY_MISMATCH),
        ({"fiscal_period": "Q4 2025"}, FinancialIntegrityGapType.PERIOD_MISMATCH),
        ({"company_perimeter": "combined company"}, FinancialIntegrityGapType.PERIMETER_MISMATCH),
        ({"period_classification": FinancialPeriodClass.FORECAST}, FinancialIntegrityGapType.ACTUAL_FORECAST_MIX),
        ({"metric_classification": FinancialMetricClass.ADJUSTED}, FinancialIntegrityGapType.REPORTED_ADJUSTED_MIX),
    ],
)
def test_05_financial_compatibility_gaps_are_explicit(changes, gap_type):
    first = _point()
    second = replace(first, data_point_id="FDP-TEST-02", **changes)
    gaps = validate_compatible_financial_points([first, second], owning_module="B1", purpose="test")
    assert gap_type in {item.gap_type for item in gaps}


def test_06_lineage_normalization_and_forecast_classification_are_preserved(block_b_run):
    _, output = block_b_run
    points = _json(output, "03_financial_data/financial_data_points.json")
    revenue = next(row for row in points if row["data_point_id"] == "FDP-B1-REV-A-01")
    forecast = next(row for row in points if row["data_point_id"] == "FDP-B1-REV-F-01")
    assert revenue["original_value"] == "200000" and revenue["normalized_value"] == "200"
    assert revenue["currency"] == "USD" and revenue["scale"] == "millions"
    assert revenue["source_id"] == "SRC-XLSX-FIN" and revenue["exact_locator"] == "Financials!B2"
    assert forecast["period_classification"] == "forecast"
    assert forecast["metric_classification"] == "estimated"
    assert forecast["metric_classification"] != "reported"
    normalizations = _json(output, "03_financial_data/normalization_records.json")
    assert any(row["data_point_id"] == revenue["data_point_id"] and row["conversion_factor"] == "0.001" for row in normalizations)


def test_07_qualitative_strategic_fit_cannot_become_quantified_synergy():
    with pytest.raises(ValueError, match="qualitative synergy"):
        SynergyRecord(
            synergy_id="SYN-QUAL", owning_module="B2", synergy_type="qualitative",
            mechanism="Strategic Fit only", baseline=Decimal("1"), driver=Decimal("0"),
            period="FY2027", currency="USD", unit="USD million", scale="millions",
            realization_rate=Decimal("0"), probability=Decimal("0"), source_ids=[],
            evidence_ids=[], assumption_ids=[], one_time_cost=Decimal("0"),
            recurring_cost=Decimal("0"), dis_synergy=Decimal("0"), dependencies=[],
            downside_assumptions=[], limitations=[], quantified=False, version=1,
            provider_attempt_id="ATTEMPT-QUAL",
        )


def test_08_ev_and_equity_value_remain_distinct(block_b_run):
    _, output = block_b_run
    rows = {row["calculation_type"]: row for row in _json(output, "04_calculations/latest_calculations.json")}
    assert rows["enterprise_value"]["output"] == "540"
    assert rows["equity_value"]["output"] == "520"
    assert rows["net_debt"]["output"] == "20"


def test_09_unsupported_price_creates_one_precise_initial_gap(block_b_run):
    _, output = block_b_run
    gaps = _json(output, "04_calculations/calculation_gap_history.json")
    assert len(gaps) == 1
    assert gaps[0]["gap_type"] == "VALUATION_ASSUMPTION_UNSUPPORTED"
    assert gaps[0]["owning_module"] == "B3"
    assert gaps[0]["status"] == "RESOLVED"


def test_10_capacity_is_not_willingness_to_pay(block_b_run):
    _, output = block_b_run
    b4 = _json(output, "02_modules/b4_executions.json")[0]
    conclusion = b4["result"]["business_conclusion"].lower()
    assert "capacity is not willingness to pay" in conclusion


def test_11_irr_uses_explicit_cash_flows_and_hurdle_is_separate(block_b_run):
    _, output = block_b_run
    irr = next(row for row in _json(output, "04_calculations/latest_calculations.json") if row["calculation_type"] == "irr")
    assert irr["exact_formula"] == "rate where NPV(cash_flows) = 0"
    assert irr["registered_input_values"]["cash_flows"] == ["-592", "90", "110", "130", "160", "300"]
    assert len(irr["data_point_ids"]) == 6
    criterion = next(row for row in _json(output, "06_gate_b/gate_b_result.json")["criteria"] if row["criterion_id"] == "GB-14")
    assert criterion["outcome"] == "CONDITION"
    assert "positive IRR alone is insufficient" in criterion["reason"]


def test_12_missing_hurdle_creates_return_threshold_gap():
    data = json.loads(CASE_PATH.read_text(encoding="utf-8"))["business_mandate"]
    data.pop("minimum_irr")
    gaps = mandate_threshold_gaps(data)
    assert any(item.gap_type == CalculationGapType.RETURN_THRESHOLD_MISSING for item in gaps)


def test_13_replay_is_independent_and_failure_is_a_calculation_gap(monkeypatch):
    inputs = [
        CalculationInput("equity_value", "520", "USD million", "USD", ["SRC"], ["EV"], [], ["FDP-EQ"], "millions", "FY2025", "forecast", "estimated", "target transaction"),
        CalculationInput("net_debt", "20", "USD million", "USD", ["SRC"], ["EV"], [], ["FDP-ND"], "millions", "FY2025", "historical", "reported", "target standalone"),
    ]
    monkeypatch.setattr(calculation_module, "_replay", lambda *_: Decimal("999"))
    record, replay, gap = calculation_module.run_calculation(
        calculation_id="CAL-REPLAY-FAIL", calculation_type="enterprise_value",
        owning_module="B3", scenario="base", inputs=inputs,
        output_unit="USD million", linked_claim_ids=[], required_reviewer="finance reviewer",
    )
    assert record.output == Decimal("540")
    assert replay.replay_output == Decimal("999")
    assert replay.status == ReplayStatus.FAIL
    assert gap.gap_type == CalculationGapType.FORMULA_REPLAY_FAILED


def test_14_xlsx_hash_sheet_cell_and_labels_are_retained(block_b_run, tmp_path):
    _, output = block_b_run
    rows = _json(output, "00_input/xlsx_extraction.json")
    assert rows and all(len(row["file_hash_sha256"]) == 64 for row in rows)
    assert rows[0]["sheet_name"] == "Financials" and rows[0]["locator"] == "B2"
    assert rows[0]["underlying_value"] == "200000"
    assert rows[0]["currency"] == "USD" and rows[0]["scale"] == "thousands"
    bad = tmp_path / "encrypted.xlsx"
    bad.write_bytes(b"not an OOXML workbook")
    with pytest.raises(AttachmentValidationError, match="Encrypted or unsupported"):
        extract_xlsx_cells(bad, [{"sheet_name":"Financials","locator":"B2","unit":"USD","currency":"USD","scale":"thousands"}])


def test_15_research_and_calculation_gaps_are_separate_types():
    research = BlockBResearchGap(
        gap_id="RG-B2", gap_type=BlockBResearchGapType.SYNERGY_MECHANISM_GAP,
        owning_module="B2", description="unsupported synergy", required_action="research",
        closure_test="admit evidence", status="OPEN", created_iteration=1,
    )
    calculation = CalculationGap(
        gap_id="CG-B2", gap_type=CalculationGapType.CALCULATION_INPUT_MISSING,
        calculation_id="CAL-B2", owning_module="B2", description="input missing",
        missing_or_conflicting_inputs=["baseline"], closure_test="supply input",
    )
    assert type(research) is not type(calculation)
    assert research.gap_type.value == "SYNERGY_MECHANISM_GAP"
    assert calculation.gap_type.value == "CALCULATION_INPUT_MISSING"


def test_16_targeted_repair_returns_only_to_b3_and_b5(block_b_run):
    _, output = block_b_run
    iterations = _json(output, "07_loop/iteration_records.json")
    assert len(iterations) == 2
    assert iterations[1]["modules_executed"] == ["B3", "B5"]
    assert iterations[1]["calculation_modules_executed"] == ["B3", "B5"]
    assert all(not module.startswith("A") for row in iterations for module in row["modules_executed"])


def test_17_strategic_fit_alone_cannot_pass_gate_b():
    gate = evaluate_block_b_gate(
        module_results=[], points=[], synergies=[], calculations=[], calculation_gaps=[],
        research_gaps=[], integrity_gaps=[], mandate=_mandate(),
        registry=SimpleNamespace(evidence=[], counterevidence=[], sources=[], assumptions=[], unknowns=[]),
        certification={}, human_review_items=[],
        gate_a_result={"status":"PASS", "admitted_claims":[{"claim_id":"A7", "claim_text":"Strategic Fit"}]},
    )
    assert gate.status not in {BusinessGateStatus.PASS, BusinessGateStatus.CONDITIONAL_PASS, BusinessGateStatus.RENEGOTIATE_PRICE}
    assert len(gate.failed_criterion_ids) > 1


def test_18_recorded_case_is_criteria_derived_and_complete(block_b_run):
    result, output = block_b_run
    summary = _json(output, "run_summary.json")
    gate = _json(output, "06_gate_b/gate_b_result.json")
    latest = _json(output, "04_calculations/latest_calculations.json")
    assert result.outcome.value == "RENEGOTIATE_PRICE"
    assert summary["initial_gate_b_status"] == "FAIL_CALCULATION_GAP"
    assert summary["final_gate_b_status"] == "RENEGOTIATE_PRICE"
    assert len(gate["criteria"]) == 22
    assert {row["calculation_type"] for row in latest} == set(BLOCK_B_REQUIRED_CALCULATIONS)
    assert all(row["replay_status"] == "PASS" for row in latest)
    assert summary["block_c_executed"] is False
    assert summary["transaction_recommendation_generated"] is False


def test_19_duplicate_source_and_human_review_boundary_remain_visible(block_b_run):
    _, output = block_b_run
    duplicates = _json(output, "01_research/duplicate_source_rejections.json")
    reviews = _json(output, "05_controls/human_review_items.json")
    assert duplicates[0]["object_type"] == "DUPLICATE_SOURCE_CANDIDATE"
    assert duplicates[0]["canonical_source_id"] == "SRC-B1-AUDIT"
    assert reviews[0]["required_reviewer_role"] == "treasury reviewer"
    assert reviews[0]["blocking"] is False


def test_20_new_agent_has_no_legacy_case_content_or_plaintext_credentials():
    forbidden = ("app" + "le", "darwin" + "ai")
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore").lower()
        for root in (AGENT_ROOT, PACKAGE_ROOT)
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".py", ".json", ".yaml", ".md"}
        and "__pycache__" not in path.parts and "run_output" not in path.parts
    )
    assert all(term not in text for term in forbidden)
    case = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    assert "api_key" not in json.dumps(case).lower()
