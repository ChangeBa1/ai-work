from pathlib import Path

from vnc_agent.perception.ocr.engine import run_ocr

run_id = "0272602d-af55-49f8-a645-84a4736aa4a8"
base = Path(f"artifacts/runs/{run_id}/bundles")
frames = [
    "3741592a-d1d9-4bab-8359-efc094461f7a",  # after subtotal
    "c2a63ea6-6ddf-469a-b9e8-52a46724a2e0",  # after enter
    "82f6d731-5b29-403b-94e6-5141dfc266d7",  # apply before1
    "815f6a7f-ba54-4793-acf1-fbe791bd93c4",  # apply before2
]
out = []
for name in frames:
    p = base / name / "safe_evidence.png"
    out.append(f"=== {name} exists={p.exists()}")
    if not p.exists():
        continue
    items = run_ocr(str(p))
    out.append("ALL: " + " | ".join(i.text for i in items))
    for i in items:
        box = getattr(i, "bbox", None) or getattr(i, "box", None) or getattr(i, "region", None)
        if box is None and hasattr(i, "model_dump"):
            d = i.model_dump()
            box = d.get("bbox") or d.get("box") or d.get("region") or d
        out.append(f"  {i.text!r} box={box}")
out_path = Path("artifacts/_ocr_0272602d.txt")
out_path.write_text("\n".join(out), encoding="utf-8")
print(f"wrote {out_path}")
