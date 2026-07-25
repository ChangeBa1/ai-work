"""OCR failed-frame and check needles used by old vs new testcase."""
from __future__ import annotations

from pathlib import Path

from vnc_agent.perception.ocr.engine import run_ocr, run_ocr_array
from vnc_agent.verification.ocr_verifier import verify_text
from vnc_agent.domain.verification import VerificationCondition
from vnc_agent.domain.observation import StructuredScreen, ScreenFrame, OCRItem
from datetime import datetime, timezone
import uuid
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parent
IMG = (
    ROOT
    / "runs"
    / "bb9f039e-f5f3-4437-abd6-af251b47997a"
    / "bundles"
    / "549b7950-d071-48da-a871-c4faf5166f37"
    / "safe_evidence.png"
)
OUT = ROOT / "ocr-probe-failed-frame.txt"


def check(items: list[OCRItem], needles: list[str]) -> list[str]:
    lines = []
    screen = StructuredScreen(
        frame=ScreenFrame(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            image_path=str(IMG),
            width=1024,
            height=768,
        ),
        ocr_items=items,
    )
    for n in needles:
        st = verify_text(VerificationCondition(type="text_appears", value=n), screen)
        lines.append(f"  text_appears:{n!r} -> {st}")
    return lines


def main() -> None:
    lines: list[str] = [f"img={IMG}", f"exists={IMG.exists()}"]
    items_path = run_ocr(IMG)
    lines.append(f"path_ocr n={len(items_path)}")
    for it in items_path:
        lines.append(f"  [{it.confidence:.2f}] {it.text!r} bbox={it.bbox}")

    bgr = cv2.imread(str(IMG), cv2.IMREAD_COLOR)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    items_bgr = run_ocr_array(bgr)
    items_rgb = run_ocr_array(rgb)
    lines.append(f"\nbgr_ocr n={len(items_bgr)} rgb_ocr n={len(items_rgb)}")

    old_needles = ["1", "5", "袋"]
    new_needles = ["単価", "点数", "内税", "レジ袋", "1個"]
    lines.append("\nPATH API vs OLD needles:")
    lines.extend(check(items_path, old_needles))
    lines.append("PATH API vs NEW needles:")
    lines.extend(check(items_path, new_needles))
    lines.append("BGR API vs NEW needles:")
    lines.extend(check(items_bgr, new_needles))
    lines.append("RGB API vs NEW needles:")
    lines.extend(check(items_rgb, new_needles))

    # fuzzy: anything containing 単 or 価
    lines.append("\nFUZZY contains 単/価/点/税:")
    for it in items_path:
        if any(ch in it.text for ch in ("単", "価", "点", "税", "袋")):
            lines.append(f"  {it.text!r}")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
