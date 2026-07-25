import json
import re
from pathlib import Path

log = Path("artifacts/last-mixed-kinken-run.log").read_text(encoding="utf-8", errors="replace")
m = re.findall(r'"run_id": "([^"]+)"', log)
rid = m[-1]
r = json.loads((Path("artifacts/runs") / rid / "report.json").read_text(encoding="utf-8"))
lines = [
    f"status={r['status']}",
    f"run_id={r['run_id']}",
    f"tags={json.dumps(r.get('declared_tag_counts'), ensure_ascii=False)}",
]
for s in r.get("steps") or []:
    fr = (s.get("failure_reason") or "")[:220]
    lines.append(f"{s.get('step_id')} {s.get('status')} {fr}")
out = Path("artifacts/run-brief-latest-mixed.txt")
out.write_text("\n".join(lines), encoding="utf-8")
print(out)
