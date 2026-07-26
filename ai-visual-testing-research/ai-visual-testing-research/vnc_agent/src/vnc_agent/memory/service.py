"""Persistence-backed page/element memory facade (feature 015).

``PageElementMemory`` is the single entry point the runtime (and later
feature 016's replay player) uses:

- :meth:`lookup` — read-only retrieval for the grounding hot path
  (spec FR-006/FR-007, Clarification 7: never mutates statistics);
- :meth:`record_success` — post-verification write path (spec FR-004/FR-005);
- :meth:`record_element_failure` — failed-memory-click feedback (spec FR-008).

Every method is fail-open: any internal error degrades to "no memory"
(lookup) or "no write" (record_*) with a log line — the main run flow is
never affected (spec US1-4).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from vnc_agent.domain.memory import ElementMemory, MemoryLookupResult, PageMemory
from vnc_agent.domain.observation import OCRItem, Region, StructuredScreen
from vnc_agent.memory.fingerprint import build_page_fingerprint, page_similarity
from vnc_agent.memory.retrieval import (
    find_best_page,
    match_element_template,
    region_intersects_any,
)
from vnc_agent.runtime.telemetry import log_event

if TYPE_CHECKING:
    from vnc_agent.config import MemoryConfig
    from vnc_agent.storage.repositories import MemoryRepository

_MAX_ANCHOR_TEXTS = 5


def normalize_target_label(label: str) -> str:
    """Same normalization basis as the runtime's target hint."""
    return (label or "").strip().lower()


def _nearest_anchor_texts(
    ocr_items: list[OCRItem], region: Region, limit: int = _MAX_ANCHOR_TEXTS
) -> list[str]:
    cx, cy = region.center()

    def _distance(item: OCRItem) -> float:
        x1, y1, x2, y2 = item.bbox
        icx, icy = (x1 + x2) / 2, (y1 + y2) / 2
        return float((icx - cx) ** 2 + (icy - cy) ** 2)

    ranked = sorted(
        (i for i in ocr_items if i.text.strip()),
        key=lambda i: (_distance(i), i.text),
    )
    return [i.text for i in ranked[:limit]]


