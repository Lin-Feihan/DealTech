from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from utils.schema import parse_number


HKEX_UNIVERSE_FIELDS = [
    "stock_code",
    "company_name_en",
    "company_name_zh",
    "board",
    "listing_status",
    "listing_date",
    "industry",
    "source",
    "source_date",
    "notes",
]

INITIAL_SCREENING_FIELDS = [
    "stock_code",
    "company_name",
    "board",
    "industry",
    "market_cap_hkd",
    "pb_ratio",
    "share_price_hkd",
    "avg_turnover_60d_hkd",
    "latest_revenue_hkd",
    "latest_net_assets_hkd",
    "profitability_status",
    "low_valuation_flag",
    "small_market_cap_flag",
    "liquidity_flag",
    "suspension_flag",
    "audit_opinion_flag",
    "major_risk_flag",
    "initial_synergy_direction",
    "initial_platform_angle",
    "screening_status",
    "screening_reason",
    "data_source",
    "data_date",
    "notes",
]

CANDIDATE_DD_FIELDS = [
    "stock_code",
    "company_name",
    "business_summary",
    "distress_signal",
    "distress_reversibility",
    "controlling_shareholder",
    "controlling_shareholder_pct",
    "control_path_feasibility",
    "public_float_risk",
    "debt_risk",
    "litigation_risk",
    "regulatory_risk",
    "audit_risk",
    "convertible_bond_risk",
    "rto_risk",
    "rule_1406b_relevance",
    "rule_1406e_relevance",
    "asset_injection_feasibility",
    "transaction_complexity",
    "estimated_transaction_cost_hkd",
    "synergy_business",
    "synergy_scenario",
    "synergy_customer",
    "synergy_channel",
    "synergy_technology",
    "synergy_license",
    "platform_redefinition_thesis",
    "commercial_story_angle",
    "founder_excitation_angle",
    "channel_expansion_optionality",
    "brand_ip_optionality",
    "international_expansion_optionality",
    "category_expansion_optionality",
    "operating_efficiency_optionality",
    "scenario_base_case",
    "scenario_upside_case",
    "scenario_blue_sky_case",
    "thesis_breakers",
    "key_dd_questions",
    "synergy_score",
    "value_creation_score",
    "transaction_feasibility_score",
    "risk_control_score",
    "commercial_story_score",
    "weighted_total_score",
    "recommendation_level",
    "key_risks",
    "next_step",
    "source_evidence_status",
    "notes",
]


def _today_from_iso(iso_text: str) -> str:
    return iso_text[:10] if iso_text else datetime.now(timezone.utc).date().isoformat()


def build_hkex_universe_from_market_rows(
    market_rows: list[dict[str, Any]], source_id: str, retrieved_at: str
) -> list[dict[str, Any]]:
    source_date = _today_from_iso(retrieved_at)
    universe: list[dict[str, Any]] = []
    for row in market_rows:
        stock_code = row.get("stock_code") or row.get("ticker") or ""
        company_name = row.get("company_name") or ""
        universe.append(
            {
                "stock_code": stock_code,
                "company_name_en": "",
                "company_name_zh": company_name,
                "board": row.get("board") or "unknown",
                "listing_status": row.get("listing_status") or "unknown",
                "listing_date": row.get("listing_date") or "",
                "industry": row.get("industry") or "",
                "source": source_id,
                "source_date": source_date,
                "notes": row.get("universe_notes") or "Built from AKShare market snapshot; official HKEX listed-company status not verified in v0.1.",
            }
        )
    return universe


