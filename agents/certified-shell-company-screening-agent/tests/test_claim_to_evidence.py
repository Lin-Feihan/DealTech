from pathlib import Path
from shell_company_screening_agent.trace.claim_to_evidence import read_claim_map

def test_claim_map_not_empty():
    assert read_claim_map(Path('examples/tuntun_hk/trace/claim_to_evidence_map.csv'))
