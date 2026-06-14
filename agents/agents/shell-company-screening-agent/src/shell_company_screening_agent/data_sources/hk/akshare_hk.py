from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import math
import re
import time

from utils.io_utils import read_csv, write_csv
from utils.schema import normalize_ticker, parse_number


EASTMONEY_SPOT_ENDPOINTS = {
    "stock_hk_spot_em": {
        "url": "https://72.push2.eastmoney.com/api/qt/clist/get",
        "fs": "m:128 t:3,m:128 t:4,m:128 t:1,m:128 t:2",
    },
    "stock_hk_main_board_spot_em": {
        "url": "https://81.push2.eastmoney.com/api/qt/clist/get",
        "fs": "m:128 t:3",
    },
}


COLUMN_ALIASES = {
    "ticker": ["代码", "code", "symbol", "证券代码", "f12"],
    "company_name": ["名称", "name", "证券简称", "股票简称", "f14"],
    "last_price_hkd": ["最新价", "最新", "现价", "price", "last", "最新价(港元)", "f2"],
    "market_cap_hkd": ["总市值", "市值", "总市值-港元", "market_cap", "总市值(HKD)", "f20", "f21"],
    "pb": ["市净率", "市净率pb", "pb", "PB", "pb_ratio", "f23"],
    "turnover_hkd": ["成交额", "成交额(港元)", "amount", "turnover", "成交金额", "f6"],
    "volume": ["成交量", "volume", "f5"],
}

FINANCIAL_INDICATOR_CACHE_FIELDS = [
    "stock_code",
    "market_cap_hkd",
    "pb_ratio",
    "latest_revenue_hkd",
    "latest_net_assets_hkd",
    "net_profit_hkd",
    "profitability_status",
    "status",
    "error",
    "retrieved_at",
]

LEVERAGED_PRODUCT_KEYWORDS = (
    "两倍做多",
    "两倍做空",
    "一倍看空",
    "XL二",
    "XI二",
)

STRUCTURED_NOTE_NAME_RE = re.compile(
    r"\b[A-Z]{2,}(?:\s+[A-Z0-9()&./-]+)+\s+(?:[NBCDSP]\d{3,4}[A-Z]?|SPCS|GPCS|GSPCS|GSPCSD|RSPSC|UCS|SDS\d{2,4})\b"
)

STRUCTURED_NOTE_TOKEN_RE = re.compile(
    r"\b(?:[NBCDSP]\d{3,4}[A-Z]?|SPCS|GPCS|GSPCS|GSPCSD|RSPSC|UCS|SDS\d{2,4})\b"
)

PLACEHOLDER_STOCK_NAME_RE = re.compile(r"^STOCK\d{4,5}$")


def _find_column(columns: list[str], aliases: list[str]) -> str | None:
    lower_map = {c.lower(): c for c in columns}
    for alias in aliases:
        if alias in columns:
            return alias
        if alias.lower() in lower_map:
            return lower_map[alias.lower()]
    # Loose contains matching for vendor schema drift.
    for col in columns:
        normalized = col.lower().replace(" ", "")
        for alias in aliases:
            a = alias.lower().replace(" ", "")
            if a and (normalized == a or a in normalized):
                return col
    return None


def _normalize_hk_company_name(company_name: str = "") -> str:
    return (company_name or "").upper().replace("－", "-").strip()


def classify_hk_snapshot_row_exclusion(stock_code: str, company_name: str = "") -> str | None:
    try:
        if bool(stock_code) and int(stock_code) >= 40000:
            return "high_code_non_equity"
    except Exception:
        pass

    normalized_name = _normalize_hk_company_name(company_name)
    if normalized_name.endswith(("-U", "-R", "-WR", "-SWR")):
        return "special_counter_suffix"
    if normalized_name.endswith("-Z") or " ACQ-Z" in normalized_name or "收购-Z" in normalized_name:
        return "spac_counter"
    if any(keyword in normalized_name for keyword in LEVERAGED_PRODUCT_KEYWORDS):
        return "leveraged_inverse_product"
    if PLACEHOLDER_STOCK_NAME_RE.fullmatch(normalized_name):
        return "placeholder_name"
    if STRUCTURED_NOTE_NAME_RE.search(normalized_name):
        return "structured_note_name"
    if STRUCTURED_NOTE_TOKEN_RE.search(normalized_name) and " " in normalized_name:
        return "structured_note_token"
    return None