def _infer_initial_angles(industry: str) -> tuple[str, str]:
    text = (industry or "").strip().lower()
    if not text:
        return (
            "requires business/announcement review; not inferred in v0.1",
            "requires business review; platform direction not inferred in v0.1",
        )

    consumer_terms = ["retail", "consumer", "food", "beverage", "apparel", "household", "lifestyle", "fashion"]
    industrial_terms = ["industrial", "machinery", "materials", "electronics", "manufacturing"]
    property_terms = ["property", "real estate", "land", "construction"]

    if any(term in text for term in consumer_terms):
        return (
            "preliminary consumer / retail / lifestyle synergy possible; requires document review",
            "preliminary consumer-platform or lifestyle-platform angle; requires document review",
        )
    if any(term in text for term in property_terms):
        return (
            "possible community / offline scene synergy; requires document review",
            "possible scene-based platform angle; requires document review",
        )
    if any(term in text for term in industrial_terms):
        return (
            "synergy unclear from industry label alone; requires business review",
            "possible manufacturing or supply-chain platform angle; requires document review",
        )
    return (
        "synergy direction not inferred from industry label alone; requires document review",
        "platform direction not inferred from industry label alone; requires document review",
    )


def _round_score(value: float) -> float:
    return round(max(1.0, min(10.0, value)), 1)


def _compute_stage1_candidate_scores(row: dict[str, Any]) -> dict[str, float]:
    market_cap = parse_number(row.get("market_cap_hkd"))
    pb = parse_number(row.get("pb_ratio"))
    turnover_present = bool(parse_number(row.get("avg_turnover_60d_hkd")) or parse_number(row.get("turnover_hkd")) or row.get("liquidity_flag") == "adequate")
    status = str(row.get("screening_status") or "")
    synergy_text = " ".join(
        [
            str(row.get("initial_synergy_direction") or ""),
            str(row.get("initial_platform_angle") or ""),
            str(row.get("industry") or ""),
        ]
    ).lower()

    synergy_score = 4.5
    if any(term in synergy_text for term in ["consumer", "retail", "lifestyle", "community", "offline scene"]):
        synergy_score = 6.5
    elif any(term in synergy_text for term in ["manufacturing", "supply-chain", "industrial"]):
        synergy_score = 5.5
    elif status == "pass":
        synergy_score = 5.0

    value_creation_score = 4.0 if status == "watchlist" else 6.0
    if market_cap is not None and market_cap <= 500_000_000:
        value_creation_score += 1.5
    elif market_cap is not None and market_cap <= 1_000_000_000:
        value_creation_score += 1.0
    if pb is not None and 0 < pb <= 0.3:
        value_creation_score += 1.5
    elif pb is not None and pb <= 0.6:
        value_creation_score += 0.8

    transaction_feasibility_score = 3.5 if status == "watchlist" else 5.5
    if turnover_present:
        transaction_feasibility_score += 0.5
    if str(row.get("board") or "").upper() == "GEM":
        transaction_feasibility_score -= 1.0

    risk_control_score = 3.5 if status == "watchlist" else 4.5
    if str(row.get("major_risk_flag") or "") == "warning":
        risk_control_score -= 0.5
    elif str(row.get("major_risk_flag") or "") == "high":
        risk_control_score -= 1.5
    if str(row.get("suspension_flag") or "") == "current":
        risk_control_score -= 1.5

    synergy_score = _round_score(synergy_score)
    value_creation_score = _round_score(value_creation_score)
    transaction_feasibility_score = _round_score(transaction_feasibility_score)
    risk_control_score = _round_score(risk_control_score)
    commercial_story_score = _round_score((synergy_score * 0.6) + (value_creation_score * 0.4))
    weighted_total_score = round(
        synergy_score * 0.30
        + value_creation_score * 0.30
        + transaction_feasibility_score * 0.25
        + risk_control_score * 0.15,
        2,
    )
    return {
        "synergy_score": synergy_score,
        "value_creation_score": value_creation_score,
        "transaction_feasibility_score": transaction_feasibility_score,
        "risk_control_score": risk_control_score,
        "commercial_story_score": commercial_story_score,
        "weighted_total_score": weighted_total_score,
    }


