"""Cached verification-path visual answers (Feature 008,
vision-answer-cache-contract.md).

The cacheable unit is the *pure* visual answer function
``(frame pixel content, exact question text, request-side model identity) →
VisionUnderstandingResponse`` — never a Verifier conclusion, ActionEffect
combination, or escalation/arbitration decision (those always re-run per
iteration, Constitution Principle IV). Lookup is eligible only for a
StructuredScreen whose owning ScreenFrame the FrameCaptureService has already
rigorously proven pixel-identical to its direct predecessor
(``deduplicated=true`` + ``duplicate_of_frame_id``), reusing the Feature 004
bounded ``AnalysisResultCache`` (``perception.cache_max_frames`` 3..5) —
no new cache mechanism, no pixels/paths stored.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.models.provider import (
    PlannerProvider,
    VisionUnderstandingRequest,
    VisionUnderstandingResponse,
)
from vnc_agent.perception.cache import AnalysisCacheKey, AnalysisResultCache
from vnc_agent.runtime.telemetry import CounterEvent, log_event

ALGORITHM_REVISION = "vision-answer-v1"


class CachedVisualAnswerer:
    """Shared helper for every ``describe_screen(mode="answer_question")`` in
    the verification path (visual_question condition eval + business-resolver
    escalation). With no cache configured it is byte-identical to a direct
    planner call."""

    def __init__(
        self,
        *,
        cache: AnalysisResultCache | None = None,
        test_run_provider: Callable[[], Any] | None = None,
        provider_name: str = "planner-provider",
        model: str = "default",
    ) -> None:
        self.cache = cache
        self.test_run_provider = test_run_provider
        self.provider_name = provider_name
        self.model = model

    def _key(self, screen: StructuredScreen, question: str) -> AnalysisCacheKey | None:
        """Request-side identity only — the response's self-reported
        ``model_name`` can never complete a lookup (Feature 004 rule). The
        advisory structured_screen_hint is intentionally excluded
        (research.md R5; precedent: vision_describe)."""
        if self.cache is None or not screen.content_hash or not screen.scope_key:
            return None
        return AnalysisCacheKey(
            component="vision_answer",
            algorithm_revision=ALGORITHM_REVISION,
            content_hash=screen.content_hash,
            # scope_key is the scope_identity() sha, which already encodes
            # pixel format + mask identity; the two dedicated fields stay
            # uniform ("") within this component (data-model.md §2).
            scope_identity=screen.scope_key,
            pixel_format="",
            mask_identity="",
            perception_config_fingerprint="",
            component_identity={
                "provider": self.provider_name,
                "requested_model": self.model,
                "mode": "answer_question",
                "prompt_revision": ALGORITHM_REVISION,
                "schema_revision": ALGORITHM_REVISION,
                "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
            },
        )

    def _test_run(self) -> Any:
        return self.test_run_provider() if self.test_run_provider is not None else None

    def _record_hit(self, screen: StructuredScreen, source_ref: str) -> None:
        payload = {
            "component": "vision_answer",
            "frame_id": screen.frame_id,
            "source_ref": source_ref,
        }
        test_run = self._test_run()
        if test_run is not None:
            test_run.counter_events.append(
                CounterEvent(
                    kind="analysis_cache_hit", occurred_at=datetime.now(UTC), payload=payload
                )
            )
        log_event("analysis_cache_event", hit=True, **payload)

    def _record_invocation(self, invocation_id: str) -> None:
        payload = {
            "component": "vision_answer",
            "invocation_id": invocation_id,
            "status": "completed",
        }
        test_run = self._test_run()
        if test_run is not None:
            test_run.counter_events.append(
                CounterEvent(
                    kind="analysis_invocation", occurred_at=datetime.now(UTC), payload=payload
                )
            )
        log_event("analysis_cache_event", hit=False, **payload)

    async def answer(
        self,
        planner: PlannerProvider,
        screen: StructuredScreen,
        question: str,
    ) -> VisionUnderstandingResponse:
        key = self._key(screen, question)
        if key is not None:
            try:
                entry = self.cache.lookup(  # type: ignore[union-attr]
                    key,
                    frame_deduplicated=screen.deduplicated,
                    duplicate_of_frame_id=screen.duplicate_of_frame_id,
                    current_sequence=screen.capture_sequence,
                )
            except Exception:  # cache failure degrades to a real call
                entry = None
            if entry is not None:
                self._record_hit(screen, entry.source_frame_id)
                return entry.result

        # Real model call — errors propagate to the caller unchanged and are
        # never cached (FR-007).
        resp = await planner.describe_screen(
            VisionUnderstandingRequest(
                mode="answer_question",
                # FR-049: the model API must receive the unmasked image
                image_ref=screen.path_for_model() or screen.image_path or "stub",
                structured_screen_hint=screen.to_hint_dict(),
                question=question,
            )
        )
        invocation_id = str(uuid.uuid4())
        self._record_invocation(invocation_id)
        if key is not None:
            try:
                self.cache.store(  # type: ignore[union-attr]
                    key,
                    resp,
                    source_frame_id=screen.frame_id,
                    sequence=screen.capture_sequence,
                    invocation_id=invocation_id,
                )
            except Exception:  # store failure must never fail verification
                pass
        return resp
