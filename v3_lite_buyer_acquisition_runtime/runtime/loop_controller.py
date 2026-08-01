from __future__ import annotations

import json
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v3_lite_buyer_acquisition_runtime.runtime.artifact_store import write_json_artifact
from v3_lite_buyer_acquisition_runtime.runtime.case_seed_loader import load_case_seed
from v3_lite_buyer_acquisition_runtime.runtime.mandate_intake import load_mandate
from v3_lite_buyer_acquisition_runtime.runtime.openclaw_bridge import write_repair_request, write_research_request
from v3_lite_buyer_acquisition_runtime.runtime.research_planning import build_research_plan
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite import run_pipeline as run_m1_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m2_deep_research import run_m2_deep_research_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m3 import run_m3_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m4 import run_m4_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m5 import run_m5_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m5_1 import run_m5_1_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m6 import run_m6_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m7 import run_m7_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_m7_render import run_m7_render_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.run_v3_lite_step6a_audit_package import run_step6a_audit_package_pipeline
from v3_lite_buyer_acquisition_runtime.runtime.source_discovery import build_source_discovery_plan


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
RUN_STATE_FILENAME = "run_state.json"
FINAL_STATUSES = {
    "awaiting_external_research",
    "report_generated",
    "blocked_by_missing_evidence",
    "human_review_required",
    "failed",
}


class AgentRunError(RuntimeError):
    pass


