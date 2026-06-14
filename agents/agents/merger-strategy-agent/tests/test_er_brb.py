
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


def test_er_brb_required_fields():
    files = [ROOT / '05_ER_BRB/ER_BRB_case_result.md'] + all_case_files_named('ER_BRB_result.md')
    if 'merger-strategy-agent' == 'merger-strategy-agent':
        assert 'Framework only' in read('05_ER_BRB/ER_BRB_case_result.md')
        return
    required = ['claim_id','claim_text','evidence_id','source_id','evidence_reliability','business_risk','regulatory_risk','reputational_risk','certification_status','human_review_required','reason']
    for file in files:
        rows = markdown_table_rows(file.read_text(encoding='utf-8'))
        assert rows, file
        for field in required:
            assert field in rows[0], (file, rows[0])
        for row in rows:
            joined = ' '.join(row.values()).lower()
            if any(token in joined for token in ['imported artifact','source mapping pending','calculation not replayed','source replay pending']):
                assert row['certification_status'].lower() != 'certified'
                assert row['human_review_required'].lower() == 'yes'


def test_merger_has_no_fake_case_result_if_applicable():
    if 'merger-strategy-agent' == 'merger-strategy-agent':
        combined = read('README.md') + read('05_ER_BRB/ER_BRB_case_result.md') + read('06_PCE/PCE_case_result.md') + read('07_case_studies/README.md')
        assert 'Framework only' in combined
        assert 'Business workflow integrated from provided flowchart' in combined
        assert ('Clean Case-Level ' + 'Certified') not in combined
