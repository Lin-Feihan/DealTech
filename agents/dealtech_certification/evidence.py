from __future__ import annotations

from pathlib import Path
from .models import EvidenceRecord, ClaimMapRecord
from .parsers import first_existing, parse_bool, read_table


def _find_evidence_table(case_dir: Path | None, agent_dir: Path) -> Path:
    candidates = []
    if case_dir:
        candidates.extend([case_dir / 'evidence_table.csv', case_dir / 'evidence_table.md'])
    candidates.extend([
        agent_dir / '02_data_sources' / 'evidence_table.csv',
        agent_dir / '02_data_sources' / 'evidence_table.md',
    ])
    path = first_existing(candidates)
    if not path:
        raise FileNotFoundError(f'No evidence_table.md/.csv found for {case_dir or agent_dir}')
    return path


def _find_claim_map(case_dir: Path | None) -> Path | None:
    if not case_dir:
        return None
    return first_existing([
        case_dir / 'claim_to_evidence_map.csv',
        case_dir / 'claim_to_evidence_map.md',
        case_dir / 'claim_to_evidence_map.csv',
        case_dir / 'claim_to_evidence_map.md',
        case_dir / 'supporting_files' / 'trace' / 'claim_to_evidence_map.csv',
        case_dir / 'supporting_files' / 'trace' / 'claim_to_evidence_map.md',
    ])


def load_evidence_table(case_dir: Path | None, agent_dir: Path) -> list[EvidenceRecord]:
    path = _find_evidence_table(case_dir, agent_dir)
    records: list[EvidenceRecord] = []
    for row in read_table(path):
        evidence_id = row.get('evidence_id') or row.get('id') or row.get('evidence')
        claim_id = row.get('claim_id') or ''
        source_id = row.get('source_id') or ''
        if not evidence_id or evidence_id.lower().startswith('evidence_id'):
            continue
        records.append(EvidenceRecord(
            evidence_id=evidence_id,
            claim_id=claim_id,
            source_id=source_id,
            extracted_fact=row.get('extracted_fact', row.get('fact', row.get('claim_text', ''))),
            evidence_type=row.get('evidence_type', row.get('type', '')),
            confidence=row.get('confidence', ''),
            limitations=row.get('limitations', ''),
            human_review_required=parse_bool(row.get('human_review_required', '')),
            PCE_status=row.get('PCE_status', row.get('pce_status', '')),
            raw=row,
        ))
    if not records:
        raise ValueError(f'Evidence table is empty: {path}')
    return records


def load_claim_to_evidence_map(case_dir: Path | None, evidence: list[EvidenceRecord]) -> list[ClaimMapRecord]:
    path = _find_claim_map(case_dir)
    records: list[ClaimMapRecord] = []
    if path:
        for row in read_table(path):
            claim_id = row.get('claim_id') or ''
            if not claim_id or claim_id.lower().startswith('claim_id'):
                continue
            records.append(ClaimMapRecord(
                claim_id=claim_id,
                evidence_id=row.get('evidence_id', ''),
                source_id=row.get('source_id', ''),
                claim_text=row.get('claim_text', row.get('extracted_fact', '')),
                calculation_required=parse_bool(row.get('calculation_required', '')),
                calculation_replayed=parse_bool(row.get('calculation_replayed', '')),
                human_review_required=parse_bool(row.get('human_review_required', '')),
                certification_status=row.get('certification_status', row.get('PCE_status', '')),
                raw=row,
            ))
    if records:
        return records
    # Fallback: derive a real claim map from the evidence table, not an empty placeholder.
    return [ClaimMapRecord(
        claim_id=e.claim_id,
        evidence_id=e.evidence_id,
        source_id=e.source_id,
        claim_text=e.extracted_fact,
        human_review_required=e.human_review_required,
        certification_status=e.PCE_status,
        raw={'derived_from': 'evidence_table'},
    ) for e in evidence if e.claim_id]
