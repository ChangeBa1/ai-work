import json
from pathlib import Path

run_id = "0272602d-af55-49f8-a645-84a4736aa4a8"
p = Path(f"artifacts/runs/{run_id}/report.json")
r = json.loads(p.read_text(encoding="utf-8"))
out = []
for s in r.get("steps", []):
    sid = s.get("step_id") or s.get("id")
    out.append(f"==== {sid} status={s.get('status')} fail={s.get('failure_reason')}")
    for it in s.get("iterations") or []:
        sa = it.get("semantic_action") or {}
        tgt = sa.get("target") or {}
        out.append(
            f"  act={sa.get('action_type')} text_value={sa.get('text_value')!r} "
            f"keys={sa.get('keys')} target_text={tgt.get('text')!r}"
        )
        out.append(f"  intent={sa.get('intent')}")
        ea = it.get("executable_action") or {}
        er = it.get("execution_result") or {}
        out.append(
            f"  exec op={ea.get('operation')} coords={ea.get('coordinates')} "
            f"text={ea.get('text')!r} keys={ea.get('keys')} "
            f"success={er.get('success')} err={er.get('error_code')} msg={er.get('error_message')}"
        )
        out.append(f"  grounding={it.get('grounding_candidates')}")
        vr = it.get("verification_result") or {}
        out.append(
            f"  verify={vr.get('status')} matched={vr.get('matched_conditions')} "
            f"failed={vr.get('failed_conditions')}"
        )
        out.append(f"  reason={(vr.get('reason') or '')[:400]}")
        out.append(f"  effect={(it.get('action_effect') or {}).get('status')}")
        out.append(f"  before={it.get('before_frame_path')}")
        out.append(f"  after={it.get('after_frame_path')}")
        for ra in it.get("recovery_attempts") or []:
            out.append(f"  recovery={ra}")
out_path = Path("artifacts/_dbg_0272602d.txt")
out_path.write_text("\n".join(out), encoding="utf-8")
print(f"wrote {out_path} lines={len(out)}")
