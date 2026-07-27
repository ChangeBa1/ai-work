"""Feature 015: PageElementMemory persistence semantics (spec FR-003/004/005/008, SC-004).

Covers: element upsert statistics, the consecutive-success template-refresh
policy (Clarification 4), the per-page cap eviction (Clarification 8), the
mask-intersection write refusal (FR-005) and lookup tiers/exclusion.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
import pytest

from vnc_agent.config import MemoryConfig
from vnc_agent.domain.observation import OCRItem, Region, StructuredScreen
from vnc_agent.memory.service import PageElementMemory
from vnc_agent.storage.database import init_db, make_engine, make_session_factory
from vnc_agent.storage.repositories import MemoryRepository

_RESOLUTION = (300, 200)
_TARGET = Region(x1=150, y1=85, x2=170, y2=95)


def _frame(seed_shift: int = 0) -> np.ndarray:
    """Deterministic page image; ``seed_shift`` only perturbs the small target
    patch (same page identity, slightly different element appearance)."""
    xx, yy = np.meshgrid(np.arange(_RESOLUTION[0]), np.arange(_RESOLUTION[1]))
    channel = ((xx * 3 + yy * 11) % 199).astype(np.uint8)
    frame = np.stack([channel, channel[::-1], 255 - channel], axis=-1).astype(np.uint8)
    # distinctive target pattern
    px, py = np.meshgrid(np.arange(20), np.arange(10))
    pat = ((px * 23 + py * 57 + seed_shift) % 256).astype(np.uint8)
    frame[85:95, 150:170] = np.stack([pat, 255 - pat, pat // 2], axis=-1)
    return frame


def _screen(tmp_path: Path, name: str, frame: np.ndarray | None = None) -> StructuredScreen:
    frame = _frame() if frame is None else frame
    path = tmp_path / f"{name}.png"
    cv2.imwrite(str(path), frame)
    return StructuredScreen(
        frame_id=name,
        resolution=_RESOLUTION,
        captured_at=datetime.now(UTC),
        ocr_items=[
            OCRItem(text="TOTAL", bbox=(100, 80, 160, 96), confidence=0.9),
            OCRItem(text="MENU", bbox=(10, 10, 60, 26), confidence=0.9),
        ],
        image_path=str(path),
    )


@pytest.fixture
async def repo(tmp_path: Path) -> MemoryRepository:
    engine = make_engine(str(tmp_path / "mem.db"))
    await init_db(engine)
    return MemoryRepository(make_session_factory(engine))


def _service(
    repo: MemoryRepository,
    tmp_path: Path,
    *,
    mask_regions: list[list[int]] | None = None,
    **config_kwargs,
) -> PageElementMemory:
    return PageElementMemory(
        repo=repo,
        template_dir=tmp_path / "templates",
        config=MemoryConfig(**config_kwargs),
        mask_regions=mask_regions,
    )


async def test_first_success_writes_page_element_and_template(repo, tmp_path):
    svc = _service(repo, tmp_path)
    await svc.record_success(_screen(tmp_path, "f1"), "OK", _TARGET)

    pages = await repo.list_pages()
    assert len(pages) == 1
    assert pages[0].hit_count == 1
    elements = await repo.list_elements(pages[0].page_id)
    assert len(elements) == 1
    el = elements[0]
    assert el.target_label == "ok"
    assert el.bbox == _TARGET.as_tuple()
    assert el.success_count == 1 and el.consecutive_success_count == 1
    assert el.template_path is not None and Path(el.template_path).is_file()
    # anchors: nearest OCR texts, closest first
    assert el.anchor_texts[0] == "TOTAL"


async def test_repeat_success_updates_stats_and_refresh_policy(repo, tmp_path):
    svc = _service(repo, tmp_path, template_refresh_min_consecutive_successes=3)
    screen = _screen(tmp_path, "f1")
    await svc.record_success(screen, "OK", _TARGET)
    page_id = (await repo.list_pages())[0].page_id
    first = await repo.find_element(page_id, "ok")
    original_template = Path(first.template_path).read_bytes()

    # 2nd success with a *different-looking* frame: stats move, template kept.
    await svc.record_success(_screen(tmp_path, "f2", _frame(seed_shift=50)), "OK", _TARGET)
    el = await repo.find_element(page_id, "ok")
    assert el.success_count == 2 and el.consecutive_success_count == 2
    assert Path(el.template_path).read_bytes() == original_template

    # 3rd consecutive success: template refreshed, streak counter restarts.
    await svc.record_success(_screen(tmp_path, "f3", _frame(seed_shift=90)), "OK", _TARGET)
    el = await repo.find_element(page_id, "ok")
    assert el.success_count == 3
    assert el.consecutive_success_count == 0
    assert Path(el.template_path).read_bytes() != original_template

    # page stats accumulated, single page (same fingerprint tier)
    pages = await repo.list_pages()
    assert len(pages) == 1 and pages[0].hit_count == 3


async def test_failure_bumps_counter_and_resets_streak(repo, tmp_path):
    svc = _service(repo, tmp_path)
    await svc.record_success(_screen(tmp_path, "f1"), "OK", _TARGET)
    page_id = (await repo.list_pages())[0].page_id
    el = await repo.find_element(page_id, "ok")

    await svc.record_element_failure(el.element_id)
    el = await repo.find_element(page_id, "ok")
    assert el.failure_count == 1
    assert el.consecutive_success_count == 0


async def test_mask_intersection_refuses_element_write(repo, tmp_path):
    # Security red line (FR-005): target overlaps a sensitive mask region.
    svc = _service(repo, tmp_path, mask_regions=[[160, 90, 250, 150]])
    await svc.record_success(_screen(tmp_path, "f1"), "OK", _TARGET)

    pages = await repo.list_pages()
    assert len(pages) == 1  # page memory still recorded
    assert await repo.list_elements(pages[0].page_id) == []
    assert not (tmp_path / "templates").exists()


async def test_mask_elsewhere_does_not_refuse(repo, tmp_path):
    svc = _service(repo, tmp_path, mask_regions=[[0, 0, 50, 50]])
    await svc.record_success(_screen(tmp_path, "f1"), "OK", _TARGET)
    pages = await repo.list_pages()
    assert len(await repo.list_elements(pages[0].page_id)) == 1


async def test_per_page_cap_evicts_oldest(repo, tmp_path):
    svc = _service(repo, tmp_path, max_elements_per_page=2)
    screen = _screen(tmp_path, "f1")
    r1 = Region(x1=150, y1=85, x2=170, y2=95)
    r2 = Region(x1=10, y1=10, x2=40, y2=30)
    r3 = Region(x1=200, y1=100, x2=240, y2=130)
    await svc.record_success(screen, "A", r1)
    await svc.record_success(screen, "B", r2)
    await svc.record_success(screen, "C", r3)

    page_id = (await repo.list_pages())[0].page_id
    elements = await repo.list_elements(page_id)
    assert len(elements) == 2
    labels = {e.target_label for e in elements}
    assert labels == {"b", "c"}  # "a" had the oldest last_success_at
    assert await repo.find_element(page_id, "a") is None


async def test_lookup_high_hit_and_exclusion(repo, tmp_path):
    svc = _service(repo, tmp_path)
    screen = _screen(tmp_path, "f1")
    await svc.record_success(screen, "OK", _TARGET)

    hit = await svc.lookup(screen, "OK")
    assert hit is not None
    assert hit.level == "high"
    assert hit.matched_bbox == _TARGET.as_tuple()
    assert hit.template_score is not None and hit.template_score >= 0.99
    assert hit.page_similarity >= 0.88

    # per-step ban (FR-008): excluded element never comes back
    banned = await svc.lookup(screen, "OK", exclude_element_ids={hit.element.element_id})
    assert banned is None

    # unknown label
    assert await svc.lookup(screen, "UNKNOWN") is None
    # empty label
    assert await svc.lookup(screen, "") is None


async def test_lookup_missing_template_degrades_to_hint(repo, tmp_path):
    svc = _service(repo, tmp_path)
    screen = _screen(tmp_path, "f1")
    await svc.record_success(screen, "OK", _TARGET)
    page_id = (await repo.list_pages())[0].page_id
    el = await repo.find_element(page_id, "ok")
    Path(el.template_path).unlink()

    hit = await svc.lookup(screen, "OK")
    assert hit is not None
    assert hit.level == "medium"  # hint-only: no direct click without template proof
    assert hit.matched_bbox is None
    assert hit.element is not None and hit.element.bbox == _TARGET.as_tuple()


async def test_lookup_unreadable_frame_fails_open(repo, tmp_path):
    svc = _service(repo, tmp_path)
    screen = _screen(tmp_path, "f1")
    await svc.record_success(screen, "OK", _TARGET)
    broken = screen.model_copy(update={"image_path": str(tmp_path / "missing.png")})
    # phash component degrades; text/layout still match -> never crashes.
    result = await svc.lookup(broken, "OK")
    # fail-open contract: either a (non-direct) result or None, never an error
    if result is not None:
        assert result.matched_bbox is None
