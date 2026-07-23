"""US2: changed_since_last detection on fixed images."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from vnc_agent.perception.screen_diff import compute_diff, compute_diff_arrays


@pytest.fixture
def pair(tmp_path: Path):
    a = np.zeros((100, 100, 3), dtype=np.uint8)
    b = a.copy()
    b[40:60, 40:60] = 255
    pa = tmp_path / "a.png"
    pb = tmp_path / "b.png"
    cv2.imwrite(str(pa), a)
    cv2.imwrite(str(pb), b)
    return pa, pb


def test_no_change(tmp_path: Path):
    a = np.zeros((50, 50, 3), dtype=np.uint8)
    p1 = tmp_path / "1.png"
    p2 = tmp_path / "2.png"
    cv2.imwrite(str(p1), a)
    cv2.imwrite(str(p2), a.copy())
    changed, regions, ratio, local_blobs = compute_diff(p1, p2, threshold=0.02)
    assert changed is False
    assert ratio < 0.02
    assert local_blobs == []


def test_has_change(pair):
    pa, pb = pair
    changed, regions, ratio, local_blobs = compute_diff(pa, pb, threshold=0.01)
    assert changed is True
    assert ratio > 0
    assert local_blobs


def test_diff_array_entry_ndarray_no_path_read(tmp_path: Path, monkeypatch):
    """Feature 004 (T029/T036): diff must accept already-decoded ndarrays
    directly and never read from disk; an exact pixel-identical pair
    returns ratio=0 with empty regions/blobs (perception-cache-contract.md
    "Diff special case")."""
    a = np.zeros((50, 50, 3), dtype=np.uint8)
    b = a.copy()

    read_calls = {"n": 0}
    real_imread = cv2.imread

    def counting_imread(*args, **kwargs):
        read_calls["n"] += 1
        return real_imread(*args, **kwargs)

    monkeypatch.setattr(cv2, "imread", counting_imread)
    changed, regions, ratio, local_blobs = compute_diff_arrays(a, b, threshold=0.02)
    assert changed is False
    assert ratio == 0.0
    assert regions == []
    assert local_blobs == []
    assert read_calls["n"] == 0, "compute_diff_arrays must never read from disk"
