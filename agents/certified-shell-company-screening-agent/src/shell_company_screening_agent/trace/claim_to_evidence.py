from __future__ import annotations

import csv
from pathlib import Path


def read_claim_map(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def claims_missing_evidence(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        r
        for r in rows
        if not (r.get('evidence_id') or r.get('source_id') or r.get('calc_id') or r.get('risk_id'))
    ]
