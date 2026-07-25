import json
from pathlib import Path

for run_id in [
    "978eb510-2050-4d98-b45c-e9c52ebe1f3d",
    "7254ab82-45ca-4da8-bbbf-b8ec83b031f0",
]:
    p = Path(f"artifacts/runs/{run_id}/report.json")
    if not p.exists():
        # try partial match
        matches = list(Path("artifacts/runs").glob(f"{run_id[:8]}*/report.json"))
        if not matches:
            print("missing", run_id)
            continue
        p = matches[0]
    r = json.loads(p.read_text(encoding="utf-8"))
    print("\n########", p.parent.name, r.get("status"), r.get("declared_tag_counts"))
    for s in r.get("steps", []):
        sid = s.get("step_id") or s.get("id")
        print(f"== {sid} {s.get('status')}")
        for it in s.get("iterations") or []:
            sa = it.get("semantic_action") or {}
            ea = it.get("executable_action") or {}
            print(
                f"  {sa.get('action_type')} tv={sa.get('text_value')!r} keys={sa.get('keys')} "
                f"tgt={(sa.get('target') or {}).get('text')!r} "
                f"coords={ea.get('coordinates')} text={ea.get('text')!r}"
            )
            print(f"  intent={sa.get('intent')}")
