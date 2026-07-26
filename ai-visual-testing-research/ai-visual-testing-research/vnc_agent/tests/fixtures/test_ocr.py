"""US2: OCR engine smoke (may use stub if RapidOCR unavailable)."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from vnc_agent.domain.observation import Region
from vnc_agent.perception.ocr import engine as ocr_engine


class FakeOCR:
    def __call__(self, img):
        # Simulate one text box
        box = [[10, 10], [80, 10], [80, 40], [10, 40]]
        return [[box, "Hello", 0.95]], None


def test_ocr_returns_items(tmp_path: Path):
    ocr_engine.set_engine(FakeOCR())
    try:
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        p = tmp_path / "t.png"
        cv2.imwrite(str(p), img)
        items = ocr_engine.run_ocr(p)
        assert len(items) == 1
        assert items[0].text == "Hello"
        assert items[0].bbox[0] == 10
    finally:
        ocr_engine.reset_engine()


def test_ocr_array_entry_ndarray(monkeypatch):
    """Feature 004 (T029/T034): OCR must accept an already-decoded ndarray
    directly — the analysis-component boundary the cache reuses — and never
    re-decode from a file (perception-cache-contract.md `ocr`)."""
    ocr_engine.set_engine(FakeOCR())
    decode_calls = {"n": 0}
    real_imread = cv2.imread

    def counting_imread(*args, **kwargs):
        decode_calls["n"] += 1
        return real_imread(*args, **kwargs)

    monkeypatch.setattr(cv2, "imread", counting_imread)
    try:
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        items = ocr_engine.run_ocr_array(img)
        assert len(items) == 1
        assert items[0].text == "Hello"
        assert decode_calls["n"] == 0, "run_ocr_array must never re-read/decode from disk"
    finally:
        ocr_engine.reset_engine()


# ---------------------------------------------------------------------------
# Feature 010 (ocr-japanese-model): configure_ocr / settings / scaled-ROI OCR
# ---------------------------------------------------------------------------

VNC_AGENT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _clean_ocr_engine_state():
    """Keep the module-level engine/settings isolated per test."""
    yield
    ocr_engine.configure_ocr()  # clear settings back to compat default
    ocr_engine.reset_engine()


def test_configure_ocr_unknown_lang_names_value_and_known_languages():
    with pytest.raises(ValueError) as exc:
        ocr_engine.configure_ocr(lang="klingon")
    assert "klingon" in str(exc.value)
    assert "japan" in str(exc.value)


def test_configure_ocr_missing_model_file_names_path(tmp_path: Path):
    missing = tmp_path / "nope.onnx"
    with pytest.raises(FileNotFoundError) as exc:
        ocr_engine.configure_ocr(rec_model_path=missing)
    assert str(missing) in str(exc.value)


def test_configure_ocr_missing_keys_file_names_path(tmp_path: Path):
    model = tmp_path / "m.onnx"
    model.write_bytes(b"onnx")
    missing_keys = tmp_path / "keys.txt"
    with pytest.raises(FileNotFoundError) as exc:
        ocr_engine.configure_ocr(rec_model_path=model, rec_keys_path=missing_keys)
    assert str(missing_keys) in str(exc.value)


def test_configure_ocr_lang_mapping_resolves_project_assets():
    """`ocr_lang: japan` maps to the committed in-repo model assets."""
    ocr_engine.configure_ocr(lang="japan", base_dir=VNC_AGENT_ROOT)
    settings = ocr_engine.get_ocr_settings()
    assert settings is not None
    assert settings.lang == "japan"
    assert settings.rec_model_path and settings.rec_model_path.endswith(
        "japan_PP-OCRv4_rec_mobile.onnx"
    )
    assert settings.rec_keys_path and settings.rec_keys_path.endswith("japan_dict.txt")


def test_configure_ocr_explicit_path_overrides_lang_mapping(tmp_path: Path):
    model = tmp_path / "custom.onnx"
    model.write_bytes(b"onnx")
    ocr_engine.configure_ocr(lang="japan", rec_model_path=model)
    settings = ocr_engine.get_ocr_settings()
    assert settings is not None
    assert settings.rec_model_path == str(model)
    # keys not mapped when the model path is explicit
    assert settings.rec_keys_path is None


def test_identical_reconfigure_keeps_engine_changed_settings_drop_it(tmp_path: Path):
    model_a = tmp_path / "a.onnx"
    model_a.write_bytes(b"a")
    model_b = tmp_path / "b.onnx"
    model_b.write_bytes(b"b")

    ocr_engine.configure_ocr(rec_model_path=model_a)
    sentinel = FakeOCR()
    ocr_engine.set_engine(sentinel)

    ocr_engine.configure_ocr(rec_model_path=model_a)  # identical → keep engine
    assert ocr_engine._engine is sentinel

    ocr_engine.configure_ocr(rec_model_path=model_b)  # changed → rebuild lazily
    assert ocr_engine._engine is None


def test_injected_engine_wins_over_settings():
    ocr_engine.configure_ocr(lang="japan", base_dir=VNC_AGENT_ROOT)
    ocr_engine.set_engine(FakeOCR())
    items = ocr_engine.run_ocr_array(np.zeros((50, 50, 3), dtype=np.uint8))
    assert [i.text for i in items] == ["Hello"]


def test_configure_ocr_all_none_restores_compat_default():
    ocr_engine.configure_ocr(lang="japan", base_dir=VNC_AGENT_ROOT)
    ocr_engine.configure_ocr()
    settings = ocr_engine.get_ocr_settings()
    assert settings == ocr_engine.OCREngineSettings()
    assert ocr_engine.ocr_component_identity()["language"] == "default"


def test_ocr_component_identity_reflects_configured_language():
    assert ocr_engine.ocr_component_identity()["language"] == "default"
    ocr_engine.configure_ocr(lang="japan", base_dir=VNC_AGENT_ROOT)
    identity = ocr_engine.ocr_component_identity()
    assert identity["language"] == "japan"
    assert identity["backend"] == "rapidocr-onnxruntime"


# --- run_ocr_region_scaled geometry (T017) ---------------------------------


def _write_frame(tmp_path: Path, w: int = 100, h: int = 100) -> Path:
    p = tmp_path / "frame.png"
    cv2.imwrite(str(p), np.zeros((h, w, 3), dtype=np.uint8))
    return p


def test_region_scaled_maps_bboxes_back_to_frame_coordinates(tmp_path: Path):
    frame = _write_frame(tmp_path)
    ocr_engine.set_engine(FakeOCR())  # emits box (10,10)-(80,40) on the crop
    region = Region(x1=20, y1=30, x2=60, y2=70)
    items = ocr_engine.run_ocr_region_scaled(frame, region, scale=2.0)
    assert len(items) == 1
    # (10/2+20, 10/2+30, 80/2+20, 40/2+30)
    assert items[0].bbox == (25, 35, 60, 50)
    assert items[0].text == "Hello"


def test_region_scaled_clamps_out_of_bounds_region(tmp_path: Path):
    frame = _write_frame(tmp_path)
    captured: dict[str, tuple[int, ...]] = {}

    class ShapeSpy:
        def __call__(self, img):
            captured["shape"] = img.shape
            return None, None

    ocr_engine.set_engine(ShapeSpy())
    region = Region(x1=80, y1=80, x2=200, y2=200)  # clamps to 20x20 crop
    assert ocr_engine.run_ocr_region_scaled(frame, region, scale=2.0) == []
    assert captured["shape"][:2] == (40, 40)  # 20x20 crop upscaled 2x


def test_region_scaled_fully_outside_region_returns_empty(tmp_path: Path):
    frame = _write_frame(tmp_path)

    class Boom:
        def __call__(self, img):  # pragma: no cover - must not be called
            raise AssertionError("engine must not run on an empty crop")

    ocr_engine.set_engine(Boom())
    region = Region(x1=150, y1=150, x2=200, y2=200)
    assert ocr_engine.run_ocr_region_scaled(frame, region) == []


def test_region_scaled_unreadable_image_returns_empty(tmp_path: Path):
    ocr_engine.set_engine(FakeOCR())
    region = Region(x1=0, y1=0, x2=10, y2=10)
    assert ocr_engine.run_ocr_region_scaled(tmp_path / "missing.png", region) == []
