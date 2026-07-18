from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from .block_b_models import FinancialDataPoint
from .business_models import (
    BusinessMandate,
    CalculationGap,
    CalculationGapType,
    CalculationInput,
    CalculationRecord,
    CalculationReplayResult,
)
from .calculations import run_calculation


CALCULATION_OWNERS = {
    "net_debt": "B1",
    "annual_synergy": "B2",
    "probability_adjusted_synergy": "B2",
    "integration_costs": "B2",
    "enterprise_value": "B3",
    "equity_value": "B3",
    "total_consideration": "B3",
    "ev_revenue": "B3",
    "ev_ebitda": "B3",
    "purchase_premium": "B3",
    "pro_forma_debt": "B4",
    "pro_forma_leverage": "B4",
    "closing_liquidity": "B4",
    "liquidity_headroom": "B4",
    "invested_capital": "B5",
    "roic": "B5",
    "simple_payback": "B5",
    "irr": "B5",
}

CALCULATION_ORDER = [
    "net_debt", "annual_synergy", "probability_adjusted_synergy", "integration_costs",
    "enterprise_value", "equity_value", "total_consideration", "ev_revenue",
    "ev_ebitda", "purchase_premium", "pro_forma_debt", "pro_forma_leverage",
    "closing_liquidity", "liquidity_headroom", "invested_capital", "roic",
    "simple_payback", "irr",
]


def _latest(points: list[FinancialDataPoint]) -> list[FinancialDataPoint]:
    latest: dict[tuple[str, str, str], FinancialDataPoint] = {}
    for point in points:
        key = (point.metric, point.fiscal_period, point.scenario)
        if key not in latest or point.version > latest[key].version:
            latest[key] = point
    return list(latest.values())


def _point(
    points: list[FinancialDataPoint], metric: str, *, scenario: str = "base",
    period: str | None = None,
) -> FinancialDataPoint:
    candidates = [
        item for item in _latest(points)
        if item.metric == metric and item.scenario == scenario
        and (period is None or item.fiscal_period == period)
    ]
    if not candidates:
        raise KeyError(metric)
    if len(candidates) > 1:
        candidates.sort(key=lambda item: (item.period_classification.value != "historical", item.fiscal_period))
    return candidates[-1] if period is None else candidates[0]


def _input(name: str, point: FinancialDataPoint, value: str | list[str] | None = None) -> CalculationInput:
    return CalculationInput(
        name=name,
        value=str(point.value) if value is None else value,
        unit=point.unit,
        currency=point.currency,
        source_ids=[point.source_id],
        evidence_ids=[point.evidence_id],
        assumption_ids=list(point.assumption_ids),
        data_point_ids=[point.data_point_id],
        scale=point.scale,
        period=point.fiscal_period,
        period_classification=point.period_classification.value,
        metric_classification=point.metric_classification.value,
        company_perimeter=point.company_perimeter,
    )


def _derived(
    name: str, value: Decimal, lineage: Iterable[FinancialDataPoint], *,
    unit: str, currency: str, scale: str, period: str,
    period_classification: str, metric_classification: str, perimeter: str,
) -> CalculationInput:
    rows = list(lineage)
    return CalculationInput(
        name=name,
        value=str(value),
        unit=unit,
        currency=currency,
        source_ids=sorted({item.source_id for item in rows}),
        evidence_ids=sorted({item.evidence_id for item in rows}),
        assumption_ids=sorted({value for item in rows for value in item.assumption_ids}),
        data_point_ids=sorted({item.data_point_id for item in rows}),
        scale=scale,
        period=period,
        period_classification=period_classification,
        metric_classification=metric_classification,
        company_perimeter=perimeter,
    )


