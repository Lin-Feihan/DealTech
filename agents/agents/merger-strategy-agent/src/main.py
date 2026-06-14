from dealtech_certification.engine import run_agent_case, format_cli_result

AGENT_SLUG = 'merger-strategy'


def main():
    result = run_agent_case(AGENT_SLUG)
    print(format_cli_result(result))
    return result


if __name__ == '__main__':
    main()
