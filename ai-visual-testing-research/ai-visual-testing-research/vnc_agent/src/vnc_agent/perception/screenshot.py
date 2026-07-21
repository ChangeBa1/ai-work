"""Screenshot capture — raw pixels written immediately to disk (SC-009, FR-049)."""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from vnc_agent.domain.observation import ScreenFrame

if TYPE_CHECKING:
    from vnc_agent.drivers.base import VNCDriver


def apply_mask_to_png_bytes(
    raw_png: bytes, mask_regions: Sequence[Sequence[int]] | None
) -> bytes:
    """Return PNG bytes with mask_regions blacked out. No-op if no regions."""
    if not mask_regions:
        return raw_png
    import cv2
    import numpy as np

    arr = np.frombuffer(raw_png, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return raw_png
    for r in mask_regions:
        if len(r) != 4:
            continue
        x1, y1, x2, y2 = int(r[0]), int(r[1]), int(r[2]), int(r[3])
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 0), thickness=-1)
    ok, encoded = cv2.imencode(".png", img)
    if not ok:
        return raw_png
    return encoded.tobytes()


def _write_frame_pair(
    raw: bytes,
    *,
    run_id: str,
    artifacts_dir: str | Path,
    mask_regions: Sequence[Sequence[int]] | None,
) -> tuple[str, str, str]:
    """
    Persist local (masked) frame under frames/ and unmasked under frames_model/
    when mask_regions is non-empty (FR-049).

    Returns (frame_id, local_image_path, model_image_path).
    """
    frame_id = str(uuid.uuid4())
    base = Path(artifacts_dir) / "runs" / run_id
    frames_dir = base / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    local_path = frames_dir / f"{frame_id}.png"

    if mask_regions:
        model_dir = base / "frames_model"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / f"{frame_id}.png"
        # Unmasked for Planner/Grounder only
        model_path.write_bytes(raw)
        # Local persistence MUST be masked
        local_path.write_bytes(apply_mask_to_png_bytes(raw, mask_regions))
        return frame_id, str(local_path), str(model_path)

    local_path.write_bytes(raw)
    return frame_id, str(local_path), str(local_path)


async def capture_full_screen(
    driver: VNCDriver,
    *,
    run_id: str,
    step_id: str | None,
    artifacts_dir: str | Path,
    mask_regions: Sequence[Sequence[int]] | None = None,
) -> ScreenFrame:
    """Capture full screen, persist PNG, return metadata only (no raw bytes retained)."""
    raw = await driver.capture_screen()
    width, height = driver.resolution
    if width <= 0 or height <= 0:
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(raw))
            width, height = img.size
        except Exception:
            width, height = 0, 0

    frame_id, local_path, model_path = _write_frame_pair(
        raw, run_id=run_id, artifacts_dir=artifacts_dir, mask_regions=mask_regions
    )
    del raw

    return ScreenFrame(
        id=frame_id,
        run_id=run_id,
        step_id=step_id,
        image_path=local_path,
        width=width,
        height=height,
        timestamp=datetime.now(timezone.utc),
        crop_offset=(0, 0),
        model_image_path=model_path,
    )


async def capture_region(
    driver: VNCDriver,
    *,
    x: int,
    y: int,
    w: int,
    h: int,
    run_id: str,
    step_id: str | None,
    artifacts_dir: str | Path,
    mask_regions: Sequence[Sequence[int]] | None = None,
) -> ScreenFrame:
    """Capture a region; record crop offset relative to full frame (FR-005/009)."""
    raw = await driver.capture_region(x, y, w, h)
    # Shift mask regions into crop-local coordinates when masking a sub-region
    local_masks: list[list[int]] | None = None
    if mask_regions:
        local_masks = []
        for r in mask_regions:
            if len(r) != 4:
                continue
            x1, y1, x2, y2 = int(r[0]), int(r[1]), int(r[2]), int(r[3])
            # Intersect with crop window, then translate
            ix1, iy1 = max(x1, x), max(y1, y)
            ix2, iy2 = min(x2, x + w), min(y2, y + h)
            if ix1 < ix2 and iy1 < iy2:
                local_masks.append([ix1 - x, iy1 - y, ix2 - x, iy2 - y])

    frame_id, local_path, model_path = _write_frame_pair(
        raw, run_id=run_id, artifacts_dir=artifacts_dir, mask_regions=local_masks
    )
    del raw

    return ScreenFrame(
        id=frame_id,
        run_id=run_id,
        step_id=step_id,
        image_path=local_path,
        width=w,
        height=h,
        timestamp=datetime.now(timezone.utc),
        crop_offset=(x, y),
        model_image_path=model_path,
    )


def load_image_array(image_path: str | Path):
    """Load image from disk as numpy BGR array for OpenCV ops."""
    import cv2

    arr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if arr is None:
        raise FileNotFoundError(f"cannot read image: {image_path}")
    return arr
