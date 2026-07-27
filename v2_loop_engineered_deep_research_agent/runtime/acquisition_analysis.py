from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ANALYSIS_ENGINE_VERSION = "3.1.0-general-method-routing"

REPORT_SECTION_TITLES = (
    "Executive Summary",
    "Transaction Overview",
    "Buyer Strategic Objectives",
    "Target Business Quality",
    "Industry and Competitive Position",
    "Strategic Fit",
    "Standalone Financial Analysis",
    "Valuation and Acceptable Purchase Price",
    "Synergies and Value Creation",
    "Deal Structure",
    "Financing and Capital Structure Impact",
    "Returns Analysis",
    "Due Diligence Findings",
    "Regulatory, Integration, and Downside Risks",
    "Final Recommendation",
)

RECOMMENDATION_OPTIONS = {
    "Proceed",
    "Proceed with Conditions",
    "Renegotiate",
    "Defer",
    "Walk Away",
}

FORBIDDEN_REPORT_MARKERS = (
    "CLM-",
    "EVI-",
    "SRC-",
    "PCE",
    "ER_BRB",
    "claim_id",
    "evidence_id",
    "source_id",
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(
            f"Missing authoritative buyer analysis: {path}. "
            "The report renderer will not infer judgments from evidence-file presence."
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid buyer analysis JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected an object in {path}")
    return payload


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"case_analysis.json requires non-empty {field}")
    return value.strip()


def _require_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"case_analysis.json requires non-empty {field}")
    return value


def _money(value: float) -> float:
    return round(value, 1)


def _calculate_rnpv_scenario(scenario: dict[str, Any], discount_rate: float) -> dict[str, Any]:
    name = _require_text(scenario.get("name"), "models.rnpv.scenarios[].name")
    ptrs = float(scenario["ptrs"])
    margin = float(scenario["commercial_cash_margin"])
    launch_after_years = int(scenario["launch_after_years"])
    sales = [float(value) for value in scenario["annual_net_sales_usd_m"]]
    costs = [float(value) for value in scenario["development_costs_usd_m"]]
    active = [float(value) for value in scenario["development_active_probability"]]
    if not 0 <= ptrs <= 1 or not 0 <= margin <= 1:
        raise ValueError(f"{name}: PTRS and commercial cash margin must be between 0 and 1")
    if launch_after_years < 1 or len(costs) != len(active):
        raise ValueError(f"{name}: invalid launch year or development-cost probability schedule")
    if any(not 0 <= probability <= 1 for probability in active):
        raise ValueError(f"{name}: active probabilities must be between 0 and 1")

    pv_development = sum(
        cost * probability / ((1 + discount_rate) ** year)
        for year, (cost, probability) in enumerate(zip(costs, active), start=1)
    )
    expected_development = sum(cost * probability for cost, probability in zip(costs, active))
    pv_commercial = sum(
        net_sales * margin * ptrs / ((1 + discount_rate) ** year)
        for year, net_sales in enumerate(sales, start=launch_after_years)
    )
    undiscounted_risk_adjusted_commercial = sum(sales) * margin * ptrs
    asset_rnpv = pv_commercial - pv_development

    return {
        "name": name,
        "evidence_class": _require_text(scenario.get("evidence_class"), f"{name}.evidence_class"),
        "ptrs": ptrs,
        "launch_after_years": launch_after_years,
        "commercial_cash_margin": margin,
        "pv_expected_development_cost_usd_m": _money(pv_development),
        "pv_risk_adjusted_commercial_cash_flow_usd_m": _money(pv_commercial),
        "asset_rnpv_before_acquisition_consideration_usd_m": _money(asset_rnpv),
        "buyer_npv_at_upfront_consideration_usd_m": _money(
            asset_rnpv - float(scenario["upfront_consideration_usd_m"])
        ),
        "buyer_npv_at_headline_consideration_usd_m": _money(
            asset_rnpv - float(scenario["headline_consideration_usd_m"])
        ),
        "risk_adjusted_moic_at_upfront": round(
            undiscounted_risk_adjusted_commercial
            / (float(scenario["upfront_consideration_usd_m"]) + expected_development),
            2,
        ),
        "risk_adjusted_moic_at_headline": round(
            undiscounted_risk_adjusted_commercial
            / (float(scenario["headline_consideration_usd_m"]) + expected_development),
            2,
        ),
        "limitations": list(scenario.get("limitations") or []),
    }