def build_initial_screening_table(
    market_rows: list[dict[str, Any]],
    params: dict[str, float],
    source_id: str,
    retrieved_at: str | None = None,
) -> list[dict[str, Any]]:
    """Build first-round screening table without fabricating unavailable facts."""
    retrieved_at = retrieved_at or datetime.now(timezone.utc).isoformat()
    data_date = _today_from_iso(retrieved_at)
    max_market_cap = float(params.get("max_market_cap_hkd", 2_000_000_000))
    max_pb = float(params.get("max_pb", 0.8))
    min_turnover = float(params.get("min_turnover_hkd", 0))

    rows: list[dict[str, Any]] = []
    for raw in market_rows:
        market_cap = parse_number(raw.get("market_cap_hkd"))
        pb = parse_number(raw.get("pb_ratio", raw.get("pb")))
        turnover = parse_number(raw.get("avg_turnover_60d_hkd")) or parse_number(raw.get("turnover_hkd"))
        price = parse_number(raw.get("share_price_hkd", raw.get("last_price_hkd")))
        latest_revenue = parse_number(raw.get("latest_revenue_hkd"))
        latest_net_assets = parse_number(raw.get("latest_net_assets_hkd"))

        missing = []
        if market_cap is None:
            missing.append("market_cap_hkd")
        if pb is None:
            missing.append("pb_ratio")
        if turnover is None:
            missing.append("avg_turnover_60d_hkd/turnover_hkd")

        small_market_cap = market_cap is not None and market_cap <= max_market_cap
        low_valuation = pb is not None and 0 < pb <= max_pb
        has_turnover = turnover is not None and turnover > min_turnover

        if small_market_cap and low_valuation and has_turnover:
            status = "pass"
            reason = (
                f"Passes mechanical v0.1 filters: market_cap <= {max_market_cap:,.0f} HKD, "
                f"0 < P/B <= {max_pb}, and turnover is present. Needs HKEXnews verification before any recommendation."
            )
        elif market_cap is None or pb is None:
            status = "watchlist"
            reason = "Insufficient structured valuation data from public AKShare endpoint; requires official/secondary verification."
        else:
            status = "exclude"
            reason_parts = []
            if not small_market_cap:
                reason_parts.append("market cap above v0.1 small-cap threshold")
            if not low_valuation:
                reason_parts.append("P/B does not satisfy low-valuation threshold or is non-positive")
            if not has_turnover:
                reason_parts.append("turnover unavailable or not above minimum")
            reason = "; ".join(reason_parts) or "Does not pass mechanical v0.1 filters."

        initial_synergy_direction, initial_platform_angle = _infer_initial_angles(str(raw.get("industry") or ""))

        notes = ["AKShare is used only for first-round structured screening."]
        if missing:
            notes.append("missing fields: " + ", ".join(missing))
        notes.append("HKEXnews status, audit opinion, major risks, shareholder/control path and announcements not verified in v0.1.")

        rows.append(
            {
                "stock_code": raw.get("stock_code") or raw.get("ticker") or "",
                "company_name": raw.get("company_name") or "",
                "board": raw.get("board") or "unknown",
                "industry": raw.get("industry") or "",
                "market_cap_hkd": market_cap,
                "pb_ratio": pb,
                "share_price_hkd": price,
                "avg_turnover_60d_hkd": turnover,
                "latest_revenue_hkd": latest_revenue,
                "latest_net_assets_hkd": latest_net_assets,
                "profitability_status": "unknown",
                "low_valuation_flag": low_valuation,
                "small_market_cap_flag": small_market_cap,
                "liquidity_flag": "adequate" if has_turnover else "unknown",
                "suspension_flag": "unknown",
                "audit_opinion_flag": "unknown",
                "major_risk_flag": "unknown",
                "initial_synergy_direction": initial_synergy_direction,
                "initial_platform_angle": initial_platform_angle,
                "screening_status": status,
                "screening_reason": reason,
                "data_source": source_id,
                "data_date": data_date,
                "notes": " | ".join(notes),
            }
        )
    return rows


