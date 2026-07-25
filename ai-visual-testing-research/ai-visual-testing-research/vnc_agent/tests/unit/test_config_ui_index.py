"""T006: UiIndexConfig defaults on AgentConfig."""

from __future__ import annotations

from vnc_agent.config import AgentConfig, UiIndexConfig


def test_ui_index_defaults_disabled():
    cfg = AgentConfig()
    assert cfg.ui_index.bundle_dir is None
    assert isinstance(cfg.ui_index, UiIndexConfig)
    assert cfg.ui_index.screen_match_min_score == 0.6
    assert cfg.ui_index.screen_inconsistency_max_missing_ratio == 0.7
    assert cfg.ui_index.max_content_file_bytes == 50_000_000
    assert cfg.ui_index.max_content_file_records == 200_000
    assert cfg.ui_index.max_bundle_total_bytes == 200_000_000
