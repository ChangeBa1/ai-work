"""Phase 3 (T013) RED: single-decode DecodedCapture + canonical content hash.

Locks: one cv2.imdecode per capture, domain-separated SHA-256 preimage,
different-PNG-encoding-same-pixels ⇒ same content_hash, width/height/format/
single-pixel changes ⇒ different content_hash, and strict pixel equality
(shape/dtype + np.array_equal) survives an injected hash collision — hash is
only a candidate filter, never the final verdict.

capture kind / ROI coordinates / resolution / mask identity / private policy
are NOT part of the preimage — they are independent CaptureScope/cache-key
dimensions (data-model.md §2).
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import pytest

from vnc_agent.perception.screenshot import (
    CaptureDecodeError,
    DecodedCapture,
    decode_capture,
    pixels_strictly_equal,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "images" / "frame_dedup"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))


def _read(name: str) -> bytes:
    return (FIXTURES / MANIFEST[name]["file"]).read_bytes()


def test_decode_capture_decodes_exactly_once(monkeypatch):
    calls = {"n": 0}
    real_imdecode = cv2.imdecode

    def counting_imdecode(*args, **kwargs):
        calls["n"] += 1
        return real_imdecode(*args, **kwargs)

    monkeypatch.setattr(cv2, "imdecode", counting_imdecode)
    decode_capture(_read("baseline_full"))
    assert calls["n"] == 1


def test_decode_capture_pixels_are_read_only_and_c_contiguous():
    dc = decode_capture(_read("baseline_full"))
    assert isinstance(dc, DecodedCapture)
    assert dc.pixels.flags["C_CONTIGUOUS"]
    assert dc.pixels.flags["WRITEABLE"] is False


def test_decode_capture_content_hash_matches_fixture_manifest():
    dc = decode_capture(_read("baseline_full"))
    assert dc.content_hash == MANIFEST["baseline_full"]["content_hash"]
    assert dc.pixel_format == MANIFEST["baseline_full"]["pixel_format"]
    assert dc.width == MANIFEST["baseline_full"]["width"]
    assert dc.height == MANIFEST["baseline_full"]["height"]


def test_different_encoding_same_pixels_same_content_hash():
    a = decode_capture(_read("baseline_full"))
    b = decode_capture(_read("baseline_full_alt_encoding"))
    assert a.content_hash == b.content_hash
    # but the fixture generator proved fixture_file_sha256 differs
    assert (
        MANIFEST["baseline_full"]["fixture_file_sha256"]
        != MANIFEST["baseline_full_alt_encoding"]["fixture_file_sha256"]
    )


@pytest.mark.parametrize(
    "name",
    ["single_pixel_changed", "roi_crop", "diff_resolution", "grayscale"],
)
def test_pixel_or_shape_or_format_change_changes_content_hash(name):
    baseline = decode_capture(_read("baseline_full"))
    other = decode_capture(_read(name))
    assert baseline.content_hash != other.content_hash


def test_content_hash_excludes_scope_dimensions():
    """capture kind / coordinates / resolution / mask / private policy must
    never be mixed into the pixel preimage — same pixels ⇒ same hash
    regardless of what scope they were captured under."""
    dc_full = decode_capture(_read("baseline_full"))
    # Re-decoding identical bytes under a "different scope" conceptually
    # (the caller would attach a different CaptureScope) must not change
    # the pixel-only hash.
    dc_again = decode_capture(_read("baseline_full"))
    assert dc_full.content_hash == dc_again.content_hash


def test_pixels_strictly_equal_rejects_injected_hash_collision():
    a = decode_capture(_read("baseline_full"))
    b = decode_capture(_read("single_pixel_changed"))
    forged_b = DecodedCapture(
        pixels=b.pixels, pixel_format=b.pixel_format,
        content_hash=a.content_hash,  # forced collision
        width=b.width, height=b.height,
    )
    assert forged_b.content_hash == a.content_hash  # collision is real
    assert not pixels_strictly_equal(a, forged_b)  # but pixels still differ


def test_pixels_strictly_equal_true_for_identical_arrays():
    a = decode_capture(_read("baseline_full"))
    b = decode_capture(_read("baseline_full_alt_encoding"))
    assert pixels_strictly_equal(a, b)


def test_pixels_strictly_equal_false_for_different_shape():
    a = decode_capture(_read("baseline_full"))
    b = decode_capture(_read("diff_resolution"))
    assert not pixels_strictly_equal(a, b)


def test_decode_capture_raises_on_undecodable_bytes():
    with pytest.raises(CaptureDecodeError):
        decode_capture(b"not a png")


def test_decode_capture_raises_on_empty_bytes():
    with pytest.raises(CaptureDecodeError):
        decode_capture(b"")
