from __future__ import annotations

import re
import urllib.error
import urllib.request
from typing import Any, Callable
from urllib.parse import urlparse


class SourceRefetchCheckError(ValueError):
    pass


Fetcher = Callable[[str, float], tuple[str, bytes, str]]

_TEXT_CONTENT_MARKERS = ("text/", "application/json", "application/xml", "application/xhtml+xml", "application/html")
_PDF_MARKERS = ("application/pdf", ".pdf")
_WORD_RE = re.compile(r"[a-z0-9$%]+", re.IGNORECASE)


def run_source_refetch_check(evidence_repository: dict[str, Any], fetcher: Fetcher | None = None, timeout_seconds: float = 10.0) -> list[dict[str, Any]]:
    _validate_repository_shape(evidence_repository)
    effective_fetcher = fetcher or _default_fetcher
    results = []
    for record in evidence_repository["evidence_records"]:
        urls = _urls_from(record)
        if not urls:
            results.append(_not_applicable_result(record))
            continue
        for url in urls:
            results.append(_check_record_url(record, url, effective_fetcher, timeout_seconds))
    return results


def source_refetch_results_by_record_id(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        grouped.setdefault(result["evidence_record_id"], []).append(result)
    return grouped


def _validate_repository_shape(evidence_repository: dict[str, Any]) -> None:
    if evidence_repository.get("generated_artifact") != "evidence_repository.json":
        raise SourceRefetchCheckError("Source Refetch Check requires evidence_repository.json.")
    if not isinstance(evidence_repository.get("evidence_records"), list):
        raise SourceRefetchCheckError("Source Refetch Check requires evidence_records array.")


def _check_record_url(record: dict[str, Any], url: str, fetcher: Fetcher, timeout_seconds: float) -> dict[str, Any]:
    blocking_reasons: list[str] = []
    repair_actions: list[dict[str, str]] = []
    quote_text = _quote_text_from(record)
    if _looks_like_pdf(url):
        return _result(record, url, "text_unavailable", "not_applicable", ["PDF source text was not fetched by minimal source refetch check."], [])
    try:
        content_type, body, final_url = fetcher(url, timeout_seconds)
    except urllib.error.HTTPError as exc:
        reason = f"Source URL returned HTTP error {exc.code}."
        blocking_reasons.append(reason)
        repair_actions.append(_repair_action("M2_source_retrieval", "repair_source_url", reason))
        return _result(record, url, "failed", "not_applicable", blocking_reasons, repair_actions)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = f"Source URL could not be fetched: {exc.__class__.__name__}."
        blocking_reasons.append(reason)
        repair_actions.append(_repair_action("block_pipeline_until_structure_repaired", "retry_or_document_provider_unavailable", reason))
        return _result(record, url, "provider_unavailable", "not_applicable", blocking_reasons, repair_actions)

    if _looks_like_pdf(final_url) or _looks_like_pdf(content_type) or not _looks_textual(content_type):
        return _result(record, url, "text_unavailable", "not_applicable", ["Fetched source did not expose plain text for minimal quote check."], [])
    text = _decode_text(body)
    if not text.strip():
        return _result(record, url, "text_unavailable", "not_applicable", ["Fetched source text was empty."], [])
    if not quote_text:
        return _result(record, url, "verified", "not_applicable", [], [])

    quote_status = _quote_match_status(quote_text, text)
    if quote_status in {"matched", "weak_match"}:
        return _result(record, url, "verified", quote_status, [], [])
    reason = "Evidence quote, excerpt, or summary was not matched in refetched source text."
    blocking_reasons.append(reason)
    repair_actions.append(_repair_action("M4_claim_evidence_graph", "repair_quote_or_evidence_mapping", reason))
    return _result(record, url, "failed", "not_matched", blocking_reasons, repair_actions)


def _default_fetcher(url: str, timeout_seconds: float) -> tuple[str, bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "DealTech-V3-Lite-M5-SourceRefetch/1.0"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        content_type = str(response.headers.get("content-type", ""))
        final_url = str(response.geturl() or url)
        return content_type, response.read(1_000_000), final_url


def _not_applicable_result(record: dict[str, Any]) -> dict[str, Any]:
    return _result(record, "", "not_applicable", "not_applicable", [], [])


def _result(
    record: dict[str, Any],
    url: str,
    refetch_status: str,
    quote_match_status: str,
    blocking_reasons: list[str],
    repair_actions: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "evidence_record_id": record["evidence_record_id"],
        "source_url": url,
        "source_ids": list(record.get("source_ids") or []),
        "refetch_status": refetch_status,
        "quote_match_status": quote_match_status,
        "blocking_reasons": _ordered_unique(blocking_reasons),
        "repair_actions": _dedupe_actions(repair_actions),
    }


def _urls_from(record: dict[str, Any]) -> list[str]:
    raw_urls = record.get("source_urls") or record.get("urls") or []
    if isinstance(raw_urls, str):
        raw_urls = [raw_urls]
    urls = []
    for url in raw_urls:
        if not isinstance(url, str):
            continue
        cleaned = url.strip()
        parsed = urlparse(cleaned)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            urls.append(cleaned)
    return _ordered_unique(urls)


def _quote_text_from(record: dict[str, Any]) -> str:
    for field in ("normalized_fact_summary", "extracted_text", "excerpt", "extracted_text_or_summary", "quote", "raw_quote"):
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _quote_match_status(quote: str, text: str) -> str:
    normalized_quote = _normalize_text(quote)
    normalized_text = _normalize_text(text)
    if normalized_quote and normalized_quote in normalized_text:
        return "matched"
    quote_tokens = _important_tokens(quote)
    if not quote_tokens:
        return "not_applicable"
    text_tokens = set(_important_tokens(text))
    overlap = sum(1 for token in quote_tokens if token in text_tokens)
    if overlap >= max(3, int(len(set(quote_tokens)) * 0.6)):
        return "weak_match"
    return "not_matched"


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().split())


def _important_tokens(value: str) -> list[str]:
    tokens = [token.lower() for token in _WORD_RE.findall(value)]
    return [token for token in tokens if len(token) >= 4 or token.startswith("$") or token.endswith("%")]


def _decode_text(body: bytes) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", errors="ignore")


def _looks_textual(content_type: str) -> bool:
    lowered = content_type.lower().split(";", 1)[0].strip()
    if not lowered:
        return True
    return any(marker in lowered for marker in _TEXT_CONTENT_MARKERS)


def _looks_like_pdf(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _PDF_MARKERS)


def _repair_action(target: str, action: str, reason: str) -> dict[str, str]:
    return {"target": target, "action": action, "reason": reason}


def _dedupe_actions(actions: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    deduped = []
    for action in actions:
        key = (action.get("target"), action.get("action"), action.get("reason"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped


def _ordered_unique(values: list[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        if value in seen or value in {None, ""}:
            continue
        seen.add(value)
        unique.append(value)
    return unique
