"""US2: template matching on fixed images."""

from pathlib import Path

import cv2
import numpy as np

from vnc_agent.perception.template.matcher import (
    match_template,
    match_template_array,
    template_set_fingerprint,
)


def test_template_found(tmp_path: Path):
    canvas = np.zeros((200, 200, 3), dtype=np.uint8)
    # Distinctive non-uniform patch so NCC peaks at one location
    patch = np.zeros((30, 40, 3), dtype=np.uint8)
    for i in range(30):
        for j in range(40):
            patch[i, j] = ((i * 7 + j * 13) % 200 + 40, (i * 3) % 180, (j * 5) % 180)
    canvas[50:80, 60:100] = patch
    img = tmp_path / "img.png"
    tmpl = tmp_path / "tmpl.png"
    cv2.imwrite(str(img), canvas)
    cv2.imwrite(str(tmpl), patch)
    matches = match_template(img, tmpl, template_id="btn", threshold=0.8)
    assert matches
    assert matches[0].template_id == "btn"
    x1, y1, x2, y2 = matches[0].bbox
    assert abs(x1 - 60) < 5 and abs(y1 - 50) < 5


def test_template_array_entry_ndarray(tmp_path: Path, monkeypatch):
    """Feature 004 (T029/T035): template matching must accept already-decoded
    ndarrays directly, and template-set identity must be a content
    fingerprint, never a path/mtime (perception-cache-contract.md
    `template`)."""
    canvas = np.zeros((200, 200, 3), dtype=np.uint8)
    patch = np.zeros((30, 40, 3), dtype=np.uint8)
    for i in range(30):
        for j in range(40):
            patch[i, j] = ((i * 7 + j * 13) % 200 + 40, (i * 3) % 180, (j * 5) % 180)
    canvas[50:80, 60:100] = patch

    decode_calls = {"n": 0}
    real_imread = cv2.imread

    def counting_imread(*args, **kwargs):
        decode_calls["n"] += 1
        return real_imread(*args, **kwargs)

    monkeypatch.setattr(cv2, "imread", counting_imread)
    matches = match_template_array(canvas, patch, template_id="btn", threshold=0.8)
    assert matches
    assert matches[0].template_id == "btn"
    assert decode_calls["n"] == 0, "match_template_array must never decode from disk"

    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    cv2.imwrite(str(templates_dir / "btn.png"), patch)
    fp1 = template_set_fingerprint(templates_dir)
    fp2 = template_set_fingerprint(templates_dir)
    assert fp1 == fp2
    cv2.imwrite(str(templates_dir / "btn2.png"), patch)
    fp3 = template_set_fingerprint(templates_dir)
    assert fp3 != fp1, "adding a template must change the set fingerprint"
