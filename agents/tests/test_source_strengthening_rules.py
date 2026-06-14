import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPAC = ROOT / 'agents/spac-target-acquisition-agent/07_case_studies/case_001_soren_spac_target_acquisition'
ACQ = ROOT / 'agents/acquisition-strategy-agent/07_case_studies/case_001_acquisition_strategy'


def csv_rows(path: Path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def test_no_url_or_file_source_cannot_be_certified():
    for source_registry in [SPAC / 'source_registry.md', ACQ / 'buyer_side/source_registry.md', ACQ / 'target_side/source_registry.md']:
        for line in source_registry.read_text(encoding='utf-8').splitlines():
            if not line.startswith('|SRC-'):
                continue
            cells = [c.strip() for c in line.strip('|').split('|')]
            source_id, url_or_file, pce_eligible = cells[0], cells[3].lower(), cells[6].lower()
            missing_or_placeholder = (not url_or_file) or any(token in url_or_file for token in ['pending', 'tbd', 'unknown', 'placeholder'])
            if missing_or_placeholder:
                assert pce_eligible not in {'yes', 'true'}, (source_registry, source_id)


def test_spac_source_replayed_candidates_are_not_final_recommendations():
    rows = csv_rows(SPAC / 'supporting_files/candidate_universe.csv')
    replayed = [r for r in rows if r['source_replay_status'] == 'Source replay completed']
    assert len(replayed) >= 4
    for row in replayed:
        assert row['candidate_status'] == 'Retained for further review'
        assert 'not a final recommendation' in row['notes'].lower()
    final_output = (SPAC / 'final_output.md').read_text(encoding='utf-8').lower()
    assert 'partially source-replayed screening structure' in final_output
    assert 'retained for further review only' in final_output
    assert 'not final recommended spac targets' in final_output
    assert 'spac overall status remains needs human review' in final_output


def test_darwinai_financials_and_deal_value_remain_unknown_or_not_certified():
    buyer_text = (ACQ / 'buyer_side/supporting_files/target_profile.md').read_text(encoding='utf-8')
    transaction_text = (ACQ / 'buyer_side/supporting_files/transaction_context.md').read_text(encoding='utf-8')
    target_text = (ACQ / 'target_side/supporting_files/target_standalone_case.md').read_text(encoding='utf-8')
    for section in ['Target identity', 'Public business description', 'Unknown information', 'Claims generated from this file']:
        assert section in buyer_text
    for section in ['Transaction occurrence', 'Deal terms', 'Source quality', 'Certification boundary']:
        assert section in transaction_text
    assert 'revenue unknown' in buyer_text.lower()
    assert 'ebitda unknown' in buyer_text.lower()
    assert 'deal value unknown' in buyer_text.lower()
    assert 'valuation multiple unknown' in buyer_text.lower()
    assert 'unknown' in target_text.lower()
    for side, audit_name in [('buyer_side', 'buyer_side_PCE_audit.csv'), ('target_side', 'target_side_PCE_audit.csv')]:
        rows = csv_rows(ACQ / side / 'supporting_files' / audit_name)
        blocked = [r for r in rows if any(term in r['claim_text'].lower() for term in ['valuation', 'pricing', 'deal value', 'fairness', 'go-no-go', 'accept', 'reject', 'negotiate', 'synergy', 'eps'])]
        assert blocked
        assert all(r['PCE_status'] != 'Certified' for r in blocked)


def test_strategic_rationale_distinguishes_fact_from_inference():
    rows = csv_rows(ACQ / 'buyer_side/supporting_files/strategic_rationale_table.csv')
    labels = {r['fact_or_inference'] for r in rows}
    assert 'source-backed fact' in labels
    assert 'secondary source-backed fact' in labels
    assert 'evidence-supported inference' in labels
    inference_rows = [r for r in rows if r['fact_or_inference'] == 'evidence-supported inference']
    assert inference_rows
    assert all(r['human_review_required'] == 'Yes' for r in inference_rows)
    txn_rows = [r for r in rows if 'transaction' in r['rationale_category'].lower()]
    assert txn_rows
    assert all(r['source_id'] == 'SRC-ACQ-B04' for r in txn_rows)


def test_certification_results_stay_needs_human_review_with_blocked_claims_visible():
    for rel in ['spac-target-acquisition-agent/07_case_studies/case_001_soren_spac_target_acquisition/certification_result.json', 'acquisition-strategy-agent/07_case_studies/case_001_acquisition_strategy/buyer_side/certification_result.json', 'acquisition-strategy-agent/07_case_studies/case_001_acquisition_strategy/target_side/certification_result.json']:
        cert = json.loads((ROOT / 'agents' / rel).read_text(encoding='utf-8'))
        assert cert['overall_status'] == 'Needs Human Review'
        assert any(r['PCE_status'] in {'Needs Human Review', 'Not Certified'} for r in cert['claim_results'])
        assert all(r['reason'] != 'All claim-level PCE checks passed.' for r in cert['claim_results'])

    final_output = (ACQ / 'buyer_side/final_output.md').read_text(encoding='utf-8')
    assert 'target_profile.md' in final_output
    assert 'transaction_context.md' in final_output

    buyer_claims = csv_rows(ACQ / 'buyer_side/claim_to_evidence_map.csv')
    txn_occurrence = [r for r in buyer_claims if r['claim_id'] == 'CLM-ACQ-B-TXN-001']
    assert txn_occurrence
    assert txn_occurrence[0]['certification_status'] in {'Certified with Caveat', 'Needs Human Review'}
