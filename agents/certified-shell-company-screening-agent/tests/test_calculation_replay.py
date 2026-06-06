from pathlib import Path
from shell_company_screening_agent.trace.calculation_replay import replay_trace_calculations

def test_calculation_replay_runs():
    result = replay_trace_calculations(Path('examples/tuntun_hk'))
    assert 'failure_count' in result
