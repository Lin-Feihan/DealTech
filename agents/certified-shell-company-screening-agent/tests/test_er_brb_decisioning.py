from shell_company_screening_agent.decisioning.er_brb.hard_filter_decisioning import hard_filter_decision
from shell_company_screening_agent.decisioning.er_brb.dd_decisioning import dd_decision


def test_hard_filter_outputs_review_fields_for_missing_metadata_evidence():
    result = hard_filter_decision(0.8, 0.7, missing_evidence=True, metadata_only_evidence=True)
    assert result['decision'] == 'DD escalation'
    assert result['human_review_required'] is True
    assert 'missing evidence' in result['rationale']


def test_dd_outputs_required_contract_for_conflicting_evidence():
    result = dd_decision(0.2, 0.8, conflicting_evidence=True)
    assert set(result) == {'risk_level', 'recommendation_support', 'ranking_support', 'confidence', 'caveat', 'human_review_required'}
    assert result['risk_level'] == 'unresolved'
    assert result['human_review_required'] is True
