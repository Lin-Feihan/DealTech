from dealtech_certification.engine import run_agent_case

AGENT_SLUG = 'spac-target-acquisition'

WORKFLOW_STEPS = [
    'Source registry loading',
    'Evidence table loading',
    'Imported artifact detection',
    'Apify connector status check',
    'ER/BRB evaluation',
    'PCE claim-level evaluation',
    'Final output generation',
]


def describe_workflow():
    return {'agent': AGENT_SLUG, 'workflow_steps': WORKFLOW_STEPS}


def run_workflow(case=None, view=None):
    result = run_agent_case(AGENT_SLUG, case=case, view=view).to_dict()
    result['workflow_steps_executed'] = WORKFLOW_STEPS
    result['apify_note'] = 'No authenticated Apify run was executed in this version.'
    result['imported_artifact_note'] = 'Imported artifact is not primary evidence by itself.'
    return result
