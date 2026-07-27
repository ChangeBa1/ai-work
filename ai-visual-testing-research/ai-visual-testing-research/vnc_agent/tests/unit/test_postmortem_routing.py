"""Feature 023 (click-postmortem-correction): config, routing chain, per-step
cap / capability refusal, budgets and one-shot correction-plan semantics
(FR-007/FR-008/FR-009 / SC-002)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from vnc_agent.config import (
    AgentConfig,
    AppConfig,
    ModelsConfig,
    RecoveryPolicy,
    VNCTargetsConfig,
    WrongTargetPostmortemConfig,
    load_agent_config,
)
from vnc_agent.domain.recovery import FailureType, PostmortemCorrectionPlan
from vnc_agent.recovery.classifier import Classification
from vnc_agent.recovery.engine import RecoveryEngine
from vnc_agent.recovery.strategies import ROUTING, StrategyContext, execute_strategy
from vnc_agent.runtime.step_controller import StepController

VNC_AGENT_ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------ config


def test_postmortem_config_defaults():
    cfg = WrongTargetPostmortemConfig()
    assert cfg.enabled is True
    assert cfg.confidence_threshold == 0.7
    assert cfg.max_click_distance_ratio == 0.4
    assert cfg.max_retries == 1
    assert AgentConfig().wrong_target_postmortem == cfg


def test_postmortem_config_bounds():
    with pytest.raises(ValidationError):
        WrongTargetPostmortemConfig(confidence_threshold=1.2)
    with pytest.raises(ValidationError):
        WrongTargetPostmortemConfig(max_click_distance_ratio=0.0)
    with pytest.raises(ValidationError):
        WrongTargetPostmortemConfig(max_click_distance_ratio=1.5)
    with pytest.raises(ValidationError):
        WrongTargetPostmortemConfig(max_retries=0)


def test_shipped_agent_yaml_carries_023_section():
    cfg = load_agent_config(VNC_AGENT_ROOT / "config")
    pm = cfg.wrong_target_postmortem
    assert pm.enabled is True
    assert pm.confidence_threshold == 0.7
    assert pm.max_click_distance_ratio == 0.4
    assert pm.max_retries == 1
    # Extracted from the yaml recovery: section — the per-failure-type
    # RecoveryPolicy dict stays homogeneous (zoom_reground precedent).
    assert "wrong_target_postmortem" not in cfg.recovery
    assert "zoom_reground" not in cfg.recovery


def test_yaml_section_spelling_extracts_into_agent_config():
    cfg = AgentConfig.model_validate(
        {"recovery": {"wrong_target_postmortem": {"enabled": False, "max_retries": 2}}}
    )
    assert cfg.wrong_target_postmortem.enabled is False
    assert cfg.wrong_target_postmortem.max_retries == 2
    assert cfg.recovery == {}


# ------------------------------------------------------------------ routing


def _app_config(
    *,
    enabled: bool = True,
    max_retries: int = 1,
    consumes_budget: bool = False,
) -> AppConfig:
    return AppConfig(
        agent=AgentConfig(
            recovery={
                "wrong_target": RecoveryPolicy(
                    max_retries=4,
                    cooldown_ms=0,
                    consumes_global_retry_budget=consumes_budget,
                    allows_action_path_change=True,
                    requires_strong_model=False,
                    requires_human_confirmation=False,
                )
            },
            wrong_target_postmortem=WrongTargetPostmortemConfig(
                enabled=enabled, max_retries=max_retries
            ),
        ),
        models=ModelsConfig(),
        vnc_targets=VNCTargetsConfig(),
        config_dir="config",
    )


def test_routing_chain_has_postmortem_first():
    assert ROUTING[FailureType.WRONG_TARGET] == [
        "postmortem",
        "recapture",
        "zoom_reground",
        "re_ground",
    ]


def test_strategies_for_disabled_restores_022_chain():
    engine = RecoveryEngine(_app_config(enabled=False))
    assert engine.strategies_for(FailureType.WRONG_TARGET) == [
        "recapture",
        "zoom_reground",
        "re_ground",
    ]
    enabled_engine = RecoveryEngine(_app_config(enabled=True))
    assert enabled_engine.strategies_for(FailureType.WRONG_TARGET) == [
        "postmortem",
        "recapture",
        "zoom_reground",
        "re_ground",
    ]


@pytest.mark.asyncio
async def test_capable_context_selects_postmortem_then_cap_substitutes():
    engine = RecoveryEngine(_app_config(max_retries=1))
    clf = Classification(failure_type=FailureType.WRONG_TARGET)
    first = await engine.handle(
        clf, step_controller=None, ctx=StrategyContext(postmortem_capable=True)
    )
    assert first.strategy == "postmortem" and first.resolved is True
    # Per-step cap consumed on selection (FR-008) — the second WRONG_TARGET
    # routing in the same step substitutes the 022 chain.
    second = await engine.handle(
        clf, step_controller=None, ctx=StrategyContext(postmortem_capable=True)
    )
    assert second.strategy == "recapture"


@pytest.mark.asyncio
async def test_incapable_context_substitutes_recapture():
    engine = RecoveryEngine(_app_config())
    attempt = await engine.handle(
        Classification(failure_type=FailureType.WRONG_TARGET),
        step_controller=None,
        ctx=StrategyContext(postmortem_capable=False),
    )
    assert attempt.strategy == "recapture" and attempt.resolved is True


@pytest.mark.asyncio
async def test_disabled_engine_never_selects_postmortem():
    engine = RecoveryEngine(_app_config(enabled=False))
    attempt = await engine.handle(
        Classification(failure_type=FailureType.WRONG_TARGET),
        step_controller=None,
        ctx=StrategyContext(postmortem_capable=True),
    )
    assert attempt.strategy == "recapture"


@pytest.mark.asyncio
async def test_step_reset_restores_postmortem_cap():
    engine = RecoveryEngine(_app_config(max_retries=1))
    clf = Classification(failure_type=FailureType.WRONG_TARGET)
    ctx = StrategyContext(postmortem_capable=True)
    first = await engine.handle(clf, step_controller=None, ctx=ctx)
    assert first.strategy == "postmortem"
    engine.reset_iteration()  # next TestStep
    again = await engine.handle(clf, step_controller=None, ctx=ctx)
    assert again.strategy == "postmortem"


@pytest.mark.asyncio
async def test_postmortem_consumes_global_retry_budget():
    engine = RecoveryEngine(_app_config(consumes_budget=True))
    controller = StepController(max_retries=1)
    controller.start_iteration()
    attempt = await engine.handle(
        Classification(failure_type=FailureType.WRONG_TARGET),
        step_controller=controller,
        ctx=StrategyContext(postmortem_capable=True),
    )
    assert attempt.strategy == "postmortem" and attempt.resolved is True
    assert controller.remaining_budget() == 0
    # Budget gone — the next attempt is recorded unresolved.
    blocked = await engine.handle(
        Classification(failure_type=FailureType.WRONG_TARGET),
        step_controller=controller,
        ctx=StrategyContext(postmortem_capable=True),
    )
    assert blocked.resolved is False


# ------------------------------------------------- one-shot correction plan


def test_correction_plan_one_shot_semantics():
    engine = RecoveryEngine(_app_config())
    assert engine.take_postmortem_correction() is None
    plan = PostmortemCorrectionPlan(
        corrected_bbox=(210, 80, 290, 120),
        click_point=(250, 100),
        confidence=0.9,
        clicked_element="neighbor",
        source_iteration_index=0,
    )
    engine.set_postmortem_correction(plan)
    assert engine.take_postmortem_correction() == plan
    assert engine.take_postmortem_correction() is None  # consumed
    engine.set_postmortem_correction(plan)
    engine.reset_iteration()  # TestStep boundary clears pending plans
    assert engine.take_postmortem_correction() is None


# -------------------------------------------------------- undo strategy safety


class _KeyDriver:
    def __init__(self) -> None:
        self.keys: list[str] = []
        self.hotkeys: list[list[str]] = []

    async def send_key(self, key: str) -> None:
        self.keys.append(key)

    async def send_hotkey(self, keys: list[str]) -> None:  # pragma: no cover
        self.hotkeys.append(list(keys))


@pytest.mark.asyncio
async def test_postmortem_undo_sends_single_escape_only():
    driver = _KeyDriver()
    ok = await execute_strategy("postmortem_undo", StrategyContext(driver=driver))
    assert ok is True
    # FR-003 red line: one Esc, never Alt+F4 or any destructive hotkey.
    assert driver.keys == ["escape"]
    assert driver.hotkeys == []


@pytest.mark.asyncio
async def test_postmortem_strategy_itself_is_a_noop():
    driver = _KeyDriver()
    ok = await execute_strategy("postmortem", StrategyContext(driver=driver))
    assert ok is True
    assert driver.keys == [] and driver.hotkeys == []
