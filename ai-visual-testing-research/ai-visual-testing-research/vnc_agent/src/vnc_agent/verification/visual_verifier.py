"""Visual question verifier via PlannerProvider.describe_screen (FR-032)."""

from __future__ import annotations

from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.verification import VerificationCondition, VerificationStatus
from vnc_agent.models.provider import PlannerProvider, VisionUnderstandingRequest


async def verify_visual_question(
    condition: VerificationCondition,
    screen: StructuredScreen,
    planner: PlannerProvider,
) -> tuple[VerificationStatus, str]:
    resp = await planner.describe_screen(
        VisionUnderstandingRequest(
            mode="answer_question",
            # FR-049: model API must receive unmasked image
            image_ref=screen.path_for_model(),
            structured_screen_hint=screen.to_hint_dict(),
            question=condition.value,
        )
    )
    answer: VerificationStatus = resp.answer or "uncertain"
    return answer, resp.reason or ""