def build_candidate_dd_table_from_screening(
    screening_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a conservative placeholder candidate_dd_table without fabricating DD facts.

    This scaffold is intentionally limited: it carries forward what is already known
    from stage-1 screening and leaves deeper DD / commercial thesis fields blank or
    explicitly marked as pending document review.
    """
    dd_rows: list[dict[str, Any]] = []
    for row in screening_rows:
        status = str(row.get("screening_status") or "")
        if status not in {"pass", "watchlist"}:
            continue

        scores = _compute_stage1_candidate_scores(row)
        recommendation = "moderate" if status == "pass" else "watchlist"
        if status == "pass" and scores["weighted_total_score"] >= 6.2:
            recommendation = "strong"
        fallback_synergy_direction, fallback_platform_angle = _infer_initial_angles(str(row.get("industry") or ""))
        dd_rows.append(
            {
                "stock_code": row.get("stock_code") or "",
                "company_name": row.get("company_name") or "",
                "business_summary": "pending official filing review; not extracted in current code path",
                "distress_signal": row.get("screening_reason") or "",
                "distress_reversibility": "unknown",
                "controlling_shareholder": "",
                "controlling_shareholder_pct": "",
                "control_path_feasibility": "unknown",
                "public_float_risk": "unknown",
                "debt_risk": "unknown",
                "litigation_risk": "unknown",
                "regulatory_risk": row.get("major_risk_flag") or "unknown",
                "audit_risk": row.get("audit_opinion_flag") or "unknown",
                "convertible_bond_risk": "unknown",
                "rto_risk": "unknown",
                "rule_1406b_relevance": "unknown",
                "rule_1406e_relevance": "unknown",
                "asset_injection_feasibility": "unknown",
                "transaction_complexity": "unknown",
                "estimated_transaction_cost_hkd": "",
                "synergy_business": row.get("initial_synergy_direction") or fallback_synergy_direction,
                "synergy_scenario": "pending company document review",
                "synergy_customer": "pending company document review",
                "synergy_channel": "pending company document review",
                "synergy_technology": "pending company document review",
                "synergy_license": "pending company document review",
                "platform_redefinition_thesis": row.get("initial_platform_angle") or fallback_platform_angle,
                "commercial_story_angle": "stage-1 provisional ranking only; formal commercial thesis pending DD",
                "founder_excitation_angle": "pending DD-backed thesis construction",
                "channel_expansion_optionality": "pending DD-backed hypothesis construction",
                "brand_ip_optionality": "pending DD-backed hypothesis construction",
                "international_expansion_optionality": "pending DD-backed hypothesis construction",
                "category_expansion_optionality": "pending DD-backed hypothesis construction",
                "operating_efficiency_optionality": "pending DD-backed hypothesis construction",
                "scenario_base_case": "screenable small-cap HK platform; requires DD before active engagement",
                "scenario_upside_case": "if control path and risk review clear, can move into structured shortlist and platform-thesis work",
                "scenario_blue_sky_case": "if DD confirms clean platform plus synergy, could become an asset-injection and market-repositioning candidate",
                "thesis_breakers": "control path / regulatory / business continuity questions not yet verified",
                "key_dd_questions": "official filings, control path, audit, major risk, business continuity, brand/right constraints",
                "synergy_score": scores["synergy_score"],
                "value_creation_score": scores["value_creation_score"],
                "transaction_feasibility_score": scores["transaction_feasibility_score"],
                "risk_control_score": scores["risk_control_score"],
                "commercial_story_score": scores["commercial_story_score"],
                "weighted_total_score": scores["weighted_total_score"],
                "recommendation_level": recommendation,
                "key_risks": "title-level screening only; document review pending",
                "next_step": "build DD evidence package before final ranking",
                "source_evidence_status": "partial",
                "notes": (
                    "Auto-generated scaffold from stage-1 screening only. "
                    "Scores are provisional mechanical ranking aids, not final DD-backed recommendations."
                ),
            }
        )
    return dd_rows
