from __future__ import annotations

from decimal import Decimal
from typing import Any

from .block_c_models import (
    BLOCK_C_DEPENDENCIES,
    BLOCK_C_ORDER,
    BlockCInputBundle,
    BlockCResearchGap,
    DiligenceFinding,
    DownsideScenario,
    IntegrationRisk,
    RegulatoryRisk,
)
from .business_models import (
    BusinessBlock,
    BusinessGateResult,
    BusinessGateStatus,
    BusinessMandate,
    BusinessModuleResult,
    CriterionOutcome,
    DecisionState,
    DecisionStateValue,
    GateCriterionResult,
    ReplayStatus,
)
from .models import PCEStatus


def dependent_block_c_modules(module_id: str) -> list[str]:
    affected: set[str] = set()
    frontier = [module_id]
    while frontier:
        current = frontier.pop(0)
        for candidate, dependencies in BLOCK_C_DEPENDENCIES.items():
            if current in dependencies and candidate not in affected:
                affected.add(candidate)
                frontier.append(candidate)
    return [item for item in BLOCK_C_ORDER if item in affected]


def _criterion(
    criterion_id: str,
    name: str,
    outcome: CriterionOutcome,
    reason: str,
    modules: list[str],
    evidence_ids: list[str] | None = None,
    counter_ids: list[str] | None = None,
    conditions: list[str] | None = None,
    human: bool = False,
) -> GateCriterionResult:
    return GateCriterionResult(
        criterion_id=criterion_id,
        criterion_name=name,
        outcome=outcome,
        reason=reason,
        affected_module_ids=modules,
        supporting_evidence_ids=sorted(set(evidence_ids or [])),
        counterevidence_ids=sorted(set(counter_ids or [])),
        conditions=list(conditions or []),
        human_review_required=human,
    )


def _latest_gate(history: list[dict[str, Any]], gate_id: str) -> dict[str, Any]:
    if not history or history[-1].get("gate_id") != gate_id:
        raise ValueError(f"{gate_id} history is missing or incompatible")
    return history[-1]


def _calculation_by_type(bundle: BlockCInputBundle) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in bundle.calculations:
        rows[str(item.get("calculation_type", ""))] = item
    return rows


