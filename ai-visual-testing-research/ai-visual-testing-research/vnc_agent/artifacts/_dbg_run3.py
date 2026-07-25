import json
from pathlib import Path

p = list(Path("artifacts/runs").glob("81013c4b*/report.json"))[0]
r = json.loads(p.read_text(encoding="utf-8"))
print("status", r["status"])
for s in r["steps"]:
    print("==", s.get("step_id"), s.get("status"), s.get("failure_reason"))
    for it in s.get("iterations") or []:
        sa = it.get("semantic_action") or {}
        ea = it.get("executable_action") or {}
        er = it.get("execution_result") or {}
        vr = it.get("verification_result") or {}
        print(
            " ",
            sa.get("action_type"),
            (sa.get("target") or {}).get("text"),
            ea.get("coordinates"),
            "exec",
            er.get("success"),
            "ver",
            vr.get("status"),
        )
        print("  reason", (vr.get("reason") or "")[:200])
        print("  before", it.get("before_frame_path"))
        print("  after", it.get("after_frame_path"))

pngs = list(Path("artifacts/runs/81013c4b-2aaa-4151-b8ed-d081acbdb366/bundles").rglob("*.png"))
print("pngs", len(pngs))
for pp in sorted(pngs, key=lambda x: x.stat().st_mtime):
    print(pp)