class PageElementMemory:
    """Facade over :class:`MemoryRepository` + on-disk template images."""

    def __init__(
        self,
        *,
        repo: MemoryRepository,
        template_dir: str | Path,
        config: MemoryConfig,
        mask_regions: list[list[int]] | None = None,
    ) -> None:
        self.repo = repo
        self.template_dir = Path(template_dir)
        self.config = config
        self.mask_regions = mask_regions or []

    # ------------------------------------------------------------------
    # read path (hot path + 016 extension point)
    # ------------------------------------------------------------------

    async def lookup(
        self,
        screen: StructuredScreen,
        target_label: str,
        *,
        exclude_element_ids: frozenset[str] | set[str] = frozenset(),
    ) -> MemoryLookupResult | None:
        """Retrieve memory evidence for (current screen, target label).

        Returns None when nothing usable was found (including every internal
        failure — fail-open). ``level=="high"`` + non-null ``matched_bbox``
        is the only direct-click authorization; ``level=="medium"`` (or high
        without template confirmation) is grounder-hint-only evidence
        (spec FR-006/FR-007). Read-only (spec Clarification 7).
        """
        try:
            return await self._lookup(screen, target_label, exclude_element_ids)
        except Exception as exc:  # fail-open red line (spec US2-3)
            log_event("memory_lookup_failed", error=str(exc))
            return None

    async def _lookup(
        self,
        screen: StructuredScreen,
        target_label: str,
        exclude_element_ids: frozenset[str] | set[str],
    ) -> MemoryLookupResult | None:
        label = normalize_target_label(target_label)
        if not label:
            return None
        frame = self._read_frame(screen.image_path)
        fingerprint = build_page_fingerprint(frame, screen.ocr_items, screen.resolution)
        pages = await self.repo.list_pages()
        page, score, level = find_best_page(
            fingerprint,
            pages,
            high=self.config.page_match_high,
            medium=self.config.page_match_medium,
            low=self.config.page_match_low,
        )
        if page is None or level in ("low", "none"):
            return None
        element = await self.repo.find_element(page.page_id, label)
        if element is None or element.element_id in exclude_element_ids:
            return None

        result = MemoryLookupResult(
            level="medium",
            page=page,
            page_similarity=score,
            element=element,
            template_score=None,
            matched_bbox=None,
        )
        if level != "high" or frame is None:
            return result

        template = self._read_template(element.template_path)
        if template is None:
            # Missing/lost template: degrade to hint-only evidence.
            return result
        matched = match_element_template(
            frame,
            template,
            element.bbox,
            expand_ratio=self.config.bbox_expand_ratio,
            threshold=self.config.template_match_threshold,
            resolution=screen.resolution,
        )
        if matched is None:
            return result
        bbox, template_score = matched
        return MemoryLookupResult(
            level="high",
            page=page,
            page_similarity=score,
            element=element,
            template_score=template_score,
            matched_bbox=bbox,
        )

    # ------------------------------------------------------------------
    # write path
    # ------------------------------------------------------------------

    async def record_success(
        self,
        screen: StructuredScreen,
        target_label: str,
        target_region: Region,
    ) -> None:
        """Persist memory for one verified-passed mouse action (spec FR-004).

        ``screen`` MUST be the pre-action observation (the frame the click
        was resolved on). Fail-open: any error is logged and swallowed.
        """
        try:
            await self._record_success(screen, target_label, target_region)
        except Exception as exc:
            log_event("memory_write_failed", error=str(exc))

    async def _record_success(
        self,
        screen: StructuredScreen,
        target_label: str,
        target_region: Region,
    ) -> None:
        label = normalize_target_label(target_label)
        if not label:
            return
        now = datetime.now(UTC)
        frame = self._read_frame(screen.image_path)
        fingerprint = build_page_fingerprint(frame, screen.ocr_items, screen.resolution)
        page = await self._upsert_page(fingerprint, screen.resolution, now)

        # Security red line (spec FR-005): a region touching a configured
        # sensitive mask never becomes a template — skip the element write.
        if region_intersects_any(target_region.as_tuple(), self.mask_regions):
            log_event(
                "memory_element_write_skipped_masked_region",
                target_label=label,
                region=target_region.as_tuple(),
            )
            return

        anchor_texts = _nearest_anchor_texts(screen.ocr_items, target_region)
        element = await self.repo.find_element(page.page_id, label)
        if element is None:
            await self._evict_if_full(page.page_id)
            element = ElementMemory(
                element_id=str(uuid.uuid4()),
                page_id=page.page_id,
                target_label=label,
                template_path=None,
                bbox=target_region.as_tuple(),
                anchor_texts=anchor_texts,
                success_count=1,
                failure_count=0,
                consecutive_success_count=1,
                last_success_at=now,
                created_at=now,
            )
            element.template_path = self._save_template(element.element_id, frame, target_region)
        else:
            element.success_count += 1
            element.consecutive_success_count += 1
            element.bbox = target_region.as_tuple()
            element.anchor_texts = anchor_texts
            element.last_success_at = now
            refresh_after = self.config.template_refresh_min_consecutive_successes
            if element.template_path is None or (
                element.consecutive_success_count >= refresh_after
            ):
                # Template refresh policy (spec Clarification 4): replace only
                # after N consecutive verified successes, then restart the
                # streak counter for the next refresh window.
                new_path = self._save_template(element.element_id, frame, target_region)
                if new_path is not None:
                    element.template_path = new_path
                    element.consecutive_success_count = 0
        await self.repo.save_element(element)

    async def record_element_failure(self, element_id: str) -> None:
        """A memory-derived click failed independent verification (FR-008)."""
        try:
            element = await self._get_element(element_id)
            if element is None:
                return
            element.failure_count += 1
            element.consecutive_success_count = 0
            await self.repo.save_element(element)
        except Exception as exc:
            log_event("memory_failure_write_failed", error=str(exc))

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    async def _get_element(self, element_id: str) -> ElementMemory | None:
        for page in await self.repo.list_pages():
            for element in await self.repo.list_elements(page.page_id):
                if element.element_id == element_id:
                    return element
        return None

    async def _upsert_page(
        self,
        fingerprint,
        resolution: tuple[int, int],
        now: datetime,
    ) -> PageMemory:
        """Spec Clarification 7: an existing page at >= high similarity with
        an equal resolution is *the same page* — bump stats, keep the stored
        fingerprint (stability over drift). Otherwise insert a new page."""
        pages = [p for p in await self.repo.list_pages() if tuple(p.resolution) == resolution]
        best: PageMemory | None = None
        best_score = 0.0
        for page in sorted(pages, key=lambda p: p.page_id):
            score = page_similarity(fingerprint, page.fingerprint)
            if best is None or score > best_score:
                best, best_score = page, score
        if best is not None and best_score >= self.config.page_match_high:
            best.hit_count += 1
            best.last_seen_at = now
            await self.repo.save_page(best)
            return best
        page = PageMemory(
            page_id=str(uuid.uuid4()),
            fingerprint=fingerprint,
            resolution=resolution,
            hit_count=1,
            last_seen_at=now,
            created_at=now,
        )
        await self.repo.save_page(page)
        return page

    async def _evict_if_full(self, page_id: str) -> None:
        """Deterministic per-page cap (spec Clarification 8): evict the
        element with the oldest last_success_at (nulls first, ties by
        element_id) before inserting a new one."""
        count = await self.repo.count_elements(page_id)
        if count < self.config.max_elements_per_page:
            return
        elements = await self.repo.list_elements(page_id)
        if not elements:
            return

        def _sort_key(e: ElementMemory):
            ts = e.last_success_at
            return (ts is not None, ts or datetime.min.replace(tzinfo=UTC), e.element_id)

        victim = sorted(elements, key=_sort_key)[0]
        if victim.template_path:
            Path(victim.template_path).unlink(missing_ok=True)
        await self.repo.delete_element(victim.element_id)
        log_event("memory_element_evicted", element_id=victim.element_id, page_id=page_id)

    def _read_frame(self, image_path: str) -> np.ndarray | None:
        if not image_path:
            return None
        img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        return img if img is not None and img.size else None

    def _read_template(self, template_path: str | None) -> np.ndarray | None:
        if not template_path:
            return None
        img = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
        return img if img is not None and img.size else None

    def _save_template(
        self, element_id: str, frame: np.ndarray | None, region: Region
    ) -> str | None:
        """Crop the masked-safe frame at ``region`` and persist it as the
        element's template (spec FR-004/FR-005 — the crop source is the safe
        frame, so masked pixels can never leak into memory storage)."""
        if frame is None:
            return None
        h, w = frame.shape[:2]
        x1, y1 = max(0, region.x1), max(0, region.y1)
        x2, y2 = min(w, region.x2), min(h, region.y2)
        if x1 >= x2 or y1 >= y2:
            return None
        crop = frame[y1:y2, x1:x2]
        self.template_dir.mkdir(parents=True, exist_ok=True)
        path = self.template_dir / f"{element_id}.png"
        if not cv2.imwrite(str(path), crop):
            return None
        return str(path)
