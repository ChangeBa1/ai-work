"""Feature 013 (safe-click-point): click config section (T005)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from vnc_agent.config import AgentConfig, ClickConfig, load_agent_config

VNC_AGENT_ROOT = Path(__file__).resolve().parents[2]


def test_default_edge_inset_ratio_is_015():
    assert ClickConfig().edge_inset_ratio == 0.15
    assert AgentConfig().click.edge_inset_ratio == 0.15


def test_yaml_override_via_model_validate():
    cfg = AgentConfig.model_validate({"click": {"edge_inset_ratio": 0.3}})
    assert cfg.click.edge_inset_ratio == 0.3


def test_ratio_of_half_or_more_rejected():
    with pytest.raises(ValidationError):
        ClickConfig(edge_inset_ratio=0.5)


def test_negative_ratio_rejected():
    with pytest.raises(ValidationError):
        ClickConfig(edge_inset_ratio=-0.1)


def test_zero_ratio_allowed():
    assert ClickConfig(edge_inset_ratio=0.0).edge_inset_ratio == 0.0


def test_repo_agent_yaml_loads_click_section():
    cfg = load_agent_config(VNC_AGENT_ROOT / "config")
    assert cfg.click.edge_inset_ratio == 0.15
