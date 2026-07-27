"""Feature 015: page-fingerprint construction + similarity (spec FR-001/002, SC-004)."""

from __future__ import annotations

import numpy as np
import pytest

from vnc_agent.domain.memory import PageFingerprint
from vnc_agent.memory.fingerprint import (
    WEIGHT_LAYOUT,
    WEIGHT_PHASH,
    WEIGHT_TEXT,
    build_page_fingerprint,
    classify_page_match,
    compute_phash,
    hamming_distance,
    is_dynamic_token,
    page_similarity,
)
from vnc_agent.domain.observation import OCRItem


def _textured(width: int = 300, height: int = 200, seed_shift: int = 0) -> np.ndarray:
    """Deterministic structured image (no RNG)."""
    xx, yy = np.meshgrid(np.arange(width), np.arange(height))
    channel = ((xx * 7 + yy * 13 + seed_shift) % 251).astype(np.uint8)
    return np.stack([channel, 255 - channel, (channel * 3) % 255], axis=-1).astype(np.uint8)


def _item(text: str, bbox=(10, 10, 60, 30), conf: float = 0.9) -> OCRItem:
    return OCRItem(text=text, bbox=bbox, confidence=conf)


class TestPhash:
    def test_deterministic(self):
        img = _textured()
        assert compute_phash(img) == compute_phash(img.copy())
        assert len(compute_phash(img)) == 16

    def test_small_noise_keeps_low_distance(self):
        img = _textured()
        noisy = img.copy()
        # Flip a handful of pixels — a dynamic clock digit's worth of change.
        noisy[0:4, 0:4] = 255 - noisy[0:4, 0:4]
        assert hamming_distance(compute_phash(img), compute_phash(noisy)) <= 8

    def test_different_content_diverges(self):
        a = compute_phash(_textured())
        b = compute_phash(_textured(seed_shift=97) .transpose(1, 0, 2))
        assert hamming_distance(a, b) > 8

    def test_brightness_shift_stable(self):
        img = _textured()
        brighter = np.clip(img.astype(np.int16) + 20, 0, 255).astype(np.uint8)
        assert hamming_distance(compute_phash(img), compute_phash(brighter)) <= 8


class TestDynamicTokens:
    @pytest.mark.parametrize(
        "token",
        ["12:34", "2026/07/26", "¥1,234", "no.0012", "12-31", "08時30分", "99%"],
    )
    def test_dynamic_shapes_filtered(self, token):
        assert is_dynamic_token(token.lower())

    @pytest.mark.parametrize("token", ["login", "ログイン", "登录", "f1", "ok", "総計"])
    def test_stable_labels_kept(self, token):
        assert not is_dynamic_token(token)

    def test_build_filters_dynamic_from_tokens_and_layout(self):
        items = [
            _item("ログイン", bbox=(10, 10, 60, 30)),
            _item("12:34", bbox=(250, 10, 290, 30)),
        ]
        fp = build_page_fingerprint(_textured(), items, (300, 200))
        assert fp.ocr_tokens == ["ログイン"]
        # only the stable token's cell is occupied
        assert len(fp.layout_cells) == 1


class TestFingerprintBuild:
    def test_deterministic_and_sorted(self):
        items = [_item("b", bbox=(200, 100, 240, 120)), _item("a", bbox=(10, 10, 40, 30))]
        img = _textured()
        fp1 = build_page_fingerprint(img, items, (300, 200))
        fp2 = build_page_fingerprint(img, list(reversed(items)), (300, 200))
        assert fp1 == fp2
        assert fp1.ocr_tokens == sorted(fp1.ocr_tokens)
        assert fp1.layout_cells == sorted(fp1.layout_cells)

    def test_layout_grid_scales_with_resolution(self):
        # Same relative position at two resolutions -> same grid cell.
        fp_small = build_page_fingerprint(
            None, [_item("x", bbox=(140, 90, 160, 110))], (300, 200)
        )
        fp_large = build_page_fingerprint(
            None, [_item("x", bbox=(280, 180, 320, 220))], (600, 400)
        )
        assert fp_small.layout_cells == fp_large.layout_cells

    def test_no_image_leaves_phash_empty(self):
        fp = build_page_fingerprint(None, [], (300, 200))
        assert fp.phash == ""


class TestSimilarity:
    def _fp(self, tokens, cells, phash="deadbeefdeadbeef", resolution=(300, 200)):
        return PageFingerprint(
            phash=phash, ocr_tokens=tokens, layout_cells=cells, resolution=resolution
        )

    def test_identical_is_one(self):
        fp = self._fp(["a", "b"], ["1,1"])
        assert page_similarity(fp, fp) == pytest.approx(1.0)

    def test_weights_apply_per_component(self):
        a = self._fp(["a", "b"], ["1,1"])
        b = self._fp(["c", "d"], ["1,1"])  # same phash + layout, disjoint text
        assert page_similarity(a, b) == pytest.approx(WEIGHT_PHASH + WEIGHT_LAYOUT)
        c = self._fp(["a", "b"], ["2,2"])  # same phash + text, disjoint layout
        assert page_similarity(a, c) == pytest.approx(WEIGHT_PHASH + WEIGHT_TEXT)

    def test_both_empty_token_sets_neutral(self):
        a = self._fp([], [])
        b = self._fp([], [])
        assert page_similarity(a, b) == pytest.approx(1.0)

    def test_one_sided_empty_is_mismatch(self):
        a = self._fp(["a"], ["1,1"])
        b = self._fp([], ["1,1"])
        assert page_similarity(a, b) == pytest.approx(WEIGHT_PHASH + WEIGHT_LAYOUT)


class TestClassify:
    kwargs = dict(high=0.88, medium=0.72, low=0.55)

    def test_three_tiers_and_none(self):
        assert classify_page_match(0.95, same_resolution=True, **self.kwargs) == "high"
        assert classify_page_match(0.88, same_resolution=True, **self.kwargs) == "high"
        assert classify_page_match(0.80, same_resolution=True, **self.kwargs) == "medium"
        assert classify_page_match(0.60, same_resolution=True, **self.kwargs) == "low"
        assert classify_page_match(0.40, same_resolution=True, **self.kwargs) == "none"

    def test_resolution_mismatch_caps_at_low(self):
        # bbox/template memory is resolution-dependent: never direct-click or
        # hint across resolutions (spec FR-002).
        assert classify_page_match(0.99, same_resolution=False, **self.kwargs) == "low"
        assert classify_page_match(0.80, same_resolution=False, **self.kwargs) == "low"
        assert classify_page_match(0.40, same_resolution=False, **self.kwargs) == "none"
