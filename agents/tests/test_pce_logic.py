from dealtech_certification.engine import run_agent_case
from dealtech_certification.pce import run_pce
from dealtech_certification.models import ClaimMapRecord, EvidenceRecord, SourceRecord


def test_pce_outputs_claim_level_results():
    result = run_agent_case('shell-company-screening', 'case_001_tonton_shell_company_screening')
    claim_results = result.pce_result['claim_results']
    assert claim_results
    assert all('claim_id' in r and 'PCE_status' in r and 'checks' in r for r in claim_results)
    assert any(r['checks'].get('scoped_claim_sample') for r in claim_results)


def test_human_review_blocks_pure_certified_status():
    result = run_agent_case('acquisition-strategy', 'case_001_acquisition_strategy', 'buyer_side')
    assert result.pce_result['summary']['human_review_required_claims'] > 0
    assert result.pce_result['overall_status'] != 'Certified'


def test_final_output_does_not_hide_human_review_flags():
    result = run_agent_case('spac-target-acquisition', 'case_001_soren_spac_target_acquisition')
    assert result.status == 'Needs Human Review'
    assert not any(r['checks']['final_output_hides_caveat'] for r in result.pce_result['claim_results'])


def test_pending_source_cannot_be_treated_as_pce_eligible_without_completed_replay():
    source = SourceRecord(
        source_id='SRC-PENDING',
        source_name='Pending source packet',
        url_or_file='source replay packet pending',
        PCE_eligible=True,
        source_replay_status='pending',
    )
    evidence = EvidenceRecord(
        evidence_id='EVI-PENDING',
        claim_id='CLM-PENDING',
        source_id='SRC-PENDING',
        extracted_fact='A factual claim from a pending source.',
    )
    claim = ClaimMapRecord(
        claim_id='CLM-PENDING',
        evidence_id='EVI-PENDING',
        source_id='SRC-PENDING',
        claim_text='A factual claim from a pending source.',
        certification_status='Certified',
    )
    result = run_pce('case', 'acquisition-strategy', None, [evidence], [source], [claim], [])
    row = result['claim_results'][0]
    assert row['PCE_status'] == 'Needs Human Review'
    assert row['checks']['source_replay_pending']
    assert not row['checks']['source_PCE_eligible']
    assert 'source replay pending' in row['reason']


def test_imported_artifact_and_unreplayed_calculation_cannot_be_certified():
    source = SourceRecord(
        source_id='SRC-IMPORT',
        source_type='imported artifact',
        url_or_file='reports/imported.md',
        PCE_eligible=False,
    )
    evidence = EvidenceRecord(
        evidence_id='EVI-CALC',
        claim_id='CLM-CALC',
        source_id='SRC-IMPORT',
        extracted_fact='Valuation conclusion from imported artifact.',
        evidence_type='calculation pending',
    )
    claim = ClaimMapRecord(
        claim_id='CLM-CALC',
        evidence_id='EVI-CALC',
        source_id='SRC-IMPORT',
        claim_text='Valuation conclusion from imported artifact.',
        calculation_required=True,
        calculation_replayed=False,
        certification_status='Certified',
    )
    result = run_pce('case', 'acquisition-strategy', None, [evidence], [source], [claim], [])
    row = result['claim_results'][0]
    assert row['PCE_status'] != 'Certified'
    assert row['checks']['is_imported_artifact']
    assert row['checks']['calculation_replay_required']


def test_acquisition_valuation_fairness_and_recommendation_claims_are_not_certified():
    buyer = run_agent_case('acquisition-strategy', 'case_001_acquisition_strategy', 'buyer_side')
    target = run_agent_case('acquisition-strategy', 'case_001_acquisition_strategy', 'target_side')
    blocked_terms = ['valuation', 'fairness', 'recommendation', 'go-no-go', 'accept', 'reject', 'negotiate']
    rows = buyer.pce_result['claim_results'] + target.pce_result['claim_results']
    relevant = [r for r in rows if any(term in r['claim_text'].lower() for term in blocked_terms)]
    assert relevant
    assert all(r['PCE_status'] != 'Certified' for r in relevant)
