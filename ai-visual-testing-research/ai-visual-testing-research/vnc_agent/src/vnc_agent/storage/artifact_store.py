"""Artifact store with sensitive-region masking for local persistence (FR-049)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


class ArtifactStore:
    def __init__(
        self,
        root: str | Path,
        *,
        mask_regions: list[list[int]] | None = None,
    ) -> None:
        self.root = Path(root)
        self.mask_regions = mask_regions or []
        self.root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        d = self.root / "runs" / run_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_bytes(self, run_id: str, relative: str, data: bytes) -> str:
        path = self.run_dir(run_id) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def save_json(self, run_id: str, relative: str, obj: Any) -> str:
        path = self.run_dir(run_id) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(obj, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return str(path)

    def mask_image_file(self, image_path: str | Path, out_path: str | Path | None = None) -> str:
        """Apply mask_regions blackout for local/report use only (not model API)."""
        src = Path(image_path)
        img = cv2.imread(str(src), cv2.IMREAD_COLOR)
        if img is None:
            return str(src)
        for r in self.mask_regions:
            if len(r) != 4:
                continue
            x1, y1, x2, y2 = r
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 0), thickness=-1)
        dest = Path(out_path) if out_path else src.with_name(src.stem + "_masked" + src.suffix)
        dest.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(dest), img)
        return str(dest)

    def mask_png_bytes(self, raw_png: bytes) -> bytes:
        """Mask PNG bytes in-memory (used by screenshot capture for frames/)."""
        from vnc_agent.perception.screenshot import apply_mask_to_png_bytes

        return apply_mask_to_png_bytes(raw_png, self.mask_regions)

    def copy_masked_for_report(self, image_path: str | Path, run_id: str, name: str) -> str:
        """
        Copy frame into report_frames/. If the source is already under frames/
        (already masked at capture time per FR-049), just copy; otherwise mask.
        """
        dest = self.run_dir(run_id) / "report_frames" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        src = Path(image_path)
        # frames/ is the local-persistence path and is already masked when
        # mask_regions is configured; avoid double-masking.
        if "frames" in src.parts and "frames_model" not in src.parts and self.mask_regions:
            import shutil

            shutil.copy2(src, dest)
            return str(dest)
        return self.mask_image_file(image_path, dest)
