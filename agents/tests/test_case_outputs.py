import json
from pathlib import Path
from dealtech_certification.engine import run_agent_case


def test_generated_case_outputs_exist_and_match_status():
    result = run_agent_case('shell-company-screening', 'case_001_tonton_shell_company_screening')
    out = Path(result.output_written_to)
    for name in ['certification_result.json', 'ER_BRB_case_result.md', 'PCE_case_result.md', 'final_output.md', 'scoped_claim_audit_sample.csv', 'scoped_claim_audit_result.md']:
        assert (out / name).exists()
    cert = json.loads((out / 'certification_result.json').read_text(encoding='utf-8'))
    assert cert['overall_status'] == 'Certified with Caveat'
    assert cert['claims_checked'] == result.claims_checked


def test_acquisition_target_output_stays_target_side():
    result = run_agent_case('acquisition-strategy', 'case_001_acquisition_strategy', 'target_side')
    text = Path(result.output_written_to, 'final_output.md').read_text(encoding='utf-8')
    assert 'target_side' in text
    assert 'Needs Human Review' in text


def test_shell_pce_output_includes_scoped_business_claim_sample():
    result = run_agent_case('shell-company-screening', 'case_001_tonton_shell_company_screening')
    text = Path(result.output_written_to, 'PCE_result.md').read_text(encoding='utf-8')
    assert 'Scoped sampled business claims' in text
    assert 'delivery_scope=external_final' in text
    assert 'CLM-EV-00001' in text
