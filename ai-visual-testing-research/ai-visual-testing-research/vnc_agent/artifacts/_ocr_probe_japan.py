"""Feature 010 probe: default (ch) vs japan rec model over in-repo real frames.

Run from vnc_agent/:  uv run python artifacts/_ocr_probe_japan.py
Writes artifacts/ocr-japan-compare.txt (SC-001/SC-002 evidence).
"""

from __future__ import annotations

from pathlib import Path

from vnc_agent.perception.ocr import engine as ocr_engine
from vnc_agent.verification.ocr_verifier import normalize_ocr_text

ROOT = Path(__file__).resolve().parent
VNC_AGENT = ROOT.parent
OUT = ROOT / "ocr-japan-compare.txt"

FRAMES = [
    ROOT / "rescue-after-pos-confirm.png",
    ROOT / "_last_mixed.png",
    *sorted((ROOT / "probe_click").glob("*.png")),
    *sorted((ROOT / "probe_stale").glob("*.png")),
]

# Regression terms from real-run diagnostics (spec SC-001)
TERMS = ["預り金", "単価", "レジ袋", "お釣り", "確定", "小計", "合計", "売上"]


def ocr_frame(path: Path):
    return ocr_engine.run_ocr(path)


def term_hits(items) -> dict[str, bool]:
    hays = [normalize_ocr_text(i.text) for i in items]
    joined = "".join(hays)
    out = {}
    for t in TERMS:
        needle = normalize_ocr_text(t)
        out[t] = any(needle in h for h in hays) or needle in joined
    return out


def run_pass(label: str, lang: str | None, lines: list[str]) -> dict[Path, dict[str, bool]]:
    if lang is None:
        ocr_engine.configure_ocr()
    else:
        ocr_engine.configure_ocr(lang=lang, base_dir=VNC_AGENT)
    ocr_engine.reset_engine()
    per_frame: dict[Path, dict[str, bool]] = {}
    for frame in FRAMES:
        if not frame.exists():
            continue
        items = ocr_frame(frame)
        hits = term_hits(items)
        per_frame[frame] = hits
        lines.append(f"\n--- [{label}] {frame.relative_to(ROOT)} ({len(items)} items) ---")
        for it in items:
            lines.append(f"  [{it.confidence:.2f}] {it.text!r} bbox={it.bbox}")
    return per_frame


def main() -> None:
    lines: list[str] = ["Feature 010: OCR default(ch) vs japan comparison", ""]
    default_res = run_pass("DEFAULT-ch", None, lines)
    japan_res = run_pass("JAPAN", "japan", lines)

    lines.append("\n\n===== PER-TERM SUMMARY (any-frame hit) =====")
    lines.append(f"{'term':<8} {'default':<8} {'japan':<8}")
    for t in TERMS:
        d = any(h[t] for h in default_res.values())
        j = any(h[t] for h in japan_res.values())
        lines.append(f"{t:<8} {str(d):<8} {str(j):<8}")

    lines.append("\n===== PER-FRAME PER-TERM =====")
    for frame in FRAMES:
        if frame not in default_res:
            continue
        lines.append(f"\n{frame.relative_to(ROOT)}:")
        for t in TERMS:
            lines.append(
                f"  {t}: default={default_res[frame][t]} japan={japan_res[frame][t]}"
            )

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)
    print("\n".join(lines[-40:]))


if __name__ == "__main__":
    main()
