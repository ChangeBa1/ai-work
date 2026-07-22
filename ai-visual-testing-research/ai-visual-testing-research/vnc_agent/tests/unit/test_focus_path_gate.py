"""US5 T044/T045 + T069: focus path gate via ActionPolicy and RecoveryEngine."""

from datetime import UTC, datetime

import pytest

from vnc_agent.config import (
    AgentConfig,
    AppConfig,
    ModelsConfig,
    RecoveryPolicy,
    VNCTargetsConfig,
)
from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.focus_path import VerifiedFocusNavigationPath
from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.domain.recovery import FailureType
from vnc_agent.planning.action_policy import ActionPolicy
from vnc_agent.recovery.classifier import Classification
from vnc_agent.recovery.engine import RecoveryEngine
from vnc_agent.recovery.strategies import StrategyContext


def _screen_with_unique_ocr(text: str = "レジ袋") -> StructuredScreen:
    return StructuredScreen(
        frame_id="f",
        resolution=(300, 200),
        captured_at=datetime.now(UTC),
        ocr_items=[
            OCRItem(text=text, bbox=(100, 80, 160, 110), confidence=0.95),
        ],
    )


def _screen_ordered_anchors() -> StructuredScreen:
    """Three OCR anchors in reading order: search → qty → レジ袋 (target)."""
    return StructuredScreen(
        frame_id="ordered",
        resolution=(400, 300),
        captured_at=datetime.now(UTC),
        ocr_items=[
            OCRItem(text="search", bbox=(10, 10, 80, 30), confidence=0.95),
            OCRItem(text="qty", bbox=(10, 50, 60, 70), confidence=0.95),
            OCRItem(text="レジ袋", bbox=(10, 90, 80, 120), confidence=0.95),
        ],
    )


def _click_action(text: str = "レジ袋") -> SemanticAction:
    return SemanticAction(
        action_id="c1",
        intent=f"click {text}",
        action_type="click",
        target=TargetDescription(text=text),
    )


def _app_config() -> AppConfig:
    recovery = {
        "action_no_effect": RecoveryPolicy(
            max_retries=3,
            cooldown_ms=0,
            consumes_global_retry_budget=True,
            allows_action_path_change=True,
            requires_strong_model=False,
            requires_human_confirmation=False,
        ),
        "focus_error": RecoveryPolicy(
            max_retries=3,
            cooldown_ms=0,
            consumes_global_retry_budget=True,
            allows_action_path_change=True,
            requires_strong_model=False,
            requires_human_confirmation=False,
        ),
    }
    return AppConfig(
        agent=AgentConfig(recovery=recovery),
        models=ModelsConfig(),
        vnc_targets=VNCTargetsConfig(),
        config_dir="config",
    )


def test_prefer_keyboard_without_focus_path_no_blind_tab():
    policy = ActionPolicy()
    screen = _screen_with_unique_ocr()
    result = policy.resolve(
        _click_action(),
        screen,
        prefer_keyboard=True,
        focus_path=None,
    )
    assert not (
        result.outcome == "focus"
        and result.executable is not None
        and result.executable.keys == ["tab"]
    )
    # Falls back to OCR path for unique text
    assert result.outcome == "ocr_template"
    assert result.executable is not None
    assert result.executable.method == "mouse"


def test_prefer_keyboard_with_focus_path_uses_sequence():
    policy = ActionPolicy()
    path = VerifiedFocusNavigationPath(
        from_hint="search",
        to_hint="レジ袋",
        tab_sequence=["tab", "tab", "shift+tab"],
        verification_method="prior_successful_replay",
        verified_at_frame_id="f0",
    )
    result = policy.resolve(
        _click_action(),
        _screen_with_unique_ocr(),
        prefer_keyboard=True,
        focus_path=path,
    )
    assert result.outcome == "focus"
    assert result.executable is not None
    assert result.executable.keys == ["tab", "tab", "shift+tab"]


