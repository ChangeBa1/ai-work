"""Feature 005: batch repeat key press — model validation (data-model.md).

Covers: drivers.key_mapping.is_batch_repeatable_key(), and the
SemanticAction(action_type="press_key_repeat", ...) validator (bounds,
key vocabulary, and non-interference with other action types).
"""

import pytest
from pydantic import ValidationError

from vnc_agent.domain.action import SemanticAction
from vnc_agent.drivers.key_mapping import is_batch_repeatable_key

# --- is_batch_repeatable_key() -------------------------------------------


@pytest.mark.parametrize(
    "key",
    ["backspace", "delete", "tab", "up", "down", "left", "right", "f1", "f12"],
)
def test_is_batch_repeatable_key_accepts_non_modifier_keys(key):
    assert is_batch_repeatable_key(key) is True


@pytest.mark.parametrize(
    "key",
    ["ctrl", "control", "alt", "shift", "win", "super", "meta", "cmd"],
)
def test_is_batch_repeatable_key_rejects_modifiers(key):
    assert is_batch_repeatable_key(key) is False


def test_is_batch_repeatable_key_rejects_unknown_name():
    assert is_batch_repeatable_key("not-a-real-key") is False


def test_is_batch_repeatable_key_is_case_insensitive():
    assert is_batch_repeatable_key("BACKSPACE") is True
    assert is_batch_repeatable_key("Shift") is False


# --- SemanticAction(action_type="press_key_repeat", ...) — accept path ---


def test_press_key_repeat_valid_construction_succeeds():
    sa = SemanticAction(
        action_id="a1",
        intent="clear field",
        action_type="press_key_repeat",
        keys=["backspace"],
        repeat_count=20,
    )
    assert sa.repeat_count == 20
    assert sa.repeat_interval_ms is None  # not auto-defaulted at this layer


def test_press_key_repeat_valid_construction_with_explicit_interval():
    sa = SemanticAction(
        action_id="a1",
        intent="clear field",
        action_type="press_key_repeat",
        keys=["backspace"],
        repeat_count=20,
        repeat_interval_ms=100,
    )
    assert sa.repeat_interval_ms == 100


# --- SemanticAction(action_type="press_key_repeat", ...) — reject path ---


def test_press_key_repeat_rejects_zero_keys():
    with pytest.raises(ValidationError):
        SemanticAction(
            action_id="a1",
            intent="x",
            action_type="press_key_repeat",
            keys=[],
            repeat_count=5,
        )


def test_press_key_repeat_rejects_multiple_keys():
    with pytest.raises(ValidationError):
        SemanticAction(
            action_id="a1",
            intent="x",
            action_type="press_key_repeat",
            keys=["backspace", "delete"],
            repeat_count=5,
        )


def test_press_key_repeat_rejects_modifier_key():
    with pytest.raises(ValidationError):
        SemanticAction(
            action_id="a1",
            intent="x",
            action_type="press_key_repeat",
            keys=["shift"],
            repeat_count=5,
        )


def test_press_key_repeat_rejects_unknown_key():
    with pytest.raises(ValidationError):
        SemanticAction(
            action_id="a1",
            intent="x",
            action_type="press_key_repeat",
            keys=["nope"],
            repeat_count=5,
        )


def test_press_key_repeat_rejects_missing_repeat_count():
    with pytest.raises(ValidationError):
        SemanticAction(
            action_id="a1",
            intent="x",
            action_type="press_key_repeat",
            keys=["backspace"],
        )


@pytest.mark.parametrize("count", [0, -1, 51])
def test_press_key_repeat_rejects_out_of_range_count(count):
    with pytest.raises(ValidationError):
        SemanticAction(
            action_id="a1",
            intent="x",
            action_type="press_key_repeat",
            keys=["backspace"],
            repeat_count=count,
        )


@pytest.mark.parametrize("interval_ms", [-1, 501])
def test_press_key_repeat_rejects_out_of_range_interval(interval_ms):
    with pytest.raises(ValidationError):
        SemanticAction(
            action_id="a1",
            intent="x",
            action_type="press_key_repeat",
            keys=["backspace"],
            repeat_count=5,
            repeat_interval_ms=interval_ms,
        )


# --- Other action types must stay untouched (FR-011) ---------------------


def test_press_key_rejects_repeat_count_set():
    with pytest.raises(ValidationError):
        SemanticAction(
            action_id="a1",
            intent="x",
            action_type="press_key",
            keys=["escape"],
            repeat_count=5,
        )


def test_press_key_rejects_repeat_interval_ms_set():
    with pytest.raises(ValidationError):
        SemanticAction(
            action_id="a1",
            intent="x",
            action_type="press_key",
            keys=["escape"],
            repeat_interval_ms=50,
        )


def test_hotkey_still_constructs_without_repeat_fields():
    sa = SemanticAction(
        action_id="a1",
        intent="save",
        action_type="hotkey",
        keys=["ctrl", "s"],
    )
    assert sa.repeat_count is None
    assert sa.repeat_interval_ms is None
