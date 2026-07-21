"""US2: template matching on fixed images."""

from pathlib import Path

import cv2
import numpy as np

from vnc_agent.perception.template.matcher import match_template


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
