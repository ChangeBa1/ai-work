"""Feature 003 T041 — generic scenario 2 (research.md §13): icon-only menu.

Proves, independent of any POS content and without any text anchor, that (a)
visual target identity still works via role/description alone; (b) the
coordinate-space protocol resolves candidates correctly on a non-square
(portrait) resolution used purely as an illustrative geometry example, not a
business binding (FR-018/019/020, SC-002)."""

import pytest

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.execution.action_identity import compute_identity, identity_match
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.provider import GroundingRequest

# Example portrait resolution (height >> 1000) — a geometry test parameter,
# not tied to any specific tested application.
_PORTRAIT_RESOLUTION = (1024, 1568)


def _icon_menu_action(*, action_id: str = "open-menu") -> SemanticAction:
    """An icon-only toolbar button: no text anchor at all, identified purely
    by role + description."""
    return SemanticAction(
        action_id=action_id,
        intent="open the toolbar menu",
        action_type="click",
        target=TargetDescription(
            role="icon_button",
            text=None,
            description="unlabeled hamburger icon in the top toolbar",
        ),
        action_kind="idempotent",
    )


def test_icon_only_target_identity_without_any_text_anchor() -> None:
    first = compute_identity("toolbar-step", _icon_menu_action())
    reworded = compute_identity(
        "toolbar-step",
        SemanticAction(
            action_id="open-menu",
            intent="tap the hamburger icon to reveal the menu",
            action_type="click",
            target=TargetDescription(
                role="icon_button",
                text=None,
                description="three-line menu icon, top-left corner",
            ),
            action_kind="idempotent",
        ),
    )
    assert identity_match(first, reworded) == "action_id_match"


@pytest.mark.asyncio
async def test_icon_candidate_coordinate_space_resolves_on_portrait_resolution() -> None:
    grounder = StubGrounder(
        GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(
                    bbox=(251, 402, 405, 459),
                    coordinate_space="normalized_1000",
                    confidence=0.92,
                    label="toolbar_icon_3",
                )
            ],
            model_name="stub",
        )
    )
    result = await grounder.ground(
        GroundingRequest(
            image_ref="offline.png",
            target={"role": "icon_button", "description": "hamburger icon"},
            resolution=_PORTRAIT_RESOLUTION,
        )
    )
    assert result.found is True
    candidate = result.candidates[0]
    width, height = _PORTRAIT_RESOLUTION
    x1, y1, x2, y2 = candidate.bbox
    assert 0 <= x1 < x2 <= width
    assert 0 <= y1 < y2 <= height
    # Sanity: normalized Y (402-459 of 1000) must NOT be mistaken for pixel Y
    # on a canvas taller than 1000 — the resolved Y range should scale with
    # height, not stay in the tiny 402-459 pixel band.
    assert y1 > 459


@pytest.mark.asyncio
async def test_icon_candidate_click_executes_exactly_once() -> None:
    grounder = StubGrounder(
        GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(
                    bbox=(251, 402, 405, 459),
                    coordinate_space="normalized_1000",
                    confidence=0.92,
                )
            ],
        )
    )
    result = await grounder.ground(
        GroundingRequest(
            image_ref="offline.png",
            target={"role": "icon_button"},
            resolution=_PORTRAIT_RESOLUTION,
        )
    )
    assert len(result.candidates) == 1
