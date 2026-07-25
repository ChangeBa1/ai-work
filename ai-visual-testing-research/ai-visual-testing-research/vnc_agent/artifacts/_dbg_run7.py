import json
from pathlib import Path

p = list(Path("artifacts/runs").glob("c1141e67*/report.json"))[0]
r = json.loads(p.read_text(encoding="utf-8"))
print("status", r["status"])
print("tags", r.get("declared_tag_counts"))
for s in r["steps"]:
    print("==", s.get("step_id"), s.get("status"))
    if s.get("failure_reason"):
        print("  FAIL", (s.get("failure_reason") or "")[:200])
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
            ea.get("coordinates") or er.get("actual_click_point"),
            "region",
            ea.get("target_region"),
            "exec",
            er.get("success"),
            "ver",
            vr.get("status"),
        )
        if vr.get("reason"):
            print("  r", (vr.get("reason") or "")[:160])
