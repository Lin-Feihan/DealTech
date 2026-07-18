from __future__ import annotations

from decimal import Decimal
from typing import Any

from .business_models import (
    BusinessBlock,
    BusinessGateResult,
    BusinessGateStatus,
    BusinessMandate,
    BusinessModuleResult,
    CalculationGap,
    CalculationRecord,
    CriterionOutcome,
    GateCriterionResult,
    ReplayStatus,
)
from .models import Claim, PCEStatus


GATE_MODULES = {
    "GATE_A": [
        ("A1", "Transaction Context"), ("A2", "Buyer Strategic Need"),
        ("A3", "Strategic Rationale"), ("A4", "Target Attractiveness"),
        ("A5", "Target Capability & Business Quality"),
        ("A6", "Industry / Competitive Position"), ("A7", "Strategic Fit"),
    ],
    "GATE_B": [
        ("B1", "Standalone Financial Analysis"),
        ("B2", "Synergy Mechanism & Value Creation"),
        ("B3", "Valuation & Purchase Price Discipline"),
        ("B4", "Deal Structure & Financing Impact"),
        ("B5", "Returns Analysis"),
    ],
    "GATE_C": [
        ("C1", "Due Diligence"), ("C2", "Regulatory Risk"),
        ("C3", "Integration Risk"), ("C4", "Downside Risk"),
        ("C5", "Decision State"),
    ],
}

BLOCK_BY_GATE = {
    "GATE_A": BusinessBlock.BLOCK_A,
    "GATE_B": BusinessBlock.BLOCK_B,
    "GATE_C": BusinessBlock.BLOCK_C,
}

REQUIRED_GATE_B_CALCULATIONS = {
    "enterprise_value", "equity_value", "ev_revenue", "ev_ebitda",
    "purchase_premium", "net_debt_adjustment", "total_consideration",
    "synergy_by_period", "probability_adjusted_synergy", "invested_capital",
    "roic", "payback_period", "irr", "pro_forma_leverage", "closing_liquidity",
}


def _criterion(
    module_id: str,
    name: str,
    module: BusinessModuleResult | None,
    claims: list[Claim],
) -> GateCriterionResult:
    module_claims = [claim for claim in claims if claim.business_module == name]
    if module is None:
        return GateCriterionResult(
            criterion_id=f"CRIT-{module_id}", criterion_name=name,
            outcome=CriterionOutcome.FAIL, reason="Required business module result is missing.",
            affected_module_ids=[module_id], supporting_evidence_ids=[], counterevidence_ids=[],
            conditions=[], human_review_required=False,
        )
    requested = str(module.structured_output.get("criterion_outcome", "PASS"))
    outcome = CriterionOutcome(requested)
    conditions = list(module.structured_output.get("conditions", []))
    human = bool(module.human_review_triggers or any(claim.human_review_required for claim in module_claims))
    if not module.supporting_evidence_ids or not module_claims:
        outcome = CriterionOutcome.FAIL
    if any(claim.pce_status == PCEStatus.NOT_CERTIFIED for claim in module_claims):
        outcome = CriterionOutcome.FAIL
    reason = module.business_conclusion
    return GateCriterionResult(
        criterion_id=f"CRIT-{module_id}", criterion_name=name, outcome=outcome,
        reason=reason, affected_module_ids=[module_id],
        supporting_evidence_ids=list(module.supporting_evidence_ids),
        counterevidence_ids=list(module.counterevidence_ids), conditions=conditions,
        human_review_required=human,
    )


