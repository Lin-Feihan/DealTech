from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

from .models import Claim, Evidence, PCEStatus, Source


class BusinessBlock(str, Enum):
    BLOCK_A = "Block A: Strategic Thesis"
    BLOCK_B = "Block B: Value Creation and Pricing"
    BLOCK_C = "Block C: Risk, Diligence and Decision"


class BusinessGateStatus(str, Enum):
    PASS = "PASS"
    CONDITIONAL_PASS = "CONDITIONAL_PASS"
    FAIL_RESEARCH_GAP = "FAIL_RESEARCH_GAP"
    FAIL_CALCULATION_GAP = "FAIL_CALCULATION_GAP"
    FAIL_MANDATE_GAP = "FAIL_MANDATE_GAP"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    FATAL_STRATEGIC_MISMATCH = "FATAL_STRATEGIC_MISMATCH"
    RENEGOTIATE_PRICE = "RENEGOTIATE_PRICE"
    FATAL_VALUE_DESTRUCTION = "FATAL_VALUE_DESTRUCTION"
    RENEGOTIATE = "RENEGOTIATE"
    PAUSE = "PAUSE"
    NO_GO = "NO_GO"
    FATAL_RISK = "FATAL_RISK"


class CriterionOutcome(str, Enum):
    PASS = "PASS"
    CONDITION = "CONDITION"
    FAIL = "FAIL"


class DecisionStateValue(str, Enum):
    PROCEED = "PROCEED"
    PROCEED_WITH_CONDITIONS = "PROCEED_WITH_CONDITIONS"
    RENEGOTIATE = "RENEGOTIATE"
    PAUSE = "PAUSE"
    NO_GO = "NO_GO"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class CalculationStatus(str, Enum):
    COMPLETED = "COMPLETED"
    BLOCKED_INPUT_MISSING = "BLOCKED_INPUT_MISSING"
    BLOCKED_UNIT_MISMATCH = "BLOCKED_UNIT_MISMATCH"
    BLOCKED_CURRENCY_MISMATCH = "BLOCKED_CURRENCY_MISMATCH"
    BLOCKED_SCALE_MISMATCH = "BLOCKED_SCALE_MISMATCH"
    BLOCKED_PERIOD_MISMATCH = "BLOCKED_PERIOD_MISMATCH"
    BLOCKED_PERIMETER_MISMATCH = "BLOCKED_PERIMETER_MISMATCH"
    BLOCKED_CLASSIFICATION_MISMATCH = "BLOCKED_CLASSIFICATION_MISMATCH"
    BLOCKED_UNSUPPORTED_ASSUMPTION = "BLOCKED_UNSUPPORTED_ASSUMPTION"
    FAILED = "FAILED"


class ReplayStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"


class CalculationGapType(str, Enum):
    CALCULATION_INPUT_MISSING = "CALCULATION_INPUT_MISSING"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    FORMULA_REPLAY_FAILED = "FORMULA_REPLAY_FAILED"
    VALUATION_ASSUMPTION_UNSUPPORTED = "VALUATION_ASSUMPTION_UNSUPPORTED"
    PURCHASE_PRICE_BOUNDARY_MISSING = "PURCHASE_PRICE_BOUNDARY_MISSING"
    RETURN_THRESHOLD_MISSING = "RETURN_THRESHOLD_MISSING"
    SCALE_MISMATCH = "SCALE_MISMATCH"
    PERIOD_MISMATCH = "PERIOD_MISMATCH"
    PERIMETER_MISMATCH = "PERIMETER_MISMATCH"
    ACTUAL_FORECAST_MIX = "ACTUAL_FORECAST_MIX"
    REPORTED_ADJUSTED_MIX = "REPORTED_ADJUSTED_MIX"
    CASH_FLOW_SERIES_INVALID = "CASH_FLOW_SERIES_INVALID"
    LEVERAGE_INPUT_MISSING = "LEVERAGE_INPUT_MISSING"
    LIQUIDITY_INPUT_MISSING = "LIQUIDITY_INPUT_MISSING"


