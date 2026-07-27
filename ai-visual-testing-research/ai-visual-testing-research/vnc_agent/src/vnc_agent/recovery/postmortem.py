"""Wrong-click post-mortem orchestration (feature 023).

The RecoveryEngine only *selects* the ``postmortem`` strategy (budgets,
RecoveryAttempt record); the actual work — page-restore check, annotation,
diagnosis call, strict parsing and the acceptance gates — happens here,
driven by the runtime's WRONG_TARGET branch. Every failure maps to a
distinct :class:`PostmortemAudit` outcome and falls back to the feature-022
chain; nothing on this path may raise into the run loop.

Building blocks are deliberately small pure(-ish) functions so the gates are
unit-testable without a runtime:

- :func:`render_click_annotation` — OpenCV marker (actual click point) +
  rectangle (intended target region) on the post-click frame, size preserved
  (the diagnosis answer must map 1:1 back to original pixels — FR-001);
- :func:`is_same_page_high` — feature 015's pure fingerprint math at tier
  ``high`` with the existing ``memory.*`` thresholds (FR-003);
- :func:`build_evidence_summary` — the 022 evidence, verbalized;
- distance helpers for the anti-hallucination gate (FR-004).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.recovery import (
    FailureType,
    PostmortemAudit,
    PostmortemCorrectionPlan,
    RecoveryAttempt,
    WrongTargetEvidence,
)
from vnc_agent.logging_setup import get_logger
from vnc_agent.memory.fingerprint import (
    build_page_fingerprint,
    classify_page_match,
    page_similarity,
)
from vnc_agent.models.postmortem_client import (
    PostmortemParseError,
    PostmortemProvider,
    PostmortemRequest,
    parse_postmortem_diagnosis,
    resolve_corrected_bbox,
)
from vnc_agent.planning.click_point import safe_click_point
from vnc_agent.runtime.telemetry import log_event

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from vnc_agent.config import MemoryConfig, WrongTargetPostmortemConfig
    from vnc_agent.storage.artifact_store import ArtifactStore

log = get_logger("postmortem")

# Annotation geometry/colors (BGR). Orange rectangle = intended target
# region; red circle + crosshair = the actual click point.
_TARGET_RECT_COLOR = (0, 160, 255)
_CLICK_MARK_COLOR = (0, 0, 255)
_CLICK_CIRCLE_RADIUS = 12
_CLICK_CROSS_HALF = 18
_LINE_THICKNESS = 2


def render_click_annotation(
    image_path: str,
    *,
    click_point: tuple[int, int],
    target_region: tuple[int, int, int, int],
) -> np.ndarray | None:
    """Draw the click marker + target rectangle on a copy of ``image_path``.

    The output array has exactly the source image's dimensions — the
    diagnosis coordinates must restore 1:1 to original frame pixels
    (FR-001). Returns None when the image cannot be read."""
    if not image_path:
        return None
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img is None or img.size == 0:
        return None
    x1, y1, x2, y2 = target_region
    cv2.rectangle(img, (x1, y1), (x2, y2), _TARGET_RECT_COLOR, _LINE_THICKNESS)
    cx, cy = click_point
    cv2.circle(img, (cx, cy), _CLICK_CIRCLE_RADIUS, _CLICK_MARK_COLOR, _LINE_THICKNESS)
    cv2.line(
        img,
        (cx - _CLICK_CROSS_HALF, cy),
        (cx + _CLICK_CROSS_HALF, cy),
        _CLICK_MARK_COLOR,
        _LINE_THICKNESS,
    )
    cv2.line(
        img,
        (cx, cy - _CLICK_CROSS_HALF),
        (cx, cy + _CLICK_CROSS_HALF),
        _CLICK_MARK_COLOR,
        _LINE_THICKNESS,
    )
    return img


def annotation_png_bytes(image: np.ndarray) -> bytes | None:
    ok, buf = cv2.imencode(".png", image)
    return buf.tobytes() if ok else None


def build_evidence_summary(evidence: WrongTargetEvidence) -> str:
    """Verbalize the deterministic 022 evidence for the diagnosis prompt."""
    parts = [
        f"目标区域={evidence.target_region}",
        f"实际点击点={evidence.click_point}",
        f"全屏变化占比={evidence.global_diff_ratio:.5f}",
        f"变化区域数={evidence.blob_count}"
        f"（其中 {evidence.blobs_intersecting_neighborhood} 个在目标邻域内）",
    ]
    if evidence.nearest_blob_bbox is not None:
        parts.append(
            f"最近变化区域 bbox={evidence.nearest_blob_bbox}，"
            f"距目标中心 {evidence.nearest_blob_distance_px:.1f}px，"
            f"方向 {evidence.nearest_blob_direction}"
        )
    return "；".join(parts)


def _screen_fingerprint(screen: StructuredScreen):
    img = None
    if screen.image_path:
        loaded = cv2.imread(str(screen.image_path), cv2.IMREAD_COLOR)
        if loaded is not None and loaded.size:
            img = loaded
    return build_page_fingerprint(img, screen.ocr_items, screen.resolution)


def is_same_page_high(
    reference: StructuredScreen,
    current: StructuredScreen,
    memory_cfg: MemoryConfig,
) -> tuple[bool, float]:
    """Feature 015 fingerprint tier check (FR-003): are ``reference`` and
    ``current`` the same page at tier ``high``? Thresholds come straight
    from the existing memory config; resolution mismatch can never reach
    tier high (classify_page_match caps it). Returns (same, score)."""
    score = page_similarity(_screen_fingerprint(reference), _screen_fingerprint(current))
    level = classify_page_match(
        score,
        same_resolution=tuple(reference.resolution) == tuple(current.resolution),
        high=memory_cfg.page_match_high,
        medium=memory_cfg.page_match_medium,
        low=memory_cfg.page_match_low,
    )
    return level == "high", score


def click_distance_px(a: tuple[int, int], b: tuple[int, int]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def max_click_distance_px(resolution: tuple[int, int], ratio: float) -> float:
    """Anti-hallucination cap (FR-004): ratio × screen width."""
    return resolution[0] * ratio


def _artifact_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value or "unknown")


@dataclass
class PostmortemResult:
    audit: PostmortemAudit
    plan: PostmortemCorrectionPlan | None
    undo_attempt: RecoveryAttempt | None


class PostmortemDiagnostician:
    """Runs one full post-mortem: (optional) undo → annotate → diagnose →
    strict parse → gates. Never raises; every refusal is a distinct audit
    outcome and the caller falls back to the 022 chain (FR-002/FR-004)."""

    def __init__(
        self,
        *,
        run_id: str,
        artifact_store: ArtifactStore,
        client: PostmortemProvider,
        postmortem_cfg: WrongTargetPostmortemConfig,
        memory_cfg: MemoryConfig,
        click_edge_inset_ratio: float,
    ) -> None:
        self.run_id = run_id
        self.artifact_store = artifact_store
        self.client = client
        self.cfg = postmortem_cfg
        self.memory_cfg = memory_cfg
        self.click_edge_inset_ratio = click_edge_inset_ratio

    async def run(
        self,
        *,
        step_id: str,
        iteration_index: int,
        before_screen: StructuredScreen,
        after_screen: StructuredScreen,
        target: dict[str, Any],
        evidence: WrongTargetEvidence,
        send_undo: Callable[[], Awaitable[bool]],
        reobserve: Callable[[], Awaitable[StructuredScreen]],
    ) -> PostmortemResult:
        audit = PostmortemAudit(
            outcome="diagnosis_failed",
            confidence_threshold=self.cfg.confidence_threshold,
        )
        try:
            return await self._run(
                audit,
                step_id=step_id,
                iteration_index=iteration_index,
                before_screen=before_screen,
                after_screen=after_screen,
                target=target,
                evidence=evidence,
                send_undo=send_undo,
                reobserve=reobserve,
            )
        except Exception as exc:  # absolute fail-safe red line
            log.warning(
                "postmortem_internal_error",
                run_id=self.run_id,
                step_id=step_id,
                iteration_index=iteration_index,
                error=str(exc),
            )
            audit.outcome = "diagnosis_failed"
            audit.reason = audit.reason or f"internal error: {exc}"
            return PostmortemResult(audit=audit, plan=None, undo_attempt=None)

    async def _run(
        self,
        audit: PostmortemAudit,
        *,
        step_id: str,
        iteration_index: int,
        before_screen: StructuredScreen,
        after_screen: StructuredScreen,
        target: dict[str, Any],
        evidence: WrongTargetEvidence,
        send_undo: Callable[[], Awaitable[bool]],
        reobserve: Callable[[], Awaitable[StructuredScreen]],
    ) -> PostmortemResult:
        click_point = evidence.click_point
        target_region = evidence.target_region
        if click_point is None or target_region is None:
            audit.outcome = "diagnosis_failed"
            audit.reason = "wrong_target_evidence lacks click_point/target_region"
            return PostmortemResult(audit=audit, plan=None, undo_attempt=None)

        resolution = (
            after_screen.resolution
            if after_screen.resolution != (0, 0)
            else before_screen.resolution
        )

        # --- 1. page restore check: at most ONE safe Esc (FR-003) ----------
        undo_attempt: RecoveryAttempt | None = None
        same, score = is_same_page_high(before_screen, after_screen, self.memory_cfg)
        audit.page_similarity = score
        if not same:
            undo_ok = await send_undo()
            restored = False
            observed: StructuredScreen | None = None
            if undo_ok:
                try:
                    observed = await reobserve()
                except Exception as exc:
                    log.warning(
                        "postmortem_undo_reobserve_failed",
                        run_id=self.run_id,
                        error=str(exc),
                    )
            if observed is not None:
                restored, score = is_same_page_high(
                    before_screen, observed, self.memory_cfg
                )
                audit.page_similarity = score
            undo_attempt = RecoveryAttempt(
                failure_type=FailureType.WRONG_TARGET,
                strategy="postmortem_undo",
                attempt_index=0,
                max_retries=1,
                resolved=restored,
            )
            audit.undo_performed = True
            audit.undo_restored_page = restored
            log_event(
                "postmortem_undo",
                run_id=self.run_id,
                step_id=step_id,
                iteration_index=iteration_index,
                restored=restored,
                page_similarity=score,
            )
            if not restored:
                audit.outcome = "page_not_restored"
                audit.reason = (
                    "page did not return to the pre-click state after one Esc "
                    f"(similarity {score:.3f} < high tier)"
                )
                return PostmortemResult(audit=audit, plan=None, undo_attempt=undo_attempt)

        # --- 2. annotation (original resolution; FR-001) --------------------
        slug = f"postmortem_{_artifact_slug(step_id)}_it{iteration_index}"
        safe_annotated = render_click_annotation(
            after_screen.image_path,
            click_point=click_point,
            target_region=target_region,
        )
        if safe_annotated is None:
            audit.outcome = "diagnosis_failed"
            audit.reason = "post-click frame unreadable — cannot annotate"
            return PostmortemResult(audit=audit, plan=None, undo_attempt=undo_attempt)
        safe_png = annotation_png_bytes(safe_annotated)
        if safe_png is not None:
            audit.annotated_image_ref = self.artifact_store.save_bytes(
                self.run_id, f"model/{slug}_annotated.png", safe_png
            )
        # Model copy: rendered from the unmasked model-facing frame (FR-049
        # convention); inlined only, never persisted. Identical file ⇒ reuse.
        model_path = after_screen.path_for_model()
        model_annotated = (
            safe_annotated
            if model_path == after_screen.image_path
            else render_click_annotation(
                model_path, click_point=click_point, target_region=target_region
            )
        )
        if model_annotated is None:
            model_annotated = safe_annotated
        model_png = annotation_png_bytes(model_annotated)
        if model_png is None:
            audit.outcome = "diagnosis_failed"
            audit.reason = "annotated frame could not be encoded"
            return PostmortemResult(audit=audit, plan=None, undo_attempt=undo_attempt)

        # --- 3. diagnosis call (request/response artifacts) -----------------
        evidence_summary = build_evidence_summary(evidence)
        audit.request_ref = self.artifact_store.save_json(
            self.run_id,
            f"model/{slug}_request.json",
            {
                "target": target,
                "evidence_summary": evidence_summary,
                "resolution": list(resolution),
                "before_image": before_screen.image_path,
                "annotated_image": audit.annotated_image_ref,
                "model": getattr(getattr(self.client, "cfg", None), "model", None),
            },
        )
        request = PostmortemRequest(
            before_image_ref=before_screen.path_for_model(),
            annotated_image_png=model_png,
            target=target,
            evidence_summary=evidence_summary,
            resolution=resolution,
        )
        try:
            raw = await self.client.diagnose(request)
        except Exception as exc:
            audit.response_ref = self.artifact_store.save_json(
                self.run_id, f"model/{slug}_response.json", {"error": str(exc)}
            )
            audit.outcome = "diagnosis_failed"
            audit.reason = f"diagnosis call failed: {exc}"
            return PostmortemResult(audit=audit, plan=None, undo_attempt=undo_attempt)
        audit.response_ref = self.artifact_store.save_json(
            self.run_id, f"model/{slug}_response.json", raw
        )

        # --- 4. strict parse + gates (FR-002/FR-004) -------------------------
        try:
            diagnosis = parse_postmortem_diagnosis(raw)
        except PostmortemParseError as exc:
            audit.outcome = "diagnosis_failed"
            audit.reason = f"strict parse failed: {exc}"
            return PostmortemResult(audit=audit, plan=None, undo_attempt=undo_attempt)
        audit.clicked_element = diagnosis.clicked_element or None
        audit.target_found = diagnosis.target_found
        audit.confidence = diagnosis.confidence
        audit.reason = diagnosis.reason

        if not diagnosis.target_found:
            audit.outcome = "target_not_found"
            return PostmortemResult(audit=audit, plan=None, undo_attempt=undo_attempt)

        corrected = resolve_corrected_bbox(diagnosis, resolution)
        if corrected is None:
            audit.outcome = "diagnosis_failed"
            audit.reason = (
                f"corrected_bbox {diagnosis.corrected_bbox} "
                f"(space={diagnosis.coordinate_space}) rejected by strict resolution"
            )
            return PostmortemResult(audit=audit, plan=None, undo_attempt=undo_attempt)
        audit.corrected_bbox = corrected

        if diagnosis.confidence < self.cfg.confidence_threshold:
            audit.outcome = "low_confidence"
            audit.reason = (
                f"confidence {diagnosis.confidence:.2f} < "
                f"threshold {self.cfg.confidence_threshold:.2f}"
            )
            return PostmortemResult(audit=audit, plan=None, undo_attempt=undo_attempt)

        # Corrected click point: the exact geometry every mouse path uses
        # (feature 013), siblings empty by spec.
        pt = safe_click_point(
            corrected,
            siblings=[],
            screen_resolution=resolution,
            edge_inset_ratio=self.click_edge_inset_ratio,
        )
        audit.corrected_click_point = (pt.x, pt.y)
        distance = click_distance_px(click_point, (pt.x, pt.y))
        max_distance = max_click_distance_px(
            resolution, self.cfg.max_click_distance_ratio
        )
        audit.distance_px = distance
        audit.max_distance_px = max_distance
        if distance > max_distance:
            audit.outcome = "distance_exceeded"
            audit.reason = (
                f"corrected point {distance:.1f}px from original click > "
                f"limit {max_distance:.1f}px "
                f"({self.cfg.max_click_distance_ratio} x screen width)"
            )
            return PostmortemResult(audit=audit, plan=None, undo_attempt=undo_attempt)

        audit.outcome = "corrected"
        plan = PostmortemCorrectionPlan(
            corrected_bbox=corrected,
            click_point=(pt.x, pt.y),
            confidence=diagnosis.confidence,
            clicked_element=diagnosis.clicked_element,
            source_iteration_index=iteration_index,
        )
        log_event(
            "postmortem_corrected",
            run_id=self.run_id,
            step_id=step_id,
            iteration_index=iteration_index,
            corrected_bbox=list(corrected),
            corrected_click_point=[pt.x, pt.y],
            confidence=diagnosis.confidence,
            distance_px=distance,
        )
        return PostmortemResult(audit=audit, plan=plan, undo_attempt=undo_attempt)
