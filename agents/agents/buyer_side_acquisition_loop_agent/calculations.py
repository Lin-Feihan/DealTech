from __future__ import annotations

from decimal import Decimal, getcontext
from typing import Callable

from .business_models import (
    CalculationGap,
    CalculationGapType,
    CalculationInput,
    CalculationRecord,
    CalculationReplayResult,
    CalculationStatus,
    ReplayStatus,
)

getcontext().prec = 28

D = Decimal


REQUIRED_INPUTS: dict[str, tuple[str, ...]] = {
    "enterprise_value": ("equity_value", "net_debt"),
    "equity_value": ("enterprise_value", "net_debt"),
    "ev_revenue": ("enterprise_value", "revenue"),
    "ev_ebitda": ("enterprise_value", "ebitda"),
    "purchase_premium": ("offer_equity_value", "unaffected_equity_value"),
    "net_debt_adjustment": ("debt", "cash"),
    "total_consideration": ("equity_consideration", "assumed_debt", "fees"),
    "synergy_by_period": (
        "revenue_synergy",
        "cost_synergy",
        "capex_synergy",
        "working_capital_synergy",
        "dis_synergy",
        "implementation_cost",
        "recurring_cost",
    ),
    "probability_adjusted_synergy": ("base_synergy", "probability"),
    "invested_capital": ("total_consideration", "implementation_cost", "financing_fees"),
    "roic": ("after_tax_operating_profit", "invested_capital"),
    "payback_period": ("invested_capital", "annual_cash_benefit"),
    "irr": ("cash_flows",),
    "pro_forma_leverage": ("pro_forma_net_debt", "pro_forma_ebitda"),
    "closing_liquidity": (
        "opening_liquidity",
        "cash_consideration",
        "fees",
        "financing_fees",
        "new_debt",
    ),
    "net_debt": ("gross_debt", "cash"),
    "annual_synergy": (
        "revenue_synergy", "cost_synergy", "capex_benefit",
        "working_capital_benefit", "dis_synergy", "recurring_cost",
    ),
    "integration_costs": ("cash_integration_cost", "non_cash_integration_cost"),
    "simple_payback": ("invested_capital", "annual_cash_benefit"),
    "pro_forma_debt": ("existing_debt", "new_debt", "assumed_debt", "refinanced_debt"),
    "liquidity_headroom": ("closing_liquidity", "minimum_liquidity"),
    "premium_adjusted_value_creation": (
        "standalone_value", "probability_adjusted_synergy", "total_consideration",
    ),
}

PERCENT_INPUTS = {"probability"}
NON_CURRENCY_INPUTS = {"probability", "cash_flows"}
NON_SCALE_INPUTS = {"probability"}
PERIOD_COMPATIBILITY_CALCULATIONS = {
    "net_debt", "net_debt_adjustment", "annual_synergy", "synergy_by_period",
    "integration_costs", "total_consideration", "pro_forma_debt",
}
CLASSIFICATION_COMPATIBILITY_CALCULATIONS = {
    "net_debt", "net_debt_adjustment", "annual_synergy", "synergy_by_period",
    "integration_costs",
}
PERIMETER_COMPATIBILITY_CALCULATIONS = {
    "net_debt", "net_debt_adjustment", "annual_synergy", "synergy_by_period",
    "integration_costs", "total_consideration",
}


def _v(inputs: dict[str, CalculationInput], name: str) -> Decimal:
    value = inputs[name].value
    if isinstance(value, list):
        raise ValueError(f"{name} requires a scalar")
    return D(value)


def _series(inputs: dict[str, CalculationInput], name: str) -> list[Decimal]:
    value = inputs[name].value
    if not isinstance(value, list):
        raise ValueError(f"{name} requires a series")
    return [D(item) for item in value]