class LoopController:
    def __init__(self, run_dir: Path, max_repair_iterations: int = 2) -> None:
        self.run_dir = run_dir
        self.max_repair_iterations = max_repair_iterations

    def start(self, case_path: Path) -> dict[str, Any]:
        if self.state_path.exists():
            state = self._load_state()
            if state["status"] == "awaiting_external_research":
                return state
        self.run_dir.mkdir(parents=True, exist_ok=True)
        try:
            state = self._new_state(case_id="")
            self._save_state(state)
            mandate, research_plan, case_seed = self._prepare_case(case_path, state)
            source_discovery_plan = build_source_discovery_plan(case_seed, research_plan)
            write_json_artifact(self.run_dir, "source_discovery_plan.json", source_discovery_plan)
            self._mark_completed(state, "M2_source_discovery_plan")

            write_research_request(
                mandate=mandate,
                research_plan=research_plan,
                case_seed=case_seed,
                source_discovery_plan=source_discovery_plan,
                output_dir=self.run_dir,
            )
            return self._await_external_research(
                state,
                current_stage="M2_external_research",
                next_action="Run external research from research_request.json, save deep_research_response.json, then resume.",
            )
        except Exception as exc:  # noqa: BLE001 - controller fail-closed boundary
            return self._fail(exc)

    def resume(self, research_response_path: Path) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._fail(AgentRunError(f"run_state.json not found in {self.run_dir}"))
        state = self._load_state()
        if state["status"] != "awaiting_external_research":
            return state
        try:
            self._copy_research_response(research_response_path)
            return self._run_after_external_research(state)
        except Exception as exc:  # noqa: BLE001 - controller fail-closed boundary
            return self._fail(exc)

    @property
    def state_path(self) -> Path:
        return self.run_dir / RUN_STATE_FILENAME

    def _prepare_case(self, case_path: Path, state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        payload = self._load_json(case_path)
        if "mandate" in payload:
            mandate = payload["mandate"]
            case_seed = payload.get("case_seed") or self._case_seed_for_case_id(mandate["case_id"])
            mandate_path = write_json_artifact(self.run_dir, "mandate.json", mandate)
            write_json_artifact(self.run_dir, "case_seed.json", case_seed)
            research_plan = build_research_plan(load_mandate(mandate_path))
            write_json_artifact(self.run_dir, "research_plan.json", research_plan)
        else:
            mandate_path = case_path
            artifacts = run_m1_pipeline(mandate_path, self.run_dir)
            mandate = self._load_json(artifacts["mandate"])
            research_plan = self._load_json(artifacts["research_plan"])
            case_seed = self._case_seed_for_case_id(mandate["case_id"])
            write_json_artifact(self.run_dir, "case_seed.json", case_seed)

        state["case_id"] = mandate["case_id"]
        state["current_stage"] = "M1_mandate_to_research_plan"
        self._mark_completed(state, "M1_mandate_to_research_plan")
        self._save_state(state)
        return mandate, research_plan, case_seed

    def _run_after_external_research(self, state: dict[str, Any]) -> dict[str, Any]:
        self._run_m2_replay(state)
        self._run_m3_to_m5(state)
        certification = self._load_json(self.run_dir / "certification_result.json")
        overall = certification["overall_certification_status"]
        if overall == "failed":
            return self._finish(state, "failed", "M5_loop_certification", "Certification failed closed.")
        if overall == "human_review_required":
            return self._finish(state, "human_review_required", "M5_loop_certification", "Human review is required before report generation.")
        if overall == "repair_required":
            return self._handle_repair_required(state)
        return self._run_m6_to_report(state)

    def _run_m2_replay(self, state: dict[str, Any]) -> None:
        state["current_stage"] = "M2_external_research_ingestion"
        self._save_state(state)
        kwargs: dict[str, Path | str | None] = {
            "mandate_path": self.run_dir / "mandate.json",
            "research_plan_path": self.run_dir / "research_plan.json",
            "case_seed_path": self.run_dir / "case_seed.json",
            "source_discovery_plan_path": self.run_dir / "source_discovery_plan.json",
            "output_dir": self.run_dir,
            "mode": "replay_deep_research_response",
            "replay_response_path": self.run_dir / "deep_research_response.json",
        }
        targeted_plan_path = self.run_dir / "targeted_source_discovery_plan.json"
        repair_plan_path = self.run_dir / "repair_plan.json"
        if targeted_plan_path.exists():
            kwargs["targeted_source_discovery_plan_path"] = targeted_plan_path
        if repair_plan_path.exists():
            kwargs["repair_plan_path"] = repair_plan_path
        run_m2_deep_research_pipeline(**kwargs)  # type: ignore[arg-type]
        self._mark_completed(state, "M2_external_research_ingestion")

    def _run_m3_to_m5(self, state: dict[str, Any]) -> None:
        state["current_stage"] = "M3_evidence_repository"
        self._save_state(state)
        run_m3_pipeline(self.run_dir / "raw_evidence.json", self.run_dir / "retrieved_sources_manifest.json", self.run_dir)
        self._mark_completed(state, "M3_evidence_repository")

        state["current_stage"] = "M4_claim_evidence_graph"
        self._save_state(state)
        run_m4_pipeline(self.run_dir / "evidence_repository.json", self.run_dir)
        self._mark_completed(state, "M4_claim_evidence_graph")

        state["current_stage"] = "M5_loop_certification"
        self._save_state(state)
        run_m5_pipeline(self.run_dir / "claim_evidence_graph.json", self.run_dir / "evidence_repository.json", self.run_dir)
        self._mark_completed(state, "M5_loop_certification")
        self._save_state(state)

    def _handle_repair_required(self, state: dict[str, Any]) -> dict[str, Any]:
        if state["iteration"] >= state["max_repair_iterations"]:
            return self._finish(
                state,
                "blocked_by_missing_evidence",
                "M5_loop_certification",
                "Maximum repair iterations reached with unresolved evidence or numeric gaps.",
            )
        state["current_stage"] = "M5_1_repair_loop"
        self._save_state(state)
        run_m5_1_pipeline(
            self.run_dir / "certification_result.json",
            self.run_dir / "research_gaps.json",
            self.run_dir / "repair_plan.json",
            self.run_dir,
        )
        self._mark_completed(state, "M5_1_repair_loop")
        state["iteration"] += 1

        write_repair_request(
            mandate=self._load_json(self.run_dir / "mandate.json"),
            research_plan=self._load_json(self.run_dir / "research_plan.json"),
            case_seed=self._load_json(self.run_dir / "case_seed.json"),
            source_discovery_plan=self._load_json(self.run_dir / "source_discovery_plan.json"),
            targeted_source_discovery_plan=self._load_json(self.run_dir / "targeted_source_discovery_plan.json"),
            repair_plan=self._load_json(self.run_dir / "repair_plan.json"),
            output_dir=self.run_dir,
            iteration=state["iteration"],
        )
        return self._await_external_research(
            state,
            current_stage="M5_repair_external_research",
            next_action="Run supplemental external research from repair_request.json, save deep_research_response.json, then resume.",
        )

    def _run_m6_to_report(self, state: dict[str, Any]) -> dict[str, Any]:
        state["current_stage"] = "M6_evidence_bounded_deal_analysis"
        self._save_state(state)
        run_m6_pipeline(
            self.run_dir / "certification_result.json",
            self.run_dir / "claim_evidence_graph.json",
            self.run_dir / "evidence_repository.json",
            self.run_dir / "research_gaps.json",
            self.run_dir / "repair_plan.json",
            self.run_dir,
        )
        self._mark_completed(state, "M6_evidence_bounded_deal_analysis")

        state["current_stage"] = "M7_report_rendering_gate"
        self._save_state(state)
        run_m7_pipeline(self.run_dir / "analysis_package.json", self.run_dir / "certification_result.json", self.run_dir / "repair_plan.json", self.run_dir)
        self._mark_completed(state, "M7_report_rendering_gate")

        state["current_stage"] = "Step6A_audit_package"
        self._save_state(state)
        run_step6a_audit_package_pipeline(
            self.run_dir / "report_manifest.json",
            self.run_dir / "analysis_package.json",
            self.run_dir / "certification_result.json",
            self.run_dir / "claim_evidence_graph.json",
            self.run_dir / "evidence_repository.json",
            self.run_dir,
        )
        self._mark_completed(state, "Step6A_audit_package")

        state["current_stage"] = "M7_1_report_render"
        self._save_state(state)
        render_result = run_m7_render_pipeline(
            self.run_dir / "report_manifest.json",
            self.run_dir / "analysis_package.json",
            self.run_dir / "certification_result.json",
            self.run_dir,
            audit_package_path=self.run_dir / "audit_package.json",
        )
        self._mark_completed(state, "M7_1_report_render")
        if render_result["final_report_generated"]:
            return self._finish(state, "report_generated", "M7_1_report_render", "final_report.md generated.")
        blocked_reasons = render_result.get("blocked_reasons", [])
        return self._finish_render_block(state, blocked_reasons)

    def _finish_render_block(self, state: dict[str, Any], blocked_reasons: list[dict[str, Any]]) -> dict[str, Any]:
        gates = {reason.get("gate") for reason in blocked_reasons}
        reason_text = "; ".join(str(reason.get("reason")) for reason in blocked_reasons if reason.get("reason"))
        if gates.intersection({"human_review_gate", "analysis_gate", "analysis_readiness_gate"}):
            return self._finish(
                state,
                "human_review_required",
                "M7_1_report_render",
                f"Report rendering is blocked pending human/analysis review: {reason_text}",
            )
        if gates.intersection({"repair_gate", "repair_plan_gate", "numeric_verification_gate", "claim_certification_gate", "blocked_analysis_gate"}):
            return self._finish(
                state,
                "blocked_by_missing_evidence",
                "M7_1_report_render",
                f"Report rendering is blocked by unresolved evidence, repair, or numeric gates: {reason_text}",
            )
        return self._finish(state, "failed", "M7_1_report_render", f"Report rendering failed closed: {reason_text or 'unknown gate'}")

    def _case_seed_for_case_id(self, case_id: str) -> dict[str, Any]:
        for path in sorted((RUNTIME_ROOT / "case_seeds").glob("*.json")):
            case_seed = load_case_seed(path)
            if case_seed["case_id"] == case_id:
                return case_seed
        raise AgentRunError(f"No case seed found for case_id: {case_id}")

    def _await_external_research(self, state: dict[str, Any], *, current_stage: str, next_action: str) -> dict[str, Any]:
        state["status"] = "awaiting_external_research"
        state["current_stage"] = current_stage
        state["next_action"] = next_action
        state["last_error"] = None
        self._save_state(state)
        self._log(next_action)
        return state

    def _finish(self, state: dict[str, Any], status: str, current_stage: str, next_action: str) -> dict[str, Any]:
        if status not in FINAL_STATUSES:
            raise AgentRunError(f"Invalid final status: {status}")
        state["status"] = status
        state["current_stage"] = current_stage
        state["next_action"] = next_action
        state["last_error"] = None if status != "failed" else state.get("last_error")
        self._save_state(state)
        self._log(f"{status}: {next_action}")
        return state

    def _fail(self, exc: Exception) -> dict[str, Any]:
        state = self._load_state() if self.state_path.exists() else self._new_state(case_id="")
        state["status"] = "failed"
        state["next_action"] = "Inspect run_state.json and run.log, then repair the failed input or artifact."
        state["last_error"] = str(exc)
        self._save_state(state)
        self._log(traceback.format_exc())
        return state

    def _new_state(self, case_id: str) -> dict[str, Any]:
        return {
            "case_id": case_id,
            "status": "awaiting_external_research",
            "current_stage": "initialized",
            "completed_stages": [],
            "iteration": 0,
            "max_repair_iterations": self.max_repair_iterations,
            "next_action": "start",
            "last_error": None,
            "updated_at": _now_utc_iso(),
        }

    def _mark_completed(self, state: dict[str, Any], stage: str) -> None:
        if stage not in state["completed_stages"]:
            state["completed_stages"].append(stage)
        state["updated_at"] = _now_utc_iso()
        self._save_state(state)

    def _save_state(self, state: dict[str, Any]) -> None:
        state["updated_at"] = _now_utc_iso()
        write_json_artifact(self.run_dir, RUN_STATE_FILENAME, state)

    def _load_state(self) -> dict[str, Any]:
        state = self._load_json(self.state_path)
        if state.get("status") not in FINAL_STATUSES:
            raise AgentRunError(f"run_state.status is not allowed: {state.get('status')}")
        return state

    def _copy_research_response(self, research_response_path: Path) -> None:
        target = self.run_dir / "deep_research_response.json"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        if research_response_path.resolve() != target.resolve():
            shutil.copyfile(research_response_path, target)

    def _load_json(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise AgentRunError(f"JSON artifact must be an object: {path}")
        return payload

    def _log(self, message: str) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with (self.run_dir / "run.log").open("a", encoding="utf-8") as handle:
            handle.write(f"[{_now_utc_iso()}] {message}\n")


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
