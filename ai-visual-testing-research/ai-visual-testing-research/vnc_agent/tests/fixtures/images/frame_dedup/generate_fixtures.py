"""Regenerate the deterministic frame-dedup fixture set + manifest.

Every image is derived from a fixed numpy pattern (no randomness, no
timestamps) so re-running this script is byte-for-byte idempotent — the
working tree must show no diff across consecutive runs.

Usage (from ``vnc_agent/``)::

    uv run python tests/fixtures/images/frame_dedup/generate_fixtures.py --check

``--check`` additionally asserts the cross-fixture invariants relied on by
feature 004 tests: same-pixels-different-encoding fixtures share
``content_hash`` but differ in ``fixture_file_sha256``; the single-pixel
variant differs in both.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

from vnc_agent.perception.pixel_identity import (  # noqa: E402
    canonical_pixel_format,
    pixel_content_hash,
)

OUT_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = OUT_DIR / "manifest.json"

FULL_W, FULL_H = 64, 48


def _baseline_pixels() -> np.ndarray:
    """Deterministic BGR gradient + fixed shapes — never random, never time-based."""
    img = np.zeros((FULL_H, FULL_W, 3), dtype=np.uint8)
    xs = np.arange(FULL_W, dtype=np.uint8)
    ys = np.arange(FULL_H, dtype=np.uint8)
    img[:, :, 0] = xs[np.newaxis, :] * 3  # B gradient
    img[:, :, 1] = ys[:, np.newaxis] * 4  # G gradient
    img[:, :, 2] = 128
    img[8:24, 8:24] = (0, 255, 0)
    img[30:40, 40:56] = (0, 0, 255)
    return img


def _single_pixel_changed(base: np.ndarray) -> np.ndarray:
    changed = base.copy()
    changed[0, 0] = (changed[0, 0].astype(int) + 1 % 256).astype(np.uint8)
    if tuple(changed[0, 0]) == tuple(base[0, 0]):
        changed[0, 0] = (255 - base[0, 0]).astype(np.uint8)
    return changed


def _masked(base: np.ndarray, rect: tuple[int, int, int, int]) -> np.ndarray:
    masked = base.copy()
    x1, y1, x2, y2 = rect
    masked[y1:y2, x1:x2] = 0
    return masked


def _grayscale(base: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)


def _encode_png(pixels: np.ndarray, *, compression: int) -> bytes:
    ok, buf = cv2.imencode(".png", pixels, [cv2.IMWRITE_PNG_COMPRESSION, compression])
    if not ok:
        raise RuntimeError("PNG encode failed")
    return buf.tobytes()


def _decode(png_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(png_bytes, dtype=np.uint8)
    decoded = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if decoded is None:
        raise RuntimeError("PNG decode failed")
    return decoded


def _record(name: str, png_bytes: bytes, pixels_for_hash: np.ndarray) -> dict:
    path = OUT_DIR / name
    path.write_bytes(png_bytes)
    decoded = _decode(png_bytes)
    assert np.array_equal(decoded, pixels_for_hash), f"{name}: decode mismatch"
    return {
        "file": name,
        "width": int(decoded.shape[1]),
        "height": int(decoded.shape[0]),
        "pixel_format": canonical_pixel_format(decoded),
        "fixture_file_sha256": hashlib.sha256(png_bytes).hexdigest(),
        "content_hash": pixel_content_hash(decoded),
    }


def generate() -> dict[str, dict]:
    base = _baseline_pixels()
    single_changed = _single_pixel_changed(base)
    roi = base[8:32, 8:32].copy()
    diff_resolution = cv2.resize(base, (FULL_W + 16, FULL_H + 16), interpolation=cv2.INTER_NEAREST)
    masked = _masked(base, (40, 30, 56, 40))
    gray = _grayscale(base)

    entries: dict[str, dict] = {}
    entries["baseline_full"] = _record(
        "baseline_full.png", _encode_png(base, compression=1), base
    )
    entries["baseline_full_alt_encoding"] = _record(
        "baseline_full_alt_encoding.png", _encode_png(base, compression=9), base
    )
    entries["single_pixel_changed"] = _record(
        "single_pixel_changed.png", _encode_png(single_changed, compression=1), single_changed
    )
    entries["roi_crop"] = _record("roi_crop.png", _encode_png(roi, compression=1), roi)
    entries["diff_resolution"] = _record(
        "diff_resolution.png", _encode_png(diff_resolution, compression=1), diff_resolution
    )
    entries["masked"] = _record("masked.png", _encode_png(masked, compression=1), masked)
    entries["grayscale"] = _record("grayscale.png", _encode_png(gray, compression=1), gray)

    entries["_meta"] = {
        "roi_rect_in_baseline": [8, 8, 32, 32],
        "mask_rect_in_baseline": [40, 30, 56, 40],
    }
    return entries


def check(entries: dict[str, dict]) -> None:
    same_encoding_diff = (
        entries["baseline_full"]["fixture_file_sha256"]
        != entries["baseline_full_alt_encoding"]["fixture_file_sha256"]
    )
    same_content = (
        entries["baseline_full"]["content_hash"]
        == entries["baseline_full_alt_encoding"]["content_hash"]
    )
    assert same_encoding_diff, "expected differing PNG bytes across encodings"
    assert same_content, "expected identical content_hash across encodings of same pixels"

    single_pixel_diff = (
        entries["baseline_full"]["content_hash"] != entries["single_pixel_changed"]["content_hash"]
    )
    assert single_pixel_diff, "single-pixel change must alter content_hash"

    roi_vs_baseline = (
        entries["roi_crop"]["content_hash"] != entries["baseline_full"]["content_hash"]
    )
    assert roi_vs_baseline, "ROI crop must not collide with full-screen content_hash"

    res_diff = (
        entries["diff_resolution"]["content_hash"] != entries["baseline_full"]["content_hash"]
    )
    assert res_diff, "different resolution must alter content_hash"

    fmt_diff = entries["grayscale"]["pixel_format"] != entries["baseline_full"]["pixel_format"]
    assert fmt_diff, "grayscale must have a distinct pixel_format"
    print("frame_dedup fixtures: all invariants OK")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    entries = generate()
    MANIFEST_PATH.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.check:
        check(entries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