def _calculate_dcf_scenario(
    scenario: dict[str, Any],
    discount_rate: float,
    terminal_growth_rate: float,
) -> dict[str, Any]:
    name = _require_text(scenario.get("name"), "models.dcf.scenarios[].name")
    cash_flows = [float(value) for value in _require_list(
        scenario.get("free_cash_flows"), f"{name}.free_cash_flows"
    )]
    if terminal_growth_rate >= discount_rate:
        raise ValueError(f"{name}: terminal growth must be below the discount rate")
    pv_forecast = sum(
        cash_flow / ((1 + discount_rate) ** year)
        for year, cash_flow in enumerate(cash_flows, start=1)
    )
    terminal_value = cash_flows[-1] * (1 + terminal_growth_rate) / (
        discount_rate - terminal_growth_rate
    )
    pv_terminal = terminal_value / ((1 + discount_rate) ** len(cash_flows))
    enterprise_value = pv_forecast + pv_terminal
    net_debt = float(scenario.get("net_debt", 0))
    equity_value = enterprise_value - net_debt
    consideration = float(scenario["acquisition_consideration"])
    return {
        "name": name,
        "evidence_class": _require_text(scenario.get("evidence_class"), f"{name}.evidence_class"),
        "forecast_years": len(cash_flows),
        "pv_forecast_free_cash_flow": _money(pv_forecast),
        "pv_terminal_value": _money(pv_terminal),
        "enterprise_value": _money(enterprise_value),
        "net_debt": _money(net_debt),
        "equity_value": _money(equity_value),
        "acquisition_consideration": _money(consideration),
        "buyer_npv_at_consideration": _money(equity_value - consideration),
        "limitations": list(scenario.get("limitations") or []),
    }


def _calculate_models(analysis: dict[str, Any]) -> dict[str, Any]:
    model_inputs = analysis.get("models") or {}
    if not isinstance(model_inputs, dict) or not model_inputs:
        raise ValueError("case_analysis.json requires at least one selected model")

    calculated: dict[str, Any] = {}
    for model_id, model in model_inputs.items():
        if not isinstance(model, dict):
            raise ValueError(f"models.{model_id} must be an object")
        model_type = _require_text(model.get("model_type", model_id), f"models.{model_id}.model_type")
        discount_rate = float(model["discount_rate"])
        if not 0 < discount_rate < 1:
            raise ValueError(f"models.{model_id}.discount_rate must be between 0 and 1")
        scenarios = _require_list(model.get("scenarios"), f"models.{model_id}.scenarios")
        common = {
            "model_type": model_type,
            "valuation_date": _require_text(model.get("valuation_date"), f"models.{model_id}.valuation_date"),
            "currency": _require_text(model.get("currency"), f"models.{model_id}.currency"),
            "discount_rate": discount_rate,
            "method": _require_text(model.get("method"), f"models.{model_id}.method"),
            "model_limitations": list(model.get("model_limitations") or []),
        }
        if model_type == "rnpv":
            common["scenarios"] = [_calculate_rnpv_scenario(item, discount_rate) for item in scenarios]
        elif model_type == "dcf":
            terminal_growth_rate = float(model["terminal_growth_rate"])
            common["terminal_growth_rate"] = terminal_growth_rate
            common["scenarios"] = [
                _calculate_dcf_scenario(item, discount_rate, terminal_growth_rate)
                for item in scenarios
            ]
        else:
            raise ValueError(
                f"Unsupported model_type {model_type!r} for models.{model_id}; "
                "add a replay adapter before using it in a decision-grade report"
            )
        calculated[model_id] = common
    return calculated