def _required(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")


def _required_list(value: list[Any], name: str) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty list")


@dataclass
class BusinessMandate:
    mandate_id: str
    case_id: str
    perspective: str
    buyer_name: str
    target_name: str
    transaction_type: str
    process_stage: str
    decision_question: str
    strategic_objectives: list[str]
    hard_constraints: list[str]
    currency: str
    unit: str
    as_of_date: str
    maximum_equity_purchase_price: Decimal
    minimum_roic: Decimal
    minimum_irr: Decimal
    maximum_pro_forma_leverage: Decimal
    minimum_closing_liquidity: Decimal
    selected_diligence_workstreams: list[str]
    required_reviewer_roles: list[str]
    authority_limit: str

    def __post_init__(self) -> None:
        for name in (
            "mandate_id",
            "case_id",
            "buyer_name",
            "target_name",
            "transaction_type",
            "process_stage",
            "decision_question",
            "currency",
            "unit",
            "as_of_date",
            "authority_limit",
        ):
            _required(getattr(self, name), name)
        if self.perspective != "buyer-side":
            raise ValueError("BusinessMandate must remain buyer-side")
        for name in (
            "strategic_objectives",
            "hard_constraints",
            "selected_diligence_workstreams",
            "required_reviewer_roles",
        ):
            _required_list(getattr(self, name), name)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BusinessMandate":
        values = dict(data)
        for name in (
            "maximum_equity_purchase_price",
            "minimum_roic",
            "minimum_irr",
            "maximum_pro_forma_leverage",
            "minimum_closing_liquidity",
        ):
            if name not in values or values[name] in (None, ""):
                raise ValueError(f"Mandate threshold {name} cannot be invented")
            values[name] = Decimal(str(values[name]))
        return cls(**values)


@dataclass
class BusinessResearchContract:
    contract_id: str
    case_id: str
    module_ids: list[str]
    gate_ids: list[str]
    source_policy: list[str]
    minimum_evidence_per_claim: int
    required_calculation_types: list[str]
    selected_diligence_workstreams: list[str]
    human_review_triggers: list[str]
    allowed_assumption_policy: str
    unknown_policy: str
    delivery_policy: str

    def __post_init__(self) -> None:
        for name in (
            "contract_id",
            "case_id",
            "allowed_assumption_policy",
            "unknown_policy",
            "delivery_policy",
        ):
            _required(getattr(self, name), name)
        for name in (
            "module_ids",
            "gate_ids",
            "source_policy",
            "required_calculation_types",
            "selected_diligence_workstreams",
            "human_review_triggers",
        ):
            _required_list(getattr(self, name), name)
        if self.minimum_evidence_per_claim < 1:
            raise ValueError("minimum_evidence_per_claim must be positive")


@dataclass
class BusinessModuleContract:
    module_id: str
    professional_name: str
    owning_block: BusinessBlock
    business_purpose: str
    decision_relevance: str
    required_mandate_inputs: list[str]
    required_research_questions: list[str]
    required_claims: list[str]
    preferred_source_types: list[str]
    minimum_evidence_requirements: list[str]
    counterevidence_requirements: list[str]
    assumption_requirements: list[str]
    explicit_unknown_requirements: list[str]
    materiality: str
    dependencies: list[str]
    affected_downstream_modules: list[str]
    calculation_requirements: list[str]
    human_review_triggers: list[str]
    structured_output_fields: list[str]
    possible_gap_types: list[str]
    prompt_reference: str

    def __post_init__(self) -> None:
        for name in (
            "module_id",
            "professional_name",
            "business_purpose",
            "decision_relevance",
            "materiality",
            "prompt_reference",
        ):
            _required(getattr(self, name), name)
        for name in (
            "required_mandate_inputs",
            "required_research_questions",
            "required_claims",
            "preferred_source_types",
            "minimum_evidence_requirements",
            "counterevidence_requirements",
            "assumption_requirements",
            "explicit_unknown_requirements",
            "dependencies",
            "affected_downstream_modules",
            "human_review_triggers",
            "structured_output_fields",
            "possible_gap_types",
        ):
            _required_list(getattr(self, name), name)


@dataclass
class AssumptionRecord:
    assumption_id: str
    owning_module: str
    statement: str
    materiality: str
    basis: str
    supported: bool
    source_ids: list[str]
    evidence_ids: list[str]
    human_review_required: bool


@dataclass
class UnknownRecord:
    unknown_id: str
    owning_module: str
    description: str
    materiality: str
    impact: str
    closure_requirement: str
    human_review_required: bool


@dataclass
class CounterEvidenceRecord:
    counterevidence_id: str
    owning_module: str
    description: str
    source_ids: list[str]
    evidence_ids: list[str]
    affected_claim_ids: list[str]
    disposition: str


@dataclass
class ResearchRequest:
    request_id: str
    case_id: str
    module_id: str
    module_name: str
    owning_block: BusinessBlock
    prompt_reference: str
    research_questions: list[str]
    mandate_id: str
    contract_id: str
    provenance_boundary: str
    buyer_identity: str = ""
    buyer_description: str = ""
    target_identity: str = ""
    target_description: str = ""
    transaction_context: str = ""
    buyer_strategic_need: str = ""
    strategic_rationale: str = ""
    research_question: str = ""
    decision_relevance: str = ""
    required_claim_types: list[str] = field(default_factory=list)
    preferred_source_types: list[str] = field(default_factory=list)
    excluded_source_types: list[str] = field(default_factory=list)
    evidence_threshold: dict[str, Any] = field(default_factory=dict)
    counterevidence_requirement: str = ""
    material_unknowns: list[str] = field(default_factory=list)
    supplied_attachments: list[dict[str, Any]] = field(default_factory=list)
    confidentiality_constraints: list[str] = field(default_factory=list)
    as_of_date: str = ""
    jurisdiction: list[str] = field(default_factory=list)
    prior_attempts: list[dict[str, Any]] = field(default_factory=list)
    open_gaps: list[dict[str, Any]] = field(default_factory=list)
    previous_evidence: list[dict[str, Any]] = field(default_factory=list)
    search_budget: dict[str, Any] = field(default_factory=dict)
    business_purpose: str = ""
    dependency_claims: list[dict[str, Any]] = field(default_factory=list)
    known_facts: list[dict[str, Any]] = field(default_factory=list)
    known_unknowns: list[dict[str, Any]] = field(default_factory=list)
    existing_counterevidence: list[dict[str, Any]] = field(default_factory=list)
    query_budget: int = 0
    tool_call_budget: int = 0
    prohibited_conclusions: list[str] = field(default_factory=list)
    attachment_use: list[str] = field(default_factory=list)


@dataclass
class ResearchResponse:
    response_id: str
    request_id: str
    module_id: str
    prompt_reference: str
    source_ids: list[str]
    evidence_ids: list[str]
    claim_ids: list[str]
    assumption_ids: list[str]
    unknown_ids: list[str]
    counterevidence_ids: list[str]
    result_payload: dict[str, Any]
    provenance: str


@dataclass
class BusinessModuleResult:
    module_id: str
    professional_name: str
    owning_block: BusinessBlock
    prompt_reference: str
    research_question_ids: list[str]
    facts: list[str]
    inferences: list[str]
    assumptions: list[str]
    unknowns: list[str]
    limitations: list[str]
    supporting_evidence_ids: list[str]
    counterevidence_ids: list[str]
    claim_ids: list[str]
    calculation_ids: list[str]
    pce_status: PCEStatus
    er_brb_result: dict[str, Any]
    business_conclusion: str
    human_review_triggers: list[str]
    structured_output: dict[str, Any]
    possible_gap_types: list[str]

    def __post_init__(self) -> None:
        for name in ("module_id", "professional_name", "prompt_reference", "business_conclusion"):
            _required(getattr(self, name), name)
        _required_list(self.research_question_ids, "research_question_ids")
        _required_list(self.claim_ids, "claim_ids")
        _required_list(self.supporting_evidence_ids, "supporting_evidence_ids")
        if not isinstance(self.structured_output, dict) or not self.structured_output:
            raise ValueError("structured_output cannot be empty or free-form only")


@dataclass
class GateCriterionResult:
    criterion_id: str
    criterion_name: str
    outcome: CriterionOutcome
    reason: str
    affected_module_ids: list[str]
    supporting_evidence_ids: list[str]
    counterevidence_ids: list[str]
    conditions: list[str]
    human_review_required: bool


@dataclass
class BusinessGateResult:
    gate_id: str
    gate_name: str
    block: BusinessBlock
    status: BusinessGateStatus
    criteria: list[GateCriterionResult]
    failed_criterion_ids: list[str]
    conditions: list[str]
    gap_ids: list[str]
    pce_statuses: dict[str, PCEStatus]
    er_brb_summary: dict[str, Any]
    calculation_replay_statuses: dict[str, ReplayStatus]
    human_review_items: list[str]
    prior_gate_history: list[dict[str, str]]
    business_reason: str


@dataclass
class CalculationInput:
    name: str
    value: str | list[str]
    unit: str
    currency: str
    source_ids: list[str]
    evidence_ids: list[str]
    assumption_ids: list[str]
    data_point_ids: list[str] = field(default_factory=list)
    scale: str = ""
    period: str = ""
    period_classification: str = ""
    metric_classification: str = ""
    company_perimeter: str = ""


@dataclass
class CalculationRecord:
    calculation_id: str
    calculation_type: str
    owning_module: str
    scenario: str
    formula_name: str
    formula_version: str
    exact_formula: str
    registered_input_values: dict[str, str | list[str]]
    units: dict[str, str]
    currency: str
    source_ids: list[str]
    evidence_ids: list[str]
    assumption_ids: list[str]
    output: Decimal | None
    output_unit: str
    independent_replay_output: Decimal | None
    tolerance: Decimal
    calculation_status: CalculationStatus
    replay_status: ReplayStatus
    limitations: list[str]
    linked_claim_ids: list[str]
    required_reviewer: str
    data_point_ids: list[str] = field(default_factory=list)
    period: str = ""
    scales: dict[str, str] = field(default_factory=dict)
    period_classifications: dict[str, str] = field(default_factory=dict)
    metric_classifications: dict[str, str] = field(default_factory=dict)
    company_perimeters: dict[str, str] = field(default_factory=dict)


@dataclass
class CalculationReplayResult:
    replay_id: str
    calculation_id: str
    independent_method: str
    replay_output: Decimal | None
    original_output: Decimal | None
    absolute_difference: Decimal | None
    tolerance: Decimal
    status: ReplayStatus
    reason: str


@dataclass
class CalculationGap:
    gap_id: str
    gap_type: CalculationGapType
    calculation_id: str
    owning_module: str
    description: str
    missing_or_conflicting_inputs: list[str]
    closure_test: str


@dataclass
class DecisionState:
    decision_id: str
    case_id: str
    state: DecisionStateValue
    gate_a_status: BusinessGateStatus
    gate_b_status: BusinessGateStatus
    gate_c_status: BusinessGateStatus
    rationale: list[str]
    conditions: list[str]
    walk_away_triggers: list[str]
    unresolved_gap_ids: list[str]
    human_review_items: list[str]
    authority_boundary: str


@dataclass
class BusinessTerminalState:
    status: str
    case_id: str
    gate_a_status: BusinessGateStatus
    gate_b_status: BusinessGateStatus
    gate_c_status: BusinessGateStatus
    decision_state: DecisionStateValue
    modules_executed: list[str]
    calculations_replayed: int
    open_gap_ids: list[str]
    human_review_items: list[str]
    stopping_reason: str
    generated_artifact_references: list[str]