def evaluate_block_c_gate(
    *,
    module_results: list[BusinessModuleResult],
    findings: list[DiligenceFinding],
    regulatory_risks: list[RegulatoryRisk],
    integration_risks: list[IntegrationRisk],
    downside_scenarios: list[DownsideScenario],
    input_bundle: BlockCInputBundle,
    mandate: BusinessMandate,
    registry: Any,
    certification: dict[str, Any],
    research_gaps: list[BlockCResearchGap],
    human_review_items: list[dict[str, Any]],
) -> BusinessGateResult:
    by_module = {item.module_id: item for item in module_results}
    evidence_by_module = {
        module_id: [row["evidence_id"] for row in registry.evidence if row.get("owning_module") == module_id]
        for module_id in BLOCK_C_ORDER
    }
    counters_by_module = {
        module_id: [row["counterevidence_id"] for row in registry.counterevidence if row.get("owning_module_id") == module_id]
        for module_id in BLOCK_C_ORDER
    }
    selected = set(mandate.selected_diligence_workstreams)
    covered = {item.workstream for item in findings}
    active_gaps = [item for item in research_gaps if item.status == "OPEN"]
    gate_a = _latest_gate(input_bundle.gate_a_history, "GATE_A")
    gate_b = _latest_gate(input_bundle.gate_b_history, "GATE_B")
    calculations = _calculation_by_type(input_bundle)
    criteria: list[GateCriterionResult] = []

    coverage_ok = bool(selected) and selected <= covered and covered <= selected
    criteria.append(_criterion(
        "GC-01", "Diligence scope and coverage",
        CriterionOutcome.PASS if coverage_ok else CriterionOutcome.FAIL,
        "Every selected diligence workstream has a registered finding; unselected workstreams are not marked complete." if coverage_ok else "Selected diligence coverage is incomplete or includes falsely completed unselected workstreams.",
        ["C1"], evidence_by_module["C1"], counters_by_module["C1"],
    ))

    material_open = [item for item in findings if item.materiality.lower() in {"material", "critical"} and item.status.upper() not in {"CLOSED", "MITIGATED"}]
    fatal_findings = [item for item in material_open if item.severity.lower() == "critical" and item.classification == "confirmed" and not item.mitigation.strip()]
    criteria.append(_criterion(
        "GC-02", "Material unresolved findings",
        CriterionOutcome.FAIL if fatal_findings else CriterionOutcome.CONDITION if material_open else CriterionOutcome.PASS,
        "No unmitigated confirmed critical finding remains." if not material_open else "Material diligence findings remain visible as conditions; none is silently treated as resolved." if not fatal_findings else "An unmitigated confirmed critical diligence finding remains.",
        ["C1"], evidence_by_module["C1"], counters_by_module["C1"],
        [item.required_follow_up for item in material_open if item.required_follow_up],
        any(item.human_review_required for item in material_open),
    ))

    regulatory_supported = bool(regulatory_risks) and all(item.source_ids and item.evidence_ids for item in regulatory_risks)
    criteria.append(_criterion(
        "GC-03", "Regulatory feasibility",
        CriterionOutcome.PASS if regulatory_supported else CriterionOutcome.FAIL,
        "Regulatory feasibility is supported by dated evidence and remains conditional on qualified legal advice." if regulatory_supported else "Regulatory feasibility lacks complete Source and Evidence support.",
        ["C2"], evidence_by_module["C2"], counters_by_module["C2"],
    ))
    legal_review = [item for item in regulatory_risks if item.legal_adviser_review_required]
    remedy_conditions = [item.approval_dependency for item in regulatory_risks if item.approval_dependency] + [item.remedy_risk for item in regulatory_risks if item.remedy_risk]
    criteria.append(_criterion(
        "GC-04", "Approval and remedy risk",
        CriterionOutcome.CONDITION if legal_review or remedy_conditions else CriterionOutcome.PASS,
        "Approval timing, closing dependencies and remedy risk remain conditional and are not legal advice." if legal_review or remedy_conditions else "No material approval or remedy condition is registered.",
        ["C2"], evidence_by_module["C2"], counters_by_module["C2"], remedy_conditions, bool(legal_review),
    ))

    integration_supported = bool(integration_risks) and all(item.source_ids and item.evidence_ids for item in integration_risks)
    criteria.append(_criterion(
        "GC-05", "Integration feasibility",
        CriterionOutcome.CONDITION if integration_supported and any(item.status.upper() != "CLOSED" for item in integration_risks) else CriterionOutcome.PASS if integration_supported else CriterionOutcome.FAIL,
        "Integration risks use their own evidence and are not inferred solely from Strategic Fit." if integration_supported else "Integration feasibility lacks independent risk evidence.",
        ["C3"], evidence_by_module["C3"], counters_by_module["C3"],
        [item.mitigation for item in integration_risks if item.status.upper() != "CLOSED" and item.mitigation],
        any(item.human_review_required for item in integration_risks),
    ))
    synergy_risks = [item for item in integration_risks if item.affected_synergy_or_claim_ids]
    criteria.append(_criterion(
        "GC-06", "Synergy dependency risk",
        CriterionOutcome.CONDITION if synergy_risks else CriterionOutcome.PASS,
        "Synergy dependencies and residual integration risk remain explicit." if synergy_risks else "No registered integration risk affects an admitted synergy or Claim.",
        ["C3"], evidence_by_module["C3"], counters_by_module["C3"],
        [item.residual_risk for item in synergy_risks],
    ))

    downside_complete = bool(downside_scenarios) and all(
        (item.financial_inputs and item.resulting_metrics) or (not item.financial_inputs and item.limitations)
        for item in downside_scenarios
    )
    criteria.append(_criterion(
        "GC-07", "Downside resilience",
        CriterionOutcome.CONDITION if downside_complete else CriterionOutcome.FAIL,
        "Quantified scenarios use registered inputs; qualitative material risks retain explicit limitations rather than invented percentages." if downside_complete else "A material downside scenario is incomplete.",
        ["C4"], evidence_by_module["C4"], counters_by_module["C4"],
        [item.residual_risk for item in downside_scenarios],
    ))
    mitigation_ok = all(item.mitigation.strip() for item in [*findings, *integration_risks, *downside_scenarios])
    criteria.append(_criterion(
        "GC-08", "Mitigation credibility",
        CriterionOutcome.PASS if mitigation_ok else CriterionOutcome.CONDITION,
        "Every registered material risk has a stated mitigation or follow-up owner boundary." if mitigation_ok else "One or more mitigations remain incomplete and cannot be invented.",
        ["C1", "C3", "C4"], evidence_by_module["C1"] + evidence_by_module["C3"] + evidence_by_module["C4"], [],
        [] if mitigation_ok else ["Complete mitigation ownership before transaction approval."],
    ))

    leverage = calculations.get("pro_forma_leverage", {}).get("output")
    liquidity = calculations.get("closing_liquidity", {}).get("output")
    financing_ok = leverage is not None and liquidity is not None and Decimal(str(leverage)) <= mandate.maximum_pro_forma_leverage and Decimal(str(liquidity)) >= mandate.minimum_closing_liquidity
    criteria.append(_criterion(
        "GC-09", "Financing and liquidity consistency",
        CriterionOutcome.PASS if financing_ok else CriterionOutcome.FAIL,
        "Frozen replayed leverage and liquidity remain within the Mandate." if financing_ok else "Frozen leverage or liquidity is missing or inconsistent with the Mandate.",
        ["C4", "C5"],
    ))
    irr = calculations.get("irr", {}).get("output")
    roic = calculations.get("roic", {}).get("output")
    returns_ok = irr is not None and roic is not None and Decimal(str(irr)) >= mandate.minimum_irr and Decimal(str(roic)) >= mandate.minimum_roic
    criteria.append(_criterion(
        "GC-10", "Return consistency",
        CriterionOutcome.PASS if returns_ok else CriterionOutcome.CONDITION,
        "Frozen replayed returns clear the Mandate thresholds." if returns_ok else "Frozen replayed returns do not clear all Mandate thresholds; current terms cannot proceed.",
        ["C4", "C5"], conditions=[] if returns_ok else ["Reprice or improve verified cash flows to restore the return hurdles."],
    ))

    gate_a_ok = gate_a["status"] in {"PASS", "CONDITIONAL_PASS"}
    criteria.append(_criterion(
        "GC-11", "Consistency with Gate A", CriterionOutcome.CONDITION if gate_a["status"] == "CONDITIONAL_PASS" else CriterionOutcome.PASS if gate_a_ok else CriterionOutcome.FAIL,
        f"Frozen Gate A status is {gate_a['status']} and its conditions remain immutable.", ["C5"],
        conditions=list(gate_a.get("conditions", [])),
    ))
    gate_b_ok = gate_b["status"] in {"PASS", "CONDITIONAL_PASS", "RENEGOTIATE_PRICE"}
    criteria.append(_criterion(
        "GC-12", "Consistency with Gate B", CriterionOutcome.CONDITION if gate_b["status"] == "RENEGOTIATE_PRICE" else CriterionOutcome.PASS if gate_b_ok else CriterionOutcome.FAIL,
        f"Frozen Gate B status is {gate_b['status']}; Block C cannot override the price decision.", ["C5"],
        conditions=list(gate_b.get("conditions", [])),
    ))
    equity_value = calculations.get("equity_value", {}).get("output")
    mandate_ok = equity_value is not None and Decimal(str(equity_value)) <= mandate.maximum_equity_purchase_price
    criteria.append(_criterion(
        "GC-13", "Mandate compliance", CriterionOutcome.PASS if mandate_ok else CriterionOutcome.CONDITION,
        "Frozen offered Equity Value is within the Mandate." if mandate_ok else "Frozen offered Equity Value exceeds the Mandate; no authorized price or Mandate change is registered.", ["C5"],
        conditions=[] if mandate_ok else ["Reduce Equity Value to the Mandate maximum or obtain explicit authorized Mandate change."],
    ))
    criteria.append(_criterion(
        "GC-14", "Open Research Gaps", CriterionOutcome.FAIL if active_gaps else CriterionOutcome.PASS,
        "No open Block C Research Gap remains." if not active_gaps else "Open Block C Research Gaps remain.",
        sorted({item.owning_module for item in active_gaps} or {"C1"}),
    ))
    criteria.append(_criterion(
        "GC-15", "Open Calculation Gaps", CriterionOutcome.FAIL if input_bundle.open_calculation_gaps else CriterionOutcome.PASS,
        "No frozen Calculation Gap remains." if not input_bundle.open_calculation_gaps else "Frozen Calculation Gaps remain unresolved.",
        ["C4", "C5"],
    ))
    blocking_human = [item for item in human_review_items if item.get("blocking")]
    criteria.append(_criterion(
        "GC-16", "Human Review requirements", CriterionOutcome.FAIL if blocking_human else CriterionOutcome.CONDITION if human_review_items else CriterionOutcome.PASS,
        "Reserved legal, management and committee judgements remain explicit and separate from the machine Decision State." if human_review_items and not blocking_human else "A blocking Human Review item remains." if blocking_human else "No Human Review item is registered.",
        sorted({item.get("owning_module", "C5") for item in human_review_items} or {"C5"}),
        conditions=[item.get("decision_impact", item.get("issue", "Human Review required")) for item in human_review_items],
        human=bool(human_review_items),
    ))

    pce_rows = certification.get("pce_result", {}).get("claim_results", [])
    pce_ok = bool(pce_rows) and all(row.get("PCE_status") in {PCEStatus.CERTIFIED.value, PCEStatus.CERTIFIED_WITH_CAVEAT.value} for row in pce_rows)
    criteria.append(_criterion("GC-17", "PCE", CriterionOutcome.PASS if pce_ok else CriterionOutcome.FAIL, "PCE completed for all admitted Block C Claims." if pce_ok else "PCE did not clear all admitted Block C Claims.", BLOCK_C_ORDER))
    er_rows = certification.get("er_brb_results", [])
    criteria.append(_criterion("GC-18", "ER/BRB", CriterionOutcome.PASS if er_rows else CriterionOutcome.FAIL, "ER/BRB evidence-row decisioning completed." if er_rows else "ER/BRB evidence-row results are missing.", BLOCK_C_ORDER))
    replay_ok = bool(input_bundle.calculations) and len(input_bundle.calculation_replays) == len(input_bundle.calculations) and all(row.get("status") == "PASS" for row in input_bundle.calculation_replays)
    criteria.append(_criterion("GC-19", "Calculation replay", CriterionOutcome.PASS if replay_ok else CriterionOutcome.FAIL, "Every frozen Calculation has a PASS replay reference." if replay_ok else "Frozen Calculation replay is incomplete or failed.", ["C4", "C5"]))
    precedent_conditions = list(gate_a.get("conditions", [])) + list(gate_b.get("conditions", [])) + [item.required_follow_up for item in material_open if item.required_follow_up]
    criteria.append(_criterion("GC-20", "Conditions precedent", CriterionOutcome.CONDITION if precedent_conditions else CriterionOutcome.PASS, "Conditions precedent remain explicit and traceable." if precedent_conditions else "No condition precedent is registered.", ["C1", "C2", "C3", "C4", "C5"], conditions=precedent_conditions))

    failed = [item.criterion_id for item in criteria if item.outcome == CriterionOutcome.FAIL]
    conditions = list(dict.fromkeys(condition for item in criteria for condition in item.conditions if condition))
    fatal_regulatory = [item for item in regulatory_risks if item.severity.lower() == "critical" and item.current_status.lower() in {"prohibited", "fatal"}]
    if fatal_findings or fatal_regulatory:
        status = BusinessGateStatus.FATAL_RISK
    elif blocking_human:
        status = BusinessGateStatus.HUMAN_REVIEW_REQUIRED
    elif active_gaps or input_bundle.open_calculation_gaps or failed:
        status = BusinessGateStatus.FAIL_RESEARCH_GAP
    elif gate_b["status"] == "RENEGOTIATE_PRICE" or not mandate_ok or not returns_ok:
        status = BusinessGateStatus.RENEGOTIATE
    elif any(item.outcome == CriterionOutcome.CONDITION for item in criteria):
        status = BusinessGateStatus.CONDITIONAL_PASS
    else:
        status = BusinessGateStatus.PASS

    return BusinessGateResult(
        gate_id="GATE_C",
        gate_name="Decision Gate",
        block=BusinessBlock.BLOCK_C,
        status=status,
        criteria=criteria,
        failed_criterion_ids=failed,
        conditions=conditions,
        gap_ids=[item.gap_id for item in active_gaps] + [str(item.get("gap_id", "")) for item in input_bundle.open_calculation_gaps],
        pce_statuses={row["claim_id"]: PCEStatus(row["PCE_status"]) for row in pce_rows},
        er_brb_summary={"record_count": len(er_rows), "scope": "read-only evidence-row control"},
        calculation_replay_statuses={str(row["calculation_id"]): ReplayStatus(row["status"]) for row in input_bundle.calculation_replays},
        human_review_items=[str(item["review_id"]) for item in human_review_items],
        prior_gate_history=[
            *[{"gate_id": "GATE_A", "status": str(item["status"])} for item in input_bundle.gate_a_history],
            *[{"gate_id": "GATE_B", "status": str(item["status"])} for item in input_bundle.gate_b_history],
        ],
        business_reason=f"{sum(item.outcome == CriterionOutcome.PASS for item in criteria)} criteria passed, {sum(item.outcome == CriterionOutcome.CONDITION for item in criteria)} conditional, {len(failed)} failed; Gate C remains separate from the final machine Decision State and human transaction approval.",
    )