def _specifications(points: list[FinancialDataPoint], mandate: BusinessMandate) -> dict[str, list[CalculationInput]]:
    actual_period = "FY2025"
    target = "target standalone"
    combined = "combined company"
    historical = "historical"
    reported = "reported"
    estimated = "estimated"
    currency = mandate.currency
    unit = mandate.unit
    scale = "millions"

    revenue = _point(points, "revenue", period=actual_period)
    ebitda = _point(points, "ebitda", period=actual_period)
    cash = _point(points, "cash", period=actual_period)
    gross_debt = _point(points, "gross_debt", period=actual_period)
    net_debt_value = gross_debt.value - cash.value
    offer = _point(points, "offer_equity_value")
    ev_value = offer.value + net_debt_value
    assumed_debt = _point(points, "assumed_debt")
    fees = _point(points, "transaction_fees")
    total_consideration_value = offer.value + assumed_debt.value + fees.value

    revenue_synergy = _point(points, "revenue_synergy")
    cost_synergy = _point(points, "cost_synergy")
    capex_benefit = _point(points, "capex_benefit")
    wc_benefit = _point(points, "working_capital_benefit")
    dis_synergy = _point(points, "dis_synergy")
    recurring_cost = _point(points, "recurring_synergy_cost")
    probability = _point(points, "synergy_probability")
    annual_synergy_value = (
        revenue_synergy.value + cost_synergy.value + capex_benefit.value
        + wc_benefit.value - dis_synergy.value - recurring_cost.value
    )
    cash_integration = _point(points, "cash_integration_cost")
    non_cash_integration = _point(points, "non_cash_integration_cost")
    integration_value = cash_integration.value + non_cash_integration.value

    existing_debt = _point(points, "buyer_existing_debt")
    new_debt = _point(points, "new_debt")
    refinanced_debt = _point(points, "refinanced_debt")
    opening_liquidity = _point(points, "opening_liquidity")
    financing_fees = _point(points, "financing_fees")
    pro_forma_ebitda = _point(points, "pro_forma_ebitda")
    minimum_liquidity = _point(points, "minimum_liquidity")
    pro_forma_debt_value = existing_debt.value + new_debt.value + assumed_debt.value - refinanced_debt.value
    closing_liquidity_value = opening_liquidity.value - offer.value - fees.value - financing_fees.value + new_debt.value

    after_tax_profit = _point(points, "incremental_after_tax_operating_profit")
    annual_cash_benefit = _point(points, "annual_cash_benefit")
    cash_flows = sorted(
        [item for item in _latest(points) if item.metric == "incremental_cash_flow" and item.scenario == "base"],
        key=lambda item: int(item.fiscal_period.replace("T", "")),
    )
    if not cash_flows:
        raise KeyError("incremental_cash_flow")
    invested_capital_value = total_consideration_value + integration_value + financing_fees.value

    return {
        "net_debt": [_input("gross_debt", gross_debt), _input("cash", cash)],
        "annual_synergy": [
            _input("revenue_synergy", revenue_synergy), _input("cost_synergy", cost_synergy),
            _input("capex_benefit", capex_benefit), _input("working_capital_benefit", wc_benefit),
            _input("dis_synergy", dis_synergy), _input("recurring_cost", recurring_cost),
        ],
        "probability_adjusted_synergy": [
            _derived("base_synergy", annual_synergy_value, [revenue_synergy, cost_synergy, capex_benefit, wc_benefit, dis_synergy, recurring_cost], unit=unit, currency=currency, scale=scale, period="FY2027", period_classification="forecast", metric_classification=estimated, perimeter=combined),
            _input("probability", probability),
        ],
        "integration_costs": [_input("cash_integration_cost", cash_integration), _input("non_cash_integration_cost", non_cash_integration)],
        "enterprise_value": [
            _input("equity_value", offer),
            _derived("net_debt", net_debt_value, [gross_debt, cash], unit=unit, currency=currency, scale=scale, period=actual_period, period_classification=historical, metric_classification=reported, perimeter=target),
        ],
        "equity_value": [
            _derived("enterprise_value", ev_value, [offer, gross_debt, cash], unit=unit, currency=currency, scale=scale, period=actual_period, period_classification=historical, metric_classification=reported, perimeter=target),
            _derived("net_debt", net_debt_value, [gross_debt, cash], unit=unit, currency=currency, scale=scale, period=actual_period, period_classification=historical, metric_classification=reported, perimeter=target),
        ],
        "total_consideration": [_input("equity_consideration", offer), _input("assumed_debt", assumed_debt), _input("fees", fees)],
        "ev_revenue": [
            _derived("enterprise_value", ev_value, [offer, gross_debt, cash], unit=unit, currency=currency, scale=scale, period=actual_period, period_classification=historical, metric_classification=reported, perimeter=target),
            _input("revenue", revenue),
        ],
        "ev_ebitda": [
            _derived("enterprise_value", ev_value, [offer, gross_debt, cash], unit=unit, currency=currency, scale=scale, period=actual_period, period_classification=historical, metric_classification=reported, perimeter=target),
            _input("ebitda", ebitda),
        ],
        "purchase_premium": [_input("offer_equity_value", offer), _input("unaffected_equity_value", _point(points, "unaffected_equity_value"))],
        "pro_forma_debt": [_input("existing_debt", existing_debt), _input("new_debt", new_debt), _input("assumed_debt", assumed_debt), _input("refinanced_debt", refinanced_debt)],
        "pro_forma_leverage": [
            _derived("pro_forma_net_debt", pro_forma_debt_value, [existing_debt, new_debt, assumed_debt, refinanced_debt], unit=unit, currency=currency, scale=scale, period="closing", period_classification="forecast", metric_classification=estimated, perimeter=combined),
            _input("pro_forma_ebitda", pro_forma_ebitda),
        ],
        "closing_liquidity": [_input("opening_liquidity", opening_liquidity), _input("cash_consideration", offer), _input("fees", fees), _input("financing_fees", financing_fees), _input("new_debt", new_debt)],
        "liquidity_headroom": [
            _derived("closing_liquidity", closing_liquidity_value, [opening_liquidity, offer, fees, financing_fees, new_debt], unit=unit, currency=currency, scale=scale, period="closing", period_classification="forecast", metric_classification=estimated, perimeter=combined),
            _input("minimum_liquidity", minimum_liquidity),
        ],
        "invested_capital": [
            _derived("total_consideration", total_consideration_value, [offer, assumed_debt, fees], unit=unit, currency=currency, scale=scale, period="closing", period_classification="forecast", metric_classification=estimated, perimeter=combined),
            _derived("implementation_cost", integration_value, [cash_integration, non_cash_integration], unit=unit, currency=currency, scale=scale, period="closing", period_classification="forecast", metric_classification=estimated, perimeter=combined),
            _input("financing_fees", financing_fees),
        ],
        "roic": [
            _input("after_tax_operating_profit", after_tax_profit),
            _derived("invested_capital", invested_capital_value, [offer, assumed_debt, fees, cash_integration, non_cash_integration, financing_fees], unit=unit, currency=currency, scale=scale, period="FY2027", period_classification="forecast", metric_classification=estimated, perimeter=combined),
        ],
        "simple_payback": [
            _derived("invested_capital", invested_capital_value, [offer, assumed_debt, fees, cash_integration, non_cash_integration, financing_fees], unit=unit, currency=currency, scale=scale, period="FY2027", period_classification="forecast", metric_classification=estimated, perimeter=combined),
            _input("annual_cash_benefit", annual_cash_benefit),
        ],
        "irr": [
            CalculationInput(
                name="cash_flows", value=[str(item.value) for item in cash_flows],
                unit=unit, currency=currency,
                source_ids=sorted({item.source_id for item in cash_flows}),
                evidence_ids=sorted({item.evidence_id for item in cash_flows}),
                assumption_ids=sorted({value for item in cash_flows for value in item.assumption_ids}),
                data_point_ids=[item.data_point_id for item in cash_flows], scale=scale,
                period="T0-T5", period_classification="forecast",
                metric_classification=estimated, company_perimeter=combined,
            )
        ],
    }


