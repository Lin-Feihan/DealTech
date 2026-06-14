from dealtech_certification.engine import run_agent_case

AGENT_SLUG = 'shell-company-screening'

WORKFLOW_STEPS = [
    'Input mandate',
    'Candidate universe loading',
    'Hard filter screening',
    'DD evidence review',
    'Risk matrix construction',
    'Financial calculation check',
    'ER/BRB scoring',
    'PCE audit',
    'Final certification output',
]


def describe_workflow():
    return {'agent': AGENT_SLUG, 'workflow_steps': WORKFLOW_STEPS}


def run_workflow(case=None, view=None):
    result = run_agent_case(AGENT_SLUG, case=case, view=view).to_dict()
    result['workflow_steps_executed'] = WORKFLOW_STEPS
    return result
