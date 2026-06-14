
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


def test_source_registry_required_fields():
    source_files = [ROOT / '02_data_sources/source_registry.md'] + all_case_files_named('source_registry.md')
    required = ['source_id','source_name','source_type','url_or_file','used_for','reliability_tier','PCE_eligible','limitations']
    for file in source_files:
        rows = markdown_table_rows(file.read_text(encoding='utf-8'))
        assert rows, file
        for field in required:
            assert field in rows[0], (file, rows[0])
        for row in rows:
            assert row['source_id'].strip(), file


def test_imported_artifact_not_tier1_primary():
    for file in [ROOT / '02_data_sources/source_registry.md'] + all_case_files_named('source_registry.md'):
        for row in markdown_table_rows(file.read_text(encoding='utf-8')):
            joined = ' '.join(row.values()).lower()
            if 'imported artifact' in joined:
                assert 'tier 1' not in row.get('reliability_tier','').lower()
                assert row.get('PCE_eligible','').lower() not in ['yes', 'true']
