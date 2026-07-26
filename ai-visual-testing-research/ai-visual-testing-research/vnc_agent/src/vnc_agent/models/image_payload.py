"""Image payload encoding for model requests (Feature 018, model-image-downscale).

Two encoders live here, one per model role (Constitution Principle II):

- ``_image_url_content_part`` — the pre-018 passthrough (raw file bytes,
  mime guess, base64 data URI), moved verbatim from ``planner_client.py``.
  This is the **Grounder** path: the Grounder outputs pixel coordinates
  against the image it is shown, so its payload MUST stay byte-identical to
  the original screenshot file (spec FR-004). It doubles as the disabled /
  failure fallback for the planner path.
- ``planner_image_url_content_part`` — the **Planner** path
  (``describe_screen()`` and everything funnelling through it: Feature 008
  cached visual answers, Feature 011 reviews). The planner never outputs
  coordinates, so full resolution is wasted upload + model latency; the
  image is proportionally downscaled to ``max_width`` (never upscaled) and
  re-encoded as JPEG (FR-001).

Only geometry/encoding is transformed — *which* image (masked vs unmasked)
is sent remains the caller's decision, unchanged (FR-006).
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

import cv2


def _image_url_content_part(image_path: str) -> dict[str, Any]:
    """
    Read a local image file and return an OpenAI-compatible multimodal
    `image_url` content part with the bytes inlined as a base64 data URI.

    Wire-protocol fix (contracts/model-provider-contract.md, 2026-07-22):
    the model server cannot read our local filesystem, so `image_ref`
    MUST be resolved to actual bytes before being sent, never passed as a
    bare path string.
    """
    path = Path(image_path)
    data = path.read_bytes()
    mime, _ = mimetypes.guess_type(path.name)
    mime = mime or "image/png"
    b64 = base64.b64encode(data).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{b64}"},
    }


def planner_image_url_content_part(
    image_path: str,
    *,
    enabled: bool = True,
    max_width: int = 1024,
    jpeg_quality: int = 80,
) -> dict[str, Any]:
    """Planner-bound image content part (Feature 018, FR-001/FR-002).

    read → proportional downscale to at most ``max_width`` pixels wide
    (never upscale; height rounded, floored at 1 px) → JPEG at
    ``jpeg_quality`` → ``data:image/jpeg;base64,...`` part.

    ``enabled=False`` returns output byte-identical to the pre-018
    ``_image_url_content_part``. An undecodable file or a failed JPEG
    encode also falls back to that passthrough: the pre-018 code never
    decoded pixels, so a request that used to go out must keep going out —
    preprocessing must never turn a working model call into a hard error.
    """
    if not enabled:
        return _image_url_content_part(image_path)
    image = cv2.imread(image_path)
    if image is None:  # undecodable → passthrough fallback (FR-002)
        return _image_url_content_part(image_path)
    height, width = image.shape[:2]
    if width > max_width:
        new_height = max(1, round(height * max_width / width))
        image = cv2.resize(
            image, (max_width, new_height), interpolation=cv2.INTER_AREA
        )
    ok, buf = cv2.imencode(
        ".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)]
    )
    if not ok:  # encode failure → passthrough fallback (FR-002)
        return _image_url_content_part(image_path)
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
    }
