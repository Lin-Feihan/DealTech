from __future__ import annotations

from pathlib import Path

from .policy_pi import PolicyPi


class PCECertifierAgent:
    """PCE certifier that reads Policy π as executable policy input."""

    def __init__(self, repo_root: Path, policy_path: Path | None = None) -> None:
        self.repo_root = repo_root
        self.policy = PolicyPi.load(repo_root, policy_path)
        self.policy.validate()

    @classmethod
    def for_example(cls, example_dir: Path, policy_path: Path | None = None) -> "PCECertifierAgent":
        repo_root = example_dir.resolve().parents[1]
        return cls(repo_root, policy_path)

    def certify(self, example_dir: Path) -> dict:
        from .certification_report import certify_example

        return certify_example(example_dir, policy=self.policy)
