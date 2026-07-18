from __future__ import annotations

import argparse
from pathlib import Path

from .live_research_models import A5Outcome, ProviderError, ProviderMode
from .models import TerminalStatus
from .runtime import run_case
from .storage import load_case


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the buyer-side acquisition loop or the controlled A5 research-provider pilot."
    )
    parser.add_argument("--case", required=False, type=Path, help="Path to case.yaml")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory; defaults to run_output beside case.yaml",
    )
    parser.add_argument(
        "--human-review-response",
        type=Path,
        default=None,
        help="Resume an existing paused case with a structured HumanReviewResponse JSON file.",
    )
    parser.add_argument(
        "--provider",
        choices=[item.value for item in ProviderMode],
        default=None,
        help="Explicit provider mode. Live research is never selected implicitly by fallback.",
    )
    parser.add_argument(
        "--module",
        choices=["A1", "A2", "A3", "A4", "A5", "A6", "A7", "B1", "B2", "B3", "B4", "B5", "C1", "C2", "C3", "C4", "C5", "BLOCK_A", "BLOCK_B", "BLOCK_C", "FULL_PIPELINE"],
        default=None,
        help="Controlled research scope; Milestone 6 uses BLOCK_A and Milestone 7 uses BLOCK_B.",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate provider, SDK, environment, case, attachments and output without a paid request.",
    )
    parser.add_argument(
        "--enable-live",
        action="store_true",
        help="Explicitly permit a paid live request when every other live precondition is satisfied.",
    )
    parser.add_argument(
        "--check-case",
        action="store_true",
        help="Validate a full-pipeline case and report READY, READY_WITH_WARNINGS or NOT_READY without a paid request.",
    )
    parser.add_argument(
        "--resume-run",
        type=Path,
        default=None,
        help="Validate a prior run manifest and continue from the next incomplete stage.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.resume_run is not None:
        from .full_pipeline import resume_full_pipeline

        try:
            result = resume_full_pipeline(args.resume_run, enable_live=args.enable_live)
        except ProviderError as exc:
            print(f"Run resume failed: {exc}")
            return 4
        summary = result["summary"]
        print("Full acquisition pipeline resume completed")
        print(f"Gate A / B / C: {summary['gate_a']} / {summary['gate_b']} / {summary['gate_c']}")
        print(f"Decision State: {summary['decision_state']}")
        print(f"Delivery outcome: {summary['delivery_outcome']}")
        print(f"Outputs: {result['output_dir']}")
        return 0
    if args.case is None:
        print("A --case path is required unless --resume-run is used.")
        return 4
    case_data = load_case(args.case.resolve())
    full_pipeline = case_data.get("schema_version") == "release-candidate-1"
    if args.check_case:
        if not full_pipeline:
            print("Case status: NOT_READY")
            print("Case issue: --check-case requires a release-candidate-1 case")
            print("Paid request made: False")
            return 4
        from .full_pipeline import check_full_pipeline_case

        check = check_full_pipeline_case(args.case)
        print(f"Case status: {check['status']}")
        print("Paid request made: False")
        for warning in check["warnings"]:
            print(f"Case warning: {warning}")
        for issue in check["issues"]:
            print(f"Case issue: {issue}")
        return 0 if check["ready"] else 4
    configured_provider = case_data.get("provider", {}).get("mode")
    selected_provider = args.provider or configured_provider
    milestone_5 = case_data.get("schema_version") == "milestone-5-a5"
    milestone_6 = case_data.get("schema_version") == "milestone-6-block-a"
    milestone_7 = case_data.get("schema_version") == "milestone-7-block-b"
    milestone_8 = case_data.get("schema_version") == "milestone-8-block-c"
    if full_pipeline:
        if args.module not in {None, "FULL_PIPELINE"}:
            print("Provider configuration failed: release-candidate-1 cases require --module FULL_PIPELINE")
            return 4
        if args.check_config:
            from .full_pipeline import check_full_pipeline_configuration

            check = check_full_pipeline_configuration(args.case, enable_live=args.enable_live)
            print(f"Configuration ready: {check['ready']}")
            print(f"Case status: {check['status']}")
            print(f"Paid request made: {check['paid_request_made']}")
            for issue in [*check["warnings"], *check["issues"]]:
                print(f"Configuration issue: {issue}")
            return 0 if check["ready"] else 4
        from .full_pipeline import run_full_pipeline

        try:
            result = run_full_pipeline(args.case, args.output, enable_live=args.enable_live)
        except ProviderError as exc:
            print(f"Full pipeline failed: {exc}")
            return 4
        summary = result["summary"]
        print("Full buyer-side acquisition pipeline finished")
        print(f"Modules A / B / C: {summary['module_counts']['block_a']} / {summary['module_counts']['block_b']} / {summary['module_counts']['block_c']}")
        print(f"Gate A / B / C: {summary['gate_a']} / {summary['gate_b']} / {summary['gate_c']}")
        print(f"Decision State: {summary['decision_state']}")
        print(f"Delivery outcome: {summary['delivery_outcome']}")
        print(f"Outputs: {result['output_dir']}")
        return 0
    if args.check_config:
        if milestone_8:
            from .block_c_runtime import check_block_c_configuration

            check = check_block_c_configuration(
                args.case,
                provider=selected_provider,
                module=args.module or "BLOCK_C",
                output_dir=args.output,
                enable_live=args.enable_live,
            )
            print(f"Configuration ready: {check['ready']}")
            print(f"Provider: {check['provider_mode']}")
            print(f"Module: {check['module_selection']}")
            print(f"Live execution enabled: {check['live_execution_enabled']}")
            print(f"Paid request made: {check['paid_request_made']}")
            for issue in check["issues"]:
                print(f"Configuration issue: {issue}")
            return 0 if check["ready"] else 4
        if milestone_7:
            from .block_b_runtime import check_block_b_configuration

            check = check_block_b_configuration(
                args.case,
                provider=selected_provider,
                module=args.module or "BLOCK_B",
                output_dir=args.output,
                enable_live=args.enable_live,
            )
            print(f"Configuration ready: {check['ready']}")
            print(f"Provider: {check['provider_mode']}")
            print(f"Module: {check['module_selection']}")
            print(f"Live execution enabled: {check['live_execution_enabled']}")
            print(f"Paid request made: {check['paid_request_made']}")
            for issue in check["issues"]:
                print(f"Configuration issue: {issue}")
            return 0 if check["ready"] else 4
        if milestone_6:
            from .block_a_runtime import check_block_a_configuration

            check = check_block_a_configuration(
                args.case,
                provider=selected_provider,
                module=args.module or "BLOCK_A",
                output_dir=args.output,
                enable_live=args.enable_live,
            )
            print(f"Configuration ready: {check['ready']}")
            print(f"Provider: {check['provider_mode']}")
            print(f"Module: {check['module_selection']}")
            print(f"Live execution enabled: {check['live_execution_enabled']}")
            print(f"Paid request made: {check['paid_request_made']}")
            for issue in check["issues"]:
                print(f"Configuration issue: {issue}")
            return 0 if check["ready"] else 4
        from .a5_research_runtime import check_a5_configuration

        check = check_a5_configuration(
            args.case,
            provider=selected_provider,
            module=args.module or case_data.get("module_id"),
            output_dir=args.output,
        )
        print(f"Configuration ready: {check['ready']}")
        print(f"Provider: {check['provider_mode']}")
        print(f"Module: {check['module_id']}")
        print(f"Paid request made: {check['paid_request_made']}")
        for issue in check["issues"]:
            print(f"Configuration issue: {issue}")
        return 0 if check["ready"] else 4
    if milestone_8:
        from .block_c_runtime import run_block_c_case

        try:
            result = run_block_c_case(
                args.case,
                args.output,
                provider=selected_provider,
                module=args.module or "BLOCK_C",
                enable_live=args.enable_live,
            )
        except ProviderError as exc:
            print(f"Provider configuration failed: {exc}")
            return 4
        print("Complete Block C risk, diligence and decision workflow finished")
        print(f"Provider: {result.provider_mode.value}")
        print("Modules: C1-C5")
        print(f"Module executions: {result.module_executions}")
        print(f"Gate C: {result.gate_c_result['status']}")
        print(f"Decision State: {result.decision_state['state']}")
        print(f"Delivery outcome: {result.delivery_outcome}")
        print(f"Iterations: {result.iterations}")
        print(f"Outputs: {result.output_dir}")
        return 1 if result.outcome.value == "FAILED_TECHNICAL" else 0
    if milestone_7:
        from .block_b_runtime import run_block_b_case

        try:
            result = run_block_b_case(
                args.case,
                args.output,
                provider=selected_provider,
                module=args.module or "BLOCK_B",
                enable_live=args.enable_live,
            )
        except ProviderError as exc:
            print(f"Provider configuration failed: {exc}")
            return 4
        print("Complete Block B deep-research and financial-analysis workflow finished")
        print(f"Provider: {result.provider_mode.value}")
        print("Modules: B1-B5")
        print(f"Module executions: {result.module_executions}")
        print(f"Gate B: {result.gate_b_result['status']}")
        print(f"Iterations: {result.iterations}")
        print(f"Block C executed: {result.terminal_state['block_c_executed']}")
        print(f"Outputs: {result.output_dir}")
        return 1 if result.outcome.value == "FAILED_TECHNICAL" else 0
    if milestone_6:
        from .block_a_runtime import run_block_a_case

        try:
            result = run_block_a_case(
                args.case,
                args.output,
                provider=selected_provider,
                module=args.module or "BLOCK_A",
                enable_live=args.enable_live,
            )
        except ProviderError as exc:
            print(f"Provider configuration failed: {exc}")
            return 4
        print("Complete Block A research-provider workflow finished")
        print(f"Provider: {result.provider_mode.value}")
        print(f"Modules: 7/7")
        print(f"Module executions: {result.module_executions}")
        print(f"Gate A: {result.gate_a_result['status']}")
        print(f"Iterations: {result.iterations}")
        print(f"Outputs: {result.output_dir}")
        return 1 if result.outcome.value == "FAILED_TECHNICAL" else 0
    if milestone_5 or selected_provider in {ProviderMode.RECORDED.value, ProviderMode.OPENAI_LIVE.value}:
        from .a5_research_runtime import run_a5_research_case

        try:
            result = run_a5_research_case(
                args.case,
                args.output,
                provider=selected_provider,
                module=args.module or case_data.get("module_id"),
            )
        except ProviderError as exc:
            print(f"Provider configuration failed: {exc}")
            return 4
        print("Controlled A5 research-provider pilot finished")
        print(f"Provider: {result.provider_mode.value}")
        print(f"Module: A5 - Target Capability & Business Quality")
        print(f"Outcome: {result.outcome.value}")
        print(f"Attempts: {result.attempts}")
        print(f"Gate A evaluated: {result.gate_dependency_result.get('gate_a_evaluated', False)}")
        print(f"Outputs: {result.output_dir}")
        return 1 if result.outcome == A5Outcome.FAILED_TECHNICAL else 0
    if args.module is not None or args.provider not in {None, ProviderMode.DETERMINISTIC.value}:
        print("Provider configuration failed: deterministic mode remains on the existing runtime and does not accept an A5 live-module override.")
        return 4
    if args.human_review_response is not None:
        from .review_runtime import resume_human_review_case

        resumed = resume_human_review_case(
            case_path=args.case,
            response_path=args.human_review_response,
            output_dir=args.output,
        )
        validation = resumed["validation"]
        print(f"Human Review response validation: {validation.status.value}")
        print(f"Resumed: {resumed['resume_summary']['resumed']}")
        print(f"Terminal before: {resumed['resume_summary']['terminal_state_before']}")
        print(f"Terminal after: {resumed['resume_summary']['terminal_state_after']}")
        print(f"Outputs: {resumed['output_dir']}")
        return 0 if resumed["resume_summary"]["resumed"] else 3
    result = run_case(args.case, args.output)
    if result.get("run_summary", {}).get("schema_version") in {"milestone-3", "milestone-4"}:
        summary = result["run_summary"]
        print("Deterministic buyer-side acquisition business layer finished")
        print(f"Gate A: {getattr(summary.get('gate_a'), 'value', summary.get('gate_a', 'not reached'))}")
        print(f"Gate B: {getattr(summary.get('gate_b'), 'value', summary.get('gate_b', 'not reached'))}")
        print(f"Gate C: {getattr(summary.get('gate_c'), 'value', summary.get('gate_c', 'not reached'))}")
        print(f"Decision state: {getattr(summary.get('decision_state'), 'value', summary.get('decision_state', 'not reached'))}")
        print(f"Outputs: {result['output_dir']}")
        accepted_statuses = {
            "COMPLETED_ACQUISITION_BUSINESS_LAYER",
            "COMPLETED_PROCEED",
            "COMPLETED_PROCEED_WITH_CONDITIONS",
            "COMPLETED_RENEGOTIATE",
            "COMPLETED_PAUSE",
            "COMPLETED_NO_GO",
        }
        status_value = getattr(summary.get("status"), "value", summary.get("status"))
        return 0 if status_value in accepted_statuses else 2
    memory = result["memory"]
    gap = result["research_gap"]
    terminal = result["terminal_state"]
    print("Deterministic Gate A loop finished with an explicit terminal state")
    for gate in memory.gate_results:
        print(f"Iteration {gate.iteration}: {gate.status.value} ({gate.pce_status.value})")
    print(f"Gap: {gap.gap_type.value} -> {gap.return_target}")
    print(f"Terminal: {terminal.status.value} - {terminal.stopping_reason}")
    print(f"Outputs: {result['output_dir']}")
    return 1 if terminal.status == TerminalStatus.FAILED_TECHNICAL else 0


if __name__ == "__main__":
    raise SystemExit(main())
