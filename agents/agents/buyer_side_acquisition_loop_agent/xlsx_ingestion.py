from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .live_research_models import AttachmentValidationError


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CELL_REF = re.compile(r"^[A-Z]{1,3}[1-9][0-9]*$")


@dataclass
class XLSXCellProvenance:
    filename: str
    file_hash_sha256: str
    sheet_name: str
    locator: str
    underlying_value: str
    displayed_value: str
    formula: str
    unit: str
    currency: str
    scale: str
    extraction_limitations: list[str]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_xlsx(path: Path) -> zipfile.ZipFile:
    if path.suffix.lower() != ".xlsx":
        raise AttachmentValidationError("Unsupported workbook type; only non-macro .xlsx is accepted.")
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise AttachmentValidationError(
            "Encrypted or unsupported XLSX workbook; local extraction requires an unencrypted OOXML .xlsx file."
        ) from exc
    names = set(archive.namelist())
    required = {"[Content_Types].xml", "xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
    if not required.issubset(names):
        archive.close()
        raise AttachmentValidationError("Encrypted or unsupported XLSX workbook structure.")
    if any(name.lower().endswith("vbaproject.bin") for name in names):
        archive.close()
        raise AttachmentValidationError("Macro-enabled workbook content is unsupported; macros are never evaluated.")
    return archive


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t")) for item in root]


def _sheet_paths(archive: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    target_by_id = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
    }
    result: dict[str, str] = {}
    for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
        rel_id = sheet.attrib.get(f"{{{REL_NS}}}id", "")
        target = target_by_id.get(rel_id, "")
        if not target:
            continue
        if target.startswith("/"):
            path = target.lstrip("/")
        elif target.startswith("xl/"):
            path = target
        else:
            path = "xl/" + target.lstrip("/")
        result[sheet.attrib["name"]] = path.replace("\\", "/")
    return result


def _cell_value(cell: ET.Element, shared: list[str]) -> tuple[str, str, str]:
    formula_node = cell.find(f"{{{MAIN_NS}}}f")
    value_node = cell.find(f"{{{MAIN_NS}}}v")
    inline = cell.find(f"{{{MAIN_NS}}}is")
    formula = formula_node.text or "" if formula_node is not None else ""
    raw = value_node.text or "" if value_node is not None else ""
    cell_type = cell.attrib.get("t", "")
    if cell_type == "s" and raw:
        try:
            displayed = shared[int(raw)]
        except (IndexError, ValueError) as exc:
            raise AttachmentValidationError("XLSX shared-string index is invalid.") from exc
    elif cell_type == "inlineStr" and inline is not None:
        displayed = "".join(node.text or "" for node in inline.iter(f"{{{MAIN_NS}}}t"))
        raw = displayed
    elif cell_type == "b":
        displayed = "TRUE" if raw == "1" else "FALSE"
    else:
        displayed = raw
    return raw, displayed, formula


def extract_xlsx_cells(path: Path, specifications: list[dict[str, Any]]) -> list[XLSXCellProvenance]:
    path = path.resolve()
    archive = _open_xlsx(path)
    try:
        shared = _shared_strings(archive)
        sheets = _sheet_paths(archive)
        parsed: dict[str, dict[str, tuple[str, str, str]]] = {}
        for sheet_name, sheet_path in sheets.items():
            root = ET.fromstring(archive.read(sheet_path))
            parsed[sheet_name] = {
                cell.attrib["r"]: _cell_value(cell, shared)
                for cell in root.findall(f".//{{{MAIN_NS}}}c")
                if cell.attrib.get("r")
            }
        result: list[XLSXCellProvenance] = []
        digest = _sha256(path)
        for spec in specifications:
            required = {"sheet_name", "locator", "unit", "currency", "scale"}
            missing = sorted(key for key in required if not str(spec.get(key, "")).strip())
            if missing:
                raise AttachmentValidationError(
                    f"XLSX extraction specification cannot infer missing labels: {missing}."
                )
            sheet_name = str(spec["sheet_name"])
            locator = str(spec["locator"]).upper()
            if sheet_name not in parsed:
                raise AttachmentValidationError(f"XLSX sheet does not exist: {sheet_name}")
            if not CELL_REF.fullmatch(locator):
                raise AttachmentValidationError("Milestone 7 XLSX extraction requires an exact single-cell locator.")
            if locator not in parsed[sheet_name]:
                raise AttachmentValidationError(f"XLSX cell is empty or absent: {sheet_name}!{locator}")
            raw, displayed, formula = parsed[sheet_name][locator]
            result.append(
                XLSXCellProvenance(
                    filename=path.name,
                    file_hash_sha256=digest,
                    sheet_name=sheet_name,
                    locator=locator,
                    underlying_value=raw,
                    displayed_value=displayed,
                    formula=formula,
                    unit=str(spec["unit"]),
                    currency=str(spec["currency"]),
                    scale=str(spec["scale"]),
                    extraction_limitations=[
                        "Local OOXML extraction only; formulas and macros are not evaluated.",
                        "Displayed formatting is not reconstructed; cached or underlying values are retained where practical.",
                    ],
                )
            )
        return result
    except (ET.ParseError, KeyError, ValueError) as exc:
        if isinstance(exc, AttachmentValidationError):
            raise
        raise AttachmentValidationError(f"Unsupported or malformed XLSX workbook: {exc}") from exc
    finally:
        archive.close()


def xlsx_local_text(path: Path, *, maximum_cells: int = 500) -> str:
    """Return bounded local extraction text without evaluating formulas or macros."""

    archive = _open_xlsx(path.resolve())
    try:
        shared = _shared_strings(archive)
        sheets = _sheet_paths(archive)
        rows = [f"Workbook: {path.name}", f"SHA-256: {_sha256(path)}"]
        count = 0
        for sheet_name, sheet_path in sheets.items():
            root = ET.fromstring(archive.read(sheet_path))
            for cell in root.findall(f".//{{{MAIN_NS}}}c"):
                locator = cell.attrib.get("r", "")
                raw, displayed, formula = _cell_value(cell, shared)
                rows.append(
                    f"{sheet_name}!{locator}: underlying={raw!r}; displayed={displayed!r}; formula={formula!r}"
                )
                count += 1
                if count >= maximum_cells:
                    rows.append("Extraction truncated at configured local cell limit.")
                    return "\n".join(rows)
        return "\n".join(rows)
    except (ET.ParseError, KeyError, ValueError) as exc:
        raise AttachmentValidationError(f"Unsupported or malformed XLSX workbook: {exc}") from exc
    finally:
        archive.close()
