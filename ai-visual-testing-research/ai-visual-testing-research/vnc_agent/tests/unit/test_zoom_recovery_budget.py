"""Feature 014 (FR-006/FR-007/FR-009): zoom_reground budgets, fallback after
exhaustion, path-change gating, and recovery-section config extraction."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vnc_agent.config import (
    AgentConfig,
    AppConfig,
    ModelsConfig,
    RecoveryPolicy,
    VNCTargetsConfig,
    ZoomRegroundConfig,
    load_agent_config,
)
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.recovery import FailureType
from vnc_agent.recovery.classifier import Classification
from vnc_agent.recovery.engine import RecoveryEngine
from vnc_agent.recovery.strategies import StrategyContext
from vnc_agent.runtime.step_controller import StepController


def _cfg(
    *,
    allows_action_path_change: bool = True,
    max_per_step: int = 1,
) -> AppConfig:
    agent = AgentConfig(
        recovery={
            "target_not_found": RecoveryPolicy(
                max_retries=3,
                cooldown_ms=0,
                consumes_global_retry_budget=True,
                allows_action_path_change=allows_action_path_change,
                requires_strong_model=False,
                requires_human_confirmation=False,
            ),
        },
        zoom_reground=ZoomRegroundConfig(max_per_step=max_per_step),
    )
    return AppConfig(
        agent=agent,
        models=ModelsConfig(),
        vnc_targets=VNCTargetsConfig(),
        config_dir="config",
    )


def _screen() -> StructuredScreen:
    return StructuredScreen(
        frame_id="f1",
        resolution=(1920, 1080),
        captured_at=datetime.now(UTC),
    )


def _ctx() -> StrategyContext:
    return StrategyContext(
        screen=_screen(),
        grounding_result=GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(
                    bbox=(900, 500, 940, 520),
                    coordinate_space="pixel",
                    confidence=0.4,
                )
            ],
            model_name="stub",
        ),
        target={"text": "OK"},
    )


@pytest.mark.asyncio
async def test_zoom_selected_after_recapture_with_full_observability():
    engine = RecoveryEngine(_cfg())
    controller = StepController(max_retries=5)
    controller.start_iteration()

    first = await engine.handle(
        Classification(FailureType.TARGET_NOT_FOUND),
        step_controller=controller,
        ctx=_ctx(),
    )
    assert first.strategy == "recapture"
    assert engine.zoom_request is None

    engine.begin_action_iteration()  # Tier-2 resets, step strategy index advances
    second = await engine.handle(
        Classification(FailureType.TARGET_NOT_FOUND),
        step_controller=controller,
        ctx=_ctx(),
    )
    assert second.strategy == "zoom_reground"
    assert second.resolved is True
    assert second.roi is not None
    assert second.scale_factor == 2.0
    assert second.roi_source == "grounding_candidate"
    assert engine.zoom_request is not None
    assert engine.zoom_request.roi == second.roi


@pytest.mark.asyncio
async def test_zoom_budget_exhausted_falls_back_without_new_request():
    engine = RecoveryEngine(_cfg(max_per_step=1))
    controller = StepController(max_retries=8)
    controller.start_iteration()

    await engine.handle(
        Classification(FailureType.TARGET_NOT_FOUND),
        step_controller=controller,
        ctx=_ctx(),
    )  # recapture
    engine.begin_action_iteration()
    zoom = await engine.handle(
        Classification(FailureType.TARGET_NOT_FOUND),
        step_controller=controller,
        ctx=_ctx(),
    )
    assert zoom.strategy == "zoom_reground"
    consumed = engine.take_zoom_request()
    assert consumed is not None
    assert engine.zoom_request is None  # one-shot consumption

    engine.begin_action_iteration()
    third = await engine.handle(
        Classification(FailureType.TARGET_NOT_FOUND),
        step_controller=controller,
        ctx=_ctx(),
    )
    # per-step cap reached → substituted by the next existing strategy
    assert third.strategy == "re_ground"
    assert third.roi is None
    assert engine.zoom_request is None


@pytest.mark.asyncio
async def test_zoom_disabled_via_max_per_step_zero():
    engine = RecoveryEngine(_cfg(max_per_step=0))
    controller = StepController(max_retries=5)
    controller.start_iteration()
    engine._step_strategy_index[FailureType.TARGET_NOT_FOUND.value] = 1
    attempt = await engine.handle(
        Classification(FailureType.TARGET_NOT_FOUND),
        step_controller=controller,
        ctx=_ctx(),
    )
    assert attempt.strategy == "re_ground"
    assert engine.zoom_request is None


@pytest.mark.asyncio
async def test_zoom_refused_when_no_roi_derivable():
    engine = RecoveryEngine(_cfg())
    controller = StepController(max_retries=5)
    controller.start_iteration()
    engine._step_strategy_index[FailureType.TARGET_NOT_FOUND.value] = 1
    attempt = await engine.handle(
        Classification(FailureType.TARGET_NOT_FOUND),
        step_controller=controller,
        ctx=StrategyContext(screen=_screen()),  # no candidates, no anchors
    )
    assert attempt.strategy == "re_ground"
    assert engine.zoom_request is None


@pytest.mark.asyncio
async def test_path_change_gate_applies_to_zoom(monkeypatch):
    """FR-009: allows_action_path_change=false forbids the zoom escalation."""
    engine = RecoveryEngine(_cfg(allows_action_path_change=False))
    controller = StepController(max_retries=5)
    controller.start_iteration()
    engine._step_strategy_index[FailureType.TARGET_NOT_FOUND.value] = 1
    attempt = await engine.handle(
        Classification(FailureType.TARGET_NOT_FOUND),
        step_controller=controller,
        ctx=_ctx(),
    )
    assert attempt.strategy == "zoom_reground"
    assert attempt.resolved is False
    assert engine.zoom_request is None
    assert engine._zoom_attempts_step == 0  # refused attempts don't consume cap


@pytest.mark.asyncio
async def test_reset_iteration_clears_zoom_state():
    engine = RecoveryEngine(_cfg())
    controller = StepController(max_retries=5)
    controller.start_iteration()
    engine._step_strategy_index[FailureType.TARGET_NOT_FOUND.value] = 1
    await engine.handle(
        Classification(FailureType.TARGET_NOT_FOUND),
        step_controller=controller,
        ctx=_ctx(),
    )
    assert engine.zoom_request is not None
    engine.reset_iteration()
    assert engine.zoom_request is None
    assert engine._zoom_attempts_step == 0


def test_config_extracted_from_recovery_section(tmp_path):
    (tmp_path / "agent.yaml").write_text(
        """