@pytest.mark.asyncio
async def test_recovery_switch_to_keyboard_builds_structural_focus_path():
    """
    T069: RecoveryEngine.handle() → switch_to_keyboard side effect must derive a
    non-None focus_path when OCR anchors + known focus uniquely determine a sequence.
    """
    engine = RecoveryEngine(_app_config())
    engine.reset_iteration()
    screen = _screen_ordered_anchors()
    # Known focus on first anchor; target is third → two Tabs
    engine.remember_screen(
        screen,
        target_hint="レジ袋",
        known_focus_hint="search",
    )

    # ACTION_NO_EFFECT routing: second_candidate then switch_to_keyboard
    clf = Classification(failure_type=FailureType.ACTION_NO_EFFECT)
    ctx = StrategyContext(driver=None)
    a1 = await engine.handle(clf, step_controller=None, ctx=ctx, action_timeout=1.0)
    assert a1.strategy == "second_candidate"
    assert engine.focus_path is None  # not yet on keyboard path

    a2 = await engine.handle(clf, step_controller=None, ctx=ctx, action_timeout=1.0)
    assert a2.strategy == "switch_to_keyboard"
    assert engine.prefer_keyboard is True
    assert engine.focus_path is not None, (
        "switch_to_keyboard must build VerifiedFocusNavigationPath when anchors "
        "uniquely resolve from/to (T069)"
    )
    assert engine.focus_path.tab_sequence == ["tab", "tab"]
    assert engine.focus_path.verification_method == "structural_diff_confirmed"
    assert engine.focus_path.to_hint == "レジ袋"

    # Policy consumes the recovery-built path (full pipeline, not hand-built path)
    policy = ActionPolicy()
    result = policy.resolve(
        _click_action("レジ袋"),
        screen,
        prefer_keyboard=engine.prefer_keyboard,
        focus_path=engine.focus_path,
    )
    assert result.outcome == "focus"
    assert result.executable is not None
    assert result.executable.keys == ["tab", "tab"]


@pytest.mark.asyncio
async def test_recovery_switch_to_keyboard_without_evidence_leaves_focus_path_none():
    """T069 bottom line: no reliable sequence → focus_path stays None (no blind Tab)."""
    engine = RecoveryEngine(_app_config())
    engine.reset_iteration()
    # Target only, no known focus, single OCR item — cannot derive sequence
    engine.remember_screen(
        _screen_with_unique_ocr("レジ袋"),
        target_hint="レジ袋",
    )
    clf = Classification(failure_type=FailureType.ACTION_NO_EFFECT)
    ctx = StrategyContext(driver=None)
    await engine.handle(clf, step_controller=None, ctx=ctx, action_timeout=1.0)
    await engine.handle(clf, step_controller=None, ctx=ctx, action_timeout=1.0)
    assert engine.prefer_keyboard is True
    assert engine.focus_path is None


@pytest.mark.asyncio
async def test_recovery_switch_to_keyboard_prior_successful_replay():
    """T069: within-run recorded sequence is reused as prior_successful_replay."""
    engine = RecoveryEngine(_app_config())
    engine.reset_iteration()
    screen = _screen_ordered_anchors()
    engine.remember_screen(screen, target_hint="レジ袋")
    engine.record_successful_focus_path(
        VerifiedFocusNavigationPath(
            from_hint="search",
            to_hint="レジ袋",
            tab_sequence=["tab", "tab"],
            verification_method="prior_successful_replay",
            verified_at_frame_id="prev",
        )
    )
    # Clear known focus so structural path alone would fail without prior
    engine._last_known_focus_hint = ""

    clf = Classification(failure_type=FailureType.ACTION_NO_EFFECT)
    ctx = StrategyContext(driver=None)
    await engine.handle(clf, step_controller=None, ctx=ctx, action_timeout=1.0)
    await engine.handle(clf, step_controller=None, ctx=ctx, action_timeout=1.0)

    assert engine.focus_path is not None
    assert engine.focus_path.tab_sequence == ["tab", "tab"]
    assert engine.focus_path.verification_method == "prior_successful_replay"