def _validate_analysis(analysis: dict[str, Any]) -> None:
    metadata = analysis.get("report_metadata")
    if not isinstance(metadata, dict):
        raise ValueError("case_analysis.json requires report_metadata")
    for field in ("case_id", "title", "as_of_date", "transaction_state", "decision_mandate"):
        _require_text(metadata.get(field), f"report_metadata.{field}")

    recommendation = analysis.get("recommendation")
    if not isinstance(recommendation, dict):
        raise ValueError("case_analysis.json requires recommendation")
    disposition = _require_text(recommendation.get("disposition"), "recommendation.disposition")
    if disposition not in RECOMMENDATION_OPTIONS:
        raise ValueError(f"Unsupported recommendation disposition: {disposition}")
    for field in ("decision", "price_position", "structure_position", "financing_position"):
        _require_text(recommendation.get(field), f"recommendation.{field}")

    facts = _require_list(analysis.get("facts"), "facts")
    assumptions = _require_list(analysis.get("assumptions"), "assumptions")
    valid_basis_ids: set[str] = set()
    for collection_name, collection in (("facts", facts), ("assumptions", assumptions)):
        for index, item in enumerate(collection):
            if not isinstance(item, dict):
                raise ValueError(f"{collection_name}[{index}] must be an object")
            item_id = _require_text(item.get("id"), f"{collection_name}[{index}].id")
            if item_id in valid_basis_ids:
                raise ValueError(f"Duplicate analysis basis ID: {item_id}")
            valid_basis_ids.add(item_id)
            _require_text(item.get("statement"), f"{collection_name}[{index}].statement")
            _require_text(item.get("evidence_class"), f"{collection_name}[{index}].evidence_class")

    models = analysis.get("models")
    if not isinstance(models, dict) or not models:
        raise ValueError("case_analysis.json requires at least one selected model")
    method_selection = _require_list(analysis.get("method_selection"), "method_selection")
    selected_model_ids: set[str] = set()
    for index, selection in enumerate(method_selection):
        if not isinstance(selection, dict):
            raise ValueError(f"method_selection[{index}] must be an object")
        model_id = _require_text(selection.get("model_id"), f"method_selection[{index}].model_id")
        _require_text(selection.get("analysis_area"), f"method_selection[{index}].analysis_area")
        _require_text(selection.get("method"), f"method_selection[{index}].method")
        _require_text(selection.get("rationale"), f"method_selection[{index}].rationale")
        scenario_policy = _require_text(
            selection.get("scenario_policy"), f"method_selection[{index}].scenario_policy"
        )
        if scenario_policy not in {"single_case", "downside_base_upside"}:
            raise ValueError(f"Unsupported scenario policy: {scenario_policy}")
        basis_ids = _require_list(selection.get("basis_ids"), f"method_selection[{index}].basis_ids")
        unknown_basis = sorted(set(basis_ids) - valid_basis_ids)
        if unknown_basis:
            raise ValueError(
                f"method_selection[{index}] references unknown basis IDs: {', '.join(unknown_basis)}"
            )
        if model_id in selected_model_ids:
            raise ValueError(f"Duplicate method selection for model: {model_id}")
        selected_model_ids.add(model_id)
    if selected_model_ids != set(models):
        raise ValueError(
            "method_selection model IDs must match models exactly: "
            f"selected={sorted(selected_model_ids)}, models={sorted(models)}"
        )

    chapters = _require_list(analysis.get("chapters"), "chapters")
    if len(chapters) != 15:
        raise ValueError("case_analysis.json must contain exactly 15 chapters")
    for number, (chapter, expected_title) in enumerate(zip(chapters, REPORT_SECTION_TITLES), start=1):
        if not isinstance(chapter, dict):
            raise ValueError(f"chapters[{number - 1}] must be an object")
        if chapter.get("number") != number or chapter.get("title") != expected_title:
            raise ValueError(
                f"Chapter {number} must be titled '{expected_title}', received "
                f"{chapter.get('number')!r} / {chapter.get('title')!r}"
            )
        _require_text(chapter.get("judgment"), f"chapters[{number - 1}].judgment")
        _require_list(chapter.get("paragraphs"), f"chapters[{number - 1}].paragraphs")
        basis_ids = chapter.get("basis_ids") or []
        unknown = sorted(set(basis_ids) - valid_basis_ids)
        if unknown:
            raise ValueError(f"Chapter {number} references unknown basis IDs: {', '.join(unknown)}")
        unknown_models = sorted(set(chapter.get("model_refs") or []) - set(models))
        if unknown_models:
            raise ValueError(f"Chapter {number} references unknown models: {', '.join(unknown_models)}")
        for dynamic in chapter.get("dynamic_tables") or []:
            if dynamic.startswith("model:") and dynamic.split(":", 1)[1] not in models:
                raise ValueError(f"Chapter {number} references unknown dynamic model table: {dynamic}")

    alternatives = _require_list(analysis.get("alternatives"), "alternatives")
    actual = {str(item.get("option", "")).lower() for item in alternatives if isinstance(item, dict)}
    if len(actual) < 2 or "buy" not in actual:
        raise ValueError(
            "alternatives must compare acquisition ('buy') with at least one case-relevant path"
        )