def evaluate_business_gate(
    *,
    gate_id: str,
    module_results: list[BusinessModuleResult],
    claims: list[Claim],
    mandate: BusinessMandate,
    calculations: list[CalculationRecord] | None = None,
    calculation_gaps: list[CalculationGap] | None = None,
    prior_gates: list[BusinessGateResult] | None = None,
) -> BusinessGateResult:
    if gate_id not in GATE_MODULES:
        raise ValueError(f"unknown business gate {gate_id}")
    by_id = {item.module_id: item for item in module_results}
    criteria = [_criterion(module_id, name, by_id.get(module_id), claims) for module_id, name in GATE_MODULES[gate_id]]
    status = BusinessGateStatus.PASS
    conditions = [condition for item in criteria for condition in item.conditions]
    failed = [item.criterion_id for item in criteria if item.outcome == CriterionOutcome.FAIL]
    calc_gaps = calculation_gaps or []
    replay_statuses = {item.calculation_id: item.replay_status for item in calculations or []}
    module_flags = {
        key
        for item in module_results
        for key, value in item.structured_output.items()
        if value is True
    }
    if gate_id == "GATE_A" and any(by_id.get(module_id) and by_id[module_id].structured_output.get("fatal_mismatch") for module_id, _ in GATE_MODULES[gate_id]):
        status = BusinessGateStatus.FATAL_STRATEGIC_MISMATCH
    elif gate_id == "GATE_B" and any(by_id.get(module_id) and by_id[module_id].structured_output.get("fatal_value_destruction") for module_id, _ in GATE_MODULES[gate_id]):
        status = BusinessGateStatus.FATAL_VALUE_DESTRUCTION
    elif gate_id == "GATE_C" and any(by_id.get(module_id) and by_id[module_id].structured_output.get("fatal_risk") for module_id, _ in GATE_MODULES[gate_id]):
        status = BusinessGateStatus.FATAL_RISK
    elif gate_id == "GATE_C" and "no_go" in module_flags:
        status = BusinessGateStatus.NO_GO
    elif gate_id == "GATE_C" and "pause" in module_flags:
        status = BusinessGateStatus.PAUSE
    elif gate_id == "GATE_C" and "renegotiate" in module_flags:
        status = BusinessGateStatus.RENEGOTIATE
    elif "mandate_gap" in module_flags:
        status = BusinessGateStatus.FAIL_MANDATE_GAP
    elif "human_review_blocking" in module_flags:
        status = BusinessGateStatus.HUMAN_REVIEW_REQUIRED
    elif gate_id == "GATE_B" and (
        calc_gaps
        or {item.calculation_type for item in calculations or []} != REQUIRED_GATE_B_CALCULATIONS
        or any(item.replay_status != ReplayStatus.PASS for item in calculations or [])
    ):
        status = BusinessGateStatus.FAIL_CALCULATION_GAP
    elif failed:
        status = BusinessGateStatus.FAIL_RESEARCH_GAP
    elif gate_id == "GATE_B":
        outputs = {item.calculation_type: item.output for item in calculations or []}
        offer = outputs.get("equity_value")
        if offer is not None and offer > mandate.maximum_equity_purchase_price:
            status = BusinessGateStatus.RENEGOTIATE_PRICE
            conditions.append("Reduce equity purchase price to or below the mandate maximum.")
        elif outputs.get("roic") is not None and outputs["roic"] < mandate.minimum_roic:
            status = BusinessGateStatus.RENEGOTIATE_PRICE
            conditions.append("Restore ROIC to the mandate hurdle through price or verified value creation.")
        elif outputs.get("irr") is not None and outputs["irr"] < mandate.minimum_irr:
            status = BusinessGateStatus.RENEGOTIATE_PRICE
            conditions.append("Restore IRR to the mandate hurdle through price or verified cash flows.")
        elif outputs.get("pro_forma_leverage") is not None and outputs["pro_forma_leverage"] > mandate.maximum_pro_forma_leverage:
            status = BusinessGateStatus.RENEGOTIATE
            conditions.append("Restructure financing to remain within the leverage ceiling.")
        elif outputs.get("closing_liquidity") is not None and outputs["closing_liquidity"] < mandate.minimum_closing_liquidity:
            status = BusinessGateStatus.RENEGOTIATE
            conditions.append("Restructure funding to preserve minimum closing liquidity.")
    if status == BusinessGateStatus.PASS and any(item.outcome == CriterionOutcome.CONDITION for item in criteria):
        status = BusinessGateStatus.CONDITIONAL_PASS
    if status == BusinessGateStatus.PASS and conditions:
        status = BusinessGateStatus.CONDITIONAL_PASS
    if gate_id == "GATE_C" and prior_gates:
        blocked = [gate for gate in prior_gates if gate.status not in {BusinessGateStatus.PASS, BusinessGateStatus.CONDITIONAL_PASS}]
        if blocked:
            status = BusinessGateStatus.PAUSE
            conditions.append("Resolve prior gate failure before a decision state can advance.")
    module_claims = [claim for claim in claims if claim.business_module in {name for _, name in GATE_MODULES[gate_id]}]
    pce_statuses = {claim.claim_id: claim.pce_status for claim in module_claims}
    er_summary = {
        "scope": "read-only legacy rule results are stored separately",
        "claims_in_gate": len(module_claims),
        "not_certified": sum(1 for item in module_claims if item.pce_status == PCEStatus.NOT_CERTIFIED),
    }
    human_items = sorted({trigger for item in criteria if item.human_review_required for trigger in (by_id[item.affected_module_ids[0]].human_review_triggers if item.affected_module_ids[0] in by_id else [])})
    return BusinessGateResult(
        gate_id=gate_id,
        gate_name={"GATE_A":"Strategic Thesis Gate","GATE_B":"Value Creation Gate","GATE_C":"Decision Gate"}[gate_id],
        block=BLOCK_BY_GATE[gate_id], status=status, criteria=criteria,
        failed_criterion_ids=failed, conditions=conditions,
        gap_ids=[item.gap_id for item in calc_gaps] + (
            [f"GAP-MISSING-CALC-{name}" for name in sorted(REQUIRED_GATE_B_CALCULATIONS - {item.calculation_type for item in calculations or []})]
            if gate_id == "GATE_B" else []
        ), pce_statuses=pce_statuses,
        er_brb_summary=er_summary, calculation_replay_statuses=replay_statuses,
        human_review_items=human_items,
        prior_gate_history=[{"gate_id": item.gate_id, "status": item.status.value} for item in prior_gates or []],
        business_reason=f"{sum(item.outcome == CriterionOutcome.PASS for item in criteria)} criteria passed, {sum(item.outcome == CriterionOutcome.CONDITION for item in criteria)} conditional, {len(failed)} failed.",
    )
