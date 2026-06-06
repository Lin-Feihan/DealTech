from pathlib import Path

from shell_company_screening_agent.pce.final_delivery_gate import final_delivery_allowed, validate_final_delivery_claims


def test_delivery_gate_blocks_blockers():
    assert not final_delivery_allowed('Certified', ['blocker'])


def test_delivery_gate_requires_explicit_claim_references(tmp_path: Path):
    delivery = tmp_path / 'delivery'
    delivery.mkdir()
    (delivery / 'tuntun_hk_case_study.md').write_text('Narrative without material claim id.', encoding='utf-8')
    (delivery / 'top_candidate_dd_review_pack.md').write_text('More narrative without claim id.', encoding='utf-8')
    result = validate_final_delivery_claims(tmp_path, [], [])
    assert not result['allowed']
    assert result['blockers']


def test_delivery_gate_blocks_uncertified_referenced_claim(tmp_path: Path):
    delivery = tmp_path / 'delivery'
    delivery.mkdir()
    (delivery / 'tuntun_hk_case_study.md').write_text('Material claim CLM-EV-00001.', encoding='utf-8')
    (delivery / 'top_candidate_dd_review_pack.md').write_text('', encoding='utf-8')
    result = validate_final_delivery_claims(
        tmp_path,
        [{'claim_id': 'CLM-EV-00001', 'delivery_scope': 'external_final', 'certification_status': 'Needs Human Review'}],
        [{'claim_id': 'CLM-EV-00001'}],
    )
    assert not result['allowed']
    assert any('not allowed' in b for b in result['blockers'])
