"""US3: SemanticAction rejects coordinate fields (FR-013)."""

import pytest
from pydantic import ValidationError

from vnc_agent.domain.action import SemanticAction


def test_rejects_x_y():
    with pytest.raises((ValidationError, ValueError)):
        SemanticAction.model_validate(
            {
                "action_id": "a",
                "intent": "click",
                "action_type": "click",
                "x": 10,
                "y": 20,
            }
        )


def test_rejects_coordinates_field():
    with pytest.raises((ValidationError, ValueError)):
        SemanticAction.model_validate(
            {
                "action_id": "a",
                "intent": "click",
                "action_type": "click",
                "coordinates": [1, 2],
            }
        )


def test_valid_without_coords():
    a = SemanticAction(action_id="a", intent="press escape", action_type="press_key", keys=["escape"])
    assert "x" not in a.model_dump()
