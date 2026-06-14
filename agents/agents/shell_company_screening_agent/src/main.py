from dealtech_certification.engine import run_agent_case, format_cli_result


def main() -> int:
    result = run_agent_case('shell-company-screening', case='case_001_tonton_shell_company_screening')
    print(format_cli_result(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
