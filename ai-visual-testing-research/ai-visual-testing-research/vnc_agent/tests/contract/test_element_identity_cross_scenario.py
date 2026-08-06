"""SC-006: two unrelated GUI fixtures each get write→unique identity."""

from __future__ import annotations

from vnc_agent.domain.observation import OCRItem, Region
from vnc_agent.memory.identity import (
    resolve_identity_candidates_for_lookup,
    resolve_identity_for_write,
)


def _scenario(label: str, bbox: tuple[int, int, int, int], res=(400, 300)):
    ocr = OCRItem(text=label, bbox=bbox, confidence=0.95)
    region = Region(x1=bbox[0], y1=bbox[1], x2=bbox[2], y2=bbox[3])
    w = resolve_identity_for_write(
        region=region,
        ocr_items=[ocr],
        resolution=res,
        grid_size=16,
        schema_version="eid-v1",
    )
    assert w is not None
    q = resolve_identity_candidates_for_lookup(
        target_label=label,
        ocr_items=[ocr],
        resolution=res,
        grid_size=16,
        schema_version="eid-v1",
    )
    assert q.status == "unique"
    assert q.identity is not None
    assert q.identity.identity_key == w.identity_key
    return w.identity_key


def test_two_unrelated_scenarios_identity_roundtrip():
    k1 = _scenario("CHECKOUT", (20, 20, 80, 50))
    k2 = _scenario("UPLOAD", (200, 180, 280, 220))
    assert k1 != k2
    assert "checkout" in k1
    assert "upload" in k2
