"""OCR failed-frame and check needles used by old vs new testcase."""
from __future__ import annotations

from pathlib import Path

import cv2

from vnc_agent.perception.ocr.engine import run_ocr, run_ocr_array

ROOT = Path(__file__).resolve().parent
IMG = (
    ROOT
    / "runs"
    / "bb9f039e-f5f3-4437-abd6-af251b47997a"
    / "bundles"
    / "549b7950-d071-48da-a871-c4faf5166f37"
    / "safe_evidence.png"
)
OLD_AFTER = (
    ROOT
    / "runs"
    / "a5a5ecd0-8d79-4cf6-9b16-ffdc2295b553"
    / "report_frames"
    / "add-shopping-bag_0_after.png"
)
OUT = ROOT / "ocr-probe-failed-frame.txt"


def appears(items, needle: str) -> bool:
    n = needle.strip().lower()
    return any(n in i.normalized_text or n in i.text.lower() for i in items)


def dump(label: str, items, lines: list[str]) -> None:
    lines.append(f"\n=== {label} n={len(items)} ===")
    for it in items:
        lines.append(f"  [{it.confidence:.2f}] {it.text!r} bbox={it.bbox}")
    old_needles = ["1", "5", "袋"]
    new_needles = ["単価", "点数", "内税", "レジ袋", "1個"]
    lines.append("OLD needles:")
    for n in old_needles:
        lines.append(f"  {n!r} -> {appears(items, n)}")
    lines.append("NEW needles:")
    for n in new_needles:
        lines.append(f"  {n!r} -> {appears(items, n)}")
    lines.append("FUZZY 単/価/点/税/袋:")
    for it in items:
        if any(ch in it.text for ch in ("単", "価", "点", "税", "袋", "個")):
            lines.append(f"  {it.text!r}")


def main() -> None:
    lines: list[str] = [f"img={IMG}", f"exists={IMG.exists()}"]
    items_path = run_ocr(IMG)
    dump("NEW failed after (path/cv2 BGR)", items_path, lines)

    bgr = cv2.imread(str(IMG), cv2.IMREAD_COLOR)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    dump("NEW failed after (explicit BGR)", run_ocr_array(bgr), lines)
    dump("NEW failed after (explicit RGB)", run_ocr_array(rgb), lines)

    if OLD_AFTER.exists():
        dump("OLD passed after (path)", run_ocr(OLD_AFTER), lines)
    else:
        lines.append(f"OLD after missing: {OLD_AFTER}")

    # HEAD vs worktree testcase assertion summary
    head = (ROOT / "head-testcase.yaml").read_text(encoding="utf-8", errors="replace")
    wt = Path(
        r"D:\ai-work\ai-work\ai-visual-testing-research\ai-visual-testing-research\vnc_agent\testcases\pos-buy-bag-checkout.yaml"
    ).read_text(encoding="utf-8")
    lines.append("\n=== TESTCASE HEAD first step conditions snippet ===")
    # extract expected block roughly
    for i, line in enumerate(head.splitlines()):
        if "add-shopping-bag" in line or "text_appears" in line or 'value:' in line:
            if i < 80:
                lines.append(line)
    lines.append("\n=== TESTCASE WORKTREE first step conditions ===")
    in_step = False
    for line in wt.splitlines():
        if "id: add-shopping-bag" in line:
            in_step = True
        if in_step:
            lines.append(line)
            if line.startswith("  - id:") and "add-shopping-bag" not in line:
                break
            if line.startswith("  - id: calc"):
                break

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