def is_screenable_hk_snapshot_row(stock_code: str, company_name: str = "") -> bool:
    return classify_hk_snapshot_row_exclusion(stock_code, company_name) is None


def filter_screenable_hk_market_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    filtered: list[dict[str, Any]] = []
    removed_counts: dict[str, int] = {}
    for row in rows:
        reason = classify_hk_snapshot_row_exclusion(str(row.get("ticker") or row.get("stock_code") or ""), str(row.get("company_name") or ""))
        if reason is None:
            filtered.append(row)
            continue
        removed_counts[reason] = removed_counts.get(reason, 0) + 1
    return filtered, removed_counts


def _should_skip_hk_snapshot_row(stock_code: str, company_name: str = "") -> bool:
    return not is_screenable_hk_snapshot_row(stock_code, company_name)


def _df_to_records(df: Any, source_id: str, limit: int | None = None) -> list[dict[str, Any]]:
    if df is None:
        return []
    if hasattr(df, "head") and limit:
        df = df.head(limit)
    columns = [str(c) for c in getattr(df, "columns", [])]
    colmap = {field: _find_column(columns, aliases) for field, aliases in COLUMN_ALIASES.items()}
    records: list[dict[str, Any]] = []
    raw_records = df.to_dict(orient="records") if hasattr(df, "to_dict") else []
    retrieved_at = datetime.now(timezone.utc).isoformat()
    for raw in raw_records:
        row: dict[str, Any] = {
            "source": source_id,
            "retrieved_at": retrieved_at,
        }
        stock_code = normalize_ticker(raw.get(colmap["ticker"])) if colmap.get("ticker") else ""
        row["stock_code"] = f"{stock_code}.HK" if stock_code and not stock_code.endswith(".HK") else stock_code
        row["ticker"] = stock_code
        row["company_name"] = str(raw.get(colmap["company_name"], "")).strip() if colmap.get("company_name") else ""
        if _should_skip_hk_snapshot_row(stock_code, row["company_name"]):
            continue
        row["share_price_hkd"] = parse_number(raw.get(colmap["last_price_hkd"])) if colmap.get("last_price_hkd") else None
        row["last_price_hkd"] = row["share_price_hkd"]
        row["market_cap_hkd"] = parse_number(raw.get(colmap["market_cap_hkd"])) if colmap.get("market_cap_hkd") else None
        row["pb_ratio"] = parse_number(raw.get(colmap["pb"])) if colmap.get("pb") else None
        row["pb"] = row["pb_ratio"]
        row["turnover_hkd"] = parse_number(raw.get(colmap["turnover_hkd"])) if colmap.get("turnover_hkd") else None
        row["volume"] = parse_number(raw.get(colmap["volume"])) if colmap.get("volume") else None
        missing_columns = [field for field, col in colmap.items() if col is None]
        row["data_quality_notes"] = "missing source columns: " + ",".join(missing_columns) if missing_columns else ""
        if row["stock_code"] or row["company_name"]:
            records.append(row)
    return records


def _eastmoney_get_json(url: str, params: dict[str, str], *, attempts: int = 3, timeout: int = 45) -> dict[str, Any]:
    import requests

    last_error: Exception | None = None
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://quote.eastmoney.com/center/gridlist.html#hk_stocks",
    }
    for attempt in range(1, max(1, attempts) + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout, headers=headers)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            raise ValueError("eastmoney returned non-dict payload")
        except Exception as exc:  # pragma: no cover - network/vendor dependent
            last_error = exc
            if attempt >= attempts:
                break
            time.sleep(min(4, attempt))
    raise RuntimeError(f"eastmoney request failed after {attempts} attempts: {last_error}")


