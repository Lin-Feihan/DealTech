from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

from .live_research_models import ProviderMode


BLOCK_B_MODULE_NAMES = {
    "B1": "Standalone Financial Analysis",
    "B2": "Synergy Mechanism & Value Creation",
    "B3": "Valuation & Purchase Price Discipline",
    "B4": "Deal Structure & Financing Impact",
    "B5": "Returns Analysis",
}

BLOCK_B_ORDER = ["B1", "B2", "B3", "B4", "B5"]

# This graph is the Milestone 7 execution contract. Block A inputs may be read,
# but Block A is never executed by the Block B runtime.
BLOCK_B_DEPENDENCIES = {
    "B1": [],
    "B2": [],
    "B3": ["B1", "B2"],
    "B4": [],
    "B5": ["B1", "B2", "B3", "B4"],
}

BLOCK_B_REQUIRED_CALCULATIONS = [
    "enterprise_value",
    "equity_value",
    "net_debt",
    "total_consideration",
    "ev_revenue",
    "ev_ebitda",
    "purchase_premium",
    "annual_synergy",
    "probability_adjusted_synergy",
    "integration_costs",
    "invested_capital",
    "roic",
    "simple_payback",
    "irr",
    "pro_forma_debt",
    "pro_forma_leverage",
    "closing_liquidity",
    "liquidity_headroom",
]


class BlockBOutcome(str, Enum):
    PASS = "PASS"
    CONDITIONAL_PASS = "CONDITIONAL_PASS"
    FAIL_RESEARCH_GAP = "FAIL_RESEARCH_GAP"
    FAIL_CALCULATION_GAP = "FAIL_CALCULATION_GAP"
    FAIL_MANDATE_GAP = "FAIL_MANDATE_GAP"
    RENEGOTIATE_PRICE = "RENEGOTIATE_PRICE"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    FATAL_VALUE_DESTRUCTION = "FATAL_VALUE_DESTRUCTION"
    STOPPED_ITERATION_BUDGET = "STOPPED_ITERATION_BUDGET"
    FAILED_TECHNICAL = "FAILED_TECHNICAL"


class FinancialPeriodClass(str, Enum):
    HISTORICAL = "historical"
    FORECAST = "forecast"


class FinancialMetricClass(str, Enum):
    REPORTED = "reported"
    ADJUSTED = "adjusted"
    ESTIMATED = "estimated"


class FinancialIntegrityGapType(str, Enum):
    UNIT_MISMATCH = "UNIT_MISMATCH"
    SCALE_MISMATCH = "SCALE_MISMATCH"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    PERIOD_MISMATCH = "PERIOD_MISMATCH"
    PERIMETER_MISMATCH = "PERIMETER_MISMATCH"
    ACTUAL_FORECAST_MIX = "ACTUAL_FORECAST_MIX"
    REPORTED_ADJUSTED_MIX = "REPORTED_ADJUSTED_MIX"


class BlockBResearchGapType(str, Enum):
    FINANCIAL_INPUT_MISSING = "FINANCIAL_INPUT_MISSING"
    FORECAST_ASSUMPTION_UNSUPPORTED = "FORECAST_ASSUMPTION_UNSUPPORTED"
    SYNERGY_MECHANISM_GAP = "SYNERGY_MECHANISM_GAP"
    VALUATION_ASSUMPTION_UNSUPPORTED = "VALUATION_ASSUMPTION_UNSUPPORTED"
    PURCHASE_PRICE_INPUT_UNSUPPORTED = "PURCHASE_PRICE_INPUT_UNSUPPORTED"
    FINANCING_INPUT_MISSING = "FINANCING_INPUT_MISSING"
    DOWNSIDE_SCENARIO_GAP = "DOWNSIDE_SCENARIO_GAP"
    CONFIDENTIAL_MANAGEMENT_INFORMATION = "CONFIDENTIAL_MANAGEMENT_INFORMATION"


