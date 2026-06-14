from dealtech_certification.engine import run_agent_case, format_cli_result

AGENT_SLUG = 'acquisition-strategy'


def main():
    result = run_agent_case(AGENT_SLUG, case='case_001_acquisition_strategy', view='buyer_side')
    print(format_cli_result(result))
    return result


if __name__ == '__main__':
    main()
