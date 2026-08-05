"""Feature 024 (FR-002/FR-005): the declarative plugin profile schema.

A profile file describes exactly ONE sub-window. This is the only place in the
feature where application-specific vocabulary (window titles, control labels)
is allowed to exist — the core code stays business-agnostic (Constitution VI).

Shape priors (area/aspect/size ranges) are OPTIONAL and live here rather than
in the core: a profile describes one known window, so it is the correct home
for "this window looks like this". The surveyed target environment spans
aspect ratios 0.73..5.34 and 3.3%..77.1% screen area, so any built-in default
would be wrong for someone (spec FR-005a).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator

from vnc_agent.domain.app_perception import AnchorConstraint
from vnc_agent.perception.app_plugins.source_geometry import SourceGeometry

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ProfileError(Exception):
    """Profile load/validation failure carrying file path + field path."""

    def __init__(self, path: str | Path, errors: list[dict[str, str]]) -> None:
        self.path = str(path)
        self.errors = errors
        lines = [f"  {e['path']}: {e['reason']}" for e in errors]
        super().__init__(f"invalid app-perception profile {self.path}:\n" + "\n".join(lines))


class ZoomOverride(BaseModel):
    # Fixed scale — deliberately NOT derived from window size (FR-005b).
    scale: float = Field(gt=1.0, le=8.0)


class PaddingRatio(BaseModel):
    left: float = Field(default=0.05, ge=0.0, le=2.0)
    right: float = Field(default=0.05, ge=0.0, le=2.0)
    top: float = Field(default=0.05, ge=0.0, le=2.0)
    bottom: float = Field(default=0.05, ge=0.0, le=2.0)


class PluginProfile(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None

    required_anchors: list[str] = Field(min_length=1)
    # How many of the declared anchors must be hit. Default = all of them.
    # The core deliberately does NOT hardcode "at least 2" (FR-009).
    min_required_anchor_hits: int | None = Field(default=None, ge=1)
    title_anchor: str | None = None
    template_anchor: str | None = None

    padding_ratio: PaddingRatio = Field(default_factory=PaddingRatio)

    # --- OPTIONAL per-window shape priors (no core defaults) ---------------
    area_ratio_range: tuple[float, float] | None = None
    aspect_ratio_range: tuple[float, float] | None = None
    min_size_px: int | None = Field(default=None, ge=8)

    zoom: ZoomOverride | None = None
    anchor_constraints: list[AnchorConstraint] = Field(default_factory=list)
    source_geometry: SourceGeometry | None = None

    @model_validator(mode="after")
    def validate_profile(self) -> PluginProfile:
        if not _NAME_RE.match(self.name):
            raise ValueError(
                f"name {self.name!r} must match [a-z0-9][a-z0-9-]* "
                "(it is the value test steps put in perception_scope)"
            )
        if self.min_required_anchor_hits is not None and (
            self.min_required_anchor_hits > len(self.required_anchors)
        ):
            raise ValueError(
                "min_required_anchor_hits cannot exceed the number of required_anchors"
            )
        for field in ("area_ratio_range", "aspect_ratio_range"):
            rng = getattr(self, field)
            if rng is not None:
                lo, hi = rng
                if not (0 < lo < hi):
                    raise ValueError(f"{field} must satisfy 0 < low < high")
        for c in self.anchor_constraints:
            expected = 2 if c.relation == "between" else 1
            if len(c.anchors) != expected:
                raise ValueError(
                    f"anchor_constraints[{c.subject!r}]: relation {c.relation!r} "
                    f"needs exactly {expected} anchor(s), got {len(c.anchors)}"
                )
        return self

    def anchor_hits_required(self) -> int:
        return self.min_required_anchor_hits or len(self.required_anchors)

    def scale_override(self) -> float | None:
        return self.zoom.scale if self.zoom else None


def _pydantic_errors(exc: ValidationError) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", ())) or "<root>"
        out.append({"path": loc, "reason": err.get("msg", str(err))})
    return out


def load_profile(path: str | Path) -> PluginProfile:
    """Load and validate one profile YAML. Raises ProfileError with the file
    path and per-field reasons (spec SC-008)."""
    path = Path(path)
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProfileError(path, [{"path": "<file>", "reason": "file not found"}]) from exc
    except yaml.YAMLError as exc:
        raise ProfileError(
            path, [{"path": "<file>", "reason": f"YAML parse error: {exc}"}]
        ) from exc
    if not isinstance(raw, dict):
        raise ProfileError(
            path, [{"path": "<root>", "reason": "profile root must be a mapping"}]
        )
    try:
        return PluginProfile.model_validate(raw)
    except ValidationError as exc:
        raise ProfileError(path, _pydantic_errors(exc)) from exc
    except ValueError as exc:
        raise ProfileError(path, [{"path": "<root>", "reason": str(exc)}]) from exc