def _irr_bisection(cash_flows: list[Decimal]) -> Decimal:
    if not cash_flows or cash_flows[0] >= 0 or not any(item > 0 for item in cash_flows[1:]):
        raise ValueError("IRR requires one initial outflow and at least one later inflow")
    low, high = D("-0.9999"), D("10")

    def npv(rate: Decimal) -> Decimal:
        return sum(value / ((D(1) + rate) ** index) for index, value in enumerate(cash_flows))

    if npv(low) * npv(high) > 0:
        raise ValueError("IRR root is not bracketed")
    for _ in range(240):
        midpoint = (low + high) / D(2)
        value = npv(midpoint)
        if abs(value) <= D("0.0000000001"):
            return midpoint
        if npv(low) * value <= 0:
            high = midpoint
        else:
            low = midpoint
    return (low + high) / D(2)


def _irr_newton(cash_flows: list[Decimal]) -> Decimal:
    rate = D("0.1")
    for _ in range(120):
        base = D(1) + rate
        npv = sum(value / (base**index) for index, value in enumerate(cash_flows))
        derivative = sum(
            -D(index) * value / (base ** (index + 1))
            for index, value in enumerate(cash_flows)
            if index
        )
        if derivative == 0:
            raise ValueError("IRR replay derivative is zero")
        next_rate = rate - npv / derivative
        if next_rate <= D("-0.9999"):
            next_rate = (rate + D("-0.9999")) / D(2)
        if abs(next_rate - rate) <= D("0.0000000001"):
            return next_rate
        rate = next_rate
    raise ValueError("IRR replay did not converge")


def _primary(calculation_type: str, inputs: dict[str, CalculationInput]) -> Decimal:
    a = lambda name: _v(inputs, name)
    if calculation_type == "enterprise_value": return a("equity_value") + a("net_debt")
    if calculation_type == "equity_value": return a("enterprise_value") - a("net_debt")
    if calculation_type == "ev_revenue": return a("enterprise_value") / a("revenue")
    if calculation_type == "ev_ebitda": return a("enterprise_value") / a("ebitda")
    if calculation_type == "purchase_premium": return a("offer_equity_value") / a("unaffected_equity_value") - D(1)
    if calculation_type == "net_debt_adjustment": return a("debt") - a("cash")
    if calculation_type == "total_consideration": return a("equity_consideration") + a("assumed_debt") + a("fees")
    if calculation_type == "synergy_by_period":
        return sum(a(name) for name in ("revenue_synergy", "cost_synergy", "capex_synergy", "working_capital_synergy")) - sum(a(name) for name in ("dis_synergy", "implementation_cost", "recurring_cost"))
    if calculation_type == "probability_adjusted_synergy": return a("base_synergy") * a("probability")
    if calculation_type == "invested_capital": return a("total_consideration") + a("implementation_cost") + a("financing_fees")
    if calculation_type == "roic": return a("after_tax_operating_profit") / a("invested_capital")
    if calculation_type == "payback_period": return a("invested_capital") / a("annual_cash_benefit")
    if calculation_type == "irr": return _irr_bisection(_series(inputs, "cash_flows"))
    if calculation_type == "pro_forma_leverage": return a("pro_forma_net_debt") / a("pro_forma_ebitda")
    if calculation_type == "closing_liquidity": return a("opening_liquidity") - a("cash_consideration") - a("fees") - a("financing_fees") + a("new_debt")
    if calculation_type == "net_debt": return a("gross_debt") - a("cash")
    if calculation_type == "annual_synergy":
        return sum(a(name) for name in ("revenue_synergy", "cost_synergy", "capex_benefit", "working_capital_benefit")) - a("dis_synergy") - a("recurring_cost")
    if calculation_type == "integration_costs": return a("cash_integration_cost") + a("non_cash_integration_cost")
    if calculation_type == "simple_payback": return a("invested_capital") / a("annual_cash_benefit")
    if calculation_type == "pro_forma_debt": return a("existing_debt") + a("new_debt") + a("assumed_debt") - a("refinanced_debt")
    if calculation_type == "liquidity_headroom": return a("closing_liquidity") - a("minimum_liquidity")
    if calculation_type == "premium_adjusted_value_creation": return a("standalone_value") + a("probability_adjusted_synergy") - a("total_consideration")
    raise ValueError(f"unsupported calculation type {calculation_type}")


