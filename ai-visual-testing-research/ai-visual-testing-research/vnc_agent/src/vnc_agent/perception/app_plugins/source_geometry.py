"""Feature 024 (FR-005c/d/e): source-derived relative geometry.

A profile MAY carry a snapshot of the application's *design-time* UI layout
(client size + per-control rectangles + anchor semantics), produced offline by
`scripts/gen_app_profile_from_designer.py` and reviewed by a human.

At runtime those design rectangles are mapped onto the *detected* window
bounds. The mapping is a pure function and uses no absolute screen coordinates.

RED LINE (FR-005e): mapped rectangles are HINTS and CONSTRAINT inputs only.
They MUST NOT become click coordinates — source geometry is a prior, not a
position. The final click always comes from the grounding result through the
unchanged strict restoration chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from vnc_agent.domain.app_perception import AnchorConstraint

AnchorEdge = Literal["top", "bottom", "left", "right"]


class ControlGeometry(BaseModel):
    """One design-time control: where it sits inside the client area and which
    edges it is anchored to (WinForms-style anchor semantics)."""

    name: str = Field(min_length=1)
    text: str | None = None
    # Design-time rectangle in CLIENT-AREA coordinates (never screen coords).
    rect: tuple[int, int, int, int]
    anchors: list[AnchorEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_rect(self) -> ControlGeometry:
        x1, y1, x2, y2 = self.rect
        if not (x1 < x2 and y1 < y2):
            raise ValueError(f"control {self.name!r} rect must be non-degenerate")
        return self


class SourceGeometry(BaseModel):
    client_size: tuple[int, int]
    controls: list[ControlGeometry] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_client_size(self) -> SourceGeometry:
        w, h = self.client_size
        if w <= 0 or h <= 0:
            raise ValueError("source_geometry.client_size must be positive")
        return self

    def by_text(self, text: str) -> ControlGeometry | None:
        for c in self.controls:
            if c.text is not None and c.text == text:
                return c
        return None


def map_control_rect(
    control: ControlGeometry,
    design_size: tuple[int, int],
    actual_region: tuple[int, int, int, int],
) -> tuple[int, int, int, int] | None:
    """Map a design-time control rect onto measured window bounds (FR-005d).

    Two effects are absorbed separately:

    * uniform scale ``s = min(AW/W, AH/H)`` — DPI / display scaling, under
      which the whole window (and its glyphs) grows proportionally;
    * residual ``d = A - D*s`` — a user resize, which WinForms distributes
      according to each control's anchors rather than by scaling.

    Per axis:

    ==================  ====================================================
    anchors             mapping
    ==================  ====================================================
    left                x1' = X1 + x1*s              (width stays w*s)
    right               x2' = X2 - (W-x2)*s          (width stays w*s)
    left + right        both edges pinned            (stretches)
    neither             centred float: + d/2         (width stays w*s)
    ==================  ====================================================

    When the window is scaled uniformly (d == 0) all four rules collapse to
    plain proportional scaling — a property the tests assert.

    Returns None on a degenerate or out-of-bounds result: never clamps, never
    guesses (same discipline as the click-coordinate restoration chain).
    """
    dw, dh = design_size
    if dw <= 0 or dh <= 0:
        return None
    x1, y1, x2, y2 = actual_region
    if not (x1 < x2 and y1 < y2):
        return None
    aw, ah = x2 - x1, y2 - y1
    scale = min(aw / dw, ah / dh)
    if scale <= 0:
        return None
    residual_x = aw - dw * scale
    residual_y = ah - dh * scale

    cx1, cy1, cx2, cy2 = control.rect
    anchors = set(control.anchors)

    mx1, mx2 = _map_axis(
        near=cx1,
        far=cx2,
        design_extent=dw,
        origin=x1,
        end=x2,
        scale=scale,
        residual=residual_x,
        pin_near="left" in anchors,
        pin_far="right" in anchors,
    )
    my1, my2 = _map_axis(
        near=cy1,
        far=cy2,
        design_extent=dh,
        origin=y1,
        end=y2,
        scale=scale,
        residual=residual_y,
        pin_near="top" in anchors,
        pin_far="bottom" in anchors,
    )

    rect = (round(mx1), round(my1), round(mx2), round(my2))
    rx1, ry1, rx2, ry2 = rect
    if not (rx1 < rx2 and ry1 < ry2):
        return None
    if not (x1 <= rx1 and ry1 >= y1 and rx2 <= x2 and ry2 <= y2):
        return None
    return rect


def _map_axis(
    *,
    near: float,
    far: float,
    design_extent: float,
    origin: float,
    end: float,
    scale: float,
    residual: float,
    pin_near: bool,
    pin_far: bool,
) -> tuple[float, float]:
    """One axis of the anchor-aware mapping (see map_control_rect)."""
    size = (far - near) * scale
    if pin_near and pin_far:
        return origin + near * scale, end - (design_extent - far) * scale
    if pin_far:
        far_mapped = end - (design_extent - far) * scale
        return far_mapped - size, far_mapped
    if pin_near:
        near_mapped = origin + near * scale
        return near_mapped, near_mapped + size
    near_mapped = origin + near * scale + residual / 2.0
    return near_mapped, near_mapped + size


def derive_anchor_constraints(geometry: SourceGeometry) -> list[AnchorConstraint]:
    """Derive generic same-row / same-column relations between labelled
    controls straight from the design layout (spec T052b).

    Only relations that the layout states unambiguously are emitted, and they
    are emitted as WEAK hints (``enforce=False``) — promoting one to a strong
    prior stays a deliberate, human decision in the profile file.
    """
    labelled = [c for c in geometry.controls if c.text]
    constraints: list[AnchorConstraint] = []
    for i, subject in enumerate(labelled):
        sx1, sy1, sx2, sy2 = subject.rect
        s_cy = (sy1 + sy2) / 2.0
        s_h = sy2 - sy1
        for other in labelled[i + 1 :]:
            ox1, oy1, ox2, oy2 = other.rect
            o_cy = (oy1 + oy2) / 2.0
            # Same horizontal band: centres within half a control height.
            if abs(s_cy - o_cy) <= max(s_h, oy2 - oy1) / 2.0:
                relation = "right_of" if sx1 >= ox2 else (
                    "left_of" if sx2 <= ox1 else "same_row"
                )
                constraints.append(
                    AnchorConstraint(
                        subject=subject.text or subject.name,
                        relation=relation,  # type: ignore[arg-type]
                        anchors=[other.text or other.name],
                        enforce=False,
                    )
                )
    return constraints


# --- runtime-measured design->screen transform ----------------------------
#
# WHY A MEASURED FIT RATHER THAN DESIGN PIXELS
#
# Design-time pixels cannot be used directly: DPI scaling and window chrome
# shift everything (measured 427px on screen for a 423px design client area).
# Instead we SOLVE for the mapping at runtime from anchors we actually saw:
# each profile anchor whose text OCR matched gives one (design, screen) pair,
# and a least-squares fit recovers scale + offset per axis. The window moving,
# being re-opened at another position, or the display DPI changing all show up
# as different fit parameters — nothing is assumed.
#
# ANCHOR SEMANTICS (the load-bearing caveat)
#
# One global scale+offset per axis is exact only while the window keeps its
# DESIGN PROPORTIONS (moved, and/or uniformly DPI-scaled). If a user RESIZES
# the window, WinForms does not scale its controls: `Top|Left` ones keep their
# distance to the top-left edge while `Bottom|Right` ones keep their distance
# to the bottom-right edge, so the two groups stop sharing one mapping and no
# single transform can satisfy both.
#
# That case is not silently mispredicted: it is exactly what the residual gate
# catches. A resize moves the edge-anchored anchors relative to the rest, so
# their residuals blow up and `solve_transform` refuses. Refusing degrades to
# the existing model path — never a wrong click.
#
# `_anchor_span` makes the check honest: a fit validated only against anchors
# that all sit in one corner proves nothing about the opposite corner, so a
# transform is accepted only when its anchors actually straddle the window.


@dataclass(frozen=True)
class DesignTransform:
    """design -> screen mapping, solved from measured anchors."""

    scale_x: float
    scale_y: float
    offset_x: float
    offset_y: float
    anchor_count: int
    max_residual_px: float
    residuals: tuple[tuple[str, float, float], ...] = ()

    def apply(self, rect: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = rect
        return (
            round(self.scale_x * x1 + self.offset_x),
            round(self.scale_y * y1 + self.offset_y),
            round(self.scale_x * x2 + self.offset_x),
            round(self.scale_y * y2 + self.offset_y),
        )


def _fit_axis(pairs: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Least-squares fit of screen = scale * design + offset on one axis."""
    n = len(pairs)
    if n < 2:
        return None
    sx = sum(p[0] for p in pairs)
    sy = sum(p[1] for p in pairs)
    sxx = sum(p[0] * p[0] for p in pairs)
    sxy = sum(p[0] * p[1] for p in pairs)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-9:
        # Every anchor sits at the same design coordinate on this axis: the
        # scale is unconstrained, so refuse rather than invent one.
        return None
    scale = (n * sxy - sx * sy) / denom
    offset = (sy - scale * sx) / n
    return scale, offset


