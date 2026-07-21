"""Observation pipeline orchestration (FR-010/011, FR-049)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from vnc_agent.domain.observation import StructuredScreen, VisionUnderstanding
from vnc_agent.models.provider import PlannerProvider, VisionUnderstandingRequest
from vnc_agent.perception import screenshot as shot
from vnc_agent.perception.structured_screen import assemble_structured_screen

if TYPE_CHECKING:
    from vnc_agent.drivers.base import VNCDriver


class ObservationPipeline:
    def __init__(
        self,
        driver: VNCDriver,
        *,
        artifacts_dir: str | Path,
        templates_dir: str | Path | None = None,
        planner: PlannerProvider | None = None,
        ocr_enabled: bool = True,
        template_enabled: bool = True,
        vision_fallback: bool = True,
        diff_threshold: float = 0.02,
        mask_regions: Sequence[Sequence[int]] | None = None,
    ) -> None:
        self.driver = driver
        self.artifacts_dir = Path(artifacts_dir)
        self.templates_dir = templates_dir
        self.planner = planner
        self.ocr_enabled = ocr_enabled
        self.template_enabled = template_enabled
        self.vision_fallback = vision_fallback
        self.diff_threshold = diff_threshold
        self.mask_regions = list(mask_regions) if mask_regions else []
        # Diff previous frame against unmasked model path when available
        self._last_frame_path: str | None = None

    async def observe(
        self,
        *,
        run_id: str,
        step_id: str | None = None,
    ) -> StructuredScreen:
        frame = await shot.capture_full_screen(
            self.driver,
            run_id=run_id,
            step_id=step_id,
            artifacts_dir=self.artifacts_dir,
            mask_regions=self.mask_regions or None,
        )
        # Perception (OCR/template/diff) uses unmasked model path for accuracy;
        # local evidence path remains the masked frames/ file.
        perception_path = frame.path_for_model()
        screen = assemble_structured_screen(
            frame,
            prev_frame_path=self._last_frame_path,
            ocr_enabled=self.ocr_enabled,
            template_enabled=self.template_enabled,
            templates_dir=self.templates_dir,
            diff_threshold=self.diff_threshold,
        )
        # Re-run assemble with model path as the frame image for OCR when masked
        if frame.model_image_path and frame.model_image_path != frame.image_path:
            from vnc_agent.domain.observation import ScreenFrame

            perception_frame = frame.model_copy(update={"image_path": perception_path})
            screen = assemble_structured_screen(
                perception_frame,
                prev_frame_path=self._last_frame_path,
                ocr_enabled=self.ocr_enabled,
                template_enabled=self.template_enabled,
                templates_dir=self.templates_dir,
                diff_threshold=self.diff_threshold,
            )
            # Restore local (masked) path for evidence / report
            screen = screen.model_copy(
                update={
                    "image_path": frame.image_path,
                    "model_image_path": frame.model_image_path,
                }
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

        self._last_frame_path = perception_path
        return screen

    def _needs_vision(self, screen: StructuredScreen) -> bool:
        """True when hash/OCR/template insufficient to understand the page."""
        if screen.ocr_items or screen.template_matches:
            return False
        return True
