"""OCR the after-click frame from failed run and check text_appears targets."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from vnc_agent.perception.ocr.engine import OCREngine
from vnc_agent.verification.ocr_verifier import verify_text
from vnc_agent.domain.verification import VerificationCondition
from vnc_agent.domain.observation import StructuredScreen, ScreenFrame
from datetime import datetime, timezone
import uuid

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

# also try old run after frame if present
OLD_CANDIDATES = list(
    (ROOT / "runs" / "a5a5ecd0-8d79-4cf6-9b16-ffdc2295b553").rglob("*.png")
)


def run_ocr(path: Path) -> tuple[list[str], str]:
    eng = OCREngine()
    # try path API
    if hasattr(eng, "recognize_path"):
        blocks = eng.recognize_path(str(path))
    elif hasattr(eng, "run"):
        blocks = eng.run(str(path))
    else:
        # discover methods
        methods = [m for m in dir(eng) if not m.startswith("_")]
        raise RuntimeError(f"unknown OCR API: {methods}")
    texts = []
    for b in blocks if isinstance(blocks, list) else getattr(blocks, "blocks", []):
        if isinstance(b, dict):
            texts.append(str(b.get("text") or b.get("value") or b))
        else:
            texts.append(getattr(b, "text", str(b)))
    joined = "\n".join(texts)
    return texts, joined


def main() -> None:
    lines: list[str] = []
    lines.append(f"image={IMG}")
    lines.append(f"exists={IMG.exists()}")
    eng = OCREngine()
    lines.append(f"ocr_engine_type={type(eng)}")
    lines.append(f"ocr_methods={[m for m in dir(eng) if not m.startswith('_')]}")

    # Prefer ndarray/path entry points used by production
    import inspect
    import numpy as np

    img = Image.open(IMG).convert("RGB")
    arr = np.array(img)
    lines.append(f"arr_shape={arr.shape}")

    result = None
    for name in ("recognize_ndarray", "recognize", "run_ndarray", "run", "extract", "ocr"):
        fn = getattr(eng, name, None)
        if fn is None:
            continue
        lines.append(f"trying {name} sig={inspect.signature(fn)}")
        try:
            result = fn(arr)
            lines.append(f"{name}(ndarray) OK type={type(result)}")
            break
        except TypeError as e:
            lines.append(f"{name}(ndarray) TypeError: {e}")
            try:
                result = fn(str(IMG))
                lines.append(f"{name}(path) OK type={type(result)}")
                break
            except Exception as e2:
                lines.append(f"{name}(path) fail: {e2}")
        except Exception as e:
            lines.append(f"{name} fail: {e}")

    if result is None:
        # try module-level
        lines.append("no method worked")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        print(OUT)
        return

    # normalize texts
    texts: list[str] = []
    if isinstance(result, list):
        for b in result:
            if isinstance(b, str):
                texts.append(b)
            elif isinstance(b, dict):
                texts.append(str(b.get("text") or ""))
            else:
                texts.append(str(getattr(b, "text", b)))
    elif hasattr(result, "texts"):
        texts = list(result.texts)
    elif hasattr(result, "blocks"):
        for b in result.blocks:
            texts.append(str(getattr(b, "text", b)))
    else:
        texts = [str(result)]

    joined = " | ".join(texts)
    lines.append(f"n_texts={len(texts)}")
    lines.append("ALL_TEXTS:")
    for t in texts:
        lines.append(f"  - {t!r}")

    targets = ["単価", "点数", "内税", "レジ袋", "1", "5", "袋", "1個"]
    lines.append("CONTAINS_CHECK:")
    for t in targets:
        lines.append(f"  {t!r} in joined -> {t in joined}")
        # also check any block contains
        any_block = any(t in x for x in texts)
        lines.append(f"  {t!r} in any block -> {any_block}")

    # also check old run frames OCR if available
    lines.append(f"\nOLD png count={len(OLD_CANDIDATES)}")
    for p in OLD_CANDIDATES[:5]:
        lines.append(f"  old: {p.relative_to(ROOT)}")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
