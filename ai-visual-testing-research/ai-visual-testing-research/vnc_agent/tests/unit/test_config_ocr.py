"""Feature 010 (ocr-japanese-model): perception OCR config-load matrix.

Covers spec SC-003: default / language-mapped / explicit-path /
unknown-language cases, plus the deployment-default asset-presence guard
(US2, T013).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vnc_agent.config import AgentConfig, PerceptionConfig, load_agent_config

VNC_AGENT_ROOT = Path(__file__).resolve().parents[2]


def test_ocr_fields_default_to_none_compat():
    cfg = PerceptionConfig()
    assert cfg.ocr_lang is None
    assert cfg.ocr_rec_model_path is None
    assert cfg.ocr_rec_keys_path is None


def test_agent_config_without_perception_section_still_valid():
    cfg = AgentConfig.model_validate({})
    assert cfg.perception.ocr_lang is None


def test_known_language_mapping_accepted():
    cfg = PerceptionConfig(ocr_lang="japan")
    assert cfg.ocr_lang == "japan"


def test_unknown_language_without_explicit_path_rejected():
    with pytest.raises(ValueError, match="ocr_lang 'klingon'"):
        PerceptionConfig(ocr_lang="klingon")


def test_unknown_language_with_explicit_path_accepted():
    cfg = PerceptionConfig(
        ocr_lang="klingon", ocr_rec_model_path="models/ocr/custom.onnx"
    )
    assert cfg.ocr_rec_model_path == "models/ocr/custom.onnx"


def test_yaml_round_trip_loads_all_three_fields(tmp_path: Path):
    (tmp_path / "agent.yaml").write_text(
        yaml.safe_dump(
            {
                "perception": {
                    "ocr_lang": "japan",
                    "ocr_rec_model_path": "models/ocr/a.onnx",
                    "ocr_rec_keys_path": "models/ocr/a.txt",
                }
            }
        ),
        encoding="utf-8",
    )
    cfg = load_agent_config(tmp_path)
    assert cfg.perception.ocr_lang == "japan"
    assert cfg.perception.ocr_rec_model_path == "models/ocr/a.onnx"
    assert cfg.perception.ocr_rec_keys_path == "models/ocr/a.txt"


def test_shipped_agent_yaml_ocr_assets_exist_in_repo():
    """US2/T013: when the shipped deployment config declares OCR model
    paths, the referenced assets must exist in the working tree — guards
    against a broken deployment default."""
    shipped = load_agent_config(VNC_AGENT_ROOT / "config")
    perception = shipped.perception
    if perception.ocr_lang is None and perception.ocr_rec_model_path is None:
        pytest.skip("shipped agent.yaml declares no OCR language/model config")
    for rel in (perception.ocr_rec_model_path, perception.ocr_rec_keys_path):
        if rel is None:
            continue
        path = Path(rel)
        if not path.is_absolute():
            path = VNC_AGENT_ROOT / path
        assert path.exists(), f"agent.yaml references missing OCR asset: {path}"