def run_block_b_calculations(
    *, points: list[FinancialDataPoint], mandate: BusinessMandate,
    iteration: int, module_ids: set[str] | None = None,
    unsupported_price_assumptions: list[str] | None = None,
) -> tuple[list[CalculationRecord], list[CalculationReplayResult], list[CalculationGap]]:
    inputs_by_type = _specifications(points, mandate)
    selected = module_ids or {"B1", "B2", "B3", "B4", "B5"}
    records: list[CalculationRecord] = []
    replays: list[CalculationReplayResult] = []
    gaps: list[CalculationGap] = []
    for calculation_type in CALCULATION_ORDER:
        owner = CALCULATION_OWNERS[calculation_type]
        if owner not in selected:
            continue
        output_unit = "ratio" if calculation_type in {"ev_revenue", "ev_ebitda", "purchase_premium", "roic", "irr", "pro_forma_leverage"} else "years" if calculation_type == "simple_payback" else mandate.unit
        record, replay, gap = run_calculation(
            calculation_id=f"CAL-{owner}-{calculation_type.upper()}-V{iteration}",
            calculation_type=calculation_type,
            owning_module=owner,
            scenario="base",
            inputs=inputs_by_type[calculation_type],
            output_unit=output_unit,
            linked_claim_ids=[],
            required_reviewer="finance reviewer",
        )
        records.append(record)
        replays.append(replay)
        if gap:
            gaps.append(gap)
    if unsupported_price_assumptions and "B3" in selected:
        gaps.append(
            CalculationGap(
                gap_id=f"GAP-CAL-B3-PRICE-SUPPORT-V{iteration}",
                gap_type=CalculationGapType.VALUATION_ASSUMPTION_UNSUPPORTED,
                calculation_id=f"CAL-B3-PRICE-SUPPORT-V{iteration}",
                owning_module="B3",
                description="The offered Equity Value is computationally replayable but is not supported by an admissible transaction-term Source.",
                missing_or_conflicting_inputs=list(unsupported_price_assumptions),
                closure_test="Obtain an admissible transaction-term Source and rerun B3 plus dependent B5 analysis.",
            )
        )
    return records, replays, gaps


