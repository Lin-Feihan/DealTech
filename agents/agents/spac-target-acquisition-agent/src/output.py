from dealtech_certification.engine import run_agent_case

AGENT_SLUG = 'spac-target-acquisition'


def build_output(case=None, view=None):
    return run_agent_case(AGENT_SLUG, case=case, view=view).to_dict()
