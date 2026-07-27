"""US4 T037/T038: error popup → unexpected_effect; legitimate navigation is not."""

from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.perception.action_effect import classify_action_effect
from vnc_agent.perception.screen_diff import compute_diff

W, H = 400, 300


def _screen(path: Path, *, ocr: list[OCRItem] | None = None) -> StructuredScreen:
    return StructuredScreen(
        frame_id=path.stem,
        resolution=(W, H),
        captured_at=datetime.now(timezone.utc),
        ocr_items=ocr or [],
        image_path=str(path),
    )


def test_error_popup_unexpected_effect(tmp_path: Path):
    before = np.zeros((H, W, 3), dtype=np.uint8)
    after = before.copy()
    # Large global change (dialog covers big area)
    after[50:250, 40:360] = 180
    pb = tmp_path / "b.png"
    pa = tmp_path / "a.png"
    cv2.imwrite(str(pb), before)
    cv2.imwrite(str(pa), after)
    _, _, ratio, blobs = compute_diff(pb, pa, threshold=0.02)
    assert ratio > 0.02

    result = classify_action_effect(
        _screen(pb),
        _screen(
            pa,
            ocr=[
                OCRItem(text="エラーが発生しました", bbox=(50, 60, 300, 90), confidence=0.95)
            ],
        ).model_copy(update={"local_blobs": blobs, "global_diff_ratio": ratio}),
        intent="click",
        error_keywords=["错误", "エラー", "Error", "失败", "失敗", "Failed"],
    )
    assert result.status == "unexpected_effect"
    assert result.evidence.error_popup_signal == "ocr_keyword"


def test_legitimate_page_navigation_not_unexpected(tmp_path: Path):
    before = np.zeros((H, W, 3), dtype=np.uint8)
    before[0:40, :] = 50
    after = np.zeros((H, W, 3), dtype=np.uint8)
    after[100:200, :] = 200  # full content change, no error keywords
    pb = tmp_path / "nb.png"
    pa = tmp_path / "na.png"
    cv2.imwrite(str(pb), before)
    cv2.imwrite(str(pa), after)
    _, _, ratio, blobs = compute_diff(pb, pa, threshold=0.02)

    result = classify_action_effect(
        _screen(pb, ocr=[OCRItem(text="商品一覧", bbox=(10, 10, 80, 30), confidence=0.9)]),
        _screen(
            pa,
            ocr=[OCRItem(text="確認画面", bbox=(10, 10, 80, 30), confidence=0.9)],
        ).model_copy(update={"local_blobs": blobs, "global_diff_ratio": ratio}),
        intent="submit",
    )
    assert result.status != "unexpected_effect"
    assert result.status == "expected_effect"
