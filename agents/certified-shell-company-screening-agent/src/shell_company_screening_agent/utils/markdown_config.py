from __future__ import annotations

import re
from pathlib import Path
from typing import Any


PIPE_TABLE_RE = re.compile(r"^\s*\|(.+)\|\s*$")
DEFAULT_REQUIRED_MARKDOWN = [
    "01_case_input/case_input.md",
    "02_prompts/shell_screening_prompt.md",
    "02_prompts/certified_trace_execution_prompt.md",
    "02_prompts/case_study_generation_prompt.md",
    "03_sources/source_map.md",
    "05_data_schema/candidate_schema.md",
    "06_output_format/output_format.md",
    "06_output_format/case_study_output_format.md",
    "certified_research_trace/certified_research_trace_definition.md",
    "pce_workflow/pce_policy_rules.md",
    "pce_workflow/final_delivery_gate.md",
]


def clean_cell(value: str) -> str:
    return value.strip().strip("`").strip()


def read_markdown_files(root: Path) -> dict[str, str]:
    """Read project markdown files, excluding generated/vendor directories."""
    excluded = {"outputs", "runtime_cache", ".git", "__pycache__", ".venv", "venv"}
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if any(part in excluded for part in rel.parts):
            continue
        files[str(rel)] = path.read_text(encoding="utf-8", errors="replace")
    return files


def read_required_markdown(root: Path) -> tuple[dict[str, str], list[str]]:
    files: dict[str, str] = {}
    missing: list[str] = []
    for rel in DEFAULT_REQUIRED_MARKDOWN:
        path = root / rel
        if path.exists():
            files[rel] = path.read_text(encoding="utf-8", errors="replace")
        else:
            missing.append(rel)
    # Also read runbook and certified-trace run instructions when present because they define stop conditions.
    for rel in ["04_agent_config/runbook.md", "certified_research_trace/run_instruction.md"]:
        path = root / rel
        if path.exists():
            files[rel] = path.read_text(encoding="utf-8", errors="replace")
    return files, missing


def _split_table_line(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [clean_cell(cell) for cell in stripped.split("|")]


def extract_markdown_tables(markdown: str) -> list[list[dict[str, str]]]:
    """Extract simple GitHub-style pipe tables into row dictionaries."""
    lines = markdown.splitlines()
    tables: list[list[dict[str, str]]] = []
    i = 0
    while i < len(lines):
        if not PIPE_TABLE_RE.match(lines[i]):
            i += 1
            continue
        if i + 1 >= len(lines) or not PIPE_TABLE_RE.match(lines[i + 1]):
            i += 1
            continue
        header = _split_table_line(lines[i])
        divider = _split_table_line(lines[i + 1])
        if not divider or not all(set(cell.replace(":", "").strip()) <= {"-"} and "-" in cell for cell in divider):
            i += 1
            continue
        rows: list[dict[str, str]] = []
        i += 2
        while i < len(lines) and PIPE_TABLE_RE.match(lines[i]):
            cells = _split_table_line(lines[i])
            rows.append({header[j]: cells[j] if j < len(cells) else "" for j in range(len(header))})
            i += 1
        tables.append(rows)
    return tables


def load_source_map(root: Path) -> dict[str, Any]:
    path = root / "03_sources" / "source_map.md"
    if not path.exists():
        # Backward compatible fallback for flat workspaces.
        path = root / "source_map.md"
    if not path.exists():
        return {"sources": [], "parameters": {}, "path": None, "raw_text": ""}

    markdown = path.read_text(encoding="utf-8", errors="replace")
    source_ids = re.findall(r"\*\*Source ID:\*\*\s*`?([A-Z0-9_\-]+)`?", markdown)
    sources: list[dict[str, str]] = []
    for sid in source_ids:
        if sid == "AKSHARE_HK":
            sources.append(
                {
                    "source_id": "AKSHARE_HK",
                    "priority": "2",
                    "market": "HK",
                    "data_type": "basic_quote_market_cap_pb_turnover",
                    "access_method": "akshare",
                    "akshare_function": "stock_hk_spot_em",
                    "status": "active",
                    "notes": "Parsed from 03_sources/source_map.md; AKShare is for first-round screening only.",
                }
            )
            sources.append(
                {
                    "source_id": "AKSHARE_HK_FALLBACK",
                    "priority": "2",
                    "market": "HK",
                    "data_type": "basic_quote",
                    "access_method": "akshare",
                    "akshare_function": "stock_hk_spot",
                    "status": "fallback",
                    "notes": "Fallback endpoint if stock_hk_spot_em fails or schema changes.",
                }
            )
        elif sid == "HKEXNEWS_OFFICIAL":
            sources.append(
                {
                    "source_id": sid,
                    "priority": "1",
                    "market": "HK",
                    "data_type": "announcements_filings",
                    "access_method": "planned_hkexnews",
                    "status": "planned",
                    "notes": "Official source for verification and document-level review.",
                }
            )
        elif sid in {"COMPANY_IR", "INDUSTRY_AND_COMPARABLES"}:
            sources.append(
                {
                    "source_id": sid,
                    "priority": "3",
                    "market": "HK",
                    "data_type": "commercial_reference",
                    "access_method": "planned",
                    "status": "planned",
                    "notes": "Supports inference/hypothesis layers; not a substitute for official filings.",
                }
            )
        else:
            sources.append(
                {
                    "source_id": sid,
                    "priority": "4" if "REFERENCE" in sid or "CRAWLER" in sid else "3",
                    "market": "HK",
                    "data_type": "reference",
                    "access_method": "planned",
                    "status": "planned",
                    "notes": "Parsed from markdown source map; active use depends on later pipeline stages.",
                }
            )

    # Conservative defaults inferred from prompt/runbook, not facts about issuers.
    params = {
        "max_market_cap_hkd": 2_000_000_000.0,
        "max_pb": 0.8,
        "min_turnover_hkd": 0.0,
        "max_rows_for_output": 5000.0,
    }
    return {"sources": sources, "parameters": params, "path": str(path), "raw_text": markdown}


def load_candidate_schema(root: Path) -> dict[str, Any]:
    path = root / "05_data_schema" / "candidate_schema.md"
    if not path.exists():
        path = root / "candidate_schema.md"
    if not path.exists():
        return {"tables": {}, "fields": [], "path": None}

    markdown = path.read_text(encoding="utf-8", errors="replace")
    tables: dict[str, list[str]] = {}
    current_table = "unknown"
    for line in markdown.splitlines():
        heading = re.match(r"^##+\s+.*?(hkex_full_universe\.csv|initial_screening_table\.csv|candidate_dd_table\.csv|source_evidence_table\.csv)", line)
        if heading:
            current_table = heading.group(1)
            tables.setdefault(current_table, [])
            continue
        if PIPE_TABLE_RE.match(line) and "字段名" not in line and "---" not in line:
            cells = _split_table_line(line)
            if cells:
                field = clean_cell(cells[0])
                if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", field):
                    tables.setdefault(current_table, []).append(field)

    all_fields = []
    for table, fields in tables.items():
        all_fields.extend({"table": table, "field": field} for field in fields)
    return {"tables": tables, "fields": all_fields, "path": str(path), "raw_text": markdown}
