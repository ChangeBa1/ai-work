"""Visual question verifier via PlannerProvider.describe_screen (FR-032).

Feature 008: the model call is routed through the shared
:class:`~vnc_agent.verification.answer_cache.CachedVisualAnswerer` so an
identical (frame content, question, model) evaluation on a dedup-proven
frame reuses the cached answer instead of re-issuing HTTP."""

from __future__ import annotations

from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.verification import VerificationCondition, VerificationStatus
from vnc_agent.models.provider import PlannerProvider
from vnc_agent.verification.answer_cache import CachedVisualAnswerer


async def verify_visual_question(
    condition: VerificationCondition,
    screen: StructuredScreen,
    planner: PlannerProvider,
    answerer: CachedVisualAnswerer | None = None,
) -> tuple[VerificationStatus, str]:
    # No answerer (legacy/bare callers) → uncached helper, behavior unchanged.
    resp = await (answerer or CachedVisualAnswerer()).answer(
        planner, screen, condition.value or ""
    )
    answer: VerificationStatus = resp.answer or "uncertain"
    return answer, resp.reason or ""