recovery:
  target_not_found:
    max_retries: 2
    cooldown_ms: 0
    consumes_global_retry_budget: true
    allows_action_path_change: true
    requires_strong_model: false
    requires_human_confirmation: false
  zoom_reground:
    max_per_step: 2
    scale_factor: 3.0
    roi_expand_factor: 2.5
    min_roi_size_px: 128
""",
        encoding="utf-8",
    )
    cfg = load_agent_config(tmp_path)
    assert cfg.zoom_reground.max_per_step == 2
    assert cfg.zoom_reground.scale_factor == 3.0
    assert cfg.zoom_reground.roi_expand_factor == 2.5
    assert cfg.zoom_reground.min_roi_size_px == 128
    # the per-failure-type policy dict stays homogeneous
    assert "zoom_reground" not in cfg.recovery
    assert cfg.recovery["target_not_found"].max_retries == 2


def test_config_defaults_when_absent(tmp_path):
    (tmp_path / "agent.yaml").write_text("recovery: {}\n", encoding="utf-8")
    cfg = load_agent_config(tmp_path)
    assert cfg.zoom_reground.max_per_step == 1
    assert cfg.zoom_reground.scale_factor == 2.0
    assert cfg.zoom_reground.roi_expand_factor == 2.0
    assert cfg.zoom_reground.min_roi_size_px == 64
