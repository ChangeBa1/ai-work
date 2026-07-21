"""Fixed-image template matching (FR-008)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from vnc_agent.domain.observation import Region, TemplateMatch


def match_template(
    image_path: str | Path,
    template_path: str | Path,
    *,
    template_id: str | None = None,
    threshold: float = 0.8,
    roi: Region | None = None,
) -> list[TemplateMatch]:
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    tmpl = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
    if img is None or tmpl is None:
        return []

    offset_x, offset_y = 0, 0
    if roi is not None:
        offset_x, offset_y = roi.x1, roi.y1
        img = img[roi.y1 : roi.y2, roi.x1 : roi.x2]
        if img.size == 0:
            return []

    if tmpl.shape[0] > img.shape[0] or tmpl.shape[1] > img.shape[1]:
        return []

    res = cv2.matchTemplate(img, tmpl, cv2.TM_CCOEFF_NORMED)
    locations = np.where(res >= threshold)
    h, w = tmpl.shape[:2]
    tid = template_id or Path(template_path).stem
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
                template_id=tid,
                bbox=(x + offset_x, y + offset_y, x + w + offset_x, y + h + offset_y),
                confidence=max(0.0, min(1.0, conf)),
            )
        )
    matches.sort(key=lambda m: m.confidence, reverse=True)
    return matches


def match_templates_in_dir(
    image_path: str | Path,
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
        results.extend(
            match_template(
                image_path, p, template_id=p.stem, threshold=threshold, roi=roi
            )
        )
    results.sort(key=lambda m: m.confidence, reverse=True)
    return results
