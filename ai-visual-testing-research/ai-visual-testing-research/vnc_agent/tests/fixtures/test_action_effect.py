"""US1: ActionEffect classification on programmatically constructed frames (offline)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np

from vnc_agent.domain.observation import (
    OCRItem,
    Region,
    StructuredScreen,
    TemplateMatch,
)
from vnc_agent.perception.action_effect import classify_action_effect
from vnc_agent.perception.screen_diff import compute_diff

W, H = 1024, 1568


def _blank() -> np.ndarray:
    return np.zeros((H, W, 3), dtype=np.uint8)


def _save(tmp_path: Path, name: str, img: np.ndarray) -> Path:
    p = tmp_path / name
    cv2.imwrite(str(p), img)
    return p


def _screen(
    path: Path,
    *,
    ocr: list[OCRItem] | None = None,
    templates: list[TemplateMatch] | None = None,
    local_blobs: list[Region] | None = None,
    global_diff_ratio: float = 0.0,
    changed_since_last: bool = False,
) -> StructuredScreen:
    return StructuredScreen(
        frame_id=path.stem,
        resolution=(W, H),
        captured_at=datetime.now(UTC),
        ocr_items=ocr or [],
        template_matches=templates or [],
        local_blobs=local_blobs or [],
        global_diff_ratio=global_diff_ratio,
        changed_since_last=changed_since_last,
        image_path=str(path),
    )


def test_low_global_ratio_local_change(tmp_path: Path):
    """T011: ~0.424% global change with local cart badge → expected_effect."""
    before_img = _blank()
    after_img = before_img.copy()
    # ~0.424% of 1024*1568 ≈ 6800 px → ~82×82 patch
    side = 82
    x0, y0 = 900, 40  # cart badge corner
    after_img[y0 : y0 + side, x0 : x0 + side] = 255

    pb = _save(tmp_path, "before.png", before_img)
    pa = _save(tmp_path, "after.png", after_img)

    changed, regions, ratio, local_blobs = compute_diff(pb, pa, threshold=0.02)
    assert ratio < 0.02, f"incident condition not reproduced: ratio={ratio}"
    assert changed is False  # weak global signal still False
    assert local_blobs, "local_blobs must not be gated by global threshold"

    before = _screen(pb)
    after = _screen(
        pa,
        local_blobs=local_blobs,
        global_diff_ratio=ratio,
        changed_since_last=changed,
    )
    result = classify_action_effect(before, after, intent="click レジ袋")
    assert result.status == "expected_effect"
    assert result.evidence.global_diff_ratio < 0.02


def test_nine_grid_positions(tmp_path: Path):
    """T012: local change at each of nine grid positions → all expected_effect."""
    cell_w, cell_h = W // 3, H // 3
    patch = 60
    for row in range(3):
        for col in range(3):
            before_img = _blank()
            after_img = before_img.copy()
            cx = col * cell_w + cell_w // 2 - patch // 2
            cy = row * cell_h + cell_h // 2 - patch // 2
            after_img[cy : cy + patch, cx : cx + patch] = 200
            pb = _save(tmp_path, f"b_{row}_{col}.png", before_img)
            pa = _save(tmp_path, f"a_{row}_{col}.png", after_img)
            _, _, ratio, blobs = compute_diff(pb, pa, threshold=0.02)
            before = _screen(pb)
            after = _screen(pa, local_blobs=blobs, global_diff_ratio=ratio)
            result = classify_action_effect(before, after, intent="click")
            assert result.status == "expected_effect", (
                f"grid ({row},{col}) failed: {result.status} {result.reason}"
            )


def test_list_update_form_update_page_navigation(tmp_path: Path):
    """T013: list/form/navigation frame pairs → expected_effect."""
    scenarios = {
        "list_update": (100, 200, 400, 80),
        "form_update": (200, 400, 300, 40),
        "page_navigation": (0, 0, W, H // 4),
    }
    for name, (bx, by, bw, bh) in scenarios.items():
        before_img = _blank()
        before_img[by : by + bh, bx : bx + bw] = 80
        after_img = _blank()
        # Move / replace content to create a clear local (or large) change
        ay = by + 100 if name != "page_navigation" else by + H // 3
        after_img[ay : ay + bh, bx : bx + bw] = 220
        pb = _save(tmp_path, f"{name}_b.png", before_img)
        pa = _save(tmp_path, f"{name}_a.png", after_img)
        _, _, ratio, blobs = compute_diff(pb, pa, threshold=0.02)
        before = _screen(pb)
        after = _screen(pa, local_blobs=blobs, global_diff_ratio=ratio)
        result = classify_action_effect(before, after, intent=name)
        assert result.status == "expected_effect", f"{name}: {result}"


def test_no_change_and_ocr_only_change(tmp_path: Path):
    """T014: identical frames → no_effect; OCR-only change → expected_effect."""
    img = _blank()
    pb = _save(tmp_path, "same_b.png", img)
    pa = _save(tmp_path, "same_a.png", img.copy())
    _, _, ratio, blobs = compute_diff(pb, pa, threshold=0.02)
    before = _screen(pb, local_blobs=blobs, global_diff_ratio=ratio)
    after = _screen(pa, local_blobs=blobs, global_diff_ratio=ratio)
    result = classify_action_effect(before, after, intent="noop")
    assert result.status == "no_effect"

    # OCR-only: same pixels, different OCR items
    before_ocr = _screen(
        pb,
        ocr=[OCRItem(text="0点", bbox=(10, 10, 50, 30), confidence=0.9)],
    )
    after_ocr = _screen(
        pa,
        ocr=[OCRItem(text="1点", bbox=(10, 10, 50, 30), confidence=0.9)],
    )
    result_ocr = classify_action_effect(before_ocr, after_ocr, intent="add bag")
    assert result_ocr.status == "expected_effect"
    assert "1点" in result_ocr.evidence.ocr_added or any(
        "1" in t for t in result_ocr.evidence.ocr_added
    )


def test_deduplicated_cache_hit_frames_still_yield_no_effect_not_auto_passed(tmp_path: Path):
    """Feature 004 (T031) regression: a post-action frame that is a strict
    pixel duplicate of `before` — and whose OCR/template came from an
    analysis-cache hit — must still classify as `no_effect` via ordinary
    evidence comparison. `deduplicated=True` / `analysis_source_refs` must
    never themselves short-circuit the verdict to something that reads as
    an automatic pass; ActionEffect has no `passed` status at all — the
    real "no auto pass" guarantee is enforced one layer up by
    `resolve_step_result`/VerificationEngine, which this proves is fed
    honest `no_effect` evidence rather than being bypassed."""
    img = _blank()
    pb = _save(tmp_path, "dedup_b.png", img)
    pa = _save(tmp_path, "dedup_a.png", img.copy())
    same_ocr = [OCRItem(text="同一文本", bbox=(10, 10, 50, 30), confidence=0.9)]

    before = StructuredScreen(
        frame_id="frame-before",
        resolution=(W, H),
        captured_at=datetime.now(UTC),
        ocr_items=same_ocr,
        image_path=str(pb),
        content_hash="c" * 64,
        deduplicated=False,
    )
    after = StructuredScreen(
        frame_id="frame-after",
        resolution=(W, H),
        captured_at=datetime.now(UTC),
        ocr_items=same_ocr,  # cache-hit reused OCR items, byte-identical
        image_path=str(pa),
        content_hash="c" * 64,
        deduplicated=True,
        duplicate_of_frame_id="frame-before",
        analysis_source_refs={"ocr": "frame-before"},
    )
    result = classify_action_effect(before, after, intent="click noop button")
    assert result.status == "no_effect"
    assert result.evidence.ocr_added == []
    assert result.evidence.ocr_removed == []


def test_noise_region_excluded(tmp_path: Path):
    """T015: local change confined to dynamic-noise mask → no_effect."""
    before_img = _blank()
    after_img = before_img.copy()
    # Taskbar clock area near bottom
    clock = Region(x1=W - 120, y1=H - 40, x2=W - 10, y2=H - 5)
    after_img[clock.y1 : clock.y2, clock.x1 : clock.x2] = 255
    pb = _save(tmp_path, "noise_b.png", before_img)
    pa = _save(tmp_path, "noise_a.png", after_img)

    _, _, ratio, blobs = compute_diff(
        pb, pa, threshold=0.02, mask_regions=[clock]
    )
    assert not blobs or all(
        not clock.contains_point(*b.center()) for b in blobs
    )

    before = _screen(pb)
    after = _screen(pa, local_blobs=blobs, global_diff_ratio=ratio)
    result = classify_action_effect(
        before, after, intent="wait", mask_regions=[clock]
    )
    assert result.status == "no_effect", result