def synthesize_decision_state(
    *,
    case_id: str,
    mandate: BusinessMandate,
    input_bundle: BlockCInputBundle,
    gate_c: BusinessGateResult,
    research_gaps: list[BlockCResearchGap],
    human_review_items: list[dict[str, Any]],
) -> DecisionState:
    gate_a = BusinessGateStatus(_latest_gate(input_bundle.gate_a_history, "GATE_A")["status"])
    gate_b = BusinessGateStatus(_latest_gate(input_bundle.gate_b_history, "GATE_B")["status"])
    blocking_human = [item for item in human_review_items if item.get("blocking")]
    open_gaps = [item for item in research_gaps if item.status == "OPEN"]
    if gate_c.status in {BusinessGateStatus.FATAL_RISK, BusinessGateStatus.NO_GO}:
        state = DecisionStateValue.NO_GO
    elif blocking_human or gate_c.status == BusinessGateStatus.HUMAN_REVIEW_REQUIRED:
        state = DecisionStateValue.HUMAN_REVIEW
    elif open_gaps or gate_c.status in {BusinessGateStatus.PAUSE, BusinessGateStatus.FAIL_RESEARCH_GAP}:
        state = DecisionStateValue.PAUSE
    elif gate_b == BusinessGateStatus.RENEGOTIATE_PRICE or gate_c.status == BusinessGateStatus.RENEGOTIATE:
        state = DecisionStateValue.RENEGOTIATE
    elif gate_c.status == BusinessGateStatus.CONDITIONAL_PASS:
        state = DecisionStateValue.PROCEED_WITH_CONDITIONS
    else:
        state = DecisionStateValue.PROCEED
    conditions = list(dict.fromkeys([
        *[str(item) for row in input_bundle.gate_a_history for item in row.get("conditions", [])],
        *[str(item) for row in input_bundle.gate_b_history for item in row.get("conditions", [])],
        *gate_c.conditions,
    ]))
    rationale = [
        f"Frozen Gate A remains {gate_a.value}.",
        f"Frozen Gate B remains {gate_b.value}.",
        f"Gate C completed as {gate_c.status.value} after PCE, ER/BRB and replay checks.",
    ]
    if gate_b == BusinessGateStatus.RENEGOTIATE_PRICE:
        rationale.append("Price and return conditions prevent proceeding at the current terms; no authorized price or Mandate change is registered.")
    return DecisionState(
        decision_id=f"DECISION-{case_id}",
        case_id=case_id,
        state=state,
        gate_a_status=gate_a,
        gate_b_status=gate_b,
        gate_c_status=gate_c.status,
        rationale=rationale,
        conditions=conditions,
        walk_away_triggers=[
            "Confirmed fatal diligence or regulatory risk without an authorized mitigation.",
            "Price, return, leverage or liquidity remains outside the buyer Mandate after authorized negotiation.",
        ],
        unresolved_gap_ids=[item.gap_id for item in open_gaps],
        human_review_items=[str(item["review_id"]) for item in human_review_items],
        authority_boundary=mandate.authority_limit,
    )
