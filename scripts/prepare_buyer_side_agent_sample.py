from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "agents" / "agents" / "buyer-side-acquisition-loop-agent" / "06_examples" / "recorded_full_pipeline_case"
RUN = CASE / "run_output"
SAMPLE = CASE / "sample_output"
FILES = (
    "final_acquisition_strategy_report.md",
    "run_summary.json",
    "gate_a_result.json",
    "gate_b_result.json",
    "gate_c_result.json",
    "decision_state.json",
    "final_delivery_verification.json",
    "cross_block_consistency_result.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    missing = [name for name in FILES if not (RUN / name).is_file()]
    if missing:
        raise SystemExit(f"Run the recorded FULL_PIPELINE first; missing: {missing}")
    SAMPLE.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copy2(RUN / name, SAMPLE / name)
    summary = json.loads((SAMPLE / "run_summary.json").read_text(encoding="utf-8"))
    manifest = {
        "schema_version": "release-candidate-1",
        "case_id": summary["case_id"],
        "run_id": summary["run_id"],
        "sample_scope": "Sanitized GitHub subset; full provider, evidence, calculation, loop and Human Review traces are intentionally excluded and are reproducible with the documented recorded demo command.",
        "unpublished_internal_references": ["stages/block_a/", "stages/block_b/", "stages/block_c/"],
        "artifacts": [
            {"path": name, "sha256": sha256(SAMPLE / name), "bytes": (SAMPLE / name).stat().st_size}
            for name in FILES
        ],
        "contains_local_absolute_paths": False,
        "contains_credentials": False,
    }
    (SAMPLE / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(SAMPLE.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
