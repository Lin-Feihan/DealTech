from pathlib import Path

from shell_company_screening_agent.pce.certification_report import certify_example, derive_claim_status


def test_pce_certification_runs():
    result = certify_example(Path('examples/tuntun_hk'))
    assert result['certification_status'] in {'Certified', 'Certified with Caveat', 'Internal Trace Only', 'Needs Human Review', 'Not Certified'}


def test_missing_evidence_is_not_certified():
    claim = {
        'claim_id': 'CLM-EV-99999',
        'delivery_scope': 'external_final',
        'evidence_id': 'EVI-MISSING',
        'calculation_required': 'No',
        'human_review_required': 'No',
        'stage': 'dd_evidence',
        'certification_status': 'Certified',
    }
    idx = {
        'dd_by_evidence': {},
        'calc_by_id': {},
        'risk_by_id': {},
        'er_by_claim': {},
        'hf_by_code': {},
        'risk_by_code': {},
    }
    status, reasons, evidence_status, human_review = derive_claim_status(claim, idx)
    assert status == 'Not Certified'
    assert evidence_status == 'missing'
    assert human_review == 'No'
    assert any('missing from dd_evidence_table' in r for r in reasons)


def test_needs_review_evidence_cannot_be_certified():
    claim = {
        'claim_id': 'CLM-EV-00001',
        'delivery_scope': 'external_final',
        'evidence_id': 'EVI-1',
        'calculation_required': 'No',
        'human_review_required': 'No',
        'stage': 'dd_evidence',
        'certification_status': 'Certified',
    }
    idx = {
        'dd_by_evidence': {'EVI-1': {'verification_status': 'needs_review', 'notes': '', 'company_name': '', 'source_id': ''}},
        'calc_by_id': {},
        'risk_by_id': {},
        'er_by_claim': {},
        'hf_by_code': {},
        'risk_by_code': {},
    }
    status, reasons, evidence_status, human_review = derive_claim_status(claim, idx)
    assert status == 'Needs Human Review'
    assert evidence_status == 'needs_review'
    assert human_review == 'Yes'
    assert any('verification_status=needs_review' in r for r in reasons)


def test_metadata_only_evidence_cannot_be_external_certified():
    claim = {
        'claim_id': 'CLM-EV-00002',
        'delivery_scope': 'external_final',
        'evidence_id': 'EVI-2',
        'calculation_required': 'No',
        'human_review_required': 'No',
        'stage': 'dd_evidence',
        'certification_status': 'Certified',
    }
    idx = {
        'dd_by_evidence': {'EVI-2': {'verification_status': 'document_derived', 'notes': 'metadata-level evidence only; underlying pdfs/html not parsed yet', 'field_name': '', 'field_value': '', 'company_name': '', 'source_id': ''}},
        'calc_by_id': {},
        'risk_by_id': {},
        'er_by_claim': {},
        'hf_by_code': {},
        'risk_by_code': {},
    }
    status, reasons, evidence_status, human_review = derive_claim_status(claim, idx)
    assert status == 'Needs Human Review'
    assert human_review == 'Yes'
    assert any('metadata/title-level' in r for r in reasons)


def test_upstream_human_review_propagates_to_claim_level():
    claim = {
        'claim_id': 'CLM-HF-00001',
        'delivery_scope': 'external_final',
        'stock_code': '00001.HK',
        'stage': 'hard_filter',
        'calculation_required': 'No',
        'human_review_required': 'No',
        'certification_status': 'Certified',
        'source_id': 'SRC-1',
    }
    idx = {
        'dd_by_evidence': {},
        'calc_by_id': {},
        'risk_by_id': {},
        'er_by_claim': {},
        'hf_by_code': {'00001.HK': [{'filter_record_id': 'HF-1', 'human_review_required': 'Yes'}]},
        'risk_by_code': {},
    }
    status, reasons, evidence_status, human_review = derive_claim_status(claim, idx)
    assert status == 'Needs Human Review'
    assert human_review == 'Yes'
    assert any('hard filter HF-1 requires human review' in r for r in reasons)
