"""Structured element identity (feature 025): normalize, grid, resolve.

Deterministic pure functions — no I/O, no model calls (Constitution I / FR-011).
Business-agnostic script rules only (Constitution VI).
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from vnc_agent.domain.observation import OCRItem, Region
from vnc_agent.memory.fingerprint import is_dynamic_token

IdentityStatus = Literal["unique", "ambiguous", "insufficient", "error"]

BBox = tuple[int, int, int, int]


@dataclass(frozen=True)
class ElementIdentity:
    schema_version: str
    grid_size: int
    normalized_visible_text: str
    geom_cell: str
    identity_key: str


@dataclass(frozen=True)
class IdentityResolutionResult:
    status: IdentityStatus
    candidates: list[ElementIdentity]
    identity: ElementIdentity | None
    elapsed_ms: float = 0.0


def normalize_visible_text(text: str | None) -> str:
    """Research R4 pipeline (order fixed)."""
    if text is None or not isinstance(text, str):
        return ""
    s = unicodedata.normalize("NFKC", text)
    # Half-width dakuten/handakuten residual combine is mostly handled by NFKC.
    # Long vowel: fullwidth prolonged sound mark family → U+30FC; leave ASCII '-'.
    s = s.replace("\uff70", "\u30fc")  # halfwidth ｰ
    s = s.casefold()
    # Whitespace collapse
    parts = s.split()
    s = " ".join(parts)
    return s


def geom_cell_from_center(
    cx: float, cy: float, width: int, height: int, grid_size: int
) -> str:
    if width <= 0 or height <= 0:
        raise ValueError("width/height must be positive")
    if grid_size < 1:
        raise ValueError("grid_size must be >= 1")
    col = min(grid_size - 1, max(0, int(cx / width * grid_size)))
    row = min(grid_size - 1, max(0, int(cy / height * grid_size)))
    return f"{col},{row}"


def build_identity_key(
    *,
    schema_version: str,
    grid_size: int,
    normalized_visible_text: str,
    geom_cell: str,
) -> str:
    return f"{schema_version}:g{grid_size}|{normalized_visible_text}|{geom_cell}"


def current_identity_prefix(schema_version: str, grid_size: int) -> str:
    return f"{schema_version}:g{grid_size}"


def _bbox_center(bbox: BBox) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def _ocr_text(item: OCRItem) -> str:
    return item.text or item.normalized_text or ""


def _eligible_write_candidates(
    ocr_items: Sequence[OCRItem],
) -> list[tuple[str, BBox, OCRItem]]:
    out: list[tuple[str, BBox, OCRItem]] = []
    for item in ocr_items:
        raw = _ocr_text(item)
        norm = normalize_visible_text(raw)
        if not norm or is_dynamic_token(norm) or is_dynamic_token(raw.strip()):
            continue
        out.append((norm, item.bbox, item))
    return out


def _pick_write_ocr(
    region: Region, ocr_items: Sequence[OCRItem]
) -> tuple[str, BBox] | None:
    """Nearest eligible OCR to region center; tie-break by (norm_text, bbox)."""
    rcx, rcy = region.center()
    candidates = _eligible_write_candidates(ocr_items)
    if not candidates:
        return None

    def sort_key(c: tuple[str, BBox, OCRItem]) -> tuple:
        norm, bbox, _ = c
        ocx, ocy = _bbox_center(bbox)
        dist2 = (ocx - rcx) ** 2 + (ocy - rcy) ** 2
        return (dist2, norm, bbox)

    best = min(candidates, key=sort_key)
    return best[0], best[1]


def resolve_identity_for_write(
    *,
    region: Region,
    ocr_items: Sequence[OCRItem],
    resolution: tuple[int, int],
    grid_size: int,
    schema_version: str,
) -> ElementIdentity | None:
    picked = _pick_write_ocr(region, ocr_items)
    if picked is None:
        return None
    norm, bbox = picked
    cx, cy = _bbox_center(bbox)
    w, h = resolution
    cell = geom_cell_from_center(cx, cy, w, h, grid_size)
    key = build_identity_key(
        schema_version=schema_version,
        grid_size=grid_size,
        normalized_visible_text=norm,
        geom_cell=cell,
    )
    return ElementIdentity(
        schema_version=schema_version,
        grid_size=grid_size,
        normalized_visible_text=norm,
        geom_cell=cell,
        identity_key=key,
    )


def _whole_word_in_label(token: str, label: str) -> bool:
    """True if token appears as a contiguous substring of label (normalized)."""
    if not token or not label:
        return False
    if token == label:
        return True
    # Contiguous containment is enough for long planner phrases that include the label.
    return token in label


def resolve_identity_candidates_for_lookup(
    *,
    target_label: str,
    ocr_items: Sequence[OCRItem],
    resolution: tuple[int, int],
    grid_size: int,
    schema_version: str,
) -> IdentityResolutionResult:
    L = normalize_visible_text(target_label)
    if not L:
        return IdentityResolutionResult(status="insufficient", candidates=[], identity=None)

    w, h = resolution
    matched: list[ElementIdentity] = []
    seen_keys: set[str] = set()

    exact: list[tuple[str, BBox]] = []
    for item in ocr_items:
        raw = _ocr_text(item)
        norm = normalize_visible_text(raw)
        if norm == L:
            exact.append((norm, item.bbox))

    pool = exact
    if not pool:
        # Long label: unique longest whole-token OCR contained in L
        contained: list[tuple[str, BBox]] = []
        for item in ocr_items:
            raw = _ocr_text(item)
            norm = normalize_visible_text(raw)
            if not norm or is_dynamic_token(norm):
                continue
            if _whole_word_in_label(norm, L):
                contained.append((norm, item.bbox))
        if not contained:
            return IdentityResolutionResult(
                status="insufficient", candidates=[], identity=None
            )
        max_len = max(len(t[0]) for t in contained)
        longest = [c for c in contained if len(c[0]) == max_len]
        # Unique by normalized text among longest
        texts = {c[0] for c in longest}
        if len(texts) != 1:
            # Multiple different tokens of same max length → ambiguous extraction
            cands = []
            for norm, bbox in longest:
                cx, cy = _bbox_center(bbox)
                cell = geom_cell_from_center(cx, cy, w, h, grid_size)
                key = build_identity_key(
                    schema_version=schema_version,
                    grid_size=grid_size,
                    normalized_visible_text=norm,
                    geom_cell=cell,
                )
                if key not in seen_keys:
                    seen_keys.add(key)
                    cands.append(
                        ElementIdentity(
                            schema_version=schema_version,
                            grid_size=grid_size,
                            normalized_visible_text=norm,
                            geom_cell=cell,
                            identity_key=key,
                        )
                    )
            return IdentityResolutionResult(
                status="ambiguous", candidates=cands, identity=None
            )
        pool = longest

    for norm, bbox in pool:
        cx, cy = _bbox_center(bbox)
        cell = geom_cell_from_center(cx, cy, w, h, grid_size)
        key = build_identity_key(
            schema_version=schema_version,
            grid_size=grid_size,
            normalized_visible_text=norm,
            geom_cell=cell,
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        matched.append(
            ElementIdentity(
                schema_version=schema_version,
                grid_size=grid_size,
                normalized_visible_text=norm,
                geom_cell=cell,
                identity_key=key,
            )
        )

    if not matched:
        return IdentityResolutionResult(status="insufficient", candidates=[], identity=None)
    if len(matched) >= 2:
        return IdentityResolutionResult(
            status="ambiguous", candidates=matched, identity=None
        )
    return IdentityResolutionResult(
        status="unique", candidates=matched, identity=matched[0]
    )
