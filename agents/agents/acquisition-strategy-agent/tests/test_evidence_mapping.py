
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def markdown_table_rows(text):
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not (line.startswith('|') and line.endswith('|')):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if cells and all(set(c) <= {'-',' '} for c in cells):
            continue
        rows.append(cells)
    if len(rows) < 2:
        return []
    header = rows[0]
    data = []
    for cells in rows[1:]:
        if len(cells) == len(header):
            data.append(dict(zip(header, cells)))
    return data


def table_rows(path):
    return markdown_table_rows(read(path))


def all_case_files_named(filename):
    return list((ROOT / '07_case_studies').rglob(filename))


def text_all_case_files(filename):
    return '\n'.join(p.read_text(encoding='utf-8') for p in all_case_files_named(filename))


def test_evidence_table_required_fields_and_source_mapping():
    evidence_files = [ROOT / '02_data_sources/evidence_table.md'] + all_case_files_named('evidence_table.md')
    source_ids = set()
    for sf in [ROOT / '02_data_sources/source_registry.md'] + all_case_files_named('source_registry.md'):
        for row in markdown_table_rows(sf.read_text(encoding='utf-8')):
            source_ids.add(row['source_id'])
    required = ['evidence_id','claim_id','source_id','extracted_fact','evidence_type','confidence','limitations','human_review_required','PCE_status']
    for file in evidence_files:
        rows = markdown_table_rows(file.read_text(encoding='utf-8'))
        assert rows, file
        for field in required:
            assert field in rows[0], (file, rows[0])
        for row in rows:
            assert row['claim_id'].strip(), file
            assert row['source_id'] in source_ids, (file, row['source_id'], source_ids)


def test_llm_generated_summary_not_evidence():
    for file in [ROOT / '02_data_sources/evidence_table.md'] + all_case_files_named('evidence_table.md'):
        for row in markdown_table_rows(file.read_text(encoding='utf-8')):
            joined = ' '.join(row.values()).lower()
            if 'llm-generated summary' in joined or 'llm generated summary' in joined:
                assert row.get('PCE_status','').lower() not in ['certified', 'pure certified']
                assert row.get('evidence_type','').lower() == 'not evidence'
