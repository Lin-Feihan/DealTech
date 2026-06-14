from dealtech_certification.engine import run_agent_case, format_cli_result

AGENT_SLUG = 'shell-company-screening'


def main():
    result = run_agent_case(AGENT_SLUG, case='case_001_tonton_shell_company_screening')
    print(format_cli_result(result))
    return result


if __name__ == '__main__':
    main()
