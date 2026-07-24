"""US3: Action Policy priority."""

from datetime import datetime, timezone

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.planning.action_policy import ActionPolicy


def _screen(ocr=None) -> StructuredScreen:
    return StructuredScreen(
        frame_id="f1",
        resolution=(800, 600),
        captured_at=datetime.now(timezone.utc),
        ocr_items=ocr or [],
        image_path="x.png",
    )


def test_hotkey_preferred_over_grounding():
    policy = ActionPolicy()
    action = SemanticAction(
        action_id="a",
        intent="save",
        action_type="hotkey",
        keys=["ctrl", "s"],
    )
    result = policy.resolve(action, _screen())
    assert result.outcome == "keyboard"
    assert result.needs_grounding is False
    assert result.executable is not None
    assert result.executable.method == "keyboard"
    # Feature 005 (T008 regression guard): unchanged shape after the new
    # press_key_repeat branch was added.
    assert result.executable.operation == "hotkey"
    assert result.executable.keys == ["ctrl", "s"]


def test_press_key_still_resolves_unchanged():
    policy = ActionPolicy()
    action = SemanticAction(
        action_id="a",
        intent="escape",
        action_type="press_key",
        keys=["escape"],
    )
    result = policy.resolve(action, _screen())
    assert result.outcome == "keyboard"
    assert result.needs_grounding is False
    assert result.executable is not None
    assert result.executable.method == "keyboard"
    assert result.executable.operation == "press_key"
    assert result.executable.keys == ["escape"]


def test_press_key_repeat_resolves_to_keyboard_with_carried_fields():
    policy = ActionPolicy()
    action = SemanticAction(
        action_id="a",
        intent="clear barcode",
        action_type="press_key_repeat",
        keys=["backspace"],
        repeat_count=20,
        repeat_interval_ms=None,
    )
    result = policy.resolve(action, _screen())
    assert result.outcome == "keyboard"
    assert result.needs_grounding is False
    assert result.executable is not None
    assert result.executable.method == "keyboard"
    assert result.executable.operation == "press_key_repeat"
    assert result.executable.keys == ["backspace"]
    assert result.executable.repeat_count == 20
    assert result.executable.repeat_interval_ms == 50  # default substituted


def test_press_key_repeat_carries_explicit_interval():
    policy = ActionPolicy()
    action = SemanticAction(
        action_id="a",
        intent="clear barcode",
        action_type="press_key_repeat",
        keys=["backspace"],
        repeat_count=10,
        repeat_interval_ms=100,
    )
    result = policy.resolve(action, _screen())
    assert result.executable.repeat_interval_ms == 100


def test_unique_ocr_path():
    policy = ActionPolicy()
    action = SemanticAction(
        action_id="a",
        intent="click login",
        action_type="click",
        target=TargetDescription(text="登录", description="登录按钮"),
    )
    screen = _screen(
        ocr=[OCRItem(text="登录", bbox=(10, 10, 80, 40), confidence=0.9)]
    )
    result = policy.resolve(action, screen)
    assert result.outcome == "ocr_template"
    assert result.executable is not None
    assert result.executable.method == "mouse"
    assert result.needs_grounding is False


def test_stop_when_nothing_found():
    policy = ActionPolicy()
    action = SemanticAction(
        action_id="a",
        intent="click unknown",
        action_type="click",
        target=TargetDescription(text="不存在的按钮", description="x"),
    )
    from vnc_agent.domain.grounding import GroundingResult

    result = policy.resolve(
        action, _screen(), grounding_result=GroundingResult(found=False, candidates=[])
    )
    assert result.outcome == "stop_recover"
