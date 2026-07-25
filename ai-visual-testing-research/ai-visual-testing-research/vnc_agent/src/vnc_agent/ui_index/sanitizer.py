"""Allow-list `VisibleElementHint` construction (contracts §5; data-model.md §4.1).

`to_visible_hint()` is a structural allow-list copy — it is written so that
`element.source_evidence`, `element.metadata`, `element.screen_id` and
`element.normalized_bounds` are never read anywhere in this module. This is
a code-review-checkable static guarantee (FR-015/CHK031), not a runtime
filter: `VisibleElementHint`'s field set is the entirety of what this
function is even capable of returning.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vnc_agent.ui_index.models import Element, NeighborDirection
from vnc_agent.ui_index.repository import UiIndexBundle


class VisibleElementHint(BaseModel):
    """The only shape of index data ever sent to the Planner (FR-015)."""

    model_config = ConfigDict(extra="forbid")

    element_id: str
    visible_texts: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    role: str
    region: str
    anchor_texts: list[str] = Field(default_factory=list)
    neighbor_texts: dict[Literal["up", "down", "left", "right", "near"], list[str]] = Field(
        default_factory=dict
    )


def to_visible_hint(element: Element, bundle: UiIndexBundle) -> VisibleElementHint:
    """Allow-list copy (research.md §10). `bundle` is used only to resolve
    the `visible_texts` of the elements referenced by `anchors`/`neighbors`
    — no other field of those referenced elements is read either."""
    anchor_texts: list[str] = []
    for anchor_id in element.anchors:
        anchor_element = bundle.elements.get(anchor_id)
        if anchor_element is not None:
            anchor_texts.extend(anchor_element.visible_texts)

    neighbor_texts: dict[NeighborDirection, list[str]] = {}
    for neighbor in element.neighbors:
        neighbor_element = bundle.elements.get(neighbor.element_id)
        if neighbor_element is None:
            continue
        neighbor_texts.setdefault(neighbor.direction, []).extend(neighbor_element.visible_texts)

    return VisibleElementHint(
        element_id=element.element_id,
        visible_texts=list(element.visible_texts),
        aliases=list(element.aliases),
        role=element.role,
        region=element.region,
        anchor_texts=anchor_texts,
        neighbor_texts=neighbor_texts,
    )
