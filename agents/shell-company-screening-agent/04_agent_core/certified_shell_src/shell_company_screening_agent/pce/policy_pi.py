from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_POLICY_RELATIVE_PATH = Path("configs/pce/policy_pi.yaml")


@dataclass(frozen=True)
class PolicyPi:
    """Loaded Policy π configuration.

    `configs/pce/policy_pi.yaml` is the single entrypoint for PCE policy. Rule files
    can still live under `configs/pce/rules/`, but certifiers should read this
    object rather than hard-code policy paths or treat the policy path as metadata.
    """

    path: Path
    raw: dict[str, Any]

    @classmethod
    def load(cls, repo_root: Path, policy_path: Path | None = None) -> "PolicyPi":
        path = policy_path or repo_root / DEFAULT_POLICY_RELATIVE_PATH
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        policy = data.get("policy_pi", data)
        if not isinstance(policy, dict):
            raise ValueError(f"Policy π file must contain a mapping: {path}")
        return cls(path=path, raw=policy)

    @property
    def required_trace_tables(self) -> list[str]:
        return list(self.raw.get("required_trace_tables") or [])

    @property
    def canonical_output_states(self) -> list[str]:
        return list(self.raw.get("canonical_output_states") or [])

    @property
    def final_delivery_ready_statuses(self) -> set[str]:
        scope = self.raw.get("delivery_scope", {}).get("external_final", {})
        return set(scope.get("allow_statuses") or [])

    @property
    def internal_trace_ready_statuses(self) -> set[str]:
        scope = self.raw.get("delivery_scope", {}).get("internal_trace", {})
        return set(scope.get("allow_statuses") or [])

    @property
    def blocking_statuses(self) -> set[str]:
        scope = self.raw.get("delivery_scope", {}).get("external_final", {})
        return set(scope.get("block_statuses") or [])

    @property
    def delivery_gate_rule(self) -> dict[str, Any]:
        return dict(self.raw.get("delivery_gate_rule") or {})

    @property
    def material_claim_reference_pattern(self) -> str:
        return str(self.delivery_gate_rule.get("material_claim_reference_pattern") or r"CLM-[A-Z]+-[0-9]{5}")

    @property
    def required_delivery_files(self) -> list[str]:
        return list(self.delivery_gate_rule.get("required_delivery_files") or [])

    @property
    def allowed_external_statuses(self) -> set[str]:
        values = self.delivery_gate_rule.get("allowed_external_statuses") or self.final_delivery_ready_statuses
        return set(values)

    @property
    def blocked_statuses(self) -> set[str]:
        values = self.delivery_gate_rule.get("blocked_statuses") or self.blocking_statuses
        return set(values)

    def validate(self) -> None:
        if not self.required_trace_tables:
            raise ValueError(f"Policy π must define required_trace_tables: {self.path}")
        if not self.canonical_output_states:
            raise ValueError(f"Policy π must define canonical_output_states: {self.path}")
        if not self.required_delivery_files:
            raise ValueError(f"Policy π must define delivery_gate_rule.required_delivery_files: {self.path}")
        if not self.allowed_external_statuses:
            raise ValueError(f"Policy π must define external-final allowed statuses: {self.path}")
        unknown = (self.allowed_external_statuses | self.blocked_statuses) - set(self.canonical_output_states)
        if unknown:
            raise ValueError(f"Policy π delivery gate references non-canonical statuses: {sorted(unknown)}")
