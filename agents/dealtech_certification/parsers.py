from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable


def normalize_key(key: str) -> str:
    return key.strip().strip('`').replace(' ', '_')


def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or '').strip().lower()
    return text in {'yes', 'true', 'y', '1', 'eligible', 'certified'} or text.startswith('yes')


def parse_markdown_table(path: Path) -> list[dict[str, str]]:
    rows: list[list[str]] = []
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line.startswith('|') or not line.endswith('|'):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        # Skip separator rows such as |---|---|
        if cells and all(set(c.replace(':', '').strip()) <= {'-'} for c in cells):
            continue
        rows.append(cells)
    if len(rows) < 2:
        return []
    headers = [normalize_key(h) for h in rows[0]]
    result = []
    for cells in rows[1:]:
        padded = cells + [''] * (len(headers) - len(cells))
        result.append({headers[i]: padded[i] for i in range(len(headers))})
    return result


def parse_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline='', encoding='utf-8-sig') as f:
        return [{normalize_key(k): (v or '').strip() for k, v in row.items()} for row in csv.DictReader(f)]


def read_table(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    if path.suffix.lower() == '.csv':
        return parse_csv(path)
    if path.suffix.lower() in {'.md', '.markdown'}:
        return parse_markdown_table(path)
    raise ValueError(f'Unsupported table format: {path}')


def first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None
