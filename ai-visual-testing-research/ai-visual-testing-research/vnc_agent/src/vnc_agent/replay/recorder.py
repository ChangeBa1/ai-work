"""Replay-script recorder (feature 016, spec FR-003/FR-004).

During an exploration run the runtime hands every *verified-passed* iteration
to :meth:`ReplayRecorder.observe_passed_iteration` (an in-memory draft — no
I/O). When the whole run passed, :meth:`finalize` converts the drafts into a
new immutable :class:`ReplayScript` version: fingerprints/anchors/normalized
bboxes are computed from the pre-action masked-safe frame, mouse templates
are cropped (unless the region intersects a configured security mask — such
steps become ``direct_fallback_only``), and the script is persisted with
``version = max + 1`` (older versions are never deleted).

Everything is fail-open (spec US1-4): any error is logged and swallowed; the
exploration run's result is never affected.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from vnc_agent.domain.action import ExecutableAction, SemanticAction
from vnc_agent.domain.observation import OCRItem, Region, StructuredScreen
from vnc_agent.domain.replay import (
    ReplayAnchor,
    ReplayScript,
    ReplayStep,
    normalize_bbox,
)
from vnc_agent.domain.testcase import TestStep
from vnc_agent.logging_setup import get_logger
from vnc_agent.memory.fingerprint import build_page_fingerprint
from vnc_agent.memory.retrieval import region_intersects_any
from vnc_agent.runtime.telemetry import log_event

if TYPE_CHECKING:
    from vnc_agent.runtime.run_context import RunContext
    from vnc_agent.storage.repositories import ReplayRepository

log = get_logger("replay_recorder")

_MAX_ANCHORS = 5


def nearest_anchors(
    ocr_items: list[OCRItem], region: Region, limit: int = _MAX_ANCHORS
) -> list[ReplayAnchor]:
    """Nearest non-empty OCR texts around ``region`` with their bboxes —
    same distance/ordering basis as feature 015's anchor texts (spec FR-004),
    positions kept so the anchor-translation locate stage can work."""
    cx, cy = region.center()

    def _distance(item: OCRItem) -> float:
        x1, y1, x2, y2 = item.bbox
        icx, icy = (x1 + x2) / 2, (y1 + y2) / 2
        return float((icx - cx) ** 2 + (icy - cy) ** 2)

    ranked = sorted(
        (i for i in ocr_items if i.text.strip()),
        key=lambda i: (_distance(i), i.text),
    )
    return [ReplayAnchor(text=i.text, bbox=i.bbox) for i in ranked[:limit]]


@dataclass
class _StepDraft:
    """In-memory record material for one passed step (spec Clarification 1)."""

    step: TestStep
    screen: StructuredScreen  # pre-action observation (masked-safe frame)
    semantic_action: SemanticAction
    executable: ExecutableAction


class ReplayRecorder:
    """Collects passed-iteration drafts and persists a script on run success."""

    def __init__(
        self,
        *,
        repo: ReplayRepository,
        template_dir: str | Path,
        mask_regions: list[list[int]] | None = None,
    ) -> None:
        self.repo = repo
        self.template_dir = Path(template_dir)
        self.mask_regions = mask_regions or []
        self._drafts: dict[str, _StepDraft] = {}

    def reset(self) -> None:
        """Called at exploration-run start — drafts never leak across runs."""
        self._drafts.clear()

    # ------------------------------------------------------------------
    # draft collection (called from the exploration loop, fail-open)
    # ------------------------------------------------------------------

    def observe_passed_iteration(
        self,
        step: TestStep,
        screen: StructuredScreen,
        semantic_action: SemanticAction,
        executable: ExecutableAction,
    ) -> None:
        """Register the verified-passed iteration of ``step``. Pure in-memory;
        heavy work (frame reads, crops) is deferred to :meth:`finalize` so a
        failed run costs nothing (spec Clarification 1)."""
        try:
            self._drafts[step.id] = _StepDraft(
                step=step,
                screen=screen,
                semantic_action=semantic_action,
                executable=executable,
            )
        except Exception as exc:  # pragma: no cover - defensive fail-open
            log_event("replay_record_draft_failed", step_id=step.id, error=str(exc))

    # ------------------------------------------------------------------
    # finalize (called once after a fully-passed run, fail-open)
    # ------------------------------------------------------------------

    async def finalize(self, ctx: RunContext) -> None:
        """Persist a new script version from the collected drafts."""
        try:
            await self._finalize(ctx)
        except Exception as exc:
            log_event("replay_record_failed", run_id=ctx.run_id, error=str(exc))
        finally:
            self._drafts.clear()

    async def _finalize(self, ctx: RunContext) -> None:
        test_case = ctx.test_case
        missing = [s.id for s in test_case.steps if s.id not in self._drafts]
        if missing:
            # Spec Clarification 1: a partial script is worse than none —
            # replay would deterministically fail at the missing step.
            log_event(
                "replay_record_skipped_missing_steps",
                run_id=ctx.run_id,
                test_case_id=test_case.id,
                missing_step_ids=missing,
            )
            return

        version = await self.repo.next_version(test_case.id)
        script_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        steps: list[ReplayStep] = []
        for index, test_step in enumerate(test_case.steps):
            draft = self._drafts[test_step.id]
            replay_step = self._build_step(draft, script_version=version, order_index=index)
            if replay_step is None:
                log_event(
                    "replay_record_skipped_unrecordable_step",
                    run_id=ctx.run_id,
                    test_case_id=test_case.id,
                    step_id=test_step.id,
                )
                return
            steps.append(replay_step)

        script = ReplayScript(
            script_id=script_id,
            test_case_id=test_case.id,
            version=version,
            source_run_id=ctx.run_id,
            created_at=now,
            steps=steps,
        )
        await self.repo.save_script(script)
        log_event(
            "replay_script_generated",
            run_id=ctx.run_id,
            test_case_id=test_case.id,
            script_id=script_id,
            version=version,
            step_count=len(steps),
        )
        log.info(
            "replay_script_generated",
            test_case_id=test_case.id,
            script_id=script_id,
            version=version,
            step_count=len(steps),
        )

    def _build_step(
        self, draft: _StepDraft, *, script_version: int, order_index: int
    ) -> ReplayStep | None:
        screen = draft.screen
        executable = draft.executable
        frame = self._read_frame(screen.image_path)
        fingerprint = build_page_fingerprint(frame, screen.ocr_items, screen.resolution)
        replay_step_id = str(uuid.uuid4())

        if executable.method == "keyboard":
            return ReplayStep(
                replay_step_id=replay_step_id,
                step_id=draft.step.id,
                order_index=order_index,
                page_fingerprint=fingerprint,
                semantic_action=draft.semantic_action,
                preferred_method="keyboard",
                recorded_executable=executable,
                expected=draft.step.expected.model_copy(deep=True),
                version=script_version,
            )

        region = executable.target_region
        if region is None:
            # A mouse action without a resolved region cannot be re-located.
            return None
        anchors = nearest_anchors(screen.ocr_items, region)
        masked = region_intersects_any(region.as_tuple(), self.mask_regions)
        template_path: str | None = None
        if masked:
            # Security red line (spec FR-004, same rule as feature 015): a
            # region touching a configured mask never becomes a template and
            # the step replays via grounder fallback only.
            log_event(
                "replay_record_template_refused_masked_region",
                step_id=draft.step.id,
                region=region.as_tuple(),
            )
        else:
            template_path = self._save_template(replay_step_id, frame, region)

        return ReplayStep(
            replay_step_id=replay_step_id,
            step_id=draft.step.id,
            order_index=order_index,
            page_fingerprint=fingerprint,
            semantic_action=draft.semantic_action,
            preferred_method="mouse",
            recorded_executable=executable,
            target_template_path=template_path,
            direct_fallback_only=masked,
            anchor_texts=[a.text for a in anchors],
            anchors=anchors,
            bbox=region.as_tuple(),
            normalized_bbox=normalize_bbox(region.as_tuple(), screen.resolution),
            expected=draft.step.expected.model_copy(deep=True),
            version=script_version,
        )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _read_frame(self, image_path: str) -> np.ndarray | None:
        if not image_path:
            return None
        img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        return img if img is not None and img.size else None

    def _save_template(
        self, replay_step_id: str, frame: np.ndarray | None, region: Region
    ) -> str | None:
        """Crop the masked-safe frame at ``region`` — masked pixels can never
        enter replay storage (crop source is the safe frame, spec FR-004)."""
        if frame is None:
            return None
        h, w = frame.shape[:2]
        x1, y1 = max(0, region.x1), max(0, region.y1)
        x2, y2 = min(w, region.x2), min(h, region.y2)
        if x1 >= x2 or y1 >= y2:
            return None
        crop = frame[y1:y2, x1:x2]
        self.template_dir.mkdir(parents=True, exist_ok=True)
        path = self.template_dir / f"{replay_step_id}.png"
        if not cv2.imwrite(str(path), crop):
            return None
        return str(path)
