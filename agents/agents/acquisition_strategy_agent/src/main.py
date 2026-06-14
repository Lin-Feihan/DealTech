from dealtech_certification.engine import run_agent_case, format_cli_result


def main() -> int:
    result = run_agent_case('acquisition-strategy', case='case_001_acquisition_strategy', view='buyer_side')
    print(format_cli_result(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