def _fetch_eastmoney_spot_snapshot(
    *,
    func_name: str,
    source_id: str,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import pandas as pd  # type: ignore

    endpoint = EASTMONEY_SPOT_ENDPOINTS[func_name]
    page_size = 100
    start_offset = max(0, offset)
    params = {
        "pn": "1",
        "pz": str(page_size),
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f12",
        "fs": endpoint["fs"],
        "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152",
    }
    data_json = _eastmoney_get_json(endpoint["url"], params)
    data_block = (data_json or {}).get("data") or {}
    diff = data_block.get("diff") or []
    total = int(data_block.get("total") or len(diff) or 0)
    if not diff:
        return [], {
            "source_id": source_id,
            "function": func_name,
            "status": "ok",
            "rows": 0,
            "pages_fetched": 1,
            "offset": start_offset,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }

    total_pages = max(1, math.ceil(total / page_size))
    collected: list[dict[str, Any]] = []
    filtered_seen = 0
    pages_fetched = 0
    page_errors: list[dict[str, Any]] = []

    for page in range(1, total_pages + 1):
        try:
            if page == 1:
                page_json = data_json
            else:
                params["pn"] = str(page)
                page_json = _eastmoney_get_json(endpoint["url"], params)
        except Exception as exc:  # pragma: no cover - network/vendor dependent
            page_errors.append({"page": page, "error": str(exc)})
            # Keep already-fetched rows instead of failing the whole run. This is
            # important in constrained network/proxy environments where page 1
            # often succeeds but later pages intermittently fail.
            if collected:
                break
            raise
        page_diff = ((page_json or {}).get("data") or {}).get("diff") or []
        page_records = _df_to_records(pd.DataFrame(page_diff), source_id=source_id)
        pages_fetched += 1
        page_filtered_count = len(page_records)
        if page_filtered_count == 0:
            continue
        if filtered_seen + page_filtered_count <= start_offset:
            filtered_seen += page_filtered_count
            continue
        start_in_page = max(0, start_offset - filtered_seen)
        filtered_seen += page_filtered_count
        selected_records = page_records[start_in_page:]
        if limit is not None:
            needed = max(0, limit - len(collected))
            selected_records = selected_records[:needed]
        collected.extend(selected_records)
        if limit is not None and len(collected) >= limit:
            break

    return collected, {
        "source_id": source_id,
        "function": func_name,
        "status": "partial" if page_errors else "ok",
        "rows": len(collected),
        "pages_fetched": pages_fetched,
        "page_errors": page_errors,
        "offset": start_offset,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_hk_market_snapshot(
    sources: list[dict[str, str]],
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch HK market data via AKShare according to source_map.md.

    Returns (records, metadata). It never fabricates fallback data: if AKShare is
    unavailable or endpoints fail, records is empty and metadata explains why.
    """
    try:
        import akshare as ak  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on environment
        return [], {
            "source_id": None,
            "status": "dependency_missing",
            "error": f"AKShare import failed: {exc}",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }

    ak_sources = [s for s in sources if s.get("access_method") == "akshare" and s.get("status") in {"active", "fallback"}]
    ak_sources.sort(key=lambda s: int(str(s.get("priority", "999")).strip() or 999))
    errors = []
    for source in ak_sources:
        func_name = source.get("akshare_function", "").strip()
        source_id = source.get("source_id", func_name)
        if not func_name or func_name == "n/a":
            continue
        try:
            if func_name in EASTMONEY_SPOT_ENDPOINTS:
                return _fetch_eastmoney_spot_snapshot(func_name=func_name, source_id=source_id, limit=limit, offset=offset)
            func = getattr(ak, func_name, None)
            if func is None:
                errors.append({"source_id": source_id, "error": f"akshare has no function {func_name}"})
                continue
            df = func()
            records = _df_to_records(df, source_id=source_id, limit=limit)
            return records, {
                "source_id": source_id,
                "function": func_name,
                "status": "ok",
                "rows": len(records),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:  # pragma: no cover - network/vendor dependent
            errors.append({"source_id": source_id, "function": func_name, "error": str(exc)})
    return [], {
        "source_id": None,
        "status": "all_sources_failed",
        "errors": errors,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def _first_record_value(records: list[dict[str, Any]], *names: str) -> Any:
    if not records:
        return None
    row = records[0]
    for name in names:
        if name in row:
            return row.get(name)
    return None


def _load_financial_indicator_cache(cache_path: str | Path | None) -> dict[str, dict[str, Any]]:
    if not cache_path:
        return {}
    path = Path(cache_path)
    rows = read_csv(path)
    cache: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.get("stock_code") or "").strip()
        if not code:
            continue
        cache[code] = {
            "stock_code": code,
            "market_cap_hkd": parse_number(row.get("market_cap_hkd")),
            "pb_ratio": parse_number(row.get("pb_ratio")),
            "latest_revenue_hkd": parse_number(row.get("latest_revenue_hkd")),
            "latest_net_assets_hkd": parse_number(row.get("latest_net_assets_hkd")),
            "net_profit_hkd": parse_number(row.get("net_profit_hkd")),
            "profitability_status": row.get("profitability_status") or "",
            "status": row.get("status") or "",
            "error": row.get("error") or "",
            "retrieved_at": row.get("retrieved_at") or "",
        }
    return cache


def _flush_financial_indicator_cache(cache_path: str | Path | None, cache: dict[str, dict[str, Any]]) -> None:
    if not cache_path:
        return
    path = Path(cache_path)
    write_csv(path, list(cache.values()), FINANCIAL_INDICATOR_CACHE_FIELDS)


def _apply_cached_indicator(row: dict[str, Any], cached: dict[str, Any], *, note_prefix: str) -> bool:
    used = False
    if cached.get("market_cap_hkd") is not None:
        row["market_cap_hkd"] = cached.get("market_cap_hkd")
        used = True
    if cached.get("pb_ratio") is not None:
        row["pb_ratio"] = cached.get("pb_ratio")
        row["pb"] = cached.get("pb_ratio")
        used = True
    if cached.get("latest_revenue_hkd") is not None:
        row["latest_revenue_hkd"] = cached.get("latest_revenue_hkd")
        used = True
    if cached.get("latest_net_assets_hkd") is not None:
        row["latest_net_assets_hkd"] = cached.get("latest_net_assets_hkd")
        used = True
    if cached.get("profitability_status"):
        row["profitability_status"] = cached.get("profitability_status")
        used = True
    if used:
        notes = row.get("data_quality_notes") or ""
        extra = note_prefix
        if cached.get("retrieved_at"):
            extra += f" (cached_at={cached.get('retrieved_at')})"
        row["data_quality_notes"] = (notes + " | " if notes else "") + extra
    return used


def _append_quality_note(row: dict[str, Any], note: str) -> None:
    notes = row.get("data_quality_notes") or ""
    row["data_quality_notes"] = (notes + " | " if notes else "") + note


def fetch_single_financial_indicator(symbol: str) -> dict[str, Any]:
    """Fetch one issuer's market cap/PB from AKShare Eastmoney indicator endpoint.

    This is slower than the batch spot endpoint but gives real public structured
    fields when batch valuation columns are unavailable. It returns only fields
    actually received from AKShare; missing values stay None.
    """
    import akshare as ak  # type: ignore

    clean_symbol = normalize_ticker(symbol)
    if not clean_symbol:
        return {"stock_code": symbol, "status": "skipped", "error": "empty symbol"}
    try:
        df = ak.stock_hk_financial_indicator_em(symbol=clean_symbol)
        if df is None:
            return {
                "stock_code": f"{clean_symbol}.HK",
                "status": "empty",
                "error": "no indicator data returned",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
        records = df.to_dict(orient="records") if hasattr(df, "to_dict") else []
        if not records:
            return {
                "stock_code": f"{clean_symbol}.HK",
                "status": "empty",
                "error": "empty indicator dataframe",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
        per_share_nav = parse_number(_first_record_value(records, "每股净资产(元)"))
        issued_shares = parse_number(_first_record_value(records, "已发行股本(股)"))
        latest_net_assets = per_share_nav * issued_shares if per_share_nav is not None and issued_shares is not None else None
        net_profit = parse_number(_first_record_value(records, "净利润"))
        if net_profit is None:
            profitability_status = "unknown"
        elif net_profit > 0:
            profitability_status = "profitable"
        elif net_profit < 0:
            profitability_status = "loss_making"
        else:
            profitability_status = "break_even"
        return {
            "stock_code": f"{clean_symbol}.HK",
            "market_cap_hkd": parse_number(_first_record_value(records, "总市值(港元)", "港股市值(港元)")),
            "pb_ratio": parse_number(_first_record_value(records, "市净率")),
            "latest_revenue_hkd": parse_number(_first_record_value(records, "营业总收入")),
            "latest_net_assets_hkd": latest_net_assets,
            "net_profit_hkd": net_profit,
            "profitability_status": profitability_status,
            "status": "ok",
            "error": "",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:  # pragma: no cover - network/vendor dependent
        message = str(exc)
        status = "empty" if message == "'NoneType' object is not subscriptable" else "error"
        return {
            "stock_code": f"{clean_symbol}.HK",
            "status": status,
            "error": message,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


def enrich_market_rows_with_financial_indicators(
    rows: list[dict[str, Any]],
    *,
    limit: int | None = None,
    offset: int = 0,
    max_workers: int = 8,
    cache_path: str | Path | None = None,
    cache_flush_every: int = 25,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fill missing market_cap_hkd/pb_ratio using AKShare per-symbol endpoint.

    No synthetic values are created. Rows that fail enrichment keep blanks and
    receive a note. Limit can be used for smoke tests; None means all eligible rows.
    """
    eligible = [
        row
        for row in rows
        if row.get("stock_code") and (parse_number(row.get("market_cap_hkd")) is None or parse_number(row.get("pb_ratio")) is None)
    ]
    raw_eligible = len(eligible)
    if not eligible:
        return rows, {
            "status": "skipped",
            "raw_eligible": 0,
            "attempted": 0,
            "ok": 0,
            "errors": 0,
            "cached_hits": 0,
            "empty_hits": 0,
            "fetched": 0,
            "batch_offset": max(0, offset),
        }

    by_code = {row.get("stock_code"): row for row in rows}
    cache = _load_financial_indicator_cache(cache_path)
    cached_hits = 0
    empty_hits = 0
    unresolved: list[dict[str, Any]] = []
    for row in eligible:
        cached = cache.get(str(row.get("stock_code") or ""))
        if cached and cached.get("status") == "ok" and _apply_cached_indicator(
            row,
            cached,
            note_prefix="valuation restored from AKShare indicator cache",
        ):
            cached_hits += 1
        elif cached and cached.get("status") == "empty":
            _append_quality_note(row, f"valuation cache indicates no indicator data: {cached.get('error')}")
            empty_hits += 1
        else:
            unresolved.append(row)

    batch_offset = max(0, offset)
    if batch_offset:
        unresolved = unresolved[batch_offset:]
    if limit is not None:
        unresolved = unresolved[: max(0, limit)]
    to_fetch = unresolved

    if not to_fetch:
        return rows, {
            "status": "ok",
            "raw_eligible": raw_eligible,
            "attempted": cached_hits + empty_hits,
            "ok": cached_hits,
            "errors": 0,
            "cached_hits": cached_hits,
            "empty_hits": empty_hits,
            "fetched": 0,
            "remaining_after_cache": 0,
            "batch_offset": batch_offset,
            "cache_path": str(cache_path) if cache_path else "",
        }

    ok = 0
    errors = 0
    no_data = 0
    completed_since_flush = 0
    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
        futures = {pool.submit(fetch_single_financial_indicator, str(row.get("stock_code"))): row for row in to_fetch}
        for future in as_completed(futures):
            result = future.result()
            stock_code = str(result.get("stock_code") or "")
            if stock_code:
                cache[stock_code] = {
                    "stock_code": stock_code,
                    "market_cap_hkd": result.get("market_cap_hkd"),
                    "pb_ratio": result.get("pb_ratio"),
                    "latest_revenue_hkd": result.get("latest_revenue_hkd"),
                    "latest_net_assets_hkd": result.get("latest_net_assets_hkd"),
                    "net_profit_hkd": result.get("net_profit_hkd"),
                    "profitability_status": result.get("profitability_status"),
                    "status": result.get("status"),
                    "error": result.get("error"),
                    "retrieved_at": result.get("retrieved_at") or datetime.now(timezone.utc).isoformat(),
                }
            row = by_code.get(stock_code)
            if row is None:
                continue
            if result.get("status") == "ok":
                _apply_cached_indicator(
                    row,
                    result,
                    note_prefix="valuation enriched via AKShare stock_hk_financial_indicator_em",
                )
                ok += 1
            elif result.get("status") == "empty":
                _append_quality_note(row, f"valuation enrichment returned no indicator data: {result.get('error')}")
                no_data += 1
            else:
                _append_quality_note(row, f"valuation enrichment failed: {result.get('error')}")
                errors += 1
            completed_since_flush += 1
            if cache_path and completed_since_flush >= max(1, cache_flush_every):
                _flush_financial_indicator_cache(cache_path, cache)
                completed_since_flush = 0

    if cache_path:
        _flush_financial_indicator_cache(cache_path, cache)
    return rows, {
        "status": "ok",
        "raw_eligible": raw_eligible,
        "attempted": len(to_fetch) + cached_hits + empty_hits,
        "ok": ok + cached_hits,
        "errors": errors,
        "cached_hits": cached_hits,
        "empty_hits": empty_hits + no_data,
        "fetched": len(to_fetch),
        "remaining_after_cache": max(0, raw_eligible - cached_hits - empty_hits),
        "batch_offset": batch_offset,
        "cache_path": str(cache_path) if cache_path else "",
    }
