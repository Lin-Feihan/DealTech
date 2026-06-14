
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


def test_required_agent_dirs_exist():
    for name in ['00_input_setting','01_business_workflow','02_data_sources','03_prompts','04_schemas','05_ER_BRB','06_PCE','07_case_studies','src','tests']:
        assert (ROOT / name).exists(), name


def test_readme_has_required_sections():
    text = read('README.md')
    for heading in ['## 1. Business Problem','## 2. User Input','## 3. Business Workflow','## 4. Data Sources & Evidence Layer','## 5. ER/BRB Layer','## 6. PCE Layer','## 7. Case Studies','## 8. Current Certification Status','## 9. Current Limitations','## 10. How to Run']:
        assert heading in text


def test_no_deprecated_copy_backup_files_in_agent():
    forbidden = ['old', 'final_v2', 'copy', 'backup']
    for p in ROOT.rglob('*'):
        rel = p.relative_to(ROOT).as_posix().lower()
        assert not any(token in rel for token in forbidden), rel
