from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

try:
    import pdfplumber
except Exception:  # pragma: no cover - optional dependency may be absent in skeleton installs
    pdfplumber = None  # type: ignore[assignment]

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

BODY_SIGNAL_KEYWORDS = {
    "shareholder_control": [
        "controlling shareholder",
        "substantial shareholder",
        "directors' interests",
        "董事权益",
        "主要股东",
        "控股股东",
    ],
    "debt_liquidity": [
        "borrowings",
        "bank loans",
        "liquidity risk",
        "going concern",
        "流动资金",
        "借款",
        "贷款",
        "持续经营",
    ],
    "audit": [
        "auditor",
        "qualified opinion",
        "disclaimer of opinion",
        "material uncertainty",
        "核数师",
        "保留意见",
        "无法表示意见",
        "重大不确定",
    ],
    "litigation_regulatory": [
        "litigation",
        "claim",
        "legal proceedings",
        "regulatory",
        "诉讼",
        "申索",
        "监管",
        "法律程序",
    ],
    "transaction_perimeter": [
        "connected transaction",
        "discloseable transaction",
        "major transaction",
        "very substantial",
        "continuing connected transaction",
        "关连交易",
        "须予披露交易",
        "重大交易",
    ],
    "brand_license_business_continuity": [
        "franchise",
        "licence",
        "license",
        "brand",
        "trademark",
        "termination",
        "renewal",
        "特许经营",
        "许可",
        "品牌",
        "商标",
        "终止",
        "续期",
    ],
}


@dataclass
class ParsedDocument:
    url: str
    local_path: Path
    content_type: str
    text_path: Path
    text: str
    status: str
    error: str = ""


def _safe_suffix(url: str, content_type: str) -> str:
    path = urlparse(url).path.lower()
    suffix = Path(path).suffix
    if suffix in {".pdf", ".html", ".htm", ".txt"}:
        return suffix
    if "pdf" in content_type.lower():
        return ".pdf"
    if "html" in content_type.lower():
        return ".html"
    return ".bin"


def cache_paths(url: str, cache_dir: Path) -> tuple[Path, Path]:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]
    raw_dir = cache_dir / "raw"
    text_dir = cache_dir / "text"
    raw_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir / digest, text_dir / f"{digest}.txt"


def download_document(url: str, cache_dir: Path, timeout: int = 45, force: bool = False) -> tuple[Path, str]:
    stem, _ = cache_paths(url, cache_dir)
    existing = list(stem.parent.glob(stem.name + ".*"))
    if existing and not force:
        path = existing[0]
        if path.suffix.lower() == ".pdf":
            return path, "application/pdf"
        if path.suffix.lower() in {".html", ".htm"}:
            return path, "text/html"
        return path, "application/octet-stream"

    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "")
    suffix = _safe_suffix(url, content_type)
    path = stem.with_suffix(suffix)
    path.write_bytes(resp.content)
    return path, content_type


def _extract_pdf_text(path: Path, max_pages: int | None = None) -> str:
    if pdfplumber is None:
        return ""
    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        for idx, page in enumerate(pages, 1):
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            if text.strip():
                parts.append(f"\n\n--- page {idx} ---\n{text}")
    return "\n".join(parts).strip()


def _extract_html_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def extract_document_text(path: Path, content_type: str = "", max_pages: int | None = None) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf" or "pdf" in content_type.lower():
        return _extract_pdf_text(path, max_pages=max_pages)
    if suffix in {".html", ".htm"} or "html" in content_type.lower():
        return _extract_html_text(path)
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def fetch_and_parse_document(
    url: str,
    cache_dir: Path,
    *,
    timeout: int = 45,
    max_pages: int | None = None,
    force: bool = False,
) -> ParsedDocument:
    _, text_path = cache_paths(url, cache_dir)
    try:
        local_path, content_type = download_document(url, cache_dir, timeout=timeout, force=force)
        if text_path.exists() and not force:
            text = text_path.read_text(encoding="utf-8", errors="replace")
        else:
            text = extract_document_text(local_path, content_type=content_type, max_pages=max_pages)
            text_path.write_text(text, encoding="utf-8")
        return ParsedDocument(url=url, local_path=local_path, content_type=content_type, text_path=text_path, text=text, status="ok" if text else "empty")
    except Exception as exc:
        return ParsedDocument(url=url, local_path=Path(""), content_type="", text_path=text_path, text="", status="error", error=str(exc))


def classify_body_text(text: str) -> dict[str, dict[str, Any]]:
    lower = text.lower()
    out: dict[str, dict[str, Any]] = {}
    for field, keywords in BODY_SIGNAL_KEYWORDS.items():
        hits = []
        for keyword in keywords:
            if keyword.lower() in lower:
                hits.append(keyword)
        if hits:
            out[field] = {"hit_count": len(hits), "keywords": hits[:12]}
    return out


def build_body_evidence_rows(
    *,
    stock_code: str,
    company_name: str,
    source_title: str,
    source_url: str,
    document_date: str,
    parsed: ParsedDocument,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if parsed.status not in {"ok", "empty"}:
        rows.append(
            {
                "stock_code": stock_code,
                "company_name": company_name,
                "field_name": "document_body_parse_status",
                "field_value": f"error: {parsed.error}",
                "source_type": "HKEX document body",
                "source_title": source_title,
                "source_url": source_url,
                "file_path": str(parsed.local_path) if parsed.local_path else "",
                "document_date": document_date,
                "page_number": "",
                "claim_type": "fact",
                "support_level": "official",
                "confidence_level": "medium",
                "verification_status": "parse_failed",
                "narrative_use": "factual_layer",
                "assumption_dependency": "",
                "notes": parsed.error,
            }
        )
        return rows

    signals = classify_body_text(parsed.text)
    rows.append(
        {
            "stock_code": stock_code,
            "company_name": company_name,
            "field_name": "document_body_parse_status",
            "field_value": f"{parsed.status}; extracted_chars={len(parsed.text)}",
            "source_type": "HKEX document body",
            "source_title": source_title,
            "source_url": source_url,
            "file_path": str(parsed.local_path),
            "document_date": document_date,
            "page_number": "",
            "claim_type": "fact",
            "support_level": "official",
            "confidence_level": "medium" if parsed.text else "low",
            "verification_status": "body_text_extracted" if parsed.text else "body_text_empty",
            "narrative_use": "factual_layer",
            "assumption_dependency": "",
            "notes": f"Cached text: {parsed.text_path}",
        }
    )
    for field, payload in signals.items():
        rows.append(
            {
                "stock_code": stock_code,
                "company_name": company_name,
                "field_name": f"document_body_signal:{field}",
                "field_value": ", ".join(payload["keywords"]),
                "source_type": "HKEX document body",
                "source_title": source_title,
                "source_url": source_url,
                "file_path": str(parsed.local_path),
                "document_date": document_date,
                "page_number": "",
                "claim_type": "inference",
                "support_level": "official_body_text",
                "confidence_level": "medium",
                "verification_status": "needs_human_review",
                "narrative_use": "constraint_layer",
                "assumption_dependency": "Keyword hit in extracted body text; requires analyst reading before final conclusion.",
                "notes": f"hit_count={payload['hit_count']}; cached_text={parsed.text_path}",
            }
        )
    return rows
