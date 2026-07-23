"""Fixed-image template matching (FR-008).

Feature 004: array-native entry points consume an already-decoded pixel
array; path-based entry points are offline-compatible wrappers over them.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np

from vnc_agent.domain.observation import Region, TemplateMatch


def match_template_array(
    img: np.ndarray,
    template: np.ndarray,
    *,
    template_id: str,
    threshold: float = 0.8,
    roi: Region | None = None,
) -> list[TemplateMatch]:
    offset_x, offset_y = 0, 0
    if roi is not None:
        offset_x, offset_y = roi.x1, roi.y1
        img = img[roi.y1 : roi.y2, roi.x1 : roi.x2]
        if img.size == 0:
            return []

    if template.shape[0] > img.shape[0] or template.shape[1] > img.shape[1]:
        return []

    res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(res >= threshold)
    h, w = template.shape[:2]
    matches: list[TemplateMatch] = []
    seen: set[tuple[int, int]] = set()
    for y, x in zip(*locations, strict=False):
        # Non-max: skip nearby duplicates
        key = (x // 8, y // 8)
        if key in seen:
            continue
        seen.add(key)
        conf = float(res[y, x])
        matches.append(
            TemplateMatch(
                template_id=template_id,
                bbox=(x + offset_x, y + offset_y, x + w + offset_x, y + h + offset_y),
                confidence=max(0.0, min(1.0, conf)),
            )
        )
    matches.sort(key=lambda m: m.confidence, reverse=True)
    return matches


def template_set_fingerprint(templates_dir: str | Path) -> str:
    """Stable content fingerprint of a template directory (perception-cache-
    contract.md "template" component identity) — never a path/mtime."""
    tdir = Path(templates_dir)
    if not tdir.is_dir():
        return hashlib.sha256(b"empty-template-set-v1").hexdigest()
    digest = hashlib.sha256()
    digest.update(b"template-set-v1")
    for p in sorted(tdir.glob("*.png")):
        digest.update(b"|")
        digest.update(p.name.encode("utf-8"))
        digest.update(b"|")
        digest.update(hashlib.sha256(p.read_bytes()).digest())
    return digest.hexdigest()


def match_templates_in_dir_array(
    img: np.ndarray,
    templates_dir: str | Path,
    *,
    threshold: float = 0.8,
    roi: Region | None = None,
) -> list[TemplateMatch]:
    tdir = Path(templates_dir)
    if not tdir.is_dir():
        return []
    results: list[TemplateMatch] = []
    for p in sorted(tdir.glob("*.png")):
        template = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if template is None:
            continue
        results.extend(
            match_template_array(img, template, template_id=p.stem, threshold=threshold, roi=roi)
        )
    results.sort(key=lambda m: m.confidence, reverse=True)
    return results


def match_template(
    image_path: str | Path,
    template_path: str | Path,
    *,
    template_id: str | None = None,
    threshold: float = 0.8,
    roi: Region | None = None,
) -> list[TemplateMatch]:
    """Offline-compatible path wrapper — see :func:`match_template_array`."""
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    tmpl = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
    if img is None or tmpl is None:
        return []
    tid = template_id or Path(template_path).stem
    return match_template_array(img, tmpl, template_id=tid, threshold=threshold, roi=roi)


def match_templates_in_dir(
    image_path: str | Path,
    templates_dir: str | Path,
    *,
    threshold: float = 0.8,
    roi: Region | None = None,
) -> list[TemplateMatch]:
    """Offline-compatible path wrapper — see :func:`match_templates_in_dir_array`."""
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img is None:
        return []
    return match_templates_in_dir_array(img, templates_dir, threshold=threshold, roi=roi)