def _centre(rect: tuple[int, int, int, int]) -> tuple[float, float]:
    x1, y1, x2, y2 = rect
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def _anchor_span(points: list[tuple[float, float]]) -> tuple[float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return max(xs) - min(xs), max(ys) - min(ys)


def solve_transform(
    geometry: SourceGeometry,
    measured: dict[str, tuple[int, int, int, int]],
    *,
    min_anchors: int = 3,
    min_scale: float = 0.5,
    max_scale: float = 3.0,
    max_residual_px: float = 8.0,
    min_span_ratio: float = 0.25,
) -> DesignTransform | None:
    """Solve design->screen from anchors matched by their literal text.

    `measured` maps a control's text to the bbox OCR actually found for it.
    Returns None whenever the fit cannot be trusted — every gate refuses
    rather than guesses, and refusal simply means the model path is used.
    """
    pairs: list[tuple[str, tuple[float, float], tuple[float, float]]] = []
    for control in geometry.controls:
        if not control.text:
            continue
        found = measured.get(control.text)
        if found is None:
            continue
        pairs.append((control.name, _centre(control.rect), _centre(found)))

    if len(pairs) < min_anchors:
        # Two points can be fitted exactly, leaving a zero residual that
        # proves nothing. Three is the minimum that can disagree.
        return None

    fit_x = _fit_axis([(p[1][0], p[2][0]) for p in pairs])
    fit_y = _fit_axis([(p[1][1], p[2][1]) for p in pairs])
    if fit_x is None or fit_y is None:
        return None
    scale_x, offset_x = fit_x
    scale_y, offset_y = fit_y

    if not (min_scale <= scale_x <= max_scale and min_scale <= scale_y <= max_scale):
        return None

    residuals: list[tuple[str, float, float]] = []
    worst = 0.0
    for name, design, screen in pairs:
        dx = (scale_x * design[0] + offset_x) - screen[0]
        dy = (scale_y * design[1] + offset_y) - screen[1]
        residuals.append((name, round(dx, 2), round(dy, 2)))
        worst = max(worst, abs(dx), abs(dy))
    if worst > max_residual_px:
        # Typically a resized window: the edge-anchored controls no longer
        # share a mapping with the rest (see the note above).
        return None

    design_w, design_h = geometry.client_size
    span_x, span_y = _anchor_span([p[1] for p in pairs])
    if span_x < design_w * min_span_ratio and span_y < design_h * min_span_ratio:
        # All anchors huddled in one corner: the fit is unconstrained
        # everywhere else, so it must not be extrapolated across the window.
        return None

    return DesignTransform(
        scale_x=scale_x,
        scale_y=scale_y,
        offset_x=offset_x,
        offset_y=offset_y,
        anchor_count=len(pairs),
        max_residual_px=round(worst, 2),
        residuals=tuple(residuals),
    )


def predict_control_rect(
    geometry: SourceGeometry,
    control_name: str,
    transform: DesignTransform,
    window: tuple[int, int, int, int],
) -> tuple[int, int, int, int] | None:
    """Predict a control's on-screen rect. None if it cannot be trusted.

    The whole point of naming a control rather than matching text: the most
    valuable targets (text inputs, unlabelled buttons) carry no Text at all,
    so OCR can never find them and only geometry can.
    """
    control = next((c for c in geometry.controls if c.name == control_name), None)
    if control is None:
        return None
    predicted = transform.apply(control.rect)
    px1, py1, px2, py2 = predicted
    if not (px1 < px2 and py1 < py2):
        return None
    wx1, wy1, wx2, wy2 = window
    if not (wx1 <= px1 and wy1 <= py1 and px2 <= wx2 and py2 <= wy2):
        # Outside the window we actually detected: reject, never clamp.
        return None
    return predicted
