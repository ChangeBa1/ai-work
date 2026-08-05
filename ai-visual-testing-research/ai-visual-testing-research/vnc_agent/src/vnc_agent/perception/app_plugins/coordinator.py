"""Feature 024: orchestration — declaration -> detection -> refined OCR.

The enhancement runs at the OBSERVATION stage, not inside the grounding
branch. Real-run evidence forced this: a step declaring a scope was resolved
by the OCR-direct-click path (feature 012) before grounding was ever
considered, so a grounding-stage hook could never fire for it. Refining the
OCR instead feeds every downstream consumer at once — business assertions,
OCR-direct clicks, element memory and grounding — which is also where the
observed failures actually came from: small ASCII glyphs are misread at
full-frame resolution, and the garbled text then breaks assertions, anchor
matching and OCR-direct clicks alike.

Cost control: the refined read is memoised per frame content hash, so the
repeated observations inside one step (pre-action, post-action, re-observe)
pay for an extra capture + OCR only when the screen actually changed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vnc_agent.config import AppPerceptionConfig
from vnc_agent.domain.app_perception import (
    GeometricPrediction,
    PerceptionEnhancementAudit,
    SubWindowDetection,
)
from vnc_agent.domain.observation import OCRItem, Region, StructuredScreen
from vnc_agent.perception.app_plugins.activation import (
    decide_detection,
    decide_precondition,
    is_declared,
    scope_hint_mismatch,
)
from vnc_agent.perception.app_plugins.detector import normalize
from vnc_agent.perception.app_plugins.geometry import is_inside, project_to_zoom_space
from vnc_agent.perception.app_plugins.scaling import compute_scale
from vnc_agent.perception.app_plugins.source_geometry import (
    map_control_rect,
    predict_control_rect,
    solve_transform,
)


@dataclass(frozen=True)
class ZoomPayload:
    """The magnified crop plus hints, all in the crop's coordinate space."""

    image_path: str
    crop_offset: tuple[int, int]
    scale_factor: float
    resolution: tuple[int, int]
    ocr_candidates: list[dict[str, Any]]
    source_hints: list[dict[str, Any]]


class DeclaredWindowMissingError(Exception):
    """Raised only under on_declared_window_missing="fail" (FR-013a)."""

    def __init__(self, step_id: str, scope: str, reason: str) -> None:
        self.step_id = step_id
        self.scope = scope
        self.reason = reason
        super().__init__(
            f"step {step_id!r} declared perception_scope={scope!r} but the window "
            f"was not detected in this frame ({reason})"
        )


@dataclass
class _CachedRefinement:
    """A refined read of one frame, reusable while the screen is unchanged."""

    ocr_items: list[OCRItem]
    detection: SubWindowDetection
    scale_factor: float
    zoom_image_ref: str | None
    upscaled_resolution: tuple[int, int] | None
    replaced: int
    added: int
    source_hints: list[dict[str, Any]] = field(default_factory=list)
    # Everything the grounder needs to be handed the magnified crop instead
    # of the full frame, kept in the crop's OWN coordinate space so the image
    # and its hints never disagree (the defect this feature must not repeat).
    crop_offset: tuple[int, int] = (0, 0)
    ocr_items_zoom_space: list[OCRItem] = field(default_factory=list)


