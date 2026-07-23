"""Phase 2 (T006) RED: perception.cache_max_frames + reporting.locale config.

Locks:
- ``AgentConfig.perception.cache_max_frames`` defaults to 5, and only 3..5 validate.
- ``AgentConfig.reporting.locale`` defaults to ``zh-CN``.
- an unregistered locale must fail config *loading* (not silently fall back).

Must fail before production changes (missing fields / missing validation).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vnc_agent.config import AgentConfig, PerceptionConfig, ReportingConfig


def test_cache_max_frames_default_is_five():
    cfg = PerceptionConfig()
    assert cfg.cache_max_frames == 5


@pytest.mark.parametrize("value", [3, 4, 5])
def test_cache_max_frames_accepts_three_to_five(value):
    cfg = PerceptionConfig(cache_max_frames=value)
    assert cfg.cache_max_frames == value


@pytest.mark.parametrize("value", [0, 1, 2, 6, 100, -1])
def test_cache_max_frames_rejects_outside_three_to_five(value):
    with pytest.raises(ValidationError):
        PerceptionConfig(cache_max_frames=value)


def test_reporting_locale_default_is_zh_cn():
    cfg = ReportingConfig()
    assert cfg.locale == "zh-CN"


def test_reporting_locale_accepts_registered_locale():
    cfg = ReportingConfig(locale="zh-CN")
    assert cfg.locale == "zh-CN"


def test_reporting_locale_rejects_unregistered_locale_at_load():
    with pytest.raises(ValidationError):
        ReportingConfig(locale="fr-FR")


def test_agent_config_default_includes_perception_and_reporting_locale_fields():
    cfg = AgentConfig()
    assert cfg.perception.cache_max_frames == 5
    assert cfg.reporting.locale == "zh-CN"
