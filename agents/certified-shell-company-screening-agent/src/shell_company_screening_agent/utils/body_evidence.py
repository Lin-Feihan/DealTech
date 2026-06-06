from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

SIGNAL_TO_DD_FIELD = {
    "document_body_signal:shareholder_control": "control_path_feasibility",
    "document_body_signal:debt_liquidity": "debt_risk",
    "document_body_signal:audit": "audit_risk",
    "document_body_signal:litigation_regulatory": "litigation_risk",
    "document_body_signal:transaction_perimeter": "transaction_complexity",
    "document_body_signal:brand_license_business_continuity": "asset_injection_feasibility",
}


def norm_code(value: str) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return f"{digits[-5:].zfill(5)}.HK" if digits else ""


def summarize_body_evidence(candidate_rows: list[dict[str, str]], evidence_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in evidence_rows:
        code = norm_code(row.get("stock_code", ""))
        if code:
            by_code[code].append(row)

    updated_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    touched = 0
    for row in candidate_rows:
        code = norm_code(row.get("stock_code", ""))
        evs = by_code.get(code, [])
        body_evs = [e for e in evs if e.get("source_type") == "HKEX document body"]
        if not code or not body_evs:
            updated_rows.append(dict(row))
            continue

        new = dict(row)
        field_counts = Counter(e.get("field_name", "") for e in body_evs)
        parsed_docs = field_counts.get("document_body_parse_status", 0)
        signal_fields = sorted(k for k in field_counts if k.startswith("document_body_signal:"))
        signal_notes = []
        for field in signal_fields:
            keywords = []
            urls = []
            for ev in body_evs:
                if ev.get("field_name") == field:
                    if ev.get("field_value"):
                        keywords.extend([x.strip() for x in str(ev["field_value"]).split(",") if x.strip()])
                    if ev.get("source_url"):
                        urls.append(str(ev["source_url"]))
            signal_notes.append(
                f"{field.replace('document_body_signal:', '')}({field_counts[field]}): {', '.join(dict.fromkeys(keywords[:8]))}"
            )
        new["source_evidence_status"] = "body_text_extracted_partial"
        existing_q = new.get("key_dd_questions", "")
        extra_q = "body evidence signals to review: " + " | ".join(signal_notes) if signal_notes else "body evidence parsed; analyst reading required"
        new["key_dd_questions"] = (existing_q + " ; " + extra_q).strip(" ;")

        for field, dd_field in SIGNAL_TO_DD_FIELD.items():
            if field_counts.get(field):
                prior = str(new.get(dd_field, "") or "").strip().lower()
                if prior in {"", "unknown", "pending company document review"}:
                    new[dd_field] = f"body-text keyword signal present ({field_counts[field]} hit group(s)); requires analyst confirmation"

        current_notes = str(new.get("notes", "") or "")
        notes_add = f"Body-level HKEX document parse added: {parsed_docs} document(s), {len(signal_fields)} signal categories; analyst reading still required."
        new["notes"] = (current_notes + " | " + notes_add).strip(" |")
        updated_rows.append(new)
        touched += 1
        summary_rows.append(
            {
                "stock_code": code,
                "company_name": row.get("company_name", ""),
                "body_documents_parsed": parsed_docs,
                "body_evidence_rows": len(body_evs),
                "body_signal_categories": " | ".join(signal_fields),
                "body_signal_notes": " | ".join(signal_notes),
                "updated_source_evidence_status": new.get("source_evidence_status", ""),
            }
        )
    return updated_rows, summary_rows, touched