def _replay(calculation_type: str, inputs: dict[str, CalculationInput]) -> Decimal:
    values = {name: _v(inputs, name) for name in inputs if not isinstance(inputs[name].value, list)}
    if calculation_type == "irr": return _irr_newton(_series(inputs, "cash_flows"))
    if calculation_type == "enterprise_value": return sum([values["net_debt"], values["equity_value"]], D(0))
    if calculation_type == "equity_value": return values["enterprise_value"] + (-values["net_debt"])
    if calculation_type in {"ev_revenue", "ev_ebitda"}:
        denominator = values["revenue" if calculation_type == "ev_revenue" else "ebitda"]
        return values["enterprise_value"] * (D(1) / denominator)
    if calculation_type == "purchase_premium": return (values["offer_equity_value"] - values["unaffected_equity_value"]) / values["unaffected_equity_value"]
    if calculation_type == "net_debt_adjustment": return values["debt"] + (-values["cash"])
    if calculation_type == "total_consideration": return sum(values[name] for name in ("equity_consideration", "assumed_debt", "fees"))
    if calculation_type == "synergy_by_period": return sum(values[name] for name in ("revenue_synergy", "cost_synergy", "capex_synergy", "working_capital_synergy")) + sum(-values[name] for name in ("dis_synergy", "implementation_cost", "recurring_cost"))
    if calculation_type == "probability_adjusted_synergy": return values["probability"] * values["base_synergy"]
    if calculation_type == "invested_capital": return sum(values[name] for name in ("total_consideration", "implementation_cost", "financing_fees"))
    if calculation_type == "roic": return values["after_tax_operating_profit"] * (D(1) / values["invested_capital"])
    if calculation_type == "payback_period": return values["invested_capital"] * (D(1) / values["annual_cash_benefit"])
    if calculation_type == "pro_forma_leverage": return values["pro_forma_net_debt"] * (D(1) / values["pro_forma_ebitda"])
    if calculation_type == "closing_liquidity": return sum([values["opening_liquidity"], values["new_debt"], -values["cash_consideration"], -values["fees"], -values["financing_fees"]], D(0))
    if calculation_type == "net_debt": return values["gross_debt"] + (-values["cash"])
    if calculation_type == "annual_synergy":
        positives = sum(values[name] for name in ("revenue_synergy", "cost_synergy", "capex_benefit", "working_capital_benefit"))
        return positives + (-values["dis_synergy"]) + (-values["recurring_cost"])
    if calculation_type == "integration_costs": return sum(values[name] for name in ("cash_integration_cost", "non_cash_integration_cost"))
    if calculation_type == "simple_payback": return values["invested_capital"] * (D(1) / values["annual_cash_benefit"])
    if calculation_type == "pro_forma_debt": return sum([values["existing_debt"], values["new_debt"], values["assumed_debt"], -values["refinanced_debt"]], D(0))
    if calculation_type == "liquidity_headroom": return values["closing_liquidity"] + (-values["minimum_liquidity"])
    if calculation_type == "premium_adjusted_value_creation": return sum([values["standalone_value"], values["probability_adjusted_synergy"], -values["total_consideration"]], D(0))
    raise ValueError(f"unsupported calculation type {calculation_type}")


FORMULAS = {
    "enterprise_value": "equity_value + net_debt",
    "equity_value": "enterprise_value - net_debt",
    "ev_revenue": "enterprise_value / revenue",
    "ev_ebitda": "enterprise_value / ebitda",
    "purchase_premium": "offer_equity_value / unaffected_equity_value - 1",
    "net_debt_adjustment": "debt - cash",
    "total_consideration": "equity_consideration + assumed_debt + fees",
    "synergy_by_period": "revenue + cost + capex + working_capital - dis_synergy - implementation - recurring",
    "probability_adjusted_synergy": "base_synergy * probability",
    "invested_capital": "total_consideration + implementation_cost + financing_fees",
    "roic": "after_tax_operating_profit / invested_capital",
    "payback_period": "invested_capital / annual_cash_benefit",
    "irr": "rate where NPV(cash_flows) = 0",
    "pro_forma_leverage": "pro_forma_net_debt / pro_forma_ebitda",
    "closing_liquidity": "opening_liquidity - cash_consideration - fees - financing_fees + new_debt",
    "net_debt": "gross_debt - cash",
    "annual_synergy": "revenue_synergy + cost_synergy + capex_benefit + working_capital_benefit - dis_synergy - recurring_cost",
    "integration_costs": "cash_integration_cost + non_cash_integration_cost",
    "simple_payback": "invested_capital / annual_cash_benefit",
    "pro_forma_debt": "existing_debt + new_debt + assumed_debt - refinanced_debt",
    "liquidity_headroom": "closing_liquidity - minimum_liquidity",
    "premium_adjusted_value_creation": "standalone_value + probability_adjusted_synergy - total_consideration",
}


