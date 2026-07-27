"""Feature 022 (wrong-click-detection): stale-frame guard building blocks —
neighborhood geometry (FR-A02), config (FR-A03), enum/routing/budget wiring.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from vnc_agent.config import (
    AgentConfig,
    AppConfig,
    ExecutionConfig,
    ModelsConfig,
    RecoveryPolicy,
    VNCTargetsConfig,
    load_agent_config,
)
from vnc_agent.domain.observation import Region
from vnc_agent.domain.recovery import FailureType
from vnc_agent.perception.action_effect import blobs_intersecting_neighborhood
from vnc_agent.recovery.classifier import Classification
from vnc_agent.recovery.engine import RecoveryEngine
from vnc_agent.recovery.strategies import ROUTING, StrategyContext

VNC_AGENT_ROOT = Path(__file__).resolve().parents[2]

RES = (300, 200)
# w=100 h=40; x0.25 neighborhood = (75, 70, 225, 130)
TARGET = Region(x1=100, y1=80, x2=200, y2=120)


def _hits(blobs: list[Region], expand: float = 0.25) -> list[Region]:
    return blobs_intersecting_neighborhood(
        blobs, TARGET, expand_ratio=expand, resolution=RES
    )


# ----------------------------------------------------- ROI change detection


def test_blob_inside_target_region_is_a_hit():
    assert len(_hits([Region(x1=120, y1=90, x2=160, y2=110)])) == 1


def test_blob_far_from_target_is_not_a_hit():
    assert _hits([Region(x1=10, y1=10, x2=40, y2=30)]) == []


def test_blob_in_expansion_band_is_a_hit():
    # Fully outside the raw region (x > 200) but inside the x0.25 band (< 225).
    assert len(_hits([Region(x1=210, y1=85, x2=224, y2=95)])) == 1


def test_blob_beyond_expansion_band_is_not_a_hit():
    assert _hits([Region(x1=225, y1=85, x2=240, y2=95)]) == []


def test_expand_ratio_zero_uses_raw_region():
    band_blob = Region(x1=210, y1=85, x2=224, y2=95)
    assert _hits([band_blob], expand=0.0) == []
    assert len(_hits([band_blob], expand=0.25)) == 1


def test_mixed_blobs_only_neighborhood_ones_returned():
    far = Region(x1=10, y1=10, x2=40, y2=30)
    near = Region(x1=190, y1=100, x2=230, y2=140)  # straddles the band
    hits = _hits([far, near])
    assert hits == [near]


# ------------------------------------------------------------------ config


def test_execution_config_defaults():
    cfg = ExecutionConfig()
    assert cfg.stale_frame_check_enabled is True
    assert cfg.stale_frame_region_expand_ratio == 0.25
    assert AgentConfig().execution.stale_frame_check_enabled is True


def test_execution_config_bounds():
    with pytest.raises(ValidationError):
        ExecutionConfig(stale_frame_region_expand_ratio=-0.1)
    with pytest.raises(ValidationError):
        ExecutionConfig(stale_frame_region_expand_ratio=4.5)


def test_wrong_target_perception_defaults():
    agent = AgentConfig()
    assert agent.perception.wrong_target_neighborhood_expand_ratio == 0.5
    assert agent.perception.wrong_target_global_diff_ratio_max == 0.10


def test_shipped_agent_yaml_carries_022_sections():
    cfg = load_agent_config(VNC_AGENT_ROOT / "config")
    assert cfg.execution.stale_frame_check_enabled is True
    assert cfg.execution.stale_frame_region_expand_ratio == 0.25
    assert cfg.perception.wrong_target_neighborhood_expand_ratio == 0.5
    assert cfg.perception.wrong_target_global_diff_ratio_max == 0.10
    for ft, path_change in (("stale_frame", False), ("wrong_target", True)):
        policy = cfg.recovery[ft]
        assert policy.max_retries == 2, ft
        assert policy.consumes_global_retry_budget is True, ft
        assert policy.allows_action_path_change is path_change, ft


def test_absent_yaml_sections_keep_defaults():
    cfg = AgentConfig.model_validate({"step": {"default_max_retries": 3}})
    assert cfg.execution == ExecutionConfig()


# --------------------------------------------------- enum / routing / budget


def test_failure_type_members_exist():
    assert FailureType.STALE_FRAME.value == "stale_frame"
    assert FailureType.WRONG_TARGET.value == "wrong_target"


def test_routing_entries():
    assert ROUTING[FailureType.STALE_FRAME] == ["recapture"]
    # Feature 023 (FR-007) prepends the post-mortem tier; the tail remains
    # the 022 chain and still mirrors target_not_found (FR-B03), and the
    # engine's strategies_for() restores the exact 022 list when
    # wrong_target_postmortem is disabled (covered in
    # tests/unit/test_postmortem_routing.py).
    assert ROUTING[FailureType.WRONG_TARGET] == [
        "postmortem",
        "recapture",
        "zoom_reground",
        "re_ground",
    ]
    assert ROUTING[FailureType.WRONG_TARGET][1:] == ROUTING[FailureType.TARGET_NOT_FOUND]


def _app_config(ft: str, *, path_change: bool) -> AppConfig:
    from vnc_agent.config import WrongTargetPostmortemConfig

    return AppConfig(
        agent=AgentConfig(
            recovery={
                ft: RecoveryPolicy(
                    max_retries=2,
                    cooldown_ms=0,
                    consumes_global_retry_budget=False,
                    allows_action_path_change=path_change,
                    requires_strong_model=False,
                    requires_human_confirmation=False,
                )
            },
            # Feature 023: this file pins the 022 baseline chain (FR-007:
            # disabled == byte-identical); the enabled-tier progression is
            # covered by tests/unit/test_postmortem_routing.py.
            wrong_target_postmortem=WrongTargetPostmortemConfig(enabled=False),
        ),
        models=ModelsConfig(),
        vnc_targets=VNCTargetsConfig(),
        config_dir="config",
    )


@pytest.mark.asyncio
async def test_stale_frame_tier2_budget_stops():
    engine = RecoveryEngine(_app_config("stale_frame", path_change=False))
    ctx = StrategyContext()
    results = []
    for _ in range(3):
        attempt = await engine.handle(
            Classification(failure_type=FailureType.STALE_FRAME),
            step_controller=None,
            ctx=ctx,
        )
        results.append(attempt)
    assert [a.strategy for a in results] == ["recapture", "recapture", "recapture"]
    assert [a.resolved for a in results] == [True, True, False]
    assert engine.tier2_exhausted(FailureType.STALE_FRAME)


@pytest.mark.asyncio
async def test_wrong_target_budget_and_strategy_progression():
    engine = RecoveryEngine(_app_config("wrong_target", path_change=True))
    ctx = StrategyContext()
    first = await engine.handle(
        Classification(failure_type=FailureType.WRONG_TARGET),
        step_controller=None,
        ctx=ctx,
    )
    second = await engine.handle(
        Classification(failure_type=FailureType.WRONG_TARGET),
        step_controller=None,
        ctx=ctx,
    )
    third = await engine.handle(
        Classification(failure_type=FailureType.WRONG_TARGET),
        step_controller=None,
        ctx=ctx,
    )
    assert first.strategy == "recapture" and first.resolved is True
    # No zoom evidence in ctx → zoom_reground is substituted by the next
    # strategy in the chain (feature-014 refusal semantics, reused as-is).
    assert second.strategy == "re_ground" and second.resolved is True
    assert third.resolved is False  # max_retries=2 exhausted
