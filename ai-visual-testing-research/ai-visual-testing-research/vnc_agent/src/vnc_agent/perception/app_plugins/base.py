"""Feature 024 (FR-001): the app-perception extension point.

The contract only speaks in generic structures (frame, OCR items, geometry,
confidence). Core code depends on this Protocol and never on a concrete
plugin implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from vnc_agent.domain.app_perception import SubWindowDetection
from vnc_agent.domain.observation import StructuredScreen

ActivationVote = Literal["require", "veto", "abstain"]


@dataclass(frozen=True)
class ActivationContext:
    """Read-only, generic context handed to a plugin's activation vote."""

    step_id: str
    declared_scope: str | None
    action_type: str
    target: dict[str, Any] | None
    detection: SubWindowDetection
    resolution: tuple[int, int]
    nearby_texts: list[str] = field(default_factory=list)


@runtime_checkable
class AppPerceptionPlugin(Protocol):
    """A named perception-enhancement plugin for one known sub-window."""

    @property
    def name(self) -> str:
        """Globally unique id; the value test steps put in perception_scope."""
        ...

    def detect(self, screen: StructuredScreen) -> SubWindowDetection | None:
        """Locate this plugin's sub-window in the current frame.

        Implementations MUST:
        - be pure: same screen -> same result (no time/randomness/global state);
        - be read-only: never mutate `screen`, never capture, never OCR, never
          touch the filesystem or network — only consume what the frame
          already carries (`ocr_items`, `template_matches`, `resolution`);
        - return None on any failure rather than raising (the framework also
          catches, but plugins must not rely on that);
        - return `region` in ORIGINAL frame pixels, already inside the frame.
        """
        ...

    def activation_vote(self, ctx: ActivationContext) -> ActivationVote:
        """Optional plugin-side veto channel. Default: "abstain".

        IMPORTANT: "require" CANNOT turn an undeclared step into an activated
        one. Activation has exactly one source — the test step's explicit
        `perception_scope` declaration (spec FR-011/FR-012). A plugin vote can
        only ever *block*; the framework treats "require" as "abstain".
        """
        ...