def run_calculation(
    *,
    calculation_id: str,
    calculation_type: str,
    owning_module: str,
    scenario: str,
    inputs: list[CalculationInput],
    output_unit: str,
    linked_claim_ids: list[str],
    required_reviewer: str,
    unsupported_assumptions: list[str] | None = None,
    tolerance: Decimal = D("0.000001"),
) -> tuple[CalculationRecord, CalculationReplayResult, CalculationGap | None]:
    by_name = {item.name: item for item in inputs}
    required = REQUIRED_INPUTS.get(calculation_type)
    missing = sorted(set(required or ()) - set(by_name))
    gap_type: CalculationGapType | None = None
    issue: list[str] = []
    status = CalculationStatus.COMPLETED
    if required is None or missing:
        if calculation_type in {"pro_forma_debt", "pro_forma_leverage"}:
            gap_type = CalculationGapType.LEVERAGE_INPUT_MISSING
        elif calculation_type in {"closing_liquidity", "liquidity_headroom"}:
            gap_type = CalculationGapType.LIQUIDITY_INPUT_MISSING
        else:
            gap_type = CalculationGapType.CALCULATION_INPUT_MISSING
        issue = missing or [f"unsupported calculation_type: {calculation_type}"]
        status = CalculationStatus.BLOCKED_INPUT_MISSING
    elif unsupported_assumptions:
        gap_type = CalculationGapType.VALUATION_ASSUMPTION_UNSUPPORTED
        issue = list(unsupported_assumptions)
        status = CalculationStatus.BLOCKED_UNSUPPORTED_ASSUMPTION
    else:
        currencies = {item.currency for item in inputs if item.name not in NON_CURRENCY_INPUTS and item.currency}
        units = {item.unit for item in inputs if item.name not in PERCENT_INPUTS and item.name != "cash_flows"}
        scales = {item.scale for item in inputs if item.name not in NON_SCALE_INPUTS and item.scale}
        periods = {item.period for item in inputs if item.period}
        period_classes = {item.period_classification for item in inputs if item.period_classification}
        metric_classes = {item.metric_classification for item in inputs if item.metric_classification}
        perimeters = {item.company_perimeter for item in inputs if item.company_perimeter}
        if len(currencies) > 1:
            gap_type = CalculationGapType.CURRENCY_MISMATCH
            issue = sorted(currencies)
            status = CalculationStatus.BLOCKED_CURRENCY_MISMATCH
        elif len(units) > 1:
            gap_type = CalculationGapType.UNIT_MISMATCH
            issue = sorted(units)
            status = CalculationStatus.BLOCKED_UNIT_MISMATCH
        elif len(scales) > 1:
            gap_type = CalculationGapType.SCALE_MISMATCH
            issue = sorted(scales)
            status = CalculationStatus.BLOCKED_SCALE_MISMATCH
        elif calculation_type in PERIOD_COMPATIBILITY_CALCULATIONS and len(periods) > 1:
            gap_type = CalculationGapType.PERIOD_MISMATCH
            issue = sorted(periods)
            status = CalculationStatus.BLOCKED_PERIOD_MISMATCH
        elif calculation_type in CLASSIFICATION_COMPATIBILITY_CALCULATIONS and len(period_classes) > 1:
            gap_type = CalculationGapType.ACTUAL_FORECAST_MIX
            issue = sorted(period_classes)
            status = CalculationStatus.BLOCKED_CLASSIFICATION_MISMATCH
        elif calculation_type in CLASSIFICATION_COMPATIBILITY_CALCULATIONS and len(metric_classes) > 1:
            gap_type = CalculationGapType.REPORTED_ADJUSTED_MIX
            issue = sorted(metric_classes)
            status = CalculationStatus.BLOCKED_CLASSIFICATION_MISMATCH
        elif calculation_type in PERIMETER_COMPATIBILITY_CALCULATIONS and len(perimeters) > 1:
            gap_type = CalculationGapType.PERIMETER_MISMATCH
            issue = sorted(perimeters)
            status = CalculationStatus.BLOCKED_PERIMETER_MISMATCH

    output: Decimal | None = None
    replay_output: Decimal | None = None
    replay_status = ReplayStatus.NOT_RUN
    replay_reason = "Calculation was blocked before execution."
    if status == CalculationStatus.COMPLETED:
        try:
            output = _primary(calculation_type, by_name)
            replay_output = _replay(calculation_type, by_name)
            difference = abs(output - replay_output)
            replay_status = ReplayStatus.PASS if difference <= tolerance else ReplayStatus.FAIL
            replay_reason = "Independent formula replay matched within tolerance." if replay_status == ReplayStatus.PASS else "Independent formula replay exceeded tolerance."
            if replay_status == ReplayStatus.FAIL:
                gap_type = CalculationGapType.FORMULA_REPLAY_FAILED
                issue = [format(difference, "f")]
                status = CalculationStatus.FAILED
        except (ArithmeticError, ValueError) as exc:
            gap_type = (
                CalculationGapType.CASH_FLOW_SERIES_INVALID
                if calculation_type == "irr"
                else CalculationGapType.FORMULA_REPLAY_FAILED
            )
            issue = [str(exc)]
            status = CalculationStatus.FAILED
            replay_status = ReplayStatus.FAIL
            replay_reason = str(exc)
    difference = abs(output - replay_output) if output is not None and replay_output is not None else None
    all_source_ids = sorted({value for item in inputs for value in item.source_ids})
    all_evidence_ids = sorted({value for item in inputs for value in item.evidence_ids})
    all_assumption_ids = sorted({value for item in inputs for value in item.assumption_ids})
    all_data_point_ids = sorted({value for item in inputs for value in item.data_point_ids})
    currency = next((item.currency for item in inputs if item.currency), "")
    record = CalculationRecord(
        calculation_id=calculation_id,
        calculation_type=calculation_type,
        owning_module=owning_module,
        scenario=scenario,
        formula_name=calculation_type,
        formula_version="1.0",
        exact_formula=FORMULAS.get(calculation_type, "unsupported"),
        registered_input_values={item.name: item.value for item in inputs},
        units={item.name: item.unit for item in inputs},
        currency=currency,
        source_ids=all_source_ids,
        evidence_ids=all_evidence_ids,
        assumption_ids=all_assumption_ids,
        output=output,
        output_unit=output_unit,
        independent_replay_output=replay_output,
        tolerance=tolerance,
        calculation_status=status,
        replay_status=replay_status,
        limitations=[],
        linked_claim_ids=linked_claim_ids,
        required_reviewer=required_reviewer,
        data_point_ids=all_data_point_ids,
        period=next((item.period for item in inputs if item.period), ""),
        scales={item.name: item.scale for item in inputs},
        period_classifications={item.name: item.period_classification for item in inputs},
        metric_classifications={item.name: item.metric_classification for item in inputs},
        company_perimeters={item.name: item.company_perimeter for item in inputs},
    )
    replay = CalculationReplayResult(
        replay_id=f"REPLAY-{calculation_id}",
        calculation_id=calculation_id,
        independent_method="independent algebraic path" if calculation_type != "irr" else "Newton method independent of bisection",
        replay_output=replay_output,
        original_output=output,
        absolute_difference=difference,
        tolerance=tolerance,
        status=replay_status,
        reason=replay_reason,
    )
    gap = None
    if gap_type:
        gap = CalculationGap(
            gap_id=f"GAP-{calculation_id}",
            gap_type=gap_type,
            calculation_id=calculation_id,
            owning_module=owning_module,
            description=f"{calculation_type} cannot support a decision until this gap is closed.",
            missing_or_conflicting_inputs=issue,
            closure_test="Provide admissible, unit-consistent inputs and obtain an independent replay PASS.",
        )
    return record, replay, gap
