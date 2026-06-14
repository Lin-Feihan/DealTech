from dealtech_certification.engine import run_agent_case, format_cli_result

AGENT_SLUG = 'spac-target-acquisition'


def main():
    result = run_agent_case(AGENT_SLUG, case='case_001_soren_spac_target_acquisition')
    print(format_cli_result(result))
    return result


if __name__ == '__main__':
    main()
