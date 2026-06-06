from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.io_utils import write_csv

CASE_NAME = "吨吨健康科技集团港股上市公司重组标的筛选"
TRACE_ID = "TRACE-TUNTUN-001"

SOURCE_INVENTORY_FIELDS = [
    "source_id",
    "source_name",
    "source_category",
    "priority_level",
    "official_status",
    "allowed_use",
    "restrictions",
    "default_confidence",
]

RETRIEVAL_LOG_FIELDS = [
    "retrieval_id",
    "retrieval_datetime",
    "stage",
    "company_name",
    "source_id",
    "query_or_document",
    "action_taken",
    "output_file",
    "result_status",
    "notes",
]

CANDIDATE_UNIVERSE_FIELDS = [
    "universe_id",
    "stock_code",
    "company_name",
    "board",
    "industry",
    "market_cap_hkd",
    "pb_ratio",
    "listing_status",
    "initial_inclusion_reason",
    "source_id",
    "data_date",
]

HARD_FILTER_FIELDS = [
    "filter_record_id",
    "stock_code",
    "company_name",
    "filter_stage",
    "filter_name",
    "filter_result",
    "rationale",
    "source_id",
    "er_brb_rule_id",
    "human_review_required",
]

EXCLUSION_REASON_FIELDS = [
    "exclusion_id",
    "stock_code",
    "company_name",
    "exclusion_stage",
    "exclusion_reason",
    "severity",
    "source_id",
    "uncertainty_label",
    "reviewer_note",
]

DD_EVIDENCE_FIELDS = [
    "evidence_id",
    "stock_code",
    "company_name",
    "field_name",
    "field_value",
    "claim_type",
    "source_id",
    "source_title",
    "source_link_or_file",
    "support_level",
    "verification_status",
    "confidence_level",
    "notes",
]

RISK_MATRIX_FIELDS = [
    "risk_id",
    "stock_code",
    "company_name",
    "risk_category",
    "risk_flag",
    "risk_description",
    "source_id",
    "severity",
    "human_review_required",
    "mitigation_or_next_step",
]

FINANCIAL_CALC_FIELDS = [
    "calc_id",
    "stock_code",
    "company_name",
    "metric_name",
    "input_1",
    "input_2",
    "formula_or_logic",
    "output_value",
    "unit",
    "calculation_required",
    "calculation_replayed",
    "linked_claim_id",
    "notes",
]

ER_BRB_FIELDS = [
    "er_brb_id",
    "stage",
    "stock_code",
    "company_name",
    "rule_id",
    "rule_family",
    "score_component",
    "score_value",
    "source_reliability",
    "belief_state_1_label",
    "belief_state_1_value",
    "belief_state_2_label",
    "belief_state_2_value",
    "belief_state_3_label",
    "belief_state_3_value",
    "belief_state_4_label",
    "belief_state_4_value",
    "belief_state_5_label",
    "belief_state_5_value",
    "aggregation_logic",
    "decision_output",
    "requires_dd_escalation",
    "evidence_gap_note",
    "rationale",
    "source_id",
    "linked_claim_id",
    "uncertainty_label",
    "human_review_required",
]

CLAIM_MAP_FIELDS = [
    "claim_id",
    "claim_text",
    "company_name",
    "stage",
    "source_id",
    "evidence_id",
    "calc_id",
    "risk_id",
    "calculation_required",
    "calculation_replayed",
    "uncertainty_label",
    "human_review_required",
    "delivery_scope",
    "certification_status",
]

HUMAN_REVIEW_FIELDS = [
    "review_item_id",
    "company_name",
    "review_topic",
    "trigger_reason",
    "priority",
    "required_reviewer_type",
    "assigned_reviewer_name",
    "status",
    "review_completed_at",
    "review_outcome",
    "signoff_blocking",
    "blocking_reason",
    "linked_claim_id",
    "notes",
]

