"""VisualExperience collector — write-only (FR-043/044)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnc_agent.domain.run import ActionIteration, VisualExperience

if TYPE_CHECKING:
    from vnc_agent.storage.repositories import RunRepository


class ExperienceCollector:
    """
    Collects VisualExperience records for future self-evolution.
    MUST only write; no training, no assertion mutation, no replay rewrite (FR-044).
    """

    def __init__(self, repo: RunRepository | None = None) -> None:
        self.repo = repo
        self.written: list[VisualExperience] = []

    async def collect(
        self,
        *,
        run_id: str,
        step_id: str,
        iteration: ActionIteration,
        failure_type: str | None = None,
    ) -> VisualExperience:
        vr = iteration.verification_result
        if vr is None:
            outcome = "uncertain"
        elif vr.status == "passed":
            outcome = "success"
        elif vr.status == "failed":
            outcome = "failure"
        else:
            outcome = "uncertain"

        exp = VisualExperience(
            run_id=run_id,
            step_id=step_id,
            before_frame_id=iteration.before_frame_id,
            after_frame_id=iteration.after_frame_id,
            semantic_action=(
                iteration.semantic_action.model_dump(mode="json")
                if iteration.semantic_action
                else {}
            ),
            grounding_candidates=(
                [c.model_dump(mode="json") for c in iteration.grounding_result.candidates]
                if iteration.grounding_result
                else []
            ),
            selected_candidate=None,
            execution_result=(
                iteration.execution_result.model_dump(mode="json")
                if iteration.execution_result
                else {}
            ),
            verification_result=vr.model_dump(mode="json") if vr else {},
            outcome=outcome,  # type: ignore[arg-type]
            failure_type=failure_type,
        )
        self.written.append(exp)
        if self.repo is not None:
            await self.repo.save_experience(exp)
        return exp