def _quality_control(analysis: dict[str, Any], models: dict[str, Any]) -> dict[str, Any]:
    selected = {item["model_id"]: item for item in analysis["method_selection"]}

    def scenario_policy_passes(model_id: str) -> bool:
        policy = selected[model_id]["scenario_policy"]
        scenarios = models[model_id]["scenarios"]
        if policy == "single_case":
            return bool(scenarios)
        names = {str(item["name"]).lower() for item in scenarios}
        return names >= {"downside", "base", "upside"}

    checks = {
        "authoritative_analysis_present": True,
        "exact_15_chapter_structure": len(analysis["chapters"]) == 15,
        "recommendation_authored_in_analysis_not_renderer": True,
        "method_selection_is_case_grounded": all(
            item.get("rationale") and item.get("basis_ids")
            for item in analysis["method_selection"]
        ),
        "selected_models_replayed": set(selected) == set(models),
        "declared_scenario_policies_pass": all(scenario_policy_passes(model_id) for model_id in models),
        "acquisition_and_case_relevant_alternative_compared": (
            len({str(item["option"]).lower() for item in analysis["alternatives"]}) >= 2
            and any(str(item["option"]).lower() == "buy" for item in analysis["alternatives"])
        ),
        "facts_and_assumptions_separated": bool(analysis["facts"] and analysis["assumptions"]),
        "research_gaps_have_decision_effects": all(
            item.get("question") and item.get("decision_effect")
            for item in analysis.get("research_gaps", [])
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "note": "QC tests analysis provenance and model coverage; it does not treat prose volume or file presence as analytical completion.",
    }


def build_acquisition_analysis(
    case_id: str,
    case_dir: Path,
    certification: dict[str, Any],
) -> dict[str, Any]:
    analysis = _load_json(case_dir / "supporting_files" / "case_analysis.json")
    _validate_analysis(analysis)
    if analysis["report_metadata"]["case_id"] != case_id:
        raise ValueError(
            "case_analysis.json case_id does not match the requested case: "
            f"{analysis['report_metadata']['case_id']} != {case_id}"
        )
    models = _calculate_models(analysis)
    quality_control = _quality_control(analysis, models)
    if not quality_control["passed"]:
        failed = [name for name, passed in quality_control["checks"].items() if not passed]
        raise ValueError(f"Buyer analysis QC failed: {', '.join(failed)}")

    return {
        "analysis_engine_version": ANALYSIS_ENGINE_VERSION,
        "case_id": case_id,
        "report_metadata": analysis["report_metadata"],
        "certification_status": certification.get("overall_status", "Not available"),
        "recommendation": analysis["recommendation"]["disposition"],
        "recommendation_analysis": analysis["recommendation"],
        "facts": analysis["facts"],
        "assumptions": analysis["assumptions"],
        "method_selection": analysis["method_selection"],
        "alternatives": analysis["alternatives"],
        "models": models,
        "sections": analysis["chapters"],
        "research_gaps": analysis.get("research_gaps", []),
        "human_review_items": analysis.get("human_review_items", []),
        "quality_control": quality_control,
        "report_forbidden_markers": list(FORBIDDEN_REPORT_MARKERS),
    }


def build_recommendation_decision(package: dict[str, Any]) -> dict[str, Any]:
    recommendation = package["recommendation_analysis"]
    return {
        "case_id": package["case_id"],
        "disposition": recommendation["disposition"],
        "decision": recommendation["decision"],
        "unrestricted_approval_allowed": recommendation["disposition"] == "Proceed",
        "price_position": recommendation["price_position"],
        "structure_position": recommendation["structure_position"],
        "financing_position": recommendation["financing_position"],
        "conditions": recommendation.get("conditions", []),
        "red_lines": recommendation.get("red_lines", []),
        "next_actions": recommendation.get("next_actions", []),
    }


def build_report_manifest(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": package["case_id"],
        "analysis_engine_version": package["analysis_engine_version"],
        "overall_status": package["certification_status"],
        "recommendation": package["recommendation"],
        "sections": [
            {
                "section_id": f"B{section['number']}",
                "number": section["number"],
                "title": section["title"],
                "basis_ids": section.get("basis_ids", []),
                "model_refs": section.get("model_refs", []),
            }
            for section in package["sections"]
        ],
    }


def _table(headers: list[Any], rows: list[list[Any]]) -> str:
    clean = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(clean(value) for value in headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(clean(value) for value in row) + " |")
    return "\n".join(lines)


def _rnpv_table(model: dict[str, Any]) -> str:
    rows = []
    for scenario in model["scenarios"]:
        rows.append(
            [
                scenario["name"],
                f"{scenario['ptrs']:.0%}",
                scenario["launch_after_years"],
                f"${scenario['pv_expected_development_cost_usd_m']:.1f}m",
                f"${scenario['pv_risk_adjusted_commercial_cash_flow_usd_m']:.1f}m",
                f"${scenario['asset_rnpv_before_acquisition_consideration_usd_m']:.1f}m",
                f"${scenario['buyer_npv_at_upfront_consideration_usd_m']:.1f}m",
                f"${scenario['buyer_npv_at_headline_consideration_usd_m']:.1f}m",
                f"{scenario['risk_adjusted_moic_at_upfront']:.2f}x",
                f"{scenario['risk_adjusted_moic_at_headline']:.2f}x",
            ]
        )
    return _table(
        [
            "Scenario",
            "PTRS",
            "Years to launch",
            "PV expected development cost",
            "PV risk-adjusted commercial cash flow",
            "Asset rNPV before consideration",
            "Buyer NPV at upfront consideration",
            "Buyer NPV at headline consideration",
            "Risk-adjusted MOIC at upfront",
            "Risk-adjusted MOIC at headline",
        ],
        rows,
    )


def _dcf_table(model: dict[str, Any]) -> str:
    return _table(
        [
            "Scenario",
            "Forecast years",
            "PV forecast FCF",
            "PV terminal value",
            "Enterprise value",
            "Net debt",
            "Equity value",
            "Acquisition consideration",
            "Buyer NPV at consideration",
        ],
        [
            [
                scenario["name"],
                scenario["forecast_years"],
                scenario["pv_forecast_free_cash_flow"],
                scenario["pv_terminal_value"],
                scenario["enterprise_value"],
                scenario["net_debt"],
                scenario["equity_value"],
                scenario["acquisition_consideration"],
                scenario["buyer_npv_at_consideration"],
            ]
            for scenario in model["scenarios"]
        ],
    )


def _model_table(package: dict[str, Any], model_id: str) -> tuple[str, str]:
    try:
        model = package["models"][model_id]
    except KeyError as exc:
        raise ValueError(f"Unknown model table: {model_id}") from exc
    if model["model_type"] == "rnpv":
        return "Illustrative rNPV Sensitivity", _rnpv_table(model)
    if model["model_type"] == "dcf":
        return "Discounted Cash Flow Sensitivity", _dcf_table(model)
    raise ValueError(f"No report-table adapter for model type: {model['model_type']}")


def _alternatives_table(package: dict[str, Any]) -> str:
    return _table(
        ["Option", "Control", "Capital at risk", "Primary advantage", "Primary drawback", "Current view"],
        [
            [
                item["option"].title(),
                item["control"],
                item["capital_at_risk"],
                item["advantage"],
                item["drawback"],
                item["current_view"],
            ]
            for item in package["alternatives"]
        ],
    )


def render_acquisition_report(package: dict[str, Any]) -> str:
    metadata = package["report_metadata"]
    lines = [f"# {metadata['title']}", ""]
    lines.extend(
        [
            f"**Decision date:** {metadata['as_of_date']}",
            f"**Transaction state:** {metadata['transaction_state']}",
            f"**Decision mandate:** {metadata['decision_mandate']}",
            "",
            metadata["evidence_boundary"],
            "",
        ]
    )

    for section in package["sections"]:
        lines.extend([f"## {section['number']}. {section['title']}", "", section["judgment"], ""])
        for paragraph in section["paragraphs"]:
            lines.extend([str(paragraph).strip(), ""])
        for table_spec in section.get("tables", []):
            lines.extend(
                [
                    f"### {table_spec['title']}",
                    "",
                    _table(table_spec["headers"], table_spec["rows"]),
                    "",
                ]
            )
        for dynamic in section.get("dynamic_tables", []):
            if dynamic == "strategic_alternatives":
                lines.extend(["### Build / Buy / License / Partner / Wait", "", _alternatives_table(package), ""])
            elif dynamic.startswith("model:"):
                title, table = _model_table(package, dynamic.split(":", 1)[1])
                lines.extend([f"### {title}", "", table, ""])
            else:
                raise ValueError(f"Unknown dynamic table: {dynamic}")

    report = "\n".join(lines).rstrip() + "\n"
    leaked = [marker for marker in FORBIDDEN_REPORT_MARKERS if marker in report]
    if leaked:
        raise ValueError(f"Internal audit markers leaked into report: {', '.join(leaked)}")
    return report
