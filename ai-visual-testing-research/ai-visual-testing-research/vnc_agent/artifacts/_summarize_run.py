import json
import sys
from pathlib import Path

run_id = sys.argv[1] if len(sys.argv) > 1 else "bb9f039e-f5f3-4437-abd6-af251b47997a"
path = Path("artifacts/runs") / run_id / "report.json"
r = json.loads(path.read_text(encoding="utf-8"))
out = []
out.append(f"status={r.get('status')}")
out.append(f"run_id={r.get('run_id')}")
for k in sorted(r.keys()):
    if k in {"steps", "frames", "stage_measurements", "counter_events", "model_call_audits"}:
        continue
    v = r[k]
    if v is None:
        continue
    s = json.dumps(v, ensure_ascii=False)
    if len(s) > 400:
        s = s[:400] + "..."
    out.append(f"{k}={s}")

for s in r.get("steps") or []:
    out.append("---")
    out.append(f"step={s.get('step_id') or s.get('id')} status={s.get('status')}")
    for key, val in s.items():
        if key in {"iterations", "step_id", "id", "status"}:
            continue
        if val is None:
            continue
        txt = json.dumps(val, ensure_ascii=False)
        if len(txt) > 800:
            txt = txt[:800] + "..."
        out.append(f"  {key}={txt}")
    its = s.get("iterations") or []
    out.append(f"  iterations={len(its)}")
    for i, it in enumerate(its):
        out.append(f"  it[{i}]")
        for key, val in it.items():
            if val is None:
                continue
            txt = json.dumps(val, ensure_ascii=False)
            if len(txt) > 700:
                txt = txt[:700] + "..."
            out.append(f"    {key}={txt}")

out_path = Path("artifacts") / f"run-summary-{run_id[:8]}.txt"
out_path.write_text("\n".join(out), encoding="utf-8")
print(out_path)
print("\n".join(out[:120]))
