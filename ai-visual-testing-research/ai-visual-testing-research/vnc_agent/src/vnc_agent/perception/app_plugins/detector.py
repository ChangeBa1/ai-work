"""Feature 024 (FR-006..FR-010): the generic declarative sub-window detector.

One implementation serves every profile: profile-declared anchor texts are
located in the frame's existing OCR items, their union is padded, brought
inside the frame with the feature-014 viewing-window semantics, and checked
against plausibility rules.

The core carries NO window-shape prior. Only two shape-invariant guards live
here (an area ceiling that rejects "detection degenerated into the whole
screen", and a degeneracy floor); per-window ranges come from the profile.
"""

from __future__ import annotations

import re

from vnc_agent.domain.app_perception import AnchorHit, SubWindowDetection
from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.perception.app_plugins.base import ActivationContext, ActivationVote
from vnc_agent.perception.app_plugins.geometry import area_ratio
from vnc_agent.perception.app_plugins.profile import PluginProfile
from vnc_agent.recovery.zoom import expand_region

_ELLIPSIS = re.compile(r"(\.\.\.|…)+$")
_WS = re.compile(r"\s+")


def normalize(text: str | None) -> str:
    """Lower-case, whitespace-stripped, trailing-ellipsis tolerant.

    Truncated window titles ("ScannerSi...") are common in task-switcher and
    narrow-column renderings, so a trailing ellipsis must not defeat a match.
    """
    value = _WS.sub("", (text or "").strip().lower())
    return _ELLIPSIS.sub("", value)


def _matches(needle: str, hay: str) -> bool:
    if not needle or not hay:
        return False
    return needle in hay or hay in needle


class DeclarativeSubWindowPlugin:
    """Profile-driven plugin (the only implementation the feature ships)."""

    def __init__(self, profile: PluginProfile) -> None:
        self.profile = profile
        self._needles = [(a, normalize(a)) for a in profile.required_anchors]

    @property
    def name(self) -> str:
        return self.profile.name

    def detect(self, screen: StructuredScreen) -> SubWindowDetection | None:
        try:
            return self._detect(screen)
        except Exception:
            # FR-010: never leak into the main loop; undetected == fall open.
            return None

    def _detect(self, screen: StructuredScreen) -> SubWindowDetection | None:
        hits = self._match_anchors(screen.ocr_items)
        if len(hits) < self.profile.anchor_hits_required():
            return None

        region = self._region_from_hits(hits, screen.resolution)
        if region is None:
            return None

        ratio = area_ratio(region, screen.resolution)
        if not self._plausible(region, ratio):
            return None

        confidence = self._confidence(hits)
        return SubWindowDetection(
            plugin_name=self.profile.name,
            region=region,
            confidence=confidence,
            method="ocr_anchors",
            matched_anchors=hits,
            area_ratio=ratio,
        )

    def _match_anchors(self, ocr_items: list[OCRItem]) -> list[AnchorHit]:
        hits: list[AnchorHit] = []
        for anchor_text, needle in self._needles:
            best: OCRItem | None = None
            for item in ocr_items:
                hay = normalize(item.normalized_text or item.text)
                if _matches(needle, hay) and (best is None or item.confidence > best.confidence):
                    best = item
            if best is not None:
                hits.append(
                    AnchorHit(
                        anchor_text=anchor_text,
                        matched_text=best.text,
                        bbox=best.bbox,
                        confidence=best.confidence,
                    )
                )
        return hits

    def _region_from_hits(
        self, hits: list[AnchorHit], resolution: tuple[int, int]
    ) -> tuple[int, int, int, int] | None:
        xs1 = min(h.bbox[0] for h in hits)
        ys1 = min(h.bbox[1] for h in hits)
        xs2 = max(h.bbox[2] for h in hits)
        ys2 = max(h.bbox[3] for h in hits)
        width, height = max(1, xs2 - xs1), max(1, ys2 - ys1)
        pad = self.profile.padding_ratio
        padded = (
            int(round(xs1 - width * pad.left)),
            int(round(ys1 - height * pad.top)),
            int(round(xs2 + width * pad.right)),
            int(round(ys2 + height * pad.bottom)),
        )
        # Reuse feature 014's viewing-window semantics: shifting/shrinking an
        # observation window into frame is legitimate and is NOT the strict
        # no-clamp rule that governs click coordinates.
        #
        # min_size_px=1 on purpose: expand_region would GROW the window to any
        # floor we pass, which would silently satisfy the profile's own
        # min_size_px plausibility rule instead of letting it reject. Size
        # rejection belongs in _plausible(), on the region as actually derived.
        region = expand_region(
            padded,
            factor=1.0,
            min_size_px=1,
            resolution=resolution,
        )
        if region is None:
            return None
        return (region.x1, region.y1, region.x2, region.y2)

    def _plausible(self, region: tuple[int, int, int, int], ratio: float) -> bool:
        x1, y1, x2, y2 = region
        w, h = x2 - x1, y2 - y1
        if w <= 0 or h <= 0:
            return False
        profile = self.profile
        if profile.min_size_px is not None and min(w, h) < profile.min_size_px:
            return False
        if profile.area_ratio_range is not None:
            lo, hi = profile.area_ratio_range
            if not (lo <= ratio <= hi):
                return False
        if profile.aspect_ratio_range is not None:
            lo, hi = profile.aspect_ratio_range
            if not (lo <= w / h <= hi):
                return False
        return True

    def _confidence(self, hits: list[AnchorHit]) -> float:
        required = max(1, len(self.profile.required_anchors))
        coverage = min(1.0, len(hits) / required)
        weakest = min(h.confidence for h in hits)
        return max(0.0, min(1.0, weakest * coverage))

    def activation_vote(self, ctx: ActivationContext) -> ActivationVote:
        # Declarative profiles never veto; activation is the test author's
        # call and detection has already succeeded by the time this runs.
        return "abstain"