PCE_AUDIT_FIELDS = [
    "trace_id",
    "case_name",
    "stage",
    "company_name",
    "action_taken",
    "claim_id",
    "claim_text",
    "source_id",
    "source_type",
    "source_link_or_file",
    "evidence_status",
    "calculation_required",
    "calculation_replayed",
    "risk_flag",
    "uncertainty_label",
    "human_review_required",
    "delivery_scope",
    "certification_status",
    "reviewer_note",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _code(row: dict[str, Any]) -> str:
    return _clean(row.get("stock_code") or row.get("ticker"))


def _company(row: dict[str, Any]) -> str:
    return _clean(row.get("company_name") or row.get("company_name_zh") or row.get("company_name_en") or row.get("stock_name"))


def _severity_from_flags(*values: Any) -> str:
    text = " ".join(_clean(v).lower() for v in values)
    if any(token in text for token in ["high", "current", "disclaimer", "adverse", "suspended"]):
        return "high"
    if any(token in text for token in ["warning", "recent", "qualified", "unknown", "needs_review"]):
        return "medium"
    return "low"


def _human_required(severity: str, uncertainty: str = "") -> str:
    if severity in {"high", "medium"} or uncertainty not in {"", "none"}:
        return "Yes"
    return "No"


def _source_category_from_id(source_id: str) -> str:
    source_key = _clean(source_id).strip().lower()
    official_keys = {
        "hkexnews_official",
        "hkex_listed_company_list",
        "hkex document body",
        "hkex annual report body",
        "hkex official list of securities",
        "hkexnews",
        "hkexnews active/inactive stock lookup",
        "annual_report",
        "results_announcement",
        "announcement",
    }
    derived_keys = {"financial_calculation_sheet", "dd_scaffold"}
    if source_key in official_keys:
        return "official"
    if source_key in derived_keys:
        return "derived"
    if source_key in {"akshare_hk", "akshare_hk_snapshot_cache", "akshare eastmoney security profile", "akshare eastmoney company profile", "akshare eastmoney financial indicator", "eastmoney historical kline public api"}:
        return "structured"
    if source_key == "company_ir":
        return "corporate"
    if source_key == "industry_and_comparables":
        return "secondary"
    return "unknown" if not source_key else "unknown"


def _source_reliability(source_id: str) -> float:
    source_key = _clean(source_id).upper()
    if _source_category_from_id(source_id) == "official":
        return 0.95
    if source_key in {"AKSHARE_HK", "AKSHARE_HK_SNAPSHOT_CACHE", "FINANCIAL_CALCULATION_SHEET", "DD_SCAFFOLD"}:
        return 0.60
    if source_key in {"COMPANY_IR"}:
        return 0.70
    if source_key in {"INDUSTRY_AND_COMPARABLES"}:
        return 0.45
    if not source_key:
        return 0.35
    return 0.55


def _truthy(value: Any) -> bool:
    return _clean(value).strip().lower() in {"1", "true", "yes", "y", "pass", "adequate", "complete"}


def _normalize_beliefs(items: list[tuple[str, float]]) -> list[tuple[str, str]]:
    cleaned = [(label, max(score, 0.0)) for label, score in items]
    total = sum(score for _, score in cleaned) or 1.0
    normalized: list[tuple[str, str]] = []
    running = 0
    for idx, (label, score) in enumerate(cleaned):
        if idx == len(cleaned) - 1:
            value = max(0, 100 - running)
        else:
            value = int(round(score / total * 100))
            running += value
        normalized.append((label, str(value)))
    return normalized


def _risk_hit_count(row: dict[str, Any], fields: list[str]) -> int:
    count = 0
    for field in fields:
        text = _clean(row.get(field)).strip().lower()
        if text and text not in {"0", "none", "low", "unknown", "false"}:
            count += 1
    return count


def _material_company_sets(candidate_dd_rows: list[dict[str, Any]], evidence_rows: list[dict[str, Any]], top_n: int = 10) -> tuple[set[str], set[str]]:
    ranked: list[tuple[float, dict[str, Any]]] = []
    for row in candidate_dd_rows:
        try:
            score = float(_clean(row.get("weighted_total_score")) or 0)
        except ValueError:
            score = 0.0
        ranked.append((score, row))
    ranked.sort(key=lambda item: item[0], reverse=True)

    codes: set[str] = set()
    names: set[str] = set()

    def remember(row: dict[str, Any]) -> None:
        code = _code(row)
        name = _company(row)
        if code:
            codes.add(code)
        if name:
            names.add(name)

    shortlist_path = Path(__file__).resolve().parents[1] / "outputs" / "dd_review" / "top_candidate_dd_review_summary.csv"
    if shortlist_path.exists():
        with shortlist_path.open("r", newline="", encoding="utf-8-sig") as f:
            shortlist_rows = list(csv.DictReader(f))
        for row in shortlist_rows[:top_n]:
            remember(row)
        if codes or names:
            return codes, names

    for _, row in ranked[:top_n]:
        remember(row)
    return codes, names


def _is_material_company(row: dict[str, Any], material_codes: set[str], material_names: set[str]) -> bool:
    code = _code(row)
    name = _company(row)
    return (bool(code) and code in material_codes) or (bool(name) and name in material_names)


def _to_float(value: Any) -> float | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _format_points(value: float | None) -> str:
    if value is None:
        return ""
    text = f"{value:.2f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _replay_weighted_total(row: dict[str, Any]) -> tuple[str, str, str]:
    synergy = _to_float(row.get("synergy_score"))
    value_creation = _to_float(row.get("value_creation_score"))
    feasibility = _to_float(row.get("transaction_feasibility_score"))
    risk_control = _to_float(row.get("risk_control_score"))
    reported = _to_float(row.get("weighted_total_score"))
    if None in {synergy, value_creation, feasibility, risk_control, reported}:
        return _clean(row.get("weighted_total_score")), "No", "Insufficient numeric inputs for deterministic replay; manual replay still required."
    replayed = synergy * 0.30 + value_creation * 0.30 + feasibility * 0.25 + risk_control * 0.15
    matched = abs(replayed - reported) <= 0.01
    note = "Auto-replayed from candidate DD score inputs; formula matched stored weighted_total_score." if matched else "Auto-replayed from candidate DD score inputs; stored weighted_total_score did not match replay result and needs manual review."
    return _format_points(reported), "Yes" if matched else "No", note


def _is_verified_evidence(verification_status: str) -> bool:
    return _clean(verification_status).strip().lower() in {
        "verified",
        "verified_from_annual_report_body",
        "body_text_extracted",
    }


def _delivery_scope_for_claim(*, stage: str, source_id: str, material: bool, verification_status: str = "", calculation_required: str = "No") -> str:
    if stage == "financial_calculation" and calculation_required == "Yes":
        return "external_final"
    if stage == "dd_evidence" and material and _is_verified_evidence(verification_status) and _source_category_from_id(source_id) == "official":
        return "external_final"
    return "internal_trace"


EXIT_CLAIM_LAYER_BATCH1_COMPOSITES = {
    ("稻香控股", "document_body_signal:audit", "auditor", "Annual Report 2025"),
    ("同得仕（集团）", "document_body_signal:audit", "auditor", "2025 ANNUAL REPORT"),
    ("同得仕（集团）", "document_body_signal:litigation_regulatory", "regulatory", "2025 ANNUAL REPORT"),
    ("稻香控股", "document_body_signal:brand_license_business_continuity", "brand", "Annual Report 2024"),
    (
        "新兴光学",
        "document_body_signal:audit",
        "auditor",
        "NOTIFICATION LETTER TO NON-REGISTERED SHAREHOLDERS - NOTICE OF PUBLICATION OF 2024-25 ANNUAL REPORT, CIRCULAR DATED 24 JULY 2025 IN RELATION TO GENERAL MANDATES TO ISSUE NEW SHARES AND TO REPURCHASE SHARES, RE-ELECTION OF DIRECTORS AND NOTICE OF ANNUAL GENERAL MEETING AND 2024-2025 ENVIRONMENTAL, SOCIAL AND GOVERNANCE REPORT",
    ),
    ("杉杉品牌", "document_body_signal:audit", "auditor", "2025 ANNUAL REPORT"),
    ("杉杉品牌", "document_body_signal:brand_license_business_continuity", "brand", "2025 ANNUAL REPORT"),
    ("杉杉品牌", "document_body_signal:brand_license_business_continuity", "brand, 品牌", "SUPPLEMENTAL ANNOUNCEMENT IN RELATION TO THE ANNUAL REPORTS"),
    ("同得仕（集团）", "document_body_signal:brand_license_business_continuity", "brand", "ANNUAL REPORT 2023"),
    ("新兴光学", "document_body_signal:brand_license_business_continuity", "brand", "2022-23 Annual Report"),
    ("中星集团控股", "document_body_signal:audit", "auditor", "Annual Report 2025"),
    ("REGAL INT'L", "document_body_signal:audit", "auditor", "2025 ANNUAL REPORT"),
    ("谊砾控股", "document_body_signal:audit", "auditor", "2025 Annual Report"),
    ("金粤控股", "document_body_signal:brand_license_business_continuity", "brand", "2025/2026 INTERIM REPORT"),
    ("渝太地产", "document_body_signal:audit", "auditor", "2025 Annual Report"),
}


EXIT_CLAIM_LAYER_BATCH3_EVIDENCE_IDS = {
    # Ratio-definition-only / false-positive signal rows. Preserve as DD evidence,
    # but do not certify them as standalone claim rows.
    "EV-00277",  # ratio definitions only, not company-specific debt exposure
    "EV-00493",  # non-controlling shareholder amount due, not control trace
    "EV-00498",  # director/SFO biography, not brand/license continuity
    "EV-00527",  # director brand-planning biography, not brand continuity constraint
    "EV-00532",  # director termination/governance wording, not business termination
    # Batch-4: reviewed cached contexts; these are false-positive body signals.
    "EV-00326",  # ratio-definition / five-year-summary label, not current debt fact
    "EV-00327",  # generic "brand new shopping experience" marketing wording
    "EV-00486",  # HKEX standard disclaimer liability wording, not litigation claim
    "EV-00489",  # borrower due-diligence procedure in lending business, not issuer debt exposure
    "EV-00494",  # HKEX standard disclaimer liability wording, not litigation claim
    "EV-00501",  # HKEX standard disclaimer liability wording, not litigation claim
    "EV-00531",  # HKEX standard disclaimer liability wording, not litigation claim
}

PROMOTED_BODY_SIGNAL_CLAIMS = {
    "EV-00305": "同得仕（集团）: FY2024 finance costs were HK$3.326 million and decreased mainly because trade-finance borrowings declined with lower export sales activity.",
    "EV-00306": "同得仕（集团）: FY2024 accrued payables included franchise deposits received of HK$1.130 million, down 17.0% from HK$1.361 million in FY2023.",
    "EV-00360": "新兴光学: FY2024/25 annual-report text identified outstanding bank borrowings of approximately HK$34 million, repayable by installments over 20 years.",
    "EV-00361": "新兴光学: FY2024/25 annual-report text reported branded-eyewear distribution as 20% of revenue and licensing income of HK$1 million connected with the Jill Stuart trademark.",
    "EV-00481": "亚洲果业: as at 31 December 2025, liabilities in respect of bank and other borrowings were approximately RMB11.9 million and cash and cash equivalents were approximately RMB7.6 million.",
    "EV-00482": "亚洲果业: during the review period, the air-conditioners distribution business focused on sales of a well-known PRC brand of air conditioners.",
    "EV-00484": "亚洲果业: interim-results text referred to interest income from a loan to an independent third party secured by a substantial shareholder of the company.",
    "EV-00485": "亚洲果业: as at 31 December 2025, bank and other borrowings were approximately RMB11.9 million, cash and cash equivalents were approximately RMB7.6 million, and the current and quick ratios were approximately 3.0 and 2.6.",
    "EV-00487": "亚洲果业: interim-results text stated that the air-conditioners distribution business focused on sales of a well-known PRC brand of air conditioners during the review period.",
    "EV-00491": "中星集团控股: the 2025 annual report described Grand Prospects, a wholly owned subsidiary, as a Hong Kong incorporated licensed money lender under the Money Lenders Ordinance.",
    "EV-00502": "REGAL INT'L: the 2025 results announcement stated that the relevant hotel licence was issued in November 2021 and the hotel grand-opened in April 2023.",
    "EV-00504": "谊砾控股: as at 31 December 2025, the group recorded net current assets of approximately HK$410.0 million, had no bank borrowings, and reported a gearing ratio of approximately 0.02%.",
    "EV-00507": "谊砾控股: the 2025 annual report disclosed that aggregated USDT transactions would have constituted a discloseable transaction under the Listing Rules.",
    "EV-00512": "谊砾控股: the supplemental announcement stated that certain cryptocurrency acquisitions would have constituted discloseable, major, and very substantial transactions on an aggregated basis.",
    "EV-00524": "渝太地产: as at 31 December 2025, net borrowing was HK$850.9 million, total borrowings were HK$4,098.5 million, cash and bank balances were HK$3,247.7 million, and gearing was 122.7%.",
    "EV-00529": "渝太地产: the 2025 annual results announcement listed current interest-bearing bank and other borrowings of HK$728.301 million and total current liabilities of HK$19,838.968 million.",
    "EV-00322": "CEC INT'L HOLD: as at 30 April 2025, bank balances and cash were HK$78.174 million, bank loans excluding guarantees were HK$30.856 million, unused banking facilities were approximately HK$350.537 million, and debt-to-equity ratio was 0.07.",
    "EV-00496": "REGAL INT'L: the 2025 annual report stated that Regal REIT financial expenses decreased to HK$508.4 million from HK$640.4 million as HIBOR softened for bank-loan-linked borrowing costs.",
    "EV-00324": "CEC INT'L HOLD: FY2024/25 annual-report text stated that certain customer projects ceased production, causing termination of procurement for related coil-product models and a one-off HK$3.640 million raw-material provision.",
    "EV-00500": "REGAL INT'L: the 2025 final-results announcement stated that Regal REIT financial expenses decreased to HK$508.4 million from HK$640.4 million as HIBOR softened for bank-loan-linked borrowing costs.",
    "EV-00506": "谊砾控股: the 2025 annual report stated that the Goldpay blockchain-voucher project was not yet completed, both parties agreed to waive claims against each other, and MUP traded on Klickl, which was licensed by the Abu Dhabi Global Market Financial Services Regulatory Authority.",
    "EV-00508": "谊砾控股: the 2025 annual report stated that MUP was traded on Klickl and Richberg cryptocurrency exchange platforms and that Klickl was licensed by the Abu Dhabi Global Market Financial Services Regulatory Authority.",
    "EV-00511": "谊砾控股: the supplemental announcement disclosed notifiable cryptocurrency acquisitions/disposals, remedial measures, and that MUP traded on platforms including Klickl, which was licensed by the Abu Dhabi Global Market Financial Services Regulatory Authority.",
    "EV-00513": "谊砾控股: the supplemental announcement stated that MUP traded on Klickl and Richberg cryptocurrency exchange platforms and that Klickl was licensed by the Abu Dhabi Global Market Financial Services Regulatory Authority.",
    "EV-00526": "渝太地产: the 2025 annual report stated that the board reviewed compliance with legal and regulatory requirements and that the company complied with the CG Code except for deviations from C.2.1 and C.3.3.",
}


def _is_exit_claim_layer_batch1(row: dict[str, str]) -> bool:
    """Return True for weak body-signal rows triaged to leave the claim layer.

    These rows remain in `dd_evidence_table.csv` for trace continuity. They are
    excluded only from claim-level certification because the first triage pass
    classified them as auditor TOC/notice/report-label hits, generic regulatory
    wording, or standalone brand mentions rather than quote-ready DD facts.
    """

    composite = (
        _clean(row.get("company_name")).strip(),
        _clean(row.get("field_name")).strip().lower(),
        _clean(row.get("field_value")).strip(),
        _clean(row.get("source_title")).strip(),
    )
    return composite in EXIT_CLAIM_LAYER_BATCH1_COMPOSITES


def _is_exit_claim_layer_batch3(row: dict[str, str]) -> bool:
    return _clean(row.get("evidence_id")).strip() in EXIT_CLAIM_LAYER_BATCH3_EVIDENCE_IDS


def _promoted_body_signal_claim_text(row: dict[str, str]) -> str:
    return PROMOTED_BODY_SIGNAL_CLAIMS.get(_clean(row.get("evidence_id")).strip(), "")


def _is_nonclaim_dd_signal(row: dict[str, str]) -> bool:
    field_name = _clean(row.get("field_name")).strip().lower()
    field_value = _clean(row.get("field_value")).strip().lower()
    verification_status = _clean(row.get("verification_status")).strip().lower()
    if field_name == "hkexnews_announcement_capture":
        return True
    if field_name.startswith("hkexnews_title_signal:"):
        return True
    if verification_status in {"metadata_only", "document_derived", "structured_source_unverified_against_issuer_pdf"}:
        return True
    if field_name == "document_body_signal:audit" and field_value == "auditor":
        return True
    if _is_exit_claim_layer_batch1(row):
        return True
    if _is_exit_claim_layer_batch3(row):
        return True
    return False


def _cert_status(*, source_id: str, calculation_required: str = "No", calculation_replayed: str = "No", human_review_required: str = "No", severity: str = "low") -> str:
    if not source_id:
        return "Insufficient Evidence"
    if calculation_required == "Yes" and calculation_replayed != "Yes":
        return "Needs Human Review"
    if human_review_required == "Yes" or severity in {"high", "medium"}:
        return "Needs Human Review" if severity == "high" else "Certified with DD Issues"
    return "Certified"


def build_source_inventory() -> list[dict[str, str]]:
    return [
        {
            "source_id": "HKEXNEWS_OFFICIAL",
            "source_name": "HKEXnews / 披露易",
            "source_category": "official",
            "priority_level": "1",
            "official_status": "official",
            "allowed_use": "financial facts; filings; audit opinions; transactions; regulatory disclosures",
            "restrictions": "preferred source for material claims",
            "default_confidence": "high",
        },
        {
            "source_id": "HKEX_LISTED_COMPANY_LIST",
            "source_name": "HKEX listed company list",
            "source_category": "official",
            "priority_level": "1",
            "official_status": "official",
            "allowed_use": "universe construction; listing status",
            "restrictions": "cannot alone support DD-level conclusions",
            "default_confidence": "high",
        },
        {
            "source_id": "AKSHARE_HK",
            "source_name": "AKShare HK market data",
            "source_category": "structured",
            "priority_level": "2",
            "official_status": "non_official",
            "allowed_use": "market snapshot; first-pass screening",
            "restrictions": "not sufficient alone for final material claims",
            "default_confidence": "medium",
        },
        {
            "source_id": "COMPANY_IR",
            "source_name": "Company IR / official website",
            "source_category": "corporate",
            "priority_level": "3",
            "official_status": "non_official",
            "allowed_use": "business description; channels; brand narrative",
            "restrictions": "cannot replace audited or filing-based facts",
            "default_confidence": "medium",
        },
        {
            "source_id": "INDUSTRY_AND_COMPARABLES",
            "source_name": "Industry / comparable sources",
            "source_category": "secondary",
            "priority_level": "3",
            "official_status": "non_official",
            "allowed_use": "commercial thesis; industry context; optionality",
            "restrictions": "cannot be treated as high-confidence fact",
            "default_confidence": "low",
        },
        {
            "source_id": "FINANCIAL_CALCULATION_SHEET",
            "source_name": "Deterministic financial calculation sheet",
            "source_category": "derived",
            "priority_level": "2",
            "official_status": "derived_from_trace",
            "allowed_use": "replayed ranking calculations; score math",
            "restrictions": "must be replayed from trace inputs before clean external delivery",
            "default_confidence": "medium",
        },
        {
            "source_id": "DD_SCAFFOLD",
            "source_name": "Candidate DD scaffold",
            "source_category": "derived",
            "priority_level": "3",
            "official_status": "non_official",
            "allowed_use": "internal DD queueing; issue scaffolding",
            "restrictions": "not sufficient alone for clean external factual claims",
            "default_confidence": "low",
        },
    ]


def map_universe_rows(universe_rows: list[dict[str, Any]], fallback_source_id: str, data_date: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for idx, row in enumerate(universe_rows, 1):
        out.append(
            {
                "universe_id": f"UNI-{idx:05d}",
                "stock_code": _code(row),
                "company_name": _company(row),
                "board": _clean(row.get("board") or "unknown"),
                "industry": _clean(row.get("industry")),
                "market_cap_hkd": _clean(row.get("market_cap_hkd")),
                "pb_ratio": _clean(row.get("pb_ratio") or row.get("pb")),
                "listing_status": _clean(row.get("listing_status") or "unknown"),
                "initial_inclusion_reason": "Included in generator universe before certified hard filters.",
                "source_id": _clean(row.get("source") or fallback_source_id or "AKSHARE_HK"),
                "data_date": _clean(row.get("source_date") or row.get("retrieved_at") or data_date),
            }
        )
    return out


def map_hard_filter_rows(screening_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for idx, row in enumerate(screening_rows, 1):
        status = _clean(row.get("screening_status") or "watchlist")
        severity = _severity_from_flags(row.get("major_risk_flag"), row.get("suspension_flag"), row.get("audit_opinion_flag"))
        out.append(
            {
                "filter_record_id": f"HF-{idx:05d}",
                "stock_code": _code(row),
                "company_name": _company(row),
                "filter_stage": "hard_filter",
                "filter_name": "Generator initial hard filter bundle",
                "filter_result": status,
                "rationale": _clean(row.get("screening_reason") or row.get("notes") or "Generator produced initial screening status."),
                "source_id": _clean(row.get("data_source") or "AKSHARE_HK"),
                "er_brb_rule_id": "ERHF-GENERATOR-BUNDLE",
                "human_review_required": _human_required(severity, "partial_support" if status == "watchlist" else ""),
            }
        )
    return out


def map_exclusion_rows(screening_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in screening_rows:
        status = _clean(row.get("screening_status")).lower()
        if status not in {"exclude", "excluded", "fail"}:
            continue
        idx = len(out) + 1
        severity = _severity_from_flags(row.get("major_risk_flag"), row.get("suspension_flag"), row.get("audit_opinion_flag"))
        out.append(
            {
                "exclusion_id": f"EX-{idx:05d}",
                "stock_code": _code(row),
                "company_name": _company(row),
                "exclusion_stage": "hard_filter",
                "exclusion_reason": _clean(row.get("screening_reason") or "Excluded by generator initial screening."),
                "severity": severity,
                "source_id": _clean(row.get("data_source") or "AKSHARE_HK"),
                "uncertainty_label": "partial_support" if _clean(row.get("data_source")).upper() != "HKEXNEWS_OFFICIAL" else "none",
                "reviewer_note": "PCE should confirm exclusion against official filings if material to case study.",
            }
        )
    return out


def map_dd_evidence_rows(evidence_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for idx, row in enumerate(evidence_rows, 1):
        source_id = _clean(row.get("source_id") or row.get("source_type") or "")
        source_link = _clean(row.get("source_url") or row.get("file_path"))
        out.append(
            {
                "evidence_id": f"EV-{idx:05d}",
                "stock_code": _code(row),
                "company_name": _company(row),
                "field_name": _clean(row.get("field_name")),
                "field_value": _clean(row.get("field_value")),
                "claim_type": _clean(row.get("claim_type") or "fact"),
                "source_id": source_id,
                "source_title": _clean(row.get("source_title")),
                "source_link_or_file": source_link,
                "support_level": _clean(row.get("support_level") or "secondary"),
                "verification_status": _clean(row.get("verification_status") or "needs_review"),
                "confidence_level": _clean(row.get("confidence_level") or "medium"),
                "notes": _clean(row.get("notes")),
            }
        )
    return out


def map_risk_rows(
    screening_rows: list[dict[str, Any]],
    candidate_dd_rows: list[dict[str, Any]],
    material_codes: set[str],
    material_names: set[str],
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in screening_rows:
        flags = [
            ("suspension", row.get("suspension_flag")),
            ("audit", row.get("audit_opinion_flag")),
            ("major_risk", row.get("major_risk_flag")),
        ]
        is_material = _is_material_company(row, material_codes, material_names)
        for category, flag in flags:
            flag_text = _clean(flag)
            if not flag_text or flag_text.lower() in {"none", "clean", "false", "0"}:
                continue
            severity = _severity_from_flags(flag_text)
            is_placeholder = flag_text.strip().lower() == "unknown"
            review_required = "Yes" if not is_placeholder and (severity == "high" or (severity == "medium" and is_material)) else "No"
            idx = len(out) + 1
            out.append(
                {
                    "risk_id": f"RISK-{idx:05d}",
                    "stock_code": _code(row),
                    "company_name": _company(row),
                    "risk_category": category,
                    "risk_flag": flag_text,
                    "risk_description": f"Generator screening flagged {category}: {flag_text}.",
                    "source_id": _clean(row.get("data_source") or "AKSHARE_HK"),
                    "severity": severity,
                    "human_review_required": review_required,
                    "mitigation_or_next_step": "Verify against HKEXnews filings and legal / DD review before certification." if review_required == "Yes" else "Track in risk matrix; no blocking sign-off until promoted into material review scope.",
                }
            )
    dd_risk_fields = [
        "public_float_risk",
        "debt_risk",
        "litigation_risk",
        "regulatory_risk",
        "audit_risk",
        "convertible_bond_risk",
        "rto_risk",
    ]
    for row in candidate_dd_rows:
        is_material = _is_material_company(row, material_codes, material_names)
        for field in dd_risk_fields:
            flag_text = _clean(row.get(field))
            if not flag_text or flag_text.lower() in {"none", "low", "false", "0"}:
                continue
            severity = _severity_from_flags(flag_text)
            is_placeholder = flag_text.strip().lower() == "unknown"
            review_required = "Yes" if not is_placeholder and (severity == "high" or (severity == "medium" and is_material)) else "No"
            idx = len(out) + 1
            out.append(
                {
                    "risk_id": f"RISK-{idx:05d}",
                    "stock_code": _code(row),
                    "company_name": _company(row),
                    "risk_category": field,
                    "risk_flag": flag_text,
                    "risk_description": f"Candidate DD scaffold flagged {field}: {flag_text}.",
                    "source_id": "DD_SCAFFOLD",
                    "severity": severity,
                    "human_review_required": review_required,
                    "mitigation_or_next_step": "Review underlying evidence and update PCE audit row." if review_required == "Yes" else "Document as non-blocking scaffold risk unless elevated during DD.",
                }
            )
    return out


def map_financial_calculation_rows(candidate_dd_rows: list[dict[str, Any]], material_codes: set[str], material_names: set[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    score_fields = [
        "synergy_score",
        "value_creation_score",
        "transaction_feasibility_score",
        "risk_control_score",
        "weighted_total_score",
    ]
    for row in candidate_dd_rows:
        if not any(_clean(row.get(field)) for field in score_fields):
            continue
        idx = len(out) + 1
        claim_id = f"CLM-CALC-{idx:05d}"
        is_material = _is_material_company(row, material_codes, material_names)
        calc_required = "Yes" if is_material else "No"
        output_value, replayed_status, replay_note = _replay_weighted_total(row)
        out.append(
            {
                "calc_id": f"CALC-{idx:05d}",
                "stock_code": _code(row),
                "company_name": _company(row),
                "metric_name": "weighted_total_score",
                "input_1": "; ".join(f"{field}={_clean(row.get(field))}" for field in score_fields if field != "weighted_total_score"),
                "input_2": "weights: synergy 0.30; value_creation 0.30; transaction_feasibility 0.25; risk_control 0.15",
                "formula_or_logic": "weighted_total_score = synergy_score*0.30 + value_creation_score*0.30 + transaction_feasibility_score*0.25 + risk_control_score*0.15",
                "output_value": output_value,
                "unit": "points",
                "calculation_required": calc_required,
                "calculation_replayed": replayed_status if calc_required == "Yes" else "No",
                "linked_claim_id": claim_id,
                "notes": replay_note if calc_required == "Yes" else "Non-material scaffold ranking row; replay not required unless promoted into shortlist / final delivery scope.",
            }
        )
    return out


def map_er_brb_rows(screening_rows: list[dict[str, Any]], candidate_dd_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    status_score = {"pass": "1.0", "watchlist": "0.5", "exclude": "0.0", "excluded": "0.0", "fail": "0.0"}
    dd_risk_fields = [
        "public_float_risk",
        "debt_risk",
        "litigation_risk",
        "regulatory_risk",
        "audit_risk",
        "convertible_bond_risk",
        "rto_risk",
    ]

    for row in screening_rows:
        idx = len(out) + 1
        status = _clean(row.get("screening_status") or "watchlist").lower()
        source_id = _clean(row.get("data_source") or "AKSHARE_HK")
        reliability = _source_reliability(source_id)
        severity = _severity_from_flags(row.get("major_risk_flag"), row.get("suspension_flag"), row.get("audit_opinion_flag"))

        pass_score = 18.0
        warning_score = 18.0
        exclude_score = 18.0
        insufficient_score = 12.0

        if status == "pass":
            pass_score += 34
            warning_score += 10
        elif status == "watchlist":
            pass_score += 12
            warning_score += 30
        else:
            exclude_score += 42
            insufficient_score += 6

        if _truthy(row.get("low_valuation_flag")):
            pass_score += 10
        else:
            warning_score += 5
            exclude_score += 6

        if _truthy(row.get("small_market_cap_flag")):
            pass_score += 12
        else:
            exclude_score += 18

        liquidity_flag = _clean(row.get("liquidity_flag")).lower()
        if liquidity_flag == "adequate":
            pass_score += 8
        elif liquidity_flag in {"unknown", "", "none"}:
            insufficient_score += 12
        else:
            warning_score += 8
            exclude_score += 10

        if severity == "high":
            warning_score += 15
            exclude_score += 18
        elif severity == "medium":
            warning_score += 20
            insufficient_score += 6

        insufficient_score += max(0.0, (0.85 - reliability) * 40)
        beliefs = _normalize_beliefs([
            ("Pass", pass_score),
            ("Warning", warning_score),
            ("Exclude", exclude_score),
            ("Insufficient Evidence", insufficient_score),
            ("Confidence Buffer", max(4.0, reliability * 10)),
        ])
        belief_map = {label: int(value) for label, value in beliefs}
        if status in {"exclude", "excluded", "fail"} or belief_map.get("Exclude", 0) >= 45:
            decision = "Exclude"
        elif belief_map.get("Insufficient Evidence", 0) >= 35:
            decision = "Insufficient Evidence"
        elif status == "watchlist" or belief_map.get("Warning", 0) >= belief_map.get("Pass", 0):
            decision = "Needs DD"
        else:
            decision = "Pass"
        uncertainty = "partial_support" if decision in {"Needs DD", "Insufficient Evidence"} else "none"
        out.append(
            {
                "er_brb_id": f"ERBRB-{idx:05d}",
                "stage": "hard_filter",
                "stock_code": _code(row),
                "company_name": _company(row),
                "rule_id": "ERHF-GENERATOR-BUNDLE",
                "rule_family": "hard_filter_mechanical_gate",
                "score_component": "hard_filter_retention_signal",
                "score_value": status_score.get(status, "0.5"),
                "source_reliability": f"{reliability:.2f}",
                "belief_state_1_label": beliefs[0][0],
                "belief_state_1_value": beliefs[0][1],
                "belief_state_2_label": beliefs[1][0],
                "belief_state_2_value": beliefs[1][1],
                "belief_state_3_label": beliefs[2][0],
                "belief_state_3_value": beliefs[2][1],
                "belief_state_4_label": beliefs[3][0],
                "belief_state_4_value": beliefs[3][1],
                "belief_state_5_label": beliefs[4][0],
                "belief_state_5_value": beliefs[4][1],
                "aggregation_logic": "signal × source reliability -> belief distribution -> ER aggregation -> hard-filter retain/exclude/DD-escalation decision",
                "decision_output": decision,
                "requires_dd_escalation": "Yes" if decision in {"Pass", "Needs DD", "Insufficient Evidence"} else "No",
                "evidence_gap_note": _clean(row.get("notes") or "Mechanical screen still requires official HKEX/HKEXnews confirmation before any external conclusion."),
                "rationale": _clean(row.get("screening_reason") or "Initial hard-filter status converted into ER/BRB trace signal."),
                "source_id": source_id,
                "linked_claim_id": f"CLM-HF-{idx:05d}",
                "uncertainty_label": uncertainty,
                "human_review_required": _human_required(severity, uncertainty),
            }
        )

    for row in candidate_dd_rows:
        weighted = _clean(row.get("weighted_total_score"))
        if not weighted:
            continue
        idx = len(out) + 1
        try:
            weighted_value = float(weighted)
        except ValueError:
            weighted_value = 0.0
        source_evidence_status = _clean(row.get("source_evidence_status") or "partial")
        reliability = 0.85 if source_evidence_status == "complete" else 0.72 if source_evidence_status == "body_text_extracted_partial" else 0.60
        risk_hits = _risk_hit_count(row, dd_risk_fields)
        high_severity = _severity_from_flags(*(row.get(field) for field in dd_risk_fields))

        clean_score = max(5.0, 22 + weighted_value * 6 - risk_hits * 3)
        manageable_score = 18 + (8 if 5.0 <= weighted_value <= 7.5 else 2) + (10 if source_evidence_status != "complete" else 0)
        high_score = 8 + risk_hits * 8 + (6 if source_evidence_status == "body_text_extracted_partial" else 0)
        critical_score = 4 + (18 if high_severity == "high" else 0)
        insufficient_score = 6 + (22 if source_evidence_status != "complete" else 0)
        beliefs = _normalize_beliefs([
            ("Clean / Low Risk", clean_score),
            ("Manageable Risk", manageable_score),
            ("High Risk", high_score),
            ("Critical / Not Tradable", critical_score),
            ("Insufficient Evidence", insufficient_score),
        ])
        belief_map = {label: int(value) for label, value in beliefs}
        if belief_map.get("Critical / Not Tradable", 0) >= 35:
            decision = "Reject"
        elif belief_map.get("Insufficient Evidence", 0) >= 30:
            decision = "Insufficient Evidence"
        elif belief_map.get("High Risk", 0) >= 28 or source_evidence_status != "complete":
            decision = "Proceed with Conditions"
        else:
            decision = "Proceed"
        uncertainty = "needs_dd_evidence" if source_evidence_status != "complete" else "none"
        out.append(
            {
                "er_brb_id": f"ERBRB-{idx:05d}",
                "stage": "post_dd",
                "stock_code": _code(row),
                "company_name": _company(row),
                "rule_id": "ERDD-WEIGHTED-RERANK",
                "rule_family": "post_dd_reranking",
                "score_component": "post_dd_weighted_score",
                "score_value": weighted,
                "source_reliability": f"{reliability:.2f}",
                "belief_state_1_label": beliefs[0][0],
                "belief_state_1_value": beliefs[0][1],
                "belief_state_2_label": beliefs[1][0],
                "belief_state_2_value": beliefs[1][1],
                "belief_state_3_label": beliefs[2][0],
                "belief_state_3_value": beliefs[2][1],
                "belief_state_4_label": beliefs[3][0],
                "belief_state_4_value": beliefs[3][1],
                "belief_state_5_label": beliefs[4][0],
                "belief_state_5_value": beliefs[4][1],
                "aggregation_logic": "weighted DD score + evidence completeness modifier + risk penalty -> ER/BRB belief distribution -> reranking / condition-setting decision",
                "decision_output": decision,
                "requires_dd_escalation": "Yes" if decision != "Proceed" else "No",
                "evidence_gap_note": _clean(row.get("source_evidence_status") or "partial") + "; analyst must reconcile document-level evidence before external certification.",
                "rationale": _clean(row.get("recommendation_level") or "DD scaffold weighted score carried into ER/BRB reranking trace."),
                "source_id": "DD_SCAFFOLD",
                "linked_claim_id": f"CLM-ERDD-{idx:05d}",
                "uncertainty_label": uncertainty,
                "human_review_required": "Yes" if source_evidence_status != "complete" or decision != "Proceed" else "No",
            }
        )
    return out


def map_claim_rows(
    dd_evidence_rows: list[dict[str, str]],
    financial_calc_rows: list[dict[str, str]],
    risk_rows: list[dict[str, str]],
    material_codes: set[str],
    material_names: set[str],
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in dd_evidence_rows:
        source_id = row.get("source_id", "")
        promoted_claim_text = _promoted_body_signal_claim_text(row)
        uncertainty = "none" if promoted_claim_text or _is_verified_evidence(row.get("verification_status", "")) else "needs_review"
        is_material = _is_material_company(row, material_codes, material_names)
        if not is_material or _is_nonclaim_dd_signal(row):
            continue
        idx = len(out) + 1
        review_required = "Yes" if uncertainty in {"needs_dd_evidence", "high_risk_review"} else "No"
        out.append(
            {
                "claim_id": f"CLM-EV-{idx:05d}",
                "claim_text": promoted_claim_text or f"{row.get('company_name')}: {row.get('field_name')} = {row.get('field_value')}",
                "company_name": row.get("company_name", ""),
                "stage": "dd_evidence",
                "source_id": source_id,
                "evidence_id": row.get("evidence_id", ""),
                "calc_id": "",
                "risk_id": "",
                "calculation_required": "No",
                "calculation_replayed": "No",
                "uncertainty_label": uncertainty,
                "human_review_required": review_required,
                "delivery_scope": _delivery_scope_for_claim(stage="dd_evidence", source_id=source_id, material=is_material, verification_status=row.get("verification_status", "")),
                "certification_status": _cert_status(
                    source_id=source_id,
                    human_review_required=review_required,
                    severity="medium" if review_required == "Yes" else "low",
                ),
            }
        )
    for row in financial_calc_rows:
        idx = len(out) + 1
        calc_required = row.get("calculation_required", "Yes")
        replay_missing = calc_required == "Yes" and row.get("calculation_replayed") != "Yes"
        out.append(
            {
                "claim_id": row.get("linked_claim_id") or f"CLM-CALC-{idx:05d}",
                "claim_text": f"{row.get('company_name')}: {row.get('metric_name')} = {row.get('output_value')}",
                "company_name": row.get("company_name", ""),
                "stage": "financial_calculation",
                "source_id": "FINANCIAL_CALCULATION_SHEET",
                "evidence_id": "",
                "calc_id": row.get("calc_id", ""),
                "risk_id": "",
                "calculation_required": calc_required,
                "calculation_replayed": row.get("calculation_replayed", "No"),
                "uncertainty_label": "needs_replay" if replay_missing else "none",
                "human_review_required": "Yes" if replay_missing else "No",
                "delivery_scope": _delivery_scope_for_claim(stage="financial_calculation", source_id="FINANCIAL_CALCULATION_SHEET", material=calc_required == "Yes", calculation_required=calc_required),
                "certification_status": _cert_status(
                    source_id="FINANCIAL_CALCULATION_SHEET",
                    calculation_required=calc_required,
                    calculation_replayed=row.get("calculation_replayed", "No"),
                    human_review_required="Yes" if replay_missing else "No",
                    severity="medium" if replay_missing else "low",
                ),
            }
        )
    for row in risk_rows:
        severity = row.get("severity", "medium")
        review_required = row.get("human_review_required", "No")
        if review_required != "Yes" and severity != "high":
            continue
        idx = len(out) + 1
        out.append(
            {
                "claim_id": row.get("risk_id", "").replace("RISK-", "CLM-RISK-") or f"CLM-RISK-{idx:05d}",
                "claim_text": f"{row.get('company_name')}: {row.get('risk_category')} risk = {row.get('risk_flag')}",
                "company_name": row.get("company_name", ""),
                "stage": "risk_review",
                "source_id": row.get("source_id", ""),
                "evidence_id": "",
                "calc_id": "",
                "risk_id": row.get("risk_id", ""),
                "calculation_required": "No",
                "calculation_replayed": "No",
                "uncertainty_label": "high_risk_review" if severity == "high" else "dd_issue" if severity == "medium" else "none",
                "human_review_required": review_required,
                "delivery_scope": "internal_trace",
                "certification_status": _cert_status(source_id=row.get("source_id", ""), human_review_required=review_required, severity=severity),
            }
        )
    return out


def map_human_review_rows(
    risk_rows: list[dict[str, str]],
    claim_rows: list[dict[str, str]],
    material_codes: set[str],
    material_names: set[str],
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    blocking_risk_topics = {"audit", "major_risk", "regulatory_risk", "audit_risk", "rto_risk", "litigation_risk", "debt_risk"}
    for row in risk_rows:
        if row.get("human_review_required") != "Yes":
            continue
        idx = len(out) + 1
        priority = "high" if row.get("severity") == "high" else "medium"
        is_material = _is_material_company(row, material_codes, material_names)
        blocking = "Yes" if row.get("severity") == "high" or (is_material and row.get("risk_category") in blocking_risk_topics) else "No"
        out.append(
            {
                "review_item_id": f"HR-{idx:05d}",
                "company_name": row.get("company_name", ""),
                "review_topic": row.get("risk_category", "risk review"),
                "trigger_reason": row.get("risk_description", "Risk matrix trigger."),
                "priority": priority,
                "required_reviewer_type": "legal / transaction advisor / DD analyst" if priority == "high" else "DD analyst / transaction advisor",
                "assigned_reviewer_name": "",
                "status": "open",
                "review_completed_at": "",
                "review_outcome": "",
                "signoff_blocking": blocking,
                "blocking_reason": "Material or high-severity risk must be closed before external final delivery." if blocking == "Yes" else "",
                "linked_claim_id": row.get("risk_id", "").replace("RISK-", "CLM-RISK-") or f"CLM-RISK-{idx:05d}",
                "notes": row.get("mitigation_or_next_step", ""),
            }
        )
    for row in claim_rows:
        if row.get("human_review_required") != "Yes" or row.get("stage") == "risk_review":
            continue
        stage = row.get("stage", "claim review")
        uncertainty = row.get("uncertainty_label", "Needs review.")
        if stage == "dd_evidence" and uncertainty not in {"needs_dd_evidence", "high_risk_review"}:
            continue
        idx = len(out) + 1
        blocking = "Yes" if uncertainty in {"needs_replay", "high_risk_review", "needs_dd_evidence"} else "No"
        reviewer_type = "accounting reviewer" if stage == "financial_calculation" else "DD analyst / legal / transaction advisor"
        out.append(
            {
                "review_item_id": f"HR-{idx:05d}",
                "company_name": row.get("company_name", ""),
                "review_topic": stage,
                "trigger_reason": uncertainty,
                "priority": "high" if blocking == "Yes" else "medium",
                "required_reviewer_type": reviewer_type,
                "assigned_reviewer_name": "",
                "status": "open",
                "review_completed_at": "",
                "review_outcome": "",
                "signoff_blocking": blocking,
                "blocking_reason": "Claim must be reviewed / replayed before certificate can be signed." if blocking == "Yes" else "",
                "linked_claim_id": row.get("claim_id", ""),
                "notes": "Resolve before final delivery certificate can be signed.",
            }
        )
    return out


def map_pce_audit_rows(claim_rows: list[dict[str, str]], source_type_by_id: dict[str, str] | None = None) -> list[dict[str, str]]:
    source_type_by_id = source_type_by_id or {}
    out: list[dict[str, str]] = []
    for row in claim_rows:
        source_id = row.get("source_id", "")
        source_type = source_type_by_id.get(source_id) or _source_category_from_id(source_id)
        status = row.get("certification_status", "Needs Human Review")
        evidence_status = "sufficient" if status == "Certified" else "partial" if status == "Certified with DD Issues" else "needs_review"
        uncertainty = row.get("uncertainty_label", "none")
        if not source_id:
            status = "Insufficient Evidence"
            evidence_status = "missing"
        elif source_type != "official" and row.get("stage") == "dd_evidence":
            if status == "Certified":
                status = "Certified with DD Issues"
                evidence_status = "partial"
            if uncertainty == "none":
                uncertainty = "non_official_source"
        elif uncertainty in {"needs_review", "needs_dd_evidence", "needs_replay", "high_risk_review"} and status == "Certified":
            status = "Certified with DD Issues"
            evidence_status = "partial"
        out.append(
            {
                "trace_id": TRACE_ID,
                "case_name": CASE_NAME,
                "stage": row.get("stage", ""),
                "company_name": row.get("company_name", ""),
                "action_taken": "certification_check",
                "claim_id": row.get("claim_id", ""),
                "claim_text": row.get("claim_text", ""),
                "source_id": source_id,
                "source_type": source_type,
                "source_link_or_file": row.get("evidence_id") or row.get("calc_id") or row.get("risk_id") or "",
                "evidence_status": evidence_status,
                "calculation_required": row.get("calculation_required", "No"),
                "calculation_replayed": row.get("calculation_replayed", "No"),
                "risk_flag": "high" if row.get("stage") == "risk_review" and row.get("human_review_required") == "Yes" else "warning" if row.get("human_review_required") == "Yes" else "none",
                "uncertainty_label": uncertainty,
                "human_review_required": row.get("human_review_required", "No"),
                "delivery_scope": row.get("delivery_scope", "internal_trace"),
                "certification_status": status,
                "reviewer_note": "Generated by PCE audit export; reviewer should resolve non-Certified rows before final delivery.",
            }
        )
    return out


def write_final_delivery_certificate(trace_dir: Path, *, claim_rows: list[dict[str, str]], pce_rows: list[dict[str, str]], human_review_rows: list[dict[str, str]]) -> None:
    blockers: list[str] = []
    warnings: list[str] = []
    if not claim_rows:
        blockers.append("No claim-to-evidence map rows generated.")

    unresolved = [row for row in pce_rows if row.get("certification_status") not in {"Certified", "Certified with DD Issues"}]
    calc_not_replayed = [row for row in pce_rows if row.get("calculation_required") == "Yes" and row.get("calculation_replayed") != "Yes"]
    missing_source = [row for row in pce_rows if not (row.get("source_id") or "").strip()]
    unsupported_certified = [row for row in pce_rows if row.get("evidence_status") in {"missing", "unsupported"} and row.get("certification_status") in {"Certified", "Certified with DD Issues"}]
    non_official_certified = [row for row in pce_rows if row.get("source_type") not in {"official", "unknown"} and row.get("certification_status") == "Certified"]
    blocking_signoffs = [row for row in human_review_rows if row.get("signoff_blocking") == "Yes" and row.get("status") != "completed"]
    open_high_risk = [row for row in pce_rows if row.get("risk_flag") == "high" and row.get("human_review_required") == "Yes"]

    if unresolved:
        blockers.append(f"{len(unresolved)} audit rows are not delivery-ready.")
    if calc_not_replayed:
        blockers.append(f"{len(calc_not_replayed)} calculation-based claims still need replay.")
    if missing_source:
        blockers.append(f"{len(missing_source)} material audit rows have no source_id.")
    if unsupported_certified:
        blockers.append(f"{len(unsupported_certified)} rows with missing/unsupported evidence are incorrectly marked certifiable.")
    if blocking_signoffs:
        blockers.append(f"{len(blocking_signoffs)} blocking human-review items remain unresolved.")
    if open_high_risk:
        blockers.append(f"{len(open_high_risk)} high-risk rows still require completed human sign-off.")
    if non_official_certified:
        warnings.append(f"{len(non_official_certified)} rows rely on non-official sources and should not be treated as high-confidence facts.")

    if blockers:
        status = "Draft / Not Yet Certified"
    elif any(row.get("certification_status") == "Certified with DD Issues" for row in pce_rows):
        status = "Certified with DD Issues"
    else:
        status = "Certified"

    status_counts: dict[str, int] = {}
    for row in pce_rows:
        key = row.get("certification_status") or "UNKNOWN"
        status_counts[key] = status_counts.get(key, 0) + 1

    content = [
        "# Final Delivery Certificate",
        "",
        f"- **certificate_status:** {status}",
        f"- **case_name:** {CASE_NAME}",
        f"- **trace_id:** {TRACE_ID}",
        "- **certification_scope:** case study + final report",
        f"- **generated_at:** {_now()}",
        f"- **audit_rows:** {len(pce_rows)}",
        f"- **claim_rows:** {len(claim_rows)}",
        f"- **blocking_human_review_rows:** {len(blocking_signoffs)}",
        "- **core_rule:** No certified trace, no final delivery.",
        "",
        "## Status Counts",
    ]
    if status_counts:
        content.extend(f"- {k}: {v}" for k, v in sorted(status_counts.items()))
    else:
        content.append("- No audit rows.")
    content.extend(["", "## Blockers"])
    if blockers:
        content.extend(f"- {item}" for item in blockers)
    else:
        content.append("- None based on current PCE export. Residual DD issues must still be disclosed.")
    content.extend(["", "## Warnings / DD Issues"])
    if warnings:
        content.extend(f"- {item}" for item in warnings)
    else:
        content.append("- None.")
    content.extend(
        [
            "",
            "## Approved Deliverables If Certified",
            "- outputs/reports/tuntun_hk_restructuring_screening_report.md",
            "- outputs/case_studies/tuntun_hk_case_study.md",
            "",
            "## Reviewer Signoff",
            "Final external delivery requires explicit human sign-off for all blocking review items. `Certified with DD Issues` may support internal case-study / DD workflow handoff only if those issues are disclosed.",
        ]
    )
    (trace_dir / "final_delivery_certificate.md").write_text("\n".join(content) + "\n", encoding="utf-8")


def export_certified_trace(
    *,
    trace_dir: Path,
    pce_audit_dir: Path,
    universe_rows: list[dict[str, Any]],
    screening_rows: list[dict[str, Any]],
    candidate_dd_rows: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    source_id: str,
    data_date: str,
    fetch_meta: dict[str, Any],
    hkexnews_meta: dict[str, Any],
) -> dict[str, str]:
    trace_dir.mkdir(parents=True, exist_ok=True)
    pce_audit_dir.mkdir(parents=True, exist_ok=True)

    source_inventory = build_source_inventory()
    source_type_by_id = {row["source_id"]: row["source_category"] for row in source_inventory}
    retrieval_rows = [
        {
            "retrieval_id": "RTL-00001",
            "retrieval_datetime": _now(),
            "stage": "market_snapshot",
            "company_name": "ALL",
            "source_id": _clean(fetch_meta.get("source_id") or source_id),
            "query_or_document": _clean(fetch_meta.get("function") or "market snapshot / existing cache"),
            "action_taken": "generator_market_snapshot",
            "output_file": "candidate_universe_table.csv",
            "result_status": _clean(fetch_meta.get("status") or "unknown"),
            "notes": _clean(fetch_meta.get("error") or fetch_meta.get("errors") or ""),
        },
        {
            "retrieval_id": "RTL-00002",
            "retrieval_datetime": _now(),
            "stage": "hkexnews",
            "company_name": "pass/watchlist candidates",
            "source_id": "HKEXNEWS_OFFICIAL",
            "query_or_document": f"years_back={hkexnews_meta.get('years_back', '')}; candidate_count={hkexnews_meta.get('candidate_count', '')}",
            "action_taken": "generator_hkexnews_title_search",
            "output_file": "dd_evidence_table.csv",
            "result_status": _clean(hkexnews_meta.get("status") or "not_run"),
            "notes": _clean(hkexnews_meta.get("error_samples") or "Title metadata is not full document-body DD."),
        },
    ]

    material_codes, material_names = _material_company_sets(candidate_dd_rows, evidence_rows)

    candidate_universe = map_universe_rows(universe_rows, source_id, data_date)
    hard_filters = map_hard_filter_rows(screening_rows)
    exclusions = map_exclusion_rows(screening_rows)
    dd_evidence = map_dd_evidence_rows(evidence_rows)
    risk_rows = map_risk_rows(screening_rows, candidate_dd_rows, material_codes, material_names)
    calc_rows = map_financial_calculation_rows(candidate_dd_rows, material_codes, material_names)
    er_brb_rows = map_er_brb_rows(screening_rows, candidate_dd_rows)
    claim_rows = map_claim_rows(dd_evidence, calc_rows, risk_rows, material_codes, material_names)
    human_review_rows = map_human_review_rows(risk_rows, claim_rows, material_codes, material_names)
    pce_rows = map_pce_audit_rows(claim_rows, source_type_by_id)

    outputs = {
        "source_inventory_csv": trace_dir / "source_inventory.csv",
        "retrieval_log_csv": trace_dir / "retrieval_log.csv",
        "candidate_universe_table_csv": trace_dir / "candidate_universe_table.csv",
        "hard_filter_table_csv": trace_dir / "hard_filter_table.csv",
        "exclusion_reason_table_csv": trace_dir / "exclusion_reason_table.csv",
        "dd_evidence_table_csv": trace_dir / "dd_evidence_table.csv",
        "risk_matrix_csv": trace_dir / "risk_matrix.csv",
        "financial_calculation_sheet_csv": trace_dir / "financial_calculation_sheet.csv",
        "er_brb_scoring_table_csv": trace_dir / "er_brb_scoring_table.csv",
        "claim_to_evidence_map_csv": trace_dir / "claim_to_evidence_map.csv",
        "human_review_checklist_csv": trace_dir / "human_review_checklist.csv",
        "pce_audit_current_run_csv": pce_audit_dir / "pce_audit_current_run.csv",
    }

    write_csv(outputs["source_inventory_csv"], source_inventory, SOURCE_INVENTORY_FIELDS)
    write_csv(outputs["retrieval_log_csv"], retrieval_rows, RETRIEVAL_LOG_FIELDS)
    write_csv(outputs["candidate_universe_table_csv"], candidate_universe, CANDIDATE_UNIVERSE_FIELDS)
    write_csv(outputs["hard_filter_table_csv"], hard_filters, HARD_FILTER_FIELDS)
    write_csv(outputs["exclusion_reason_table_csv"], exclusions, EXCLUSION_REASON_FIELDS)
    write_csv(outputs["dd_evidence_table_csv"], dd_evidence, DD_EVIDENCE_FIELDS)
    write_csv(outputs["risk_matrix_csv"], risk_rows, RISK_MATRIX_FIELDS)
    write_csv(outputs["financial_calculation_sheet_csv"], calc_rows, FINANCIAL_CALC_FIELDS)
    write_csv(outputs["er_brb_scoring_table_csv"], er_brb_rows, ER_BRB_FIELDS)
    write_csv(outputs["claim_to_evidence_map_csv"], claim_rows, CLAIM_MAP_FIELDS)
    write_csv(outputs["human_review_checklist_csv"], human_review_rows, HUMAN_REVIEW_FIELDS)
    write_csv(outputs["pce_audit_current_run_csv"], pce_rows, PCE_AUDIT_FIELDS)
    write_final_delivery_certificate(trace_dir, claim_rows=claim_rows, pce_rows=pce_rows, human_review_rows=human_review_rows)

    return {key: str(path) for key, path in outputs.items()} | {
        "final_delivery_certificate_md": str(trace_dir / "final_delivery_certificate.md"),
    }
