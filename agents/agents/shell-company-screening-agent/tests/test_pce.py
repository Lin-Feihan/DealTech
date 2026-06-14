
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


def test_pce_does_not_hide_human_review():
    files = [ROOT / '06_PCE/PCE_case_result.md'] + all_case_files_named('PCE_result.md')
    for file in files:
        text = file.read_text(encoding='utf-8')
        if 'human_review_required' in text or 'Human Review Required' in text or 'Needs Human Review' in text:
            assert ('Clean Case-Level ' + 'Certified') not in text
            assert 'pure `Certified`' not in text or 'not pure `Certified`' in text


def test_pce_required_claim_checks_present_in_workflow():
    workflow = read('06_PCE/PCE_workflow.md')
    for token in ['claim_id','source_id','PCE_eligible','imported artifact','metadata-level','calculation replay','risk escalation','human_review_required','final output']:
        assert token in workflow


def test_agent_specific_certification_status():
    combined = read('README.md') + read('06_PCE/PCE_case_result.md') + text_all_case_files('PCE_result.md')
    if 'shell-company-screening-agent' == 'shell-company-screening-agent':
        assert 'Certified with Caveat' in combined
        assert ('Clean Case-Level ' + 'Certified') not in combined
    elif 'shell-company-screening-agent' == 'spac-target-acquisition-agent':
        assert 'No authenticated Apify run was executed in this version.' in combined
        assert 'Human Review Required' in combined or 'Needs Human Review' in combined
        assert ('Clean Case-Level ' + 'Certified') not in combined and ('Live-Data ' + 'Rerun') not in combined and ('Live ' + 'Automated') not in combined
    elif 'shell-company-screening-agent' == 'acquisition-strategy-agent':
        assert 'Original source mapping pending; not PCE-eligible until source replay is completed.' in combined
        assert 'Needs Human Review' in combined
        assert ('clean case-level ' + 'certified') not in combined.lower()
    elif 'shell-company-screening-agent' == 'merger-strategy-agent':
        assert 'Framework only' in combined
        assert 'Business workflow integrated from provided flowchart' in combined
