"""Observation pipeline orchestration (FR-010/011, FR-049).

Feature 004: consumes ScreenFrames from the shared `FrameCaptureService`
recorder — no more per-call `capture_full_screen`, no more double
`assemble_structured_screen` for the masked case (the decoded pixel array is
already in memory once; masking only matters for the persisted safe file,
never for perception).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from vnc_agent.domain.observation import Region, StructuredScreen, VisionUnderstanding
from vnc_agent.models.provider import PlannerProvider, VisionUnderstandingRequest
from vnc_agent.perception.structured_screen import assemble_structured_screen_from_pixels

if TYPE_CHECKING:
    from vnc_agent.perception.screenshot import FrameCaptureService


class ObservationPipeline:
    def __init__(
        self,
        capture_service: FrameCaptureService,
        *,
        templates_dir: str | Path | None = None,
        planner: PlannerProvider | None = None,
        ocr_enabled: bool = True,
        template_enabled: bool = True,
        vision_fallback: bool = True,
        diff_threshold: float = 0.02,
    ) -> None:
        self.capture_service = capture_service
        self.templates_dir = templates_dir
        self.planner = planner
        self.ocr_enabled = ocr_enabled
        self.template_enabled = template_enabled
        self.vision_fallback = vision_fallback
        self.diff_threshold = diff_threshold

    async def observe(
        self,
        *,
        step_id: str | None = None,
        capture_source: str = "observation",
        roi: Region | None = None,
    ) -> StructuredScreen:
        outcome = await self.capture_service.capture(
            step_id=step_id, capture_source=capture_source, roi=roi
        )
        frame = outcome.frame
        decoded = outcome.decoded

        screen = assemble_structured_screen_from_pixels(
            frame,
            decoded.pixels,
            previous_pixels=outcome.previous_decoded.pixels if outcome.previous_decoded else None,
            ocr_enabled=self.ocr_enabled,
            template_enabled=self.template_enabled,
            templates_dir=self.templates_dir,
            diff_threshold=self.diff_threshold,
        )

        if self.vision_fallback and self._needs_vision(screen) and self.planner:
            try:
                resp = await self.planner.describe_screen(
                    VisionUnderstandingRequest(
                        mode="describe",
                        # FR-049: model API MUST receive unmasked image
                        image_ref=frame.path_for_model(),
                        structured_screen_hint=screen.to_hint_dict(),
                        question=None,
                    )
                )
                screen = screen.model_copy(
                    update={
                        "vision_understanding": VisionUnderstanding(
                            description=resp.description or "",
                            confidence=resp.confidence,
                            model_name=resp.model_name,
                        )
                    }
                )
            except Exception:
                pass  # vision is best-effort supplement

        return screen

    def _needs_vision(self, screen: StructuredScreen) -> bool:
        """True when hash/OCR/template insufficient to understand the page."""
        if screen.ocr_items or screen.template_matches:
            return False
        return True
