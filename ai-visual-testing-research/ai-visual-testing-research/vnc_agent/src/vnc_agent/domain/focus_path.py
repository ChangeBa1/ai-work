"""VerifiedFocusNavigationPath (data-model.md §8) — gates keyboard focus recovery."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FocusVerificationMethod = Literal[
    "structural_diff_confirmed",
    "prior_successful_replay",
]

TabKey = Literal["tab", "shift+tab"]


class VerifiedFocusNavigationPath(BaseModel):
    from_hint: str = ""
    to_hint: str = ""
    tab_sequence: list[TabKey] = Field(default_factory=list)
    verification_method: FocusVerificationMethod = "structural_diff_confirmed"
    verified_at_frame_id: str = ""
