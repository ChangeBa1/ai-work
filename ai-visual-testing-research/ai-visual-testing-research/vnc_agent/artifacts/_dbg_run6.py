import json
from pathlib import Path

p = list(Path("artifacts/runs").glob("c390b63d*/report.json"))[0]
r = json.loads(p.read_text(encoding="utf-8"))
print("status", r["status"])
for s in r["steps"]:
    print("==", s.get("step_id"), s.get("status"))
    for it in s.get("iterations") or []:
        sa = it.get("semantic_action") or {}
        ea = it.get("executable_action") or {}
        er = it.get("execution_result") or {}
        vr = it.get("verification_result") or {}
        print(
            " ",
            sa.get("action_type"),
            (sa.get("target") or {}).get("text"),
            "coords",
            ea.get("coordinates"),
            "region",
            ea.get("target_region"),
            "exec",
            er.get("success"),
            "ver",
            vr.get("status"),
        )
        print("  reason", (vr.get("reason") or "")[:180])