class AppPerceptionCoordinator:
    def __init__(self, config: AppPerceptionConfig, registry: Any) -> None:
        self.config = config
        self.registry = registry
        self._activations: dict[str, int] = {}
        self._cache: dict[tuple[str, str], _CachedRefinement] = {}
        self._last_audit: PerceptionEnhancementAudit | None = None

    def reset_step(self, step_id: str) -> None:
        self._activations.pop(step_id, None)
        for key in [k for k in self._cache if k[0] == step_id]:
            self._cache.pop(key, None)
        self._last_audit = None

    @property
    def last_audit(self) -> PerceptionEnhancementAudit | None:
        return self._last_audit

    def _allowed(self, target_id: str | None, plugin_name: str) -> bool:
        allowed = self.config.allowed_plugins
        if target_id is None or target_id not in allowed:
            # Target not listed => every registered plugin is allowed.
            return True
        return plugin_name in allowed[target_id]

    async def enhance_screen(
        self,
        screen: StructuredScreen,
        *,
        step_id: str,
        declared_scope: str | None,
        target_id: str | None,
        pipeline: Any,
        target: dict[str, Any] | None = None,
    ) -> tuple[StructuredScreen, PerceptionEnhancementAudit]:
        """Refine `screen`'s OCR inside a declared sub-window.

        Returns the screen to use downstream (the original object when nothing
        was enhanced) plus an audit record. A step that declared a scope ALWAYS
        gets an audit record, whatever happens — "not triggered" and "broken"
        must be distinguishable from the report alone.
        """
        audit = PerceptionEnhancementAudit(
            enabled=self.config.enabled, declared_scope=declared_scope
        )

        pre = decide_precondition(
            declared_scope=declared_scope,
            enabled=self.config.enabled,
            plugin_registered=(
                is_declared(declared_scope)
                and self.registry.get(declared_scope or "") is not None
            ),
            plugin_allowed=(
                is_declared(declared_scope) and self._allowed(target_id, declared_scope or "")
            ),
        )
        if pre is not None:
            self._last_audit = self._merge(audit, pre)
            return screen, self._last_audit

        scope = declared_scope or ""
        plugin = self.registry.get(scope)
        cache_key = (step_id, screen.content_hash or screen.frame_id)

        cached = self._cache.get(cache_key)
        if cached is not None:
            enhanced = self._apply(screen, cached)
            self._fill_success(audit, cached, cached_hit=True)
            audit.scope_hint_mismatch = scope_hint_mismatch(
                target, list(enhanced.ocr_items), cached.detection.region
            )
            self._last_audit = audit
            return enhanced, audit

        used = self._activations.get(step_id, 0)
        budget = self.config.max_activations_per_step
        if budget <= 0 or used >= budget:
            audit.reason_code = "budget_exhausted"
            self._last_audit = audit
            return screen, audit

        detection = plugin.detect(screen)
        det = decide_detection(
            declared_scope=scope,
            detection=detection,
            min_detection_confidence=self.config.min_detection_confidence,
            roi_area_ratio_max=self.config.roi_area_ratio_max,
            min_roi_size_px=self.config.min_roi_size_px,
        )
        if det is not None:
            audit = self._merge(audit, det)
            if detection is not None:
                self._fill_detection(audit, detection)
            self._last_audit = audit
            if self.config.on_declared_window_missing == "fail":
                raise DeclaredWindowMissingError(step_id, scope, det.reason_code)
            return screen, audit

        assert detection is not None
        self._fill_detection(audit, detection)

        profile = getattr(plugin, "profile", None)
        scale = compute_scale(
            detection.region,
            default_scale=self.config.default_scale,
            min_scale=self.config.min_scale,
            max_scale=self.config.max_scale,
            max_upscaled_megapixels=self.config.max_upscaled_megapixels,
            profile_override=profile.scale_override() if profile else None,
        )
        if scale is None:
            audit.reason_code = "scale_not_beneficial"
            self._last_audit = audit
            return screen, audit

        x1, y1, x2, y2 = detection.region
        try:
            observation = await pipeline.observe_zoom(
                roi=Region(x1=x1, y1=y1, x2=x2, y2=y2),
                scale_factor=scale,
                step_id=step_id,
                capture_source="app_perception",
            )
        except Exception:
            observation = None
        if observation is None:
            audit.reason_code = "observation_failed"
            self._last_audit = audit
            return screen, audit

        refinement = self._build_refinement(screen, detection, observation, plugin)
        self._cache[cache_key] = refinement
        self._activations[step_id] = used + 1

        enhanced = self._apply(screen, refinement)
        self._fill_success(audit, refinement, cached_hit=False)
        audit.scope_hint_mismatch = scope_hint_mismatch(
            target, list(enhanced.ocr_items), detection.region
        )
        self._last_audit = audit
        return enhanced, audit

    # --- refinement construction / application ----------------------------

    def _build_refinement(
        self,
        screen: StructuredScreen,
        detection: SubWindowDetection,
        observation: Any,
        plugin: Any,
    ) -> _CachedRefinement:
        """Merge the refined sub-window read into the full-frame read.

        `observe_zoom` already maps its OCR boxes back to ORIGINAL frame
        pixels (`round(v/scale) + crop_offset`), so everything downstream
        stays in one coordinate space — which is what keeps region-scoped
        assertions such as `region: [10, 76, 480, 118]` and OCR-direct click
        points correct.

        Inside the detected window the refined read supersedes the full-frame
        one; outside it the full-frame read is untouched, so assertions about
        the main screen behind the window keep working.
        """
        region = detection.region
        refined = [item for item in observation.ocr_items if self._within(region, item.bbox)]
        if not refined:
            # The magnified pass read nothing inside the window. Replacing the
            # full-frame items with an empty set would DELETE text the coarse
            # read did manage to catch, silently breaking assertions. Keep the
            # original read: no worse than before the feature existed.
            return _CachedRefinement(
                ocr_items=list(screen.ocr_items),
                detection=detection,
                scale_factor=observation.scale_factor,
                zoom_image_ref=observation.image_path,
                upscaled_resolution=observation.resolution,
                replaced=0,
                added=0,
                source_hints=self.source_geometry_hints(plugin, region),
                crop_offset=observation.crop_offset,
                ocr_items_zoom_space=list(
                    getattr(observation, "ocr_items_zoom_space", []) or []
                ),
            )
        kept = [item for item in screen.ocr_items if not is_inside(region, item.bbox)]
        replaced = len(screen.ocr_items) - len(kept)
        return _CachedRefinement(
            ocr_items=kept + refined,
            detection=detection,
            scale_factor=observation.scale_factor,
            zoom_image_ref=observation.image_path,
            upscaled_resolution=observation.resolution,
            replaced=replaced,
            added=len(refined),
            source_hints=self.source_geometry_hints(plugin, region),
            crop_offset=observation.crop_offset,
            ocr_items_zoom_space=list(
                getattr(observation, "ocr_items_zoom_space", []) or []
            ),
        )

    @staticmethod
    def _within(region: tuple[int, int, int, int], bbox: tuple[int, int, int, int]) -> bool:
        """Strict rejection, never clamping: a restored box that fell outside
        the crop is dropped rather than squeezed into range."""
        rx1, ry1, rx2, ry2 = region
        x1, y1, x2, y2 = bbox
        if not (x1 < x2 and y1 < y2):
            return False
        return rx1 <= x1 and ry1 <= y1 and x2 <= rx2 and y2 <= ry2

    @staticmethod
    def _apply(screen: StructuredScreen, refinement: _CachedRefinement) -> StructuredScreen:
        return screen.model_copy(update={"ocr_items": list(refinement.ocr_items)})

    def source_geometry_hints(
        self, plugin: Any, region: tuple[int, int, int, int]
    ) -> list[dict[str, Any]]:
        """Design-time control rects mapped onto the detected bounds (FR-005c/d).

        Emitted in ORIGINAL frame coordinates, matching the full-frame image
        the grounder receives.

        HINTS ONLY (FR-005e): they ride the existing candidate hint channel
        and feed constraint evaluation. They never become click coordinates —
        the click always comes from the grounding result (or from OCR) via the
        unchanged strict restoration chain.
        """
        profile = getattr(plugin, "profile", None)
        geometry = getattr(profile, "source_geometry", None)
        if geometry is None:
            return []
        hints: list[dict[str, Any]] = []
        for control in geometry.controls:
            if not control.text:
                continue
            mapped = map_control_rect(control, geometry.client_size, region)
            if mapped is None:
                continue
            hints.append(
                {
                    "template_id": f"source_geometry:{control.name}",
                    "bbox": list(mapped),
                    "confidence": 0.5,
                    "text": control.text,
                }
            )
        return hints

    # --- audit helpers -----------------------------------------------------

    def _fill_success(
        self,
        audit: PerceptionEnhancementAudit,
        refinement: _CachedRefinement,
        *,
        cached_hit: bool,
    ) -> None:
        self._fill_detection(audit, refinement.detection)
        audit.activated = True
        audit.reason_code = "activated_cached" if cached_hit else "activated"
        audit.scale_factor = refinement.scale_factor
        audit.upscaled_resolution = refinement.upscaled_resolution
        audit.zoom_image_ref = refinement.zoom_image_ref
        audit.ocr_items_replaced = refinement.replaced
        audit.ocr_items_added = refinement.added
        audit.source_geometry_hints = len(refinement.source_hints)

    @staticmethod
    def _fill_detection(audit: PerceptionEnhancementAudit, detection: Any) -> None:
        audit.plugin_name = detection.plugin_name
        audit.roi = detection.region
        audit.detection_method = detection.method
        audit.detection_confidence = detection.confidence
        audit.matched_anchors = list(detection.matched_anchors)

    @staticmethod
    def _merge(audit: PerceptionEnhancementAudit, decision: Any) -> PerceptionEnhancementAudit:
        audit.activated = decision.activated
        audit.reason_code = decision.reason_code
        audit.declared_but_undetected = decision.declared_but_undetected
        return audit

    def _cached_for(self, step_id: str, screen: StructuredScreen) -> _CachedRefinement | None:
        return self._cache.get((step_id, screen.content_hash or screen.frame_id))

    def cached_hints(self, step_id: str, screen: StructuredScreen) -> list[dict[str, Any]]:
        """Source-geometry hints for an already-enhanced frame, for the
        grounding request's hint channel."""
        cached = self._cached_for(step_id, screen)
        return list(cached.source_hints) if cached else []

    def cached_anchors(self, step_id: str, screen: StructuredScreen) -> list[Any]:
        cached = self._cached_for(step_id, screen)
        return list(cached.detection.matched_anchors) if cached else []

    def cached_zoom(self, step_id: str, screen: StructuredScreen) -> ZoomPayload | None:
        """The magnified crop of this frame, ready to hand to the grounder.

        Refining the OCR alone was not enough: the model that actually decides
        the click point is the grounder, and it was still being shown the full
        frame — so a small control stayed just as illegible to it as before.
        Returns None when this frame was not enhanced.
        """
        cached = self._cached_for(step_id, screen)
        if cached is None or not cached.zoom_image_ref or not cached.upscaled_resolution:
            return None
        return ZoomPayload(
            image_path=cached.zoom_image_ref,
            crop_offset=cached.crop_offset,
            scale_factor=cached.scale_factor,
            resolution=cached.upscaled_resolution,
            # Hints in the CROP's coordinate space — never the restored ones.
            ocr_candidates=[i.model_dump() for i in cached.ocr_items_zoom_space],
            source_hints=[
                projected
                for projected in (
                    self._project_hint(h, cached) for h in cached.source_hints
                )
                if projected is not None
            ],
        )

    @staticmethod
    def _project_hint(hint: dict[str, Any], cached: _CachedRefinement) -> dict[str, Any] | None:
        box = project_to_zoom_space(
            tuple(hint["bbox"]),
            crop_offset=cached.crop_offset,
            scale_factor=cached.scale_factor,
            zoom_resolution=cached.upscaled_resolution,
        )
        if box is None:
            return None
        return {**hint, "bbox": list(box)}

    @staticmethod
    def _fit_key(text: str | None) -> str:
        """Normalise a label for FIT matching.

        Deliberately stricter than the detector's matching. Detection uses
        bidirectional containment, which is right for identifying a window but
        wrong here: a short label is a substring of a longer one (a button
        caption inside the window title, say), and one mispaired anchor drags
        the whole least-squares solution off. Equality of the
        punctuation-stripped form still absorbs the real OCR variants — a lost
        trailing colon, a stray full stop, a word split by a spurious space —
        without admitting substrings of other labels.
        """
        return normalize(text).rstrip(":.,;-_ ")

    @classmethod
    def _measure_controls(cls, geometry: Any, ocr_items: list[OCRItem], window: Any) -> dict:
        """Pair text-bearing design controls with what OCR read for them."""
        wx1, wy1, wx2, wy2 = window
        measured: dict[str, tuple[int, int, int, int]] = {}
        for control in geometry.controls:
            if not control.text:
                continue
            needle = cls._fit_key(control.text)
            if not needle:
                continue
            best = None
            for item in ocr_items:
                bx1, by1, bx2, by2 = item.bbox
                # Only text inside the detected window may anchor the fit;
                # an identical string on the main screen behind it would
                # drag the solution somewhere meaningless.
                if not (wx1 <= bx1 and wy1 <= by1 and bx2 <= wx2 and by2 <= wy2):
                    continue
                if cls._fit_key(item.normalized_text or item.text) != needle:
                    continue
                if best is None or item.confidence > best.confidence:
                    best = item
            if best is not None:
                measured[control.text] = best.bbox
        return measured

    def predict_target(
        self, step_id: str, screen: StructuredScreen, control_name: str
    ) -> GeometricPrediction:
        """Locate a named control by solving design->screen from measured anchors.

        Always returns a record: a refusal has to be as visible as a success,
        because "the geometry declined" and "the geometry was never tried" are
        different bugs.
        """
        prediction = GeometricPrediction(control_name=control_name)
        cached = self._cached_for(step_id, screen)
        if cached is None:
            prediction.reject_reason = "not_enhanced"
            return prediction

        plugin = self.registry.get(cached.detection.plugin_name)
        geometry = getattr(getattr(plugin, "profile", None), "source_geometry", None)
        if geometry is None:
            prediction.reject_reason = "no_source_geometry"
            return prediction
        if not any(c.name == control_name for c in geometry.controls):
            prediction.reject_reason = "unknown_control"
            return prediction

        window = cached.detection.region
        short_edge = min(window[2] - window[0], window[3] - window[1])
        cfg = self.config
        # Fit anchors are deliberately NOT the profile's detection anchors:
        # those identify the window (and are chosen for OCR reliability),
        # whereas the fit needs points whose DESIGN coordinates are known,
        # i.e. source_geometry controls carrying text. Match each such
        # control against the refined OCR under a punctuation-insensitive
        # comparison, so a trailing colon lost to OCR still pairs up.
        measured = self._measure_controls(geometry, cached.ocr_items, window)
        transform = solve_transform(
            geometry,
            measured,
            min_anchors=cfg.min_anchors_for_transform,
            min_scale=cfg.transform_min_scale,
            max_scale=cfg.transform_max_scale,
            max_residual_px=cfg.max_transform_residual_ratio * short_edge,
            min_span_ratio=cfg.min_anchor_span_ratio,
        )
        if transform is None:
            prediction.reject_reason = "transform_rejected"
            prediction.anchor_count = len(measured)
            return prediction

        prediction.scale_x = round(transform.scale_x, 4)
        prediction.scale_y = round(transform.scale_y, 4)
        prediction.offset_x = round(transform.offset_x, 2)
        prediction.offset_y = round(transform.offset_y, 2)
        prediction.anchor_count = transform.anchor_count
        prediction.max_residual_px = transform.max_residual_px
        prediction.residuals = [list(r) for r in transform.residuals]

        rect = predict_control_rect(geometry, control_name, transform, window)
        if rect is None:
            prediction.reject_reason = "outside_window"
            return prediction
        prediction.predicted_rect = rect
        return prediction
