from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from html import unescape
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HKEX_BASE_URL = "https://www1.hkexnews.hk"
TITLE_SEARCH_URL = f"{HKEX_BASE_URL}/search/titleSearchServlet.do"
ACTIVE_STOCK_URL = f"{HKEX_BASE_URL}/ncms/script/eds/activestock_sehk_e.json"
INACTIVE_STOCK_URL = f"{HKEX_BASE_URL}/ncms/script/eds/inactivestock_sehk_e.json"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": f"{HKEX_BASE_URL}/search/titlesearch.xhtml?lang=en",
    "Accept": "application/json,text/javascript,*/*;q=0.1",
}

HKEX_ANNOUNCEMENT_FIELDS = [
    "stock_code",
    "company_name",
    "stock_short_name",
    "stock_id",
    "release_time",
    "release_date",
    "title",
    "headline",
    "headline_long",
    "file_link",
    "file_type",
    "file_size",
    "news_id",
    "total_count_for_query",
    "dod_web_path",
    "query_from_date",
    "query_to_date",
    "query_category",
    "query_search_type",
    "source",
    "source_url",
    "notes",
]

SOURCE_EVIDENCE_FIELDS = [
    "stock_code",
    "company_name",
    "field_name",
    "field_value",
    "source_type",
    "source_title",
    "source_url",
    "file_path",
    "document_date",
    "page_number",
    "claim_type",
    "support_level",
    "confidence_level",
    "verification_status",
    "narrative_use",
    "assumption_dependency",
    "notes",
]

_STOCK_LOOKUP_CACHE: dict[str, dict[str, dict[str, Any]]] = {}

SUSPENSION_KEYWORDS = [
    "suspension of trading",
    "trading suspension",
    "trading halt",
    "short halt",
    "resumption of trading",
    "resumption",
]

AUDIT_KEYWORDS = [
    "auditor resignation",
    "change of auditor",
    "appointment of auditor",
    "disclaimer of opinion",
    "qualified opinion",
    "adverse opinion",
    "non-disclaimer",
    "delay in publication of annual results",
    "delay in despatch of annual report",
    "delay in despatch of circular",
]

MAJOR_RISK_HIGH_KEYWORDS = [
    "winding up petition",
    "winding-up petition",
    "liquidation",
    "liquidator",
    "receiver appointed",
    "appointment of receiver",
    "petition",
    "loan default",
    "default on",
    "statutory demand",
    "inside information in relation to liquidation",
]

MAJOR_RISK_WARNING_KEYWORDS = [
    "inside information",
    "profit warning",
    "delay in publication",
    "delay in despatch",
    "debt restructuring",
    "restructuring support agreement",
    "very substantial disposal",
    "connected transaction",
]


def _http_get_text(url: str, params: dict[str, Any] | None = None, timeout: int = 30) -> str:
    if params:
        query = urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{url}?{query}"
    req = Request(url, headers=DEFAULT_HEADERS)
    with urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _http_get_json(url: str, params: dict[str, Any] | None = None, timeout: int = 30) -> Any:
    text = _http_get_text(url, params=params, timeout=timeout)
    return json.loads(text)


def _parse_jsonp(text: str) -> Any:
    payload = text.strip()
    match = re.match(r"^[^(]+\((.*)\)\s*;?\s*$", payload, flags=re.S)
    if not match:
        raise ValueError("Unable to parse JSONP payload from HKEXnews endpoint")
    return json.loads(match.group(1))


def _normalize_stock_code(stock_code: str) -> str:
    digits = re.sub(r"\D", "", stock_code or "")
    if not digits:
        return ""
    return digits[-5:].zfill(5)


def _date_to_compact(d: date) -> str:
    return d.strftime("%Y%m%d")


