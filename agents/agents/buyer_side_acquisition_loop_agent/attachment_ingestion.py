from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from .live_research_models import (
    AttachmentRecord,
    AttachmentValidationError,
    ProviderMode,
)
from .xlsx_ingestion import xlsx_local_text


SUPPORTED_ATTACHMENT_TYPES = {".pdf", ".txt", ".md", ".html", ".csv", ".xlsx"}
PLAIN_TEXT_TYPES = {".txt", ".md", ".html", ".csv"}
SECRET_FIELD_NAMES = {
    "api_key",
    "openai_api_key",
    "authorization",
    "bearer_token",
    "client_secret",
    "secret_key",
}


def validate_no_plaintext_credentials(value: Any, path: str = "case") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).strip().lower()
            if lowered in SECRET_FIELD_NAMES and item not in (None, "", []):
                raise AttachmentValidationError(
                    f"Plaintext credential field is prohibited in case input: {path}.{key}"
                )
            validate_no_plaintext_credentials(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_no_plaintext_credentials(item, f"{path}[{index}]")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_attachment_path(case_dir: Path, relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise AttachmentValidationError("Attachment paths must be non-empty and relative to the case directory.")
    root = case_dir.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise AttachmentValidationError("Attachment path escapes the case directory.") from exc
    if not candidate.is_file():
        raise AttachmentValidationError(f"Attachment does not exist: {relative_path}")
    return candidate


def prepare_attachments(
    *,
    case_dir: Path,
    manifest: list[dict[str, Any]],
    provider_mode: ProviderMode,
) -> tuple[list[AttachmentRecord], list[dict[str, Any]]]:
    records: list[AttachmentRecord] = []
    blocked: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in manifest:
        required = {
            "attachment_id",
            "path",
            "original_filename",
            "file_type",
            "confidentiality",
            "supplied_by",
            "document_date",
            "allow_provider_upload",
        }
        missing = sorted(key for key in required if key not in row)
        if missing:
            raise AttachmentValidationError(f"Attachment manifest entry misses {missing}.")
        attachment_id = str(row["attachment_id"]).strip()
        if not attachment_id or attachment_id in seen_ids:
            raise AttachmentValidationError(f"Duplicate or empty attachment_id: {attachment_id!r}")
        seen_ids.add(attachment_id)
        path = _safe_attachment_path(case_dir, str(row["path"]))
        extension = path.suffix.lower()
        if extension not in SUPPORTED_ATTACHMENT_TYPES:
            raise AttachmentValidationError(
                f"Unsupported attachment type {extension or '<none>'}; supported: PDF, TXT, Markdown, HTML, CSV, XLSX."
            )
        if extension == ".xlsx" and not any(
            str(module_id) in {"B1", "B2", "B3", "B4", "B5"}
            for module_id in row.get("permitted_modules", [])
        ):
            raise AttachmentValidationError(
                "Unsupported attachment type .xlsx outside the explicit Block B local-ingestion boundary."
            )
        declared = str(row["file_type"]).lower()
        if declared not in {extension, extension.lstrip(".")}:
            raise AttachmentValidationError(
                f"Attachment {attachment_id} file_type does not match {extension}."
            )
        if str(row["original_filename"]) != path.name:
            raise AttachmentValidationError(
                f"Attachment {attachment_id} original_filename must match the supplied file."
            )
        confidentiality = str(row["confidentiality"]).strip()
        permitted = bool(row["allow_provider_upload"])
        if (
            provider_mode == ProviderMode.OPENAI_LIVE
            and confidentiality.lower() != "public"
            and not permitted
        ):
            blocked.append(
                {
                    "attachment_id": attachment_id,
                    "reason": "Confidential attachment upload was not explicitly permitted.",
                    "route": "HUMAN_REVIEW",
                }
            )
        local_text = ""
        if extension in PLAIN_TEXT_TYPES:
            try:
                local_text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise AttachmentValidationError(
                    f"Attachment {attachment_id} is not valid UTF-8 text."
                ) from exc
        elif extension == ".xlsx":
            local_text = xlsx_local_text(path)
        if extension == ".csv":
            row_count = max(0, len(local_text.splitlines()) - 1)
            locator = f"rows 1-{row_count}" if row_count else "header only"
            extraction_method = "local UTF-8 CSV row preservation"
        elif extension == ".html":
            locator = "entire HTML document with original markup preserved"
            extraction_method = "local UTF-8 HTML read; no browser rendering"
        elif extension in {".txt", ".md"}:
            locator = "entire file; line locators required in extracted Evidence"
            extraction_method = "local UTF-8 text read"
        elif extension == ".xlsx":
            locator = "exact sheet and cell locator required in extracted Evidence"
            extraction_method = "local OOXML cell extraction; formulas and macros are not evaluated"
        else:
            locator = "page locator must be returned by the provider"
            extraction_method = "OpenAI Responses API input_file; no OCR"
        records.append(
            AttachmentRecord(
                attachment_id=attachment_id,
                original_filename=path.name,
                relative_path=str(row["path"]).replace("\\", "/"),
                file_hash_sha256=_hash(path),
                file_type=extension.lstrip("."),
                confidentiality=confidentiality,
                supplied_by=str(row["supplied_by"]),
                document_date=str(row["document_date"]),
                locator=locator,
                extraction_method=extraction_method,
                extraction_limitations=str(
                    row.get(
                        "extraction_limitations",
                        "No OCR; facts require exact page, section, line or row locator.",
                    )
                ),
                allow_provider_upload=permitted,
                source_id=str(row.get("source_id") or f"SRC-ATT-{attachment_id}"),
                local_text=local_text,
                absolute_path=str(path),
            )
        )
    return records, blocked


def attachment_source(record: AttachmentRecord) -> dict[str, Any]:
    return {
        "source_id": record.source_id,
        "url": "",
        "page_title": record.original_filename,
        "publisher_or_owner": record.supplied_by,
        "source_type": "case-supplied attachment",
        "source_tier": "Tier 2 case-supplied document",
        "publication_date": record.document_date,
        "retrieval_timestamp": "",
        "author": record.supplied_by,
        "exact_relevant_locator": record.locator,
        "discovery_query": "case attachment manifest",
        "provider_response_reference": record.attachment_id,
        "pce_eligible": True,
        "limitations": record.extraction_limitations,
        "confidentiality_classification": record.confidentiality,
        "source_kind": "attachment",
        "original_filename": record.original_filename,
        "file_hash_sha256": record.file_hash_sha256,
        "file_type": record.file_type,
        "supplied_by": record.supplied_by,
        "document_date": record.document_date,
        "extraction_method": record.extraction_method,
    }


def attachment_manifest_artifact(records: list[AttachmentRecord]) -> list[dict[str, Any]]:
    return [
        {
            "attachment_id": item.attachment_id,
            "source_id": item.source_id,
            "original_filename": item.original_filename,
            "relative_path": item.relative_path,
            "file_hash_sha256": item.file_hash_sha256,
            "file_type": item.file_type,
            "confidentiality": item.confidentiality,
            "supplied_by": item.supplied_by,
            "document_date": item.document_date,
            "locator": item.locator,
            "extraction_method": item.extraction_method,
            "extraction_limitations": item.extraction_limitations,
            "allow_provider_upload": item.allow_provider_upload,
        }
        for item in records
    ]


def output_directory_is_writable(path: Path) -> bool:
    candidate = path if path.exists() else path.parent
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate.is_dir() and os.access(candidate, os.W_OK)
