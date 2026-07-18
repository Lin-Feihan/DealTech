from __future__ import annotations

from typing import Any

from .block_b_calculations import latest_calculations
from .block_b_models import (
    BLOCK_B_DEPENDENCIES,
    BLOCK_B_MODULE_NAMES,
    BLOCK_B_ORDER,
    BLOCK_B_REQUIRED_CALCULATIONS,
    BlockBResearchGap,
    FinancialDataPoint,
    FinancialIntegrityGap,
    SynergyRecord,
)
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
from .models import PCEStatus


def dependent_block_b_modules(module_id: str) -> list[str]:
    affected: set[str] = set()
    frontier = [module_id]
    while frontier:
        current = frontier.pop(0)
        for candidate, dependencies in BLOCK_B_DEPENDENCIES.items():
            if current in dependencies and candidate not in affected:
                affected.add(candidate)
                frontier.append(candidate)
    return [item for item in BLOCK_B_ORDER if item in affected]


def _criterion(
    criterion_id: str, name: str, outcome: CriterionOutcome, reason: str,
    modules: list[str], evidence_ids: list[str], counter_ids: list[str],
    conditions: list[str] | None = None, human: bool = False,
) -> GateCriterionResult:
    return GateCriterionResult(
        criterion_id=criterion_id,
        criterion_name=name,
        outcome=outcome,
        reason=reason,
        affected_module_ids=modules,
        supporting_evidence_ids=sorted(set(evidence_ids)),
        counterevidence_ids=sorted(set(counter_ids)),
        conditions=list(conditions or []),
        human_review_required=human,
    )