def _date_from_hkex_release(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def _clean_text(text: str) -> str:
    text = unescape((text or "").replace("<br/>", " ").replace("<br>", " "))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _absolute_url(path_or_url: str) -> str:
    if not path_or_url:
        return ""
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    if path_or_url.startswith("/"):
        return f"{HKEX_BASE_URL}{path_or_url}"
    return f"{HKEX_BASE_URL}/{path_or_url.lstrip('/')}"


def load_stock_lookup(current_securities: bool = True) -> dict[str, dict[str, Any]]:
    cache_key = "active" if current_securities else "inactive"
    if cache_key in _STOCK_LOOKUP_CACHE:
        return _STOCK_LOOKUP_CACHE[cache_key]

    url = ACTIVE_STOCK_URL if current_securities else INACTIVE_STOCK_URL
    payload = _http_get_json(url)
    lookup: dict[str, dict[str, Any]] = {}
    for item in payload:
        code = _normalize_stock_code(str(item.get("c") or item.get("code") or ""))
        if not code:
            continue
        lookup[code] = {
            "stock_id": item.get("i") or item.get("stockId"),
            "stock_code": code,
            "company_name": item.get("n") or item.get("name") or "",
            "raw": item,
        }
    _STOCK_LOOKUP_CACHE[cache_key] = lookup
    return lookup


def resolve_stock_id(stock_code: str, current_securities: bool = True) -> dict[str, Any] | None:
    code = _normalize_stock_code(stock_code)
    if not code:
        return None

    lookup = load_stock_lookup(current_securities=current_securities)
    if code in lookup:
        return lookup[code]

    params = {
        "lang": "EN",
        "type": "A" if current_securities else "I",
        "name": code,
        "market": "SEHK",
        "callback": "callback",
    }
    payload = _parse_jsonp(_http_get_text(f"{HKEX_BASE_URL}/search/prefix.do", params=params))
    for item in payload.get("stockInfo", []):
        if _normalize_stock_code(str(item.get("code") or "")) == code:
            return {
                "stock_id": item.get("stockId"),
                "stock_code": code,
                "company_name": item.get("name") or "",
                "raw": item,
            }
    return None


def fetch_announcements(
    *,
    stock_code: str,
    company_name: str = "",
    stock_id: int | str | None = None,
    current_securities: bool = True,
    from_date: str | date | None = None,
    to_date: str | date | None = None,
    title_keyword: str = "",
    row_range: int = 1000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    code = _normalize_stock_code(stock_code)
    if not code:
        return [], {"status": "error", "error": f"invalid stock code: {stock_code}"}

    if stock_id is None:
        resolved = resolve_stock_id(code, current_securities=current_securities)
        if not resolved:
            return [], {"status": "error", "error": f"stock_id not found for {code}"}
        stock_id = resolved.get("stock_id")
        company_name = company_name or resolved.get("company_name") or ""

    if isinstance(from_date, date):
        from_date_text = _date_to_compact(from_date)
    elif from_date:
        from_date_text = str(from_date)
    else:
        from_date_text = _date_to_compact(date.today() - timedelta(days=365 * 5))

    if isinstance(to_date, date):
        to_date_text = _date_to_compact(to_date)
    elif to_date:
        to_date_text = str(to_date)
    else:
        to_date_text = _date_to_compact(date.today())

    params = {
        "sortDir": "0",
        "sortByOptions": "DateTime",
        "category": "0" if current_securities else "1",
        "market": "SEHK",
        "stockId": str(stock_id),
        "documentType": "",
        "fromDate": from_date_text,
        "toDate": to_date_text,
        "title": title_keyword,
        "searchType": "0",
        "t1code": "",
        "t2Gcode": "",
        "t2code": "",
        "rowRange": str(row_range),
        "lang": "E",
    }

    try:
        payload = _http_get_json(TITLE_SEARCH_URL, params=params, timeout=45)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return [], {
            "status": "error",
            "error": str(exc),
            "stock_code": code,
            "stock_id": stock_id,
        }

    result_rows = json.loads(payload.get("result") or "[]")
    normalized: list[dict[str, Any]] = []
    for item in result_rows:
        file_link = _absolute_url(item.get("FILE_LINK") or "")
        release_time = item.get("DATE_TIME") or ""
        headline = _clean_text(item.get("SHORT_TEXT") or "")
        headline_long = _clean_text(item.get("LONG_TEXT") or "")
        title = _clean_text(item.get("TITLE") or headline)
        normalized.append(
            {
                "stock_code": code,
                "company_name": company_name or item.get("STOCK_NAME") or "",
                "stock_short_name": item.get("STOCK_NAME") or "",
                "stock_id": stock_id,
                "release_time": release_time,
                "release_date": _date_from_hkex_release(release_time),
                "title": title,
                "headline": headline,
                "headline_long": headline_long,
                "file_link": file_link,
                "file_type": item.get("FILE_TYPE") or "",
                "file_size": item.get("FILE_INFO") or "",
                "news_id": item.get("NEWS_ID") or "",
                "total_count_for_query": item.get("TOTAL_COUNT") or payload.get("recordCnt") or "",
                "dod_web_path": _absolute_url(item.get("DOD_WEB_PATH") or ""),
                "query_from_date": from_date_text,
                "query_to_date": to_date_text,
                "query_category": "current" if current_securities else "delisted",
                "query_search_type": "all_documents",
                "source": "HKEXNEWS_OFFICIAL",
                "source_url": file_link or TITLE_SEARCH_URL,
                "notes": "Captured from HKEXnews title search metadata; underlying document not parsed yet.",
            }
        )

    meta = {
        "status": "ok",
        "stock_code": code,
        "stock_id": stock_id,
        "query_from_date": from_date_text,
        "query_to_date": to_date_text,
        "record_count": payload.get("recordCnt", len(normalized)),
        "loaded_record": payload.get("loadedRecord", len(normalized)),
        "has_next_row": payload.get("hasNextRow"),
        "row_range": payload.get("rowRange", row_range),
        "lang": payload.get("lang"),
    }
    return normalized, meta


def _contains_any(text: str, keywords: list[str]) -> bool:
    hay = text.lower()
    return any(keyword in hay for keyword in keywords)


def classify_announcement_signals(row: dict[str, Any]) -> list[dict[str, str]]:
    text = " | ".join(
        [
            str(row.get("title") or ""),
            str(row.get("headline") or ""),
            str(row.get("headline_long") or ""),
        ]
    ).lower()

    signals: list[dict[str, str]] = []
    if _contains_any(text, SUSPENSION_KEYWORDS):
        level = "warning"
        if "suspension" in text or "trading halt" in text or "short halt" in text:
            level = "high"
        signals.append({"signal_type": "suspension", "level": level})

    if _contains_any(text, AUDIT_KEYWORDS):
        signals.append({"signal_type": "audit", "level": "warning"})

    if _contains_any(text, MAJOR_RISK_HIGH_KEYWORDS):
        signals.append({"signal_type": "major_risk", "level": "high"})
    elif _contains_any(text, MAJOR_RISK_WARNING_KEYWORDS):
        signals.append({"signal_type": "major_risk", "level": "warning"})

    annual_report_hit = any(term in text for term in ["annual report", "interim report", "results announcement", "final results"])
    if annual_report_hit:
        signals.append({"signal_type": "report_like_document", "level": "info"})

    return signals


def summarize_announcements_by_stock(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.get("stock_code") or "")
        if not code:
            continue
        bucket = summary.setdefault(
            code,
            {
                "stock_code": code,
                "company_name": row.get("company_name") or "",
                "announcement_count": 0,
                "latest_release_date": "",
                "suspension_flag": "unknown",
                "audit_opinion_flag": "unknown",
                "major_risk_flag": "unknown",
                "report_like_document_count": 0,
                "signal_hits": [],
            },
        )
        bucket["announcement_count"] += 1
        release_date = str(row.get("release_date") or "")
        if release_date and (not bucket["latest_release_date"] or release_date > bucket["latest_release_date"]):
            bucket["latest_release_date"] = release_date

        for signal in classify_announcement_signals(row):
            signal_type = signal["signal_type"]
            level = signal["level"]
            if signal_type == "suspension":
                bucket["suspension_flag"] = "recent"
            elif signal_type == "audit" and bucket["audit_opinion_flag"] == "unknown":
                bucket["audit_opinion_flag"] = "warning"
            elif signal_type == "major_risk":
                current = bucket["major_risk_flag"]
                if current != "high":
                    bucket["major_risk_flag"] = "high" if level == "high" else "warning"
            elif signal_type == "report_like_document":
                bucket["report_like_document_count"] += 1

            if signal_type != "report_like_document":
                bucket["signal_hits"].append(
                    {
                        "signal_type": signal_type,
                        "level": level,
                        "title": row.get("title") or "",
                        "release_date": release_date,
                        "source_url": row.get("source_url") or row.get("file_link") or "",
                    }
                )
    return summary


def build_evidence_rows_from_announcements(
    summary_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence_rows: list[dict[str, Any]] = []
    for summary in summary_map.values():
        stock_code = summary.get("stock_code") or ""
        company_name = summary.get("company_name") or ""
        announcement_count = summary.get("announcement_count") or 0
        latest_release_date = summary.get("latest_release_date") or ""
        evidence_rows.append(
            {
                "stock_code": stock_code,
                "company_name": company_name,
                "field_name": "hkexnews_announcement_capture",
                "field_value": f"{announcement_count} announcements captured in title search window",
                "source_type": "HKEXnews",
                "source_title": "HKEXnews title search metadata",
                "source_url": TITLE_SEARCH_URL,
                "file_path": "",
                "document_date": latest_release_date,
                "page_number": "",
                "claim_type": "fact",
                "support_level": "official",
                "confidence_level": "high",
                "verification_status": "needs_review",
                "narrative_use": "factual_layer",
                "assumption_dependency": "",
                "notes": "Metadata-level evidence only; underlying PDFs/HTML not parsed yet.",
            }
        )
        for hit in summary.get("signal_hits", []):
            evidence_rows.append(
                {
                    "stock_code": stock_code,
                    "company_name": company_name,
                    "field_name": f"hkexnews_title_signal:{hit.get('signal_type')}",
                    "field_value": f"{hit.get('level')}: {hit.get('title')}",
                    "source_type": "announcement",
                    "source_title": hit.get("title") or "",
                    "source_url": hit.get("source_url") or TITLE_SEARCH_URL,
                    "file_path": "",
                    "document_date": hit.get("release_date") or "",
                    "page_number": "",
                    "claim_type": "inference",
                    "support_level": "official",
                    "confidence_level": "high",
                    "verification_status": "needs_review",
                    "narrative_use": "constraint_layer",
                    "assumption_dependency": "Title-keyword heuristic; requires underlying document review for confirmation.",
                    "notes": "Keyword/title-level signal from HKEXnews title search metadata; document review still required.",
                }
            )
    return evidence_rows


def enrich_screening_rows_with_hkex_summaries(
    screening_rows: list[dict[str, Any]], summary_map: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in screening_rows:
        code = _normalize_stock_code(str(row.get("stock_code") or ""))
        summary = summary_map.get(code)
        if not summary:
            enriched.append(row)
            continue

        new_row = dict(row)
        if summary.get("suspension_flag") != "unknown":
            new_row["suspension_flag"] = summary["suspension_flag"]
        if summary.get("audit_opinion_flag") != "unknown":
            new_row["audit_opinion_flag"] = summary["audit_opinion_flag"]
        if summary.get("major_risk_flag") != "unknown":
            new_row["major_risk_flag"] = summary["major_risk_flag"]

        notes_parts = [str(new_row.get("notes") or "").strip()]
        notes_parts.append(
            "HKEXnews title search captured "
            f"{summary.get('announcement_count', 0)} announcements in lookback window; "
            f"latest_release_date={summary.get('latest_release_date') or 'unknown'}; "
            f"title_signals={len(summary.get('signal_hits', []))}."
        )
        notes_parts.append(
            "HKEXnews flags above are title-metadata heuristics only; underlying announcement/PDF review still required."
        )
        new_row["notes"] = " | ".join(part for part in notes_parts if part)

        data_source = str(new_row.get("data_source") or "")
        if "HKEXNEWS" not in data_source.upper():
            new_row["data_source"] = f"{data_source}+HKEXNEWS" if data_source else "HKEXNEWS"
        enriched.append(new_row)
    return enriched


def fetch_announcements_for_candidates(
    screening_rows: list[dict[str, Any]],
    *,
    years_back: int = 5,
    status_filter: tuple[str, ...] = ("pass", "watchlist"),
    limit: int | None = None,
    row_range: int = 1000,
    max_workers: int = 4,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    from_date = today - timedelta(days=max(1, years_back) * 365)
    candidates = [
        row for row in screening_rows if str(row.get("screening_status") or "") in set(status_filter)
    ]
    if limit is not None:
        candidates = candidates[:limit]

    active_lookup = load_stock_lookup(current_securities=True)
    inactive_lookup = load_stock_lookup(current_securities=False)

    all_rows: list[dict[str, Any]] = []
    per_stock_meta: list[dict[str, Any]] = []

    def _job(candidate: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        code = _normalize_stock_code(str(candidate.get("stock_code") or ""))
        company_name = str(candidate.get("company_name") or "")
        resolved = active_lookup.get(code)
        current = True
        if not resolved:
            resolved = inactive_lookup.get(code)
            current = False
        if not resolved:
            return [], {"status": "error", "stock_code": code, "error": "stock_id not found in active/inactive HKEX lists"}
        return fetch_announcements(
            stock_code=code,
            company_name=company_name,
            stock_id=resolved.get("stock_id"),
            current_securities=current,
            from_date=from_date,
            to_date=today,
            row_range=row_range,
        )

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        future_map = {executor.submit(_job, candidate): candidate for candidate in candidates}
        for future in as_completed(future_map):
            rows, meta = future.result()
            all_rows.extend(rows)
            per_stock_meta.append(meta)

    seen: set[tuple[str, str]] = set()
    deduped_rows: list[dict[str, Any]] = []
    for row in sorted(all_rows, key=lambda x: (x.get("stock_code") or "", x.get("release_time") or ""), reverse=True):
        key = (str(row.get("stock_code") or ""), str(row.get("news_id") or row.get("file_link") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped_rows.append(row)

    summary_map = summarize_announcements_by_stock(deduped_rows)
    evidence_rows = build_evidence_rows_from_announcements(summary_map)

    ok = sum(1 for item in per_stock_meta if item.get("status") == "ok")
    errors = [item for item in per_stock_meta if item.get("status") != "ok"]
    meta = {
        "status": "ok" if not errors else "partial",
        "years_back": years_back,
        "candidate_count": len(candidates),
        "ok": ok,
        "errors": len(errors),
        "announcement_rows": len(deduped_rows),
        "evidence_rows": len(evidence_rows),
        "query_from_date": from_date.isoformat(),
        "query_to_date": today.isoformat(),
        "per_stock_meta": per_stock_meta,
        "error_samples": errors[:10],
    }
    return deduped_rows, summary_map, evidence_rows, meta
