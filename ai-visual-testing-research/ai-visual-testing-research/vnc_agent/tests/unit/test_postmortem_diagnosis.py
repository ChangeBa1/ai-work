"""Feature 023 (click-postmortem-correction): strict diagnosis parsing,
annotation rendering, undo (page-restore) decisions and the acceptance gates
(FR-001~FR-004 / SC-002)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
import pytest

from vnc_agent.config import MemoryConfig, WrongTargetPostmortemConfig
from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.domain.recovery import WrongTargetEvidence
from vnc_agent.models.postmortem_client import (
    PostmortemError,
    PostmortemParseError,
    StubPostmortemClient,
    parse_postmortem_diagnosis,
    resolve_corrected_bbox,
)
from vnc_agent.recovery.postmortem import (
    PostmortemDiagnostician,
    annotation_png_bytes,
    build_evidence_summary,
    click_distance_px,
    is_same_page_high,
    max_click_distance_px,
    render_click_annotation,
)
from vnc_agent.storage.artifact_store import ArtifactStore

RES = (300, 200)
TARGET = (100, 80, 200, 120)
CLICK = (150, 100)


# ------------------------------------------------------------- strict parse


def _diag_json(**overrides) -> str:
    data = {
        "clicked_element": "neighbor button",
        "target_found": True,
        "corrected_bbox": [200, 80, 260, 120],
        "coordinate_space": "pixel",
        "confidence": 0.9,
        "reason": "clicked the neighbor; target is to the right",
    }
    data.update(overrides)
    return json.dumps(data)


def test_parse_valid_pixel_diagnosis():
    diag = parse_postmortem_diagnosis(_diag_json())
    assert diag.target_found is True
    assert diag.corrected_bbox == (200, 80, 260, 120)
    assert diag.coordinate_space == "pixel"
    assert diag.confidence == 0.9
    assert resolve_corrected_bbox(diag, RES) == (200, 80, 260, 120)


def test_parse_valid_normalized_1000_diagnosis():
    diag = parse_postmortem_diagnosis(
        _diag_json(corrected_bbox=[500, 400, 800, 600], coordinate_space="normalized_1000")
    )
    # x: 500/1000*300=150, 800/1000*300=240; y: 400/1000*200=80, 600/1000*200=120
    assert resolve_corrected_bbox(diag, RES) == (150, 80, 240, 120)


def test_parse_chat_completion_envelope():
    raw = StubPostmortemClient.envelope(_diag_json())
    diag = parse_postmortem_diagnosis(raw)
    assert diag.target_found is True


def test_parse_target_not_found_without_bbox_is_valid():
    diag = parse_postmortem_diagnosis(
        _diag_json(target_found=False, corrected_bbox=None, coordinate_space=None)
    )
    assert diag.target_found is False
    assert resolve_corrected_bbox(diag, RES) is None


@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",
        json.dumps(["a", "list"]),
        _diag_json(target_found="__DEL__"),
        _diag_json(confidence="__DEL__"),
        _diag_json(confidence=1.7),
        _diag_json(corrected_bbox=[1, 2, 3]),
        _diag_json(corrected_bbox="whole screen"),
        _diag_json(corrected_bbox=None),  # found=true without bbox
        _diag_json(coordinate_space="percent"),
    ],
)
def test_parse_strict_failures(raw: str):
    if "__DEL__" in raw:
        data = json.loads(raw)
        data = {k: v for k, v in data.items() if v != "__DEL__"}
        raw = json.dumps(data)
    with pytest.raises(PostmortemParseError):
        parse_postmortem_diagnosis(raw)


def test_resolve_rejects_out_of_bounds_pixel_bbox():
    diag = parse_postmortem_diagnosis(_diag_json(corrected_bbox=[200, 80, 460, 120]))
    assert resolve_corrected_bbox(diag, RES) is None  # x2 > width, never clamped


def test_resolve_rejects_out_of_range_normalized_bbox():
    diag = parse_postmortem_diagnosis(
        _diag_json(corrected_bbox=[900, 400, 1200, 600], coordinate_space="normalized_1000")
    )
    assert resolve_corrected_bbox(diag, RES) is None


def test_resolve_undeclared_space_requires_unique_interpretation():
    # (100,80,200,120) is valid both as pixel and as normalized_1000 on a
    # 300x200 frame — ambiguous, strictly rejected (never guessed).
    diag = parse_postmortem_diagnosis(_diag_json(coordinate_space=None))
    assert resolve_corrected_bbox(diag, RES) is None
    # (400,300,600,500) only works as normalized_1000 — unique, accepted.
    diag2 = parse_postmortem_diagnosis(
        _diag_json(corrected_bbox=[400, 300, 600, 500], coordinate_space=None)
    )
    assert resolve_corrected_bbox(diag2, RES) == (120, 60, 180, 100)


# ------------------------------------------------------------- annotation


def _write_png(path: Path, img: np.ndarray) -> str:
    cv2.imwrite(str(path), img)
    return str(path)


def test_annotation_preserves_size_and_draws_markers(tmp_path: Path):
    src = np.zeros((200, 300, 3), dtype=np.uint8)
    path = _write_png(tmp_path / "after.png", src)
    annotated = render_click_annotation(path, click_point=CLICK, target_region=TARGET)
    assert annotated is not None
    # FR-001: exact original resolution — the answer must map 1:1 back.
    assert annotated.shape == src.shape
    # Target rectangle edge (orange) and click marker (red) actually drawn.
    assert tuple(annotated[80, 150]) == (0, 160, 255)  # top edge of TARGET
    assert tuple(annotated[100, 150 + 12]) == (0, 0, 255)  # circle radius point
    assert tuple(annotated[100, 150 + 17]) == (0, 0, 255)  # crosshair arm
    png = annotation_png_bytes(annotated)
    assert png is not None and png[:4] == b"\x89PNG"


def test_annotation_unreadable_image_returns_none(tmp_path: Path):
    assert (
        render_click_annotation(
            str(tmp_path / "missing.png"), click_point=CLICK, target_region=TARGET
        )
        is None
    )
    assert render_click_annotation("", click_point=CLICK, target_region=TARGET) is None


def test_evidence_summary_mentions_nearest_blob():
    ev = _evidence()
    text = build_evidence_summary(ev)
    assert "(20, 160, 80, 178)" in text
    assert "down_left" in text


# ------------------------------------------------------- distance helpers


def test_distance_helpers():
    assert click_distance_px((0, 0), (3, 4)) == 5.0
    assert max_click_distance_px(RES, 0.4) == 120.0


# ------------------------------------------------------- same-page decision


def _screen(
    tmp_path: Path,
    name: str,
    img: np.ndarray,
    *,
    ocr: list[OCRItem] | None = None,
) -> StructuredScreen:
    path = _write_png(tmp_path / name, img)
    return StructuredScreen(
        frame_id=name,
        resolution=(img.shape[1], img.shape[0]),
        captured_at=datetime.now(UTC),
        ocr_items=ocr or [],
        image_path=path,
    )


def _base_img() -> np.ndarray:
    """Busy app-like background: pHash on near-empty frames is dominated by
    any bright blob (all-black frames flip ~20/64 bits on a 60x18 change),
    which no real screenshot exhibits — realistic content keeps small local
    changes within the high-similarity tier, as designed (015 fingerprint)."""
    img = np.full((200, 300, 3), (230, 225, 220), dtype=np.uint8)
    img[0:24, 0:300] = (180, 120, 60)  # title bar
    img[24:40, 0:300] = (210, 205, 200)  # menu strip
    img[80:120, 100:200] = (60, 180, 60)  # target button
    img[80:120, 210:290] = (160, 160, 240)  # neighbor button
    img[140:190, 10:290] = (250, 250, 250)  # list panel
    for y in (150, 162, 174):
        img[y : y + 6, 16:200] = (120, 120, 120)
    return img


def _evidence(**overrides) -> WrongTargetEvidence:
    data = dict(
        suspected=True,
        target_region=TARGET,
        click_point=CLICK,
        global_diff_ratio=0.02,
        blob_count=1,
        blobs_intersecting_neighborhood=0,
        nearest_blob_bbox=(20, 160, 80, 178),
        nearest_blob_distance_px=120.0,
        nearest_blob_offset=(-100, 69),
        nearest_blob_direction="down_left",
        reason="all blobs miss the neighborhood",
    )
    data.update(overrides)
    return WrongTargetEvidence(**data)


def test_same_page_high_for_identical_frames(tmp_path: Path):
    ocr = [OCRItem(text="confirm", bbox=(110, 90, 190, 110), confidence=0.9)]
    a = _screen(tmp_path, "a.png", _base_img(), ocr=ocr)
    b = _screen(tmp_path, "b.png", _base_img(), ocr=list(ocr))
    same, score = is_same_page_high(a, b, MemoryConfig())
    assert same is True and score > 0.95


def test_different_page_not_high(tmp_path: Path):
    dialog = _base_img()
    dialog[40:150, 60:260] = (255, 255, 255)  # big dialog surface
    a = _screen(
        tmp_path,
        "a.png",
        _base_img(),
        ocr=[OCRItem(text="confirm", bbox=(110, 90, 190, 110), confidence=0.9)],
    )
    b = _screen(
        tmp_path,
        "b.png",
        dialog,
        ocr=[OCRItem(text="are you sure", bbox=(70, 60, 200, 80), confidence=0.9)],
    )
    same, _score = is_same_page_high(a, b, MemoryConfig())
    assert same is False


def test_resolution_mismatch_never_high(tmp_path: Path):
    a = _screen(tmp_path, "a.png", _base_img())
    b = _screen(tmp_path, "b.png", np.zeros((100, 150, 3), dtype=np.uint8))
    same, _ = is_same_page_high(a, b, MemoryConfig())
    assert same is False


# ------------------------------------------------------- diagnostician gates


def _diagnostician(
    tmp_path: Path,
    client,
    *,
    cfg: WrongTargetPostmortemConfig | None = None,
) -> PostmortemDiagnostician:
    return PostmortemDiagnostician(
        run_id="run-pm",
        artifact_store=ArtifactStore(tmp_path / "artifacts"),
        client=client,
        postmortem_cfg=cfg or WrongTargetPostmortemConfig(),
        memory_cfg=MemoryConfig(),
        click_edge_inset_ratio=0.15,
    )


async def _no_undo() -> bool:  # pragma: no cover - must not be called
    raise AssertionError("undo must not run on a same-page post-mortem")


async def _no_reobserve() -> StructuredScreen:  # pragma: no cover
    raise AssertionError("reobserve must not run on a same-page post-mortem")


def _run_kwargs(before: StructuredScreen, after: StructuredScreen, **overrides):
    kwargs = dict(
        step_id="s1",
        iteration_index=0,
        before_screen=before,
        after_screen=after,
        target={"text": "btn", "description": "confirm button"},
        evidence=_evidence(),
        send_undo=_no_undo,
        reobserve=_no_reobserve,
    )
    kwargs.update(overrides)
    return kwargs


@pytest.mark.asyncio
async def test_corrected_outcome_produces_plan_and_artifacts(tmp_path: Path):
    before = _screen(tmp_path, "before.png", _base_img())
    after_img = _base_img()
    after_img[160:178, 20:80] = (255, 255, 255)
    after = _screen(tmp_path, "after.png", after_img)
    client = StubPostmortemClient([StubPostmortemClient.envelope(_diag_json())])
    diag = _diagnostician(tmp_path, client)

    result = await diag.run(**_run_kwargs(before, after))

    assert result.audit.outcome == "corrected"
    assert result.plan is not None
    assert result.plan.corrected_bbox == (200, 80, 260, 120)
    # safe_click_point of (200,80,260,120) with no siblings = center.
    assert result.plan.click_point == (230, 100)
    assert result.audit.corrected_click_point == (230, 100)
    assert result.audit.distance_px == pytest.approx(80.0)
    assert result.audit.max_distance_px == pytest.approx(120.0)
    assert result.audit.undo_performed is False
    assert result.undo_attempt is None
    # Artifacts under the run's model/ directory, annotation at source size.
    assert result.audit.annotated_image_ref is not None
    annotated = cv2.imread(result.audit.annotated_image_ref)
    assert annotated.shape == after_img.shape
    assert Path(result.audit.request_ref).is_file()
    assert Path(result.audit.response_ref).is_file()
    assert "model" in Path(result.audit.annotated_image_ref).parts
    # The model saw the annotated post-click frame + the pre-click frame.
    assert len(client.calls) == 1
    assert client.calls[0].before_image_ref == before.image_path
    assert client.calls[0].resolution == RES


@pytest.mark.asyncio
async def test_low_confidence_refuses(tmp_path: Path):
    before = _screen(tmp_path, "before.png", _base_img())
    after = _screen(tmp_path, "after.png", _base_img())
    client = StubPostmortemClient(
        [StubPostmortemClient.envelope(_diag_json(confidence=0.5))]
    )
    result = await _diagnostician(tmp_path, client).run(**_run_kwargs(before, after))
    assert result.audit.outcome == "low_confidence"
    assert result.plan is None
    assert result.audit.corrected_bbox == (200, 80, 260, 120)  # evidence kept
    assert result.audit.confidence == 0.5


@pytest.mark.asyncio
async def test_distance_gate_refuses_far_correction(tmp_path: Path):
    before = _screen(tmp_path, "before.png", _base_img())
    after = _screen(tmp_path, "after.png", _base_img())
    client = StubPostmortemClient([StubPostmortemClient.envelope(_diag_json())])
    cfg = WrongTargetPostmortemConfig(max_click_distance_ratio=0.1)  # limit 30px
    result = await _diagnostician(tmp_path, client, cfg=cfg).run(
        **_run_kwargs(before, after)
    )
    assert result.audit.outcome == "distance_exceeded"
    assert result.plan is None
    assert result.audit.distance_px == pytest.approx(80.0)
    assert result.audit.max_distance_px == pytest.approx(30.0)


@pytest.mark.asyncio
async def test_target_not_found_refuses(tmp_path: Path):
    before = _screen(tmp_path, "before.png", _base_img())
    after = _screen(tmp_path, "after.png", _base_img())
    client = StubPostmortemClient(
        [
            StubPostmortemClient.envelope(
                _diag_json(target_found=False, corrected_bbox=None, coordinate_space=None)
            )
        ]
    )
    result = await _diagnostician(tmp_path, client).run(**_run_kwargs(before, after))
    assert result.audit.outcome == "target_not_found"
    assert result.plan is None


@pytest.mark.asyncio
async def test_parse_failure_refuses(tmp_path: Path):
    before = _screen(tmp_path, "before.png", _base_img())
    after = _screen(tmp_path, "after.png", _base_img())
    client = StubPostmortemClient([StubPostmortemClient.envelope("garbage not json")])
    result = await _diagnostician(tmp_path, client).run(**_run_kwargs(before, after))
    assert result.audit.outcome == "diagnosis_failed"
    assert "strict parse failed" in result.audit.reason
    assert result.plan is None


@pytest.mark.asyncio
async def test_invalid_bbox_refuses(tmp_path: Path):
    before = _screen(tmp_path, "before.png", _base_img())
    after = _screen(tmp_path, "after.png", _base_img())
    client = StubPostmortemClient(
        [StubPostmortemClient.envelope(_diag_json(corrected_bbox=[200, 80, 460, 120]))]
    )
    result = await _diagnostician(tmp_path, client).run(**_run_kwargs(before, after))
    assert result.audit.outcome == "diagnosis_failed"
    assert "rejected by strict resolution" in result.audit.reason


@pytest.mark.asyncio
async def test_client_error_refuses(tmp_path: Path):
    before = _screen(tmp_path, "before.png", _base_img())
    after = _screen(tmp_path, "after.png", _base_img())
    client = StubPostmortemClient([PostmortemError("boom")])
    result = await _diagnostician(tmp_path, client).run(**_run_kwargs(before, after))
    assert result.audit.outcome == "diagnosis_failed"
    assert "diagnosis call failed" in result.audit.reason


# ----------------------------------------------------------- undo decisions


def _dialog_img() -> np.ndarray:
    img = _base_img()
    img[40:150, 60:260] = (255, 255, 255)
    return img


@pytest.mark.asyncio
async def test_undo_restores_page_then_diagnosis_proceeds(tmp_path: Path):
    ocr = [OCRItem(text="confirm", bbox=(110, 90, 190, 110), confidence=0.9)]
    before = _screen(tmp_path, "before.png", _base_img(), ocr=ocr)
    after = _screen(
        tmp_path,
        "after.png",
        _dialog_img(),
        ocr=[OCRItem(text="unexpected dialog", bbox=(70, 60, 220, 80), confidence=0.9)],
    )
    restored = _screen(tmp_path, "restored.png", _base_img(), ocr=list(ocr))

    undo_calls: list[bool] = []

    async def _send_undo() -> bool:
        undo_calls.append(True)
        return True

    async def _reobserve() -> StructuredScreen:
        return restored

    client = StubPostmortemClient([StubPostmortemClient.envelope(_diag_json())])
    result = await _diagnostician(tmp_path, client).run(
        **_run_kwargs(before, after, send_undo=_send_undo, reobserve=_reobserve)
    )
    assert undo_calls == [True]
    assert result.undo_attempt is not None
    assert result.undo_attempt.strategy == "postmortem_undo"
    assert result.undo_attempt.resolved is True
    assert result.audit.undo_performed is True
    assert result.audit.undo_restored_page is True
    assert result.audit.outcome == "corrected"
    assert result.plan is not None


@pytest.mark.asyncio
async def test_undo_not_restored_aborts_without_model_call(tmp_path: Path):
    before = _screen(
        tmp_path,
        "before.png",
        _base_img(),
        ocr=[OCRItem(text="confirm", bbox=(110, 90, 190, 110), confidence=0.9)],
    )
    after = _screen(
        tmp_path,
        "after.png",
        _dialog_img(),
        ocr=[OCRItem(text="unexpected dialog", bbox=(70, 60, 220, 80), confidence=0.9)],
    )

    async def _send_undo() -> bool:
        return True

    async def _reobserve() -> StructuredScreen:
        return after  # dialog stays

    client = StubPostmortemClient([StubPostmortemClient.envelope(_diag_json())])
    result = await _diagnostician(tmp_path, client).run(
        **_run_kwargs(before, after, send_undo=_send_undo, reobserve=_reobserve)
    )
    assert result.audit.outcome == "page_not_restored"
    assert result.plan is None
    assert result.undo_attempt is not None and result.undo_attempt.resolved is False
    assert result.audit.undo_performed is True
    assert result.audit.undo_restored_page is False
    # Fail-safe red line: no model call, no response artifact.
    assert client.calls == []
    assert result.audit.response_ref is None


@pytest.mark.asyncio
async def test_missing_evidence_geometry_refuses(tmp_path: Path):
    before = _screen(tmp_path, "before.png", _base_img())
    after = _screen(tmp_path, "after.png", _base_img())
    client = StubPostmortemClient([StubPostmortemClient.envelope(_diag_json())])
    result = await _diagnostician(tmp_path, client).run(
        **_run_kwargs(before, after, evidence=_evidence(click_point=None))
    )
    assert result.audit.outcome == "diagnosis_failed"
    assert client.calls == []