def latest_calculations(records: list[CalculationRecord]) -> list[CalculationRecord]:
    latest: dict[str, CalculationRecord] = {}
    for record in records:
        latest[record.calculation_type] = record
    return [latest[name] for name in CALCULATION_ORDER if name in latest]


def mandate_threshold_gaps(mandate_data: dict[str, object]) -> list[CalculationGap]:
    """Classify absent decision thresholds without inventing a fallback hurdle."""

    specifications = [
        ("maximum_equity_purchase_price", CalculationGapType.PURCHASE_PRICE_BOUNDARY_MISSING, "B3"),
        ("minimum_roic", CalculationGapType.RETURN_THRESHOLD_MISSING, "B5"),
        ("minimum_irr", CalculationGapType.RETURN_THRESHOLD_MISSING, "B5"),
        ("maximum_pro_forma_leverage", CalculationGapType.LEVERAGE_INPUT_MISSING, "B4"),
        ("minimum_closing_liquidity", CalculationGapType.LIQUIDITY_INPUT_MISSING, "B4"),
    ]
    gaps = []
    for field, gap_type, module_id in specifications:
        if mandate_data.get(field) in (None, ""):
            gaps.append(
                CalculationGap(
                    gap_id=f"GAP-MANDATE-{field.upper()}",
                    gap_type=gap_type,
                    calculation_id=f"MANDATE-{field}",
                    owning_module=module_id,
                    description=f"Mandate threshold {field} is missing and cannot be invented.",
                    missing_or_conflicting_inputs=[field],
                    closure_test=f"An authorized buyer representative supplies {field}.",
                )
            )
    return gaps
