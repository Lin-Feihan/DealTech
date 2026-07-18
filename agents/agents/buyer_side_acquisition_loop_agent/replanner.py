from __future__ import annotations

from .models import QuestionStatus, ResearchGap, ResearchQuestion


def replan_for_gap(gap: ResearchGap, iteration: int) -> ResearchQuestion:
    return ResearchQuestion(
        question_id=f"RQ-A-REPAIR-{iteration:02d}",
        owner_module=gap.return_target,
        question_text=(
            "What replayable fact demonstrates that the target capability can satisfy "
            "the buyer's stated strategic need?"
        ),
        purpose=(
            "Repair only the evidence gap connecting Target Capability & Business "
            "Quality to Strategic Fit."
        ),
        iteration=iteration,
        status=QuestionStatus.PLANNED,
    )
