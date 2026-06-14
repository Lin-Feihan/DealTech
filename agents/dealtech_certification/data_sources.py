from __future__ import annotations

from pathlib import Path
from .models import SourceRecord
from .parsers import first_existing, parse_bool, read_table


def _find_source_registry(case_dir: Path | None, agent_dir: Path) -> Path:
    candidates = []
    if case_dir:
        candidates.extend([case_dir / 'source_registry.csv', case_dir / 'source_registry.md'])
    candidates.extend([
        agent_dir / '02_data_sources' / 'source_registry.csv',
        agent_dir / '02_data_sources' / 'source_registry.md',
    ])
    path = first_existing(candidates)
    if not path:
        raise FileNotFoundError(f'No source_registry.md/.csv found for {case_dir or agent_dir}')
    return path


def load_source_registry(case_dir: Path | None, agent_dir: Path) -> list[SourceRecord]:
    path = _find_source_registry(case_dir, agent_dir)
    records = []
    for row in read_table(path):
        source_id = row.get('source_id') or row.get('id') or row.get('source')
        if not source_id or source_id.lower().startswith('source_id'):
            continue
        eligible_raw = row.get('PCE_eligible') or row.get('pce_eligible') or row.get('eligible') or ''
        records.append(SourceRecord(
            source_id=source_id,
            source_name=row.get('source_name', ''),
            source_type=row.get('source_type', ''),
            url_or_file=row.get('url_or_file', row.get('file', '')),
            used_for=row.get('used_for', ''),
            reliability_tier=row.get('reliability_tier', ''),
            PCE_eligible=parse_bool(eligible_raw),
            source_replay_status=row.get('source_replay_status', row.get('replay_status', '')),
            limitations=row.get('limitations', ''),
            raw=row,
        ))
    if not records:
        raise ValueError(f'Source registry is empty: {path}')
    return records
