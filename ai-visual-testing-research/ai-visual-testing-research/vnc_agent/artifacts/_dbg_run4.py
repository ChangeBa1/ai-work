import json
from pathlib import Path

p = list(Path("artifacts/runs").glob("94ef6cc3*/report.json"))[0]
r = json.loads(p.read_text(encoding="utf-8"))
print("status", r["status"])
for s in r["steps"]:
    print("==", s.get("step_id"), s.get("status"))
    for it in s.get("iterations") or []:
        sa = it.get("semantic_action") or {}
        ea = it.get("executable_action") or {}
        er = it.get("execution_result") or {}
        print(
            " ",
            sa.get("action_type"),
            (sa.get("target") or {}).get("text"),
            ea.get("coordinates"),
            er.get("success"),
            (it.get("verification_result") or {}).get("status"),
        )

# last frame OCR
from vnc_agent.perception.ocr.engine import run_ocr

pngs = sorted(
    Path("artifacts/runs/94ef6cc3-3ecc-4014-93af-5f70286a7e24/bundles").rglob("*.png"),
    key=lambda x: x.stat().st_mtime,
)
last = pngs[-1]
print("last", last)
items = run_ocr(str(last))
print(" | ".join(i.text for i in items))
