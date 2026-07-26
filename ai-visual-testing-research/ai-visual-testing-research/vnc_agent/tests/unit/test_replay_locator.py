"""Feature 016 unit tests: pure locate chain (spec FR-006, SC-005)."""

from __future__ import annotations

import uuid

import numpy as np

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.memory import PageFingerprint
from vnc_agent.domain.observation import OCRItem
from vnc_agent.domain.replay import ReplayAnchor, ReplayStep, normalize_bbox
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.replay.locator import (
    locate_target,
    match_anchor_offset,
    semantic_target_label,
)

RESOLUTION = (300, 200)
TARGET_BBOX = (150, 85, 170, 95)


def _frame() -> np.ndarray:
    base = np.zeros((200, 300, 3), dtype=np.uint8)
    xx, yy = np.meshgrid(np.arange(20), np.arange(10))
    pat = ((xx * 23 + yy * 57) % 256).astype(np.uint8)
    base[85:95, 150:170] = np.stack([pat, 255 - pat, pat // 2], axis=-1)
    return base


def _template() -> np.ndarray:
    f = _frame()
    x1, y1, x2, y2 = TARGET_BBOX
    return f[y1:y2, x1:x2].copy()


def _step(**overrides) -> ReplayStep:
    data = dict(
        replay_step_id=str(uuid.uuid4()),
        step_id="s1",
        order_index=0,
        page_fingerprint=PageFingerprint(resolution=RESOLUTION),
        semantic_action=SemanticAction(
            action_id="a1",
            intent="click the OK button",
            action_type="click",
            target=TargetDescription(role="button", text="OK", description="ok"),
        ),
        preferred_method="mouse",
        anchors=[ReplayAnchor(text="TOTAL", bbox=(100, 80, 160, 96))],
        anchor_texts=["TOTAL"],
        bbox=TARGET_BBOX,
        normalized_bbox=normalize_bbox(TARGET_BBOX, RESOLUTION),
        expected=VerificationSpec(
            operator="all",
            conditions=[VerificationCondition(type="text_appears", value="DONE")],
        ),
        version=1,
    )
    data.update(overrides)
    return ReplayStep(**data)


def _locate(frame, ocr_items, step, template):
    return locate_target(
        frame,
        ocr_items,
        step,
        template,
        current_resolution=RESOLUTION,
        template_match_threshold=0.85,
        bbox_expand_ratio=0.5,
        anchor_offset_tolerance_px=8,
    )


class TestTemplateStage:
    def test_template_hit_wins_first(self):
        result = _locate(_frame(), [], _step(), _template())
        assert result is not None
        assert result.method == "template"
        assert result.bbox == TARGET_BBOX
        assert result.template_score is not None and result.template_score >= 0.85

    def test_flat_template_misses_and_falls_to_bbox(self):
        # A black frame gives the matcher nothing; the chain must degrade to
        # the same-resolution historical bbox stage.
        black = np.zeros((200, 300, 3), dtype=np.uint8)
        result = _locate(black, [], _step(), _template())
        assert result is not None
        assert result.method == "bbox"
        assert result.bbox == TARGET_BBOX


class TestAnchorStage:
    def test_unique_target_label_ocr_hit(self):
        ocr = [OCRItem(text="OK", bbox=(148, 84, 172, 96), confidence=0.9)]
        result = _locate(None, ocr, _step(), None)
        assert result is not None
        assert result.method == "anchor"
        assert result.bbox == (148, 84, 172, 96)

    def test_ambiguous_target_label_falls_past_anchor_stage(self):
        ocr = [
            OCRItem(text="OK", bbox=(148, 84, 172, 96), confidence=0.9),
            OCRItem(text="OK", bbox=(10, 10, 30, 20), confidence=0.9),
        ]
        step = _step(anchors=[], anchor_texts=[])
        # A non-unique label hit never locates via anchor — the chain
        # degrades to the same-resolution bbox stage.
        result = _locate(None, ocr, step, None)
        assert result is not None
        assert result.method == "bbox"
        assert result.bbox == TARGET_BBOX

    def test_anchor_offset_translation(self):
        # The page slid 10px right / 4px down: the anchor moved with it.
        # The anchor stage runs before the bbox stage, so the translated
        # box (not the recorded one) must win.
        ocr = [OCRItem(text="TOTAL", bbox=(110, 84, 170, 100), confidence=0.9)]
        result = _locate(None, ocr, _step(), None)
        assert result is not None
        assert result.method == "anchor"
        assert result.bbox == (160, 89, 180, 99)

    def test_inconsistent_anchor_offsets_abstain(self):
        anchors = [
            ReplayAnchor(text="TOTAL", bbox=(100, 80, 160, 96)),
            ReplayAnchor(text="MENU", bbox=(10, 10, 50, 26)),
        ]
        ocr = [
            OCRItem(text="TOTAL", bbox=(110, 84, 170, 100), confidence=0.9),  # +10,+4
            OCRItem(text="MENU", bbox=(60, 10, 100, 26), confidence=0.9),  # +50,0
        ]
        assert (
            match_anchor_offset(
                anchors, ocr, TARGET_BBOX, tolerance_px=8, resolution=RESOLUTION
            )
            is None
        )

    def test_offset_moving_bbox_off_screen_abstains(self):
        anchors = [ReplayAnchor(text="TOTAL", bbox=(100, 80, 160, 96))]
        ocr = [OCRItem(text="TOTAL", bbox=(250, 80, 299, 96), confidence=0.9)]
        assert (
            match_anchor_offset(
                anchors, ocr, TARGET_BBOX, tolerance_px=8, resolution=RESOLUTION
            )
            is None
        )


class TestBBoxStageAndGuards:
    def test_bbox_stage_requires_same_resolution(self):
        step = _step()
        result = locate_target(
            None,
            [],
            step,
            None,
            current_resolution=(600, 400),
            template_match_threshold=0.85,
            bbox_expand_ratio=0.5,
            anchor_offset_tolerance_px=8,
        )
        assert result is None  # never a cross-resolution direct click

    def test_direct_fallback_only_step_never_locates(self):
        step = _step(direct_fallback_only=True)
        assert _locate(_frame(), [], step, _template()) is None

    def test_semantic_target_label_prefers_text(self):
        sa = SemanticAction(
            action_id="a",
            intent="press",
            action_type="click",
            target=TargetDescription(text="OK", description="desc"),
        )
        assert semantic_target_label(sa) == "OK"
