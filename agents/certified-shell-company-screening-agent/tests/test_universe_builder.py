from pathlib import Path

def test_universe_exists():
    assert Path('examples/tuntun_hk/trace/candidate_universe_table.csv').exists()