def evaluate_block_b_gate(
    *, module_results: list[BusinessModuleResult], points: list[FinancialDataPoint],
    synergies: list[SynergyRecord], calculations: list[CalculationRecord],
    calculation_gaps: list[CalculationGap], research_gaps: list[BlockBResearchGap],
    integrity_gaps: list[FinancialIntegrityGap], mandate: BusinessMandate,
    registry: Any, certification: dict[str, Any], human_review_items: list[dict[str, Any]],
    gate_a_result: dict[str, Any],
) -> BusinessGateResult:
    by_module = {item.module_id: item for item in module_results}
    latest_calcs = latest_calculations(calculations)
    calc_by_type = {item.calculation_type: item for item in latest_calcs}
    point_metrics = {item.metric for item in points}
    evidence_by_module = {
        module_id: [row["evidence_id"] for row in registry.evidence if row.get("owning_module") == module_id]
        for module_id in BLOCK_B_ORDER
    }
    counters_by_module = {
        module_id: [row["counterevidence_id"] for row in registry.counterevidence if row.get("owning_module_id") == module_id]
        for module_id in BLOCK_B_ORDER
    }
    criteria: list[GateCriterionResult] = []

    b1_required = {"revenue", "ebitda", "free_cash_flow", "cash", "gross_debt"}
    b1_ok = "B1" in by_module and b1_required <= point_metrics
    criteria.append(_criterion("GB-01", "Standalone financial sufficiency", CriterionOutcome.PASS if b1_ok else CriterionOutcome.FAIL, "Historical earnings, cash conversion and net-debt inputs are separately traceable." if b1_ok else "Material standalone financial inputs are missing.", ["B1"], evidence_by_module["B1"], counters_by_module["B1"]))

    data_ok = not integrity_gaps and any(item.original_value != item.normalized_value for item in points)
    criteria.append(_criterion("GB-02", "Period and data quality", CriterionOutcome.PASS if data_ok else CriterionOutcome.FAIL, "Financial periods, currencies, units, scales, classifications and perimeters are controlled with explicit normalization." if data_ok else "Financial compatibility or normalization is incomplete.", ["B1"], evidence_by_module["B1"], counters_by_module["B1"]))

    forecast_points = [item for item in points if item.period_classification.value == "forecast" and item.owning_module == "B1"]
    forecast_ok = bool(forecast_points) and all(item.metric_classification.value != "reported" for item in forecast_points)
    criteria.append(_criterion("GB-03", "Forecast quality", CriterionOutcome.CONDITION if forecast_ok else CriterionOutcome.FAIL, "Management forecast remains separately classified and subject to stated limitations." if forecast_ok else "Forecast evidence is missing or misclassified as audited actuals.", ["B1"], evidence_by_module["B1"], counters_by_module["B1"], ["Validate management forecast drivers during financial diligence."] if forecast_ok else []))

    quantified = [item for item in synergies if item.quantified]
    synergy_ok = bool(quantified) and all(item.mechanism and item.dependencies for item in quantified)
    criteria.append(_criterion("GB-04", "Synergy credibility", CriterionOutcome.PASS if synergy_ok else CriterionOutcome.FAIL, "Synergies are mechanism-based rather than inferred from Strategic Fit." if synergy_ok else "Synergy mechanism support is insufficient.", ["B2"], evidence_by_module["B2"], counters_by_module["B2"]))
    quantified_ok = bool(quantified) and all(item.source_ids and item.evidence_ids for item in quantified)
    criteria.append(_criterion("GB-05", "Quantified synergy support", CriterionOutcome.PASS if quantified_ok else CriterionOutcome.FAIL, "Every quantified synergy retains baseline, driver, timing, probability and lineage." if quantified_ok else "A quantified synergy lacks required lineage.", ["B2"], evidence_by_module["B2"], counters_by_module["B2"]))
    cost_ok = {"cash_integration_cost", "non_cash_integration_cost", "dis_synergy"} <= point_metrics
    criteria.append(_criterion("GB-06", "Implementation costs and dis-synergies", CriterionOutcome.PASS if cost_ok else CriterionOutcome.FAIL, "Implementation costs, recurring costs and dis-synergies are explicit." if cost_ok else "Costs or dis-synergies are missing.", ["B2"], evidence_by_module["B2"], counters_by_module["B2"]))

    valuation_range_ok = bool(by_module.get("B3") and by_module["B3"].structured_output.get("valuation_range"))
    criteria.append(_criterion("GB-07", "Valuation range", CriterionOutcome.PASS if valuation_range_ok else CriterionOutcome.FAIL, "Base and downside valuation ranges are recorded without invented market inputs." if valuation_range_ok else "Valuation range is unsupported.", ["B3"], evidence_by_module["B3"], counters_by_module["B3"]))
    offer = calc_by_type.get("equity_value")
    price_supported = not any(item.owning_module == "B3" for item in calculation_gaps)
    price_over = bool(offer and offer.output is not None and offer.output > mandate.maximum_equity_purchase_price)
    price_outcome = CriterionOutcome.CONDITION if price_supported and price_over else CriterionOutcome.PASS if price_supported else CriterionOutcome.FAIL
    criteria.append(_criterion("GB-08", "Purchase-price discipline", price_outcome, "Verified offered Equity Value exceeds the buyer Mandate boundary." if price_over else "Offered Equity Value is compared with the explicit Mandate boundary." if price_supported else "Purchase-price support remains unresolved.", ["B3"], evidence_by_module["B3"], counters_by_module["B3"], ["Reduce Equity Value to the Mandate maximum or obtain explicit buyer authority."] if price_over else []))
    comparable_ok = any("comparable" in str(row.get("source_type", "")).lower() or "precedent" in str(row.get("source_type", "")).lower() for row in registry.sources)
    criteria.append(_criterion("GB-09", "Comparable evidence", CriterionOutcome.CONDITION if comparable_ok else CriterionOutcome.FAIL, "Comparable evidence is admitted with stated limitations." if comparable_ok else "No admissible comparable or precedent evidence supports the valuation context.", ["B3"], evidence_by_module["B3"], counters_by_module["B3"], ["Refresh comparable evidence before price approval."] if comparable_ok else []))

    structure_ok = "B4" in by_module and bool(by_module["B4"].structured_output.get("consideration_mix"))
    criteria.append(_criterion("GB-10", "Structure feasibility", CriterionOutcome.PASS if structure_ok else CriterionOutcome.FAIL, "Cash, debt, assumed debt, fees and contingent terms are separately identified." if structure_ok else "Deal structure is incomplete.", ["B4"], evidence_by_module["B4"], counters_by_module["B4"]))
    financing_ok = {"new_debt", "opening_liquidity", "financing_fees"} <= point_metrics
    criteria.append(_criterion("GB-11", "Financing constraints", CriterionOutcome.CONDITION if financing_ok else CriterionOutcome.FAIL, "Financing capacity is assessed separately from willingness to pay; funding remains subject to approval." if financing_ok else "Financing inputs are missing.", ["B4"], evidence_by_module["B4"], counters_by_module["B4"], ["Treasury must confirm funding availability and terms."] if financing_ok else [], human=financing_ok))
    leverage = calc_by_type.get("pro_forma_leverage")
    liquidity = calc_by_type.get("closing_liquidity")
    threshold_ok = bool(leverage and liquidity and leverage.output is not None and liquidity.output is not None and leverage.output <= mandate.maximum_pro_forma_leverage and liquidity.output >= mandate.minimum_closing_liquidity)
    criteria.append(_criterion("GB-12", "Leverage and liquidity", CriterionOutcome.PASS if threshold_ok else CriterionOutcome.FAIL, "Pro forma leverage and closing liquidity remain inside Mandate constraints." if threshold_ok else "Leverage or liquidity breaches or lacks a Mandate threshold.", ["B4"], evidence_by_module["B4"], counters_by_module["B4"]))

    calc_types = {item.calculation_type for item in latest_calcs}
    replay_ok = set(BLOCK_B_REQUIRED_CALCULATIONS) <= calc_types and all(item.replay_status == ReplayStatus.PASS for item in latest_calcs) and not any(item.gap_type.value == "FORMULA_REPLAY_FAILED" for item in calculation_gaps)
    criteria.append(_criterion("GB-13", "Calculation replay", CriterionOutcome.PASS if replay_ok else CriterionOutcome.FAIL, "All required Block B formulas were independently reconstructed within tolerance." if replay_ok else "Required calculation replay is incomplete or failed.", ["B1", "B2", "B3", "B4", "B5"], [row["evidence_id"] for row in registry.evidence], []))
    roic = calc_by_type.get("roic")
    irr = calc_by_type.get("irr")
    returns_ok = bool(roic and irr and roic.output is not None and irr.output is not None and roic.output >= mandate.minimum_roic and irr.output >= mandate.minimum_irr)
    criteria.append(_criterion("GB-14", "Return threshold", CriterionOutcome.PASS if returns_ok else CriterionOutcome.CONDITION if roic and irr else CriterionOutcome.FAIL, "ROIC and explicit-cash-flow IRR exceed the Mandate hurdles." if returns_ok else "Returns do not clear all Mandate hurdles; positive IRR alone is insufficient.", ["B5"], evidence_by_module["B5"], counters_by_module["B5"], [] if returns_ok else ["Reprice or improve verified cash flows to restore hurdle compliance."]))
    downside_ok = bool(by_module.get("B5") and any("downside" in item.lower() for item in by_module["B5"].structured_output.get("scenarios", [])))
    criteria.append(_criterion("GB-15", "Downside case", CriterionOutcome.PASS if downside_ok else CriterionOutcome.FAIL, "A separate downside cash-flow case is retained." if downside_ok else "Downside case is missing.", ["B5"], evidence_by_module["B5"], counters_by_module["B5"]))

    counter_ok = all(counters_by_module[module_id] for module_id in BLOCK_B_ORDER)
    criteria.append(_criterion("GB-16", "Counterevidence", CriterionOutcome.PASS if counter_ok else CriterionOutcome.FAIL, "Every Block B module retains material counterevidence." if counter_ok else "Counterevidence coverage is incomplete.", BLOCK_B_ORDER, [row["evidence_id"] for row in registry.evidence], [row["counterevidence_id"] for row in registry.counterevidence]))
    assumptions_ok = bool(registry.assumptions and registry.unknowns)
    criteria.append(_criterion("GB-17", "Assumptions and unknowns", CriterionOutcome.CONDITION if assumptions_ok else CriterionOutcome.FAIL, "Material assumptions and explicit unknowns remain visible and are not converted to facts or zero." if assumptions_ok else "Assumption or unknown registers are incomplete.", BLOCK_B_ORDER, [], [], ["Close material assumptions and unknowns through diligence."] if assumptions_ok else []))
    open_research = [item for item in research_gaps if item.status == "OPEN"]
    criteria.append(_criterion("GB-18", "Research Gaps", CriterionOutcome.FAIL if open_research or integrity_gaps else CriterionOutcome.PASS, "No open Block B Research or financial-integrity Gap remains." if not open_research and not integrity_gaps else "Open Research or financial-integrity Gaps remain.", sorted({item.owning_module for item in open_research} or {item.owning_module for item in integrity_gaps} or {"B1"}), [], []))
    criteria.append(_criterion("GB-19", "Calculation Gaps", CriterionOutcome.FAIL if calculation_gaps else CriterionOutcome.PASS, "No open Block B Calculation Gap remains." if not calculation_gaps else "Open Calculation Gaps block the affected value criterion.", sorted({item.owning_module for item in calculation_gaps} or {"B5"}), [], []))
    blocking_human = [item for item in human_review_items if item.get("blocking")]
    criteria.append(_criterion("GB-20", "Human Review", CriterionOutcome.FAIL if blocking_human else CriterionOutcome.CONDITION if human_review_items else CriterionOutcome.PASS, "Required Human Review boundaries are explicit and non-blocking for research completion." if human_review_items and not blocking_human else "Blocking Human Review remains." if blocking_human else "No Human Review item is open.", sorted({item.get("owning_module", "B4") for item in human_review_items} or {"B4"}), [], [], [item["issue_description"] for item in human_review_items] if human_review_items and not blocking_human else [], human=bool(human_review_items)))
    pce_rows = certification.get("pce_result", {}).get("claim_results", [])
    pce_ok = bool(pce_rows) and all(row.get("PCE_status") in {PCEStatus.CERTIFIED.value, PCEStatus.CERTIFIED_WITH_CAVEAT.value} for row in pce_rows)
    criteria.append(_criterion("GB-21", "PCE", CriterionOutcome.PASS if pce_ok else CriterionOutcome.FAIL, "PCE delivery control completed after deterministic calculations." if pce_ok else "PCE did not clear all admitted Block B Claims.", BLOCK_B_ORDER, [], []))
    er_rows = certification.get("er_brb_results", [])
    criteria.append(_criterion("GB-22", "ER/BRB", CriterionOutcome.PASS if er_rows else CriterionOutcome.FAIL, "ER/BRB evidence-row assessment completed after deterministic calculations." if er_rows else "ER/BRB assessment is missing.", BLOCK_B_ORDER, [], []))

    failed = [item.criterion_id for item in criteria if item.outcome == CriterionOutcome.FAIL]
    conditions = [condition for item in criteria for condition in item.conditions]
    if any(by_module.get(module) and by_module[module].structured_output.get("fatal_value_destruction") for module in BLOCK_B_ORDER):
        status = BusinessGateStatus.FATAL_VALUE_DESTRUCTION
    elif blocking_human:
        status = BusinessGateStatus.HUMAN_REVIEW_REQUIRED
    elif calculation_gaps or not replay_ok:
        status = BusinessGateStatus.FAIL_CALCULATION_GAP
    elif open_research or integrity_gaps or failed:
        status = BusinessGateStatus.FAIL_RESEARCH_GAP
    elif price_over or not returns_ok:
        status = BusinessGateStatus.RENEGOTIATE_PRICE
    elif not threshold_ok:
        status = BusinessGateStatus.FAIL_MANDATE_GAP
    elif any(item.outcome == CriterionOutcome.CONDITION for item in criteria):
        status = BusinessGateStatus.CONDITIONAL_PASS
    else:
        status = BusinessGateStatus.PASS

    return BusinessGateResult(
        gate_id="GATE_B", gate_name="Value Creation Gate", block=BusinessBlock.BLOCK_B,
        status=status, criteria=criteria, failed_criterion_ids=failed,
        conditions=conditions,
        gap_ids=[item.gap_id for item in open_research] + [item.gap_id for item in integrity_gaps] + [item.gap_id for item in calculation_gaps],
        pce_statuses={row["claim_id"]: PCEStatus(row["PCE_status"]) for row in pce_rows},
        er_brb_summary={"record_count": len(er_rows), "scope": "read-only evidence-row control"},
        calculation_replay_statuses={item.calculation_id: item.replay_status for item in latest_calcs},
        human_review_items=[item["review_id"] for item in human_review_items],
        prior_gate_history=[{"gate_id": "GATE_A", "status": gate_a_result["status"]}],
        business_reason=f"{sum(item.outcome == CriterionOutcome.PASS for item in criteria)} criteria passed, {sum(item.outcome == CriterionOutcome.CONDITION for item in criteria)} conditional, {len(failed)} failed; result derives from Gate B criteria and Mandate thresholds.",
    )