def _required(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")


@dataclass
class FinancialDataPoint:
    data_point_id: str
    owning_module: str
    metric: str
    value: Decimal
    original_value: Decimal
    normalized_value: Decimal
    currency: str
    unit: str
    scale: str
    fiscal_period: str
    period_classification: FinancialPeriodClass
    metric_classification: FinancialMetricClass
    company_perimeter: str
    source_id: str
    evidence_id: str
    exact_locator: str
    assumption_ids: list[str]
    limitations: list[str]
    version: int
    provider_attempt_id: str
    scenario: str = "base"

    def __post_init__(self) -> None:
        for name in (
            "data_point_id", "owning_module", "metric", "currency", "unit",
            "scale", "fiscal_period", "company_perimeter", "source_id",
            "evidence_id", "exact_locator", "provider_attempt_id", "scenario",
        ):
            _required(getattr(self, name), name)
        self.value = Decimal(str(self.value))
        self.original_value = Decimal(str(self.original_value))
        self.normalized_value = Decimal(str(self.normalized_value))
        if self.value != self.normalized_value:
            raise ValueError("FinancialDataPoint.value must equal normalized_value")
        if self.version < 1:
            raise ValueError("FinancialDataPoint.version must be positive")

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "FinancialDataPoint":
        values = dict(row)
        for name in ("value", "original_value", "normalized_value"):
            if values.get(name) in (None, ""):
                raise ValueError(f"FinancialDataPoint.{name} cannot be missing or converted to zero")
            values[name] = Decimal(str(values[name]))
        values["period_classification"] = FinancialPeriodClass(values["period_classification"])
        values["metric_classification"] = FinancialMetricClass(values["metric_classification"])
        return cls(**values)


@dataclass
class FinancialNormalizationRecord:
    normalization_id: str
    data_point_id: str
    rule: str
    original_value: Decimal
    normalized_value: Decimal
    from_currency: str
    to_currency: str
    from_unit: str
    to_unit: str
    from_scale: str
    to_scale: str
    from_period: str
    to_period: str
    conversion_factor: Decimal
    source_ids: list[str]
    evidence_ids: list[str]
    assumption_ids: list[str]
    limitations: list[str]

    def __post_init__(self) -> None:
        for name in (
            "normalization_id", "data_point_id", "rule", "from_currency",
            "to_currency", "from_unit", "to_unit", "from_scale", "to_scale",
            "from_period", "to_period",
        ):
            _required(getattr(self, name), name)
        self.original_value = Decimal(str(self.original_value))
        self.normalized_value = Decimal(str(self.normalized_value))
        self.conversion_factor = Decimal(str(self.conversion_factor))
        if self.original_value * self.conversion_factor != self.normalized_value:
            raise ValueError("Normalization record does not replay exactly")
        if self.from_currency != self.to_currency and not self.source_ids:
            raise ValueError("Currency conversion requires a sourced conversion record")

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "FinancialNormalizationRecord":
        values = dict(row)
        for name in ("original_value", "normalized_value", "conversion_factor"):
            if values.get(name) in (None, ""):
                raise ValueError(f"FinancialNormalizationRecord.{name} is required")
            values[name] = Decimal(str(values[name]))
        return cls(**values)


@dataclass
class SynergyRecord:
    synergy_id: str
    owning_module: str
    synergy_type: str
    mechanism: str
    baseline: Decimal
    driver: Decimal
    period: str
    currency: str
    unit: str
    scale: str
    realization_rate: Decimal
    probability: Decimal
    source_ids: list[str]
    evidence_ids: list[str]
    assumption_ids: list[str]
    one_time_cost: Decimal
    recurring_cost: Decimal
    dis_synergy: Decimal
    dependencies: list[str]
    downside_assumptions: list[str]
    limitations: list[str]
    quantified: bool
    version: int
    provider_attempt_id: str

    def __post_init__(self) -> None:
        for name in (
            "synergy_id", "owning_module", "synergy_type", "mechanism", "period",
            "currency", "unit", "scale", "provider_attempt_id",
        ):
            _required(getattr(self, name), name)
        for name in (
            "baseline", "driver", "realization_rate", "probability",
            "one_time_cost", "recurring_cost", "dis_synergy",
        ):
            setattr(self, name, Decimal(str(getattr(self, name))))
        if self.quantified and (not self.source_ids or not self.evidence_ids):
            raise ValueError("A quantified synergy requires Source and Evidence lineage")
        if not self.quantified and any(
            value != 0 for value in (self.baseline, self.driver, self.one_time_cost, self.recurring_cost, self.dis_synergy)
        ):
            raise ValueError("A qualitative synergy cannot silently contain quantified value")

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "SynergyRecord":
        return cls(**row)


@dataclass
class FinancialIntegrityGap:
    gap_id: str
    gap_type: FinancialIntegrityGapType
    owning_module: str
    data_point_ids: list[str]
    description: str
    closure_test: str


@dataclass
class BlockBResearchGap:
    gap_id: str
    gap_type: BlockBResearchGapType
    owning_module: str
    description: str
    required_action: str
    closure_test: str
    status: str
    created_iteration: int
    resolved_iteration: int | None = None
    supersedes_gap_id: str = ""


@dataclass
class BlockBResearchPlan:
    plan_id: str
    case_id: str
    module_order: list[str]
    dependency_graph: dict[str, list[str]]
    module_questions: dict[str, list[str]]
    required_periods: list[str]
    transaction_currency: str
    reporting_currency: str
    reporting_unit: str
    required_calculations: list[str]
    price_thresholds: dict[str, str]
    return_thresholds: dict[str, str]
    financing_thresholds: dict[str, str]
    attachment_permissions: dict[str, list[str]]
    research_budgets: dict[str, dict[str, Any]]
    repair_budget: dict[str, Any]
    human_review_boundaries: list[str]
    prompt_manifest: dict[str, str]


@dataclass
class BlockBModuleExecution:
    module_id: str
    module_name: str
    version: int
    iteration: int
    request_id: str
    provider_attempt_id: str
    prompt_reference: str
    dependency_claim_ids: list[str]
    status: str
    result: dict[str, Any]
    financial_data_point_ids: list[str]
    synergy_ids: list[str]
    calculation_ids: list[str]
    pce_statuses: dict[str, str]
    er_brb_statuses: dict[str, Any]
    gap_ids: list[str] = field(default_factory=list)
    invalidated_by: list[str] = field(default_factory=list)


@dataclass
class BlockBRunResult:
    case_id: str
    provider_mode: ProviderMode
    outcome: BlockBOutcome
    output_dir: str
    iterations: int
    module_executions: int
    gate_b_result: dict[str, Any]
    terminal_state: dict[str, Any]
