"""Compare old passing run vs new failing run for pos-buy-bag-checkout."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD = ROOT / "runs" / "a5a5ecd0-8d79-4cf6-9b16-ffdc2295b553" / "report.json"
NEW = ROOT / "runs" / "bb9f039e-f5f3-4437-abd6-af251b47997a" / "report.json"
OUT = ROOT / "compare-old-new.txt"


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def step_brief(s: dict) -> dict:
    its = s.get("iterations") or []
    brief_its = []
    for it in its:
        vr = it.get("verification_result") or {}
        sa = it.get("semantic_action") or {}
        ea = it.get("executable_action") or {}
        ae = it.get("action_effect") or {}
        brief_its.append(
            {
                "idx": it.get("iteration_index"),
                "action_type": sa.get("action_type"),
                "target_text": (sa.get("target") or {}).get("text") if sa.get("target") else None,
                "coords": ea.get("coordinates"),
                "exec_ok": (it.get("execution_result") or {}).get("success"),
                "effect": ae.get("status"),
                "verify": vr.get("status"),
                "matched": vr.get("matched_conditions"),
                "failed": vr.get("failed_conditions"),
                "uncertain": vr.get("uncertain_conditions"),
                "reason": (vr.get("reason") or "")[:300],
                "repeat_guard": (it.get("repeat_guard_decision") or {}).get("reason"),
            }
        )
    return {
        "step_id": s.get("step_id") or s.get("id"),
        "status": s.get("status"),
        "failure_reason": (s.get("failure_reason") or "")[:400],
        "basis": s.get("basis"),
        "iterations": brief_its,
    }


def top(r: dict) -> dict:
    keys = [
        "run_id",
        "status",
        "test_case_id",
        "started_at",
        "ended_at",
        "localized_message",
        "display_status",
    ]
    out = {k: r.get(k) for k in keys if k in r}
    pre = r.get("precondition_evaluation")
    if pre:
        out["precondition_status"] = pre.get("status")
    tags = r.get("declared_tag_counts")
    if tags:
        out["declared_tag_counts"] = tags
    out["step_count"] = len(r.get("steps") or [])
    out["frame_count"] = len(r.get("frames") or [])
    # schema differences
    out["top_keys"] = sorted(r.keys())
    return out


def main() -> None:
    lines: list[str] = []
    old = load(OLD)
    new = load(NEW)

    lines.append("=== OLD TOP ===")
    lines.append(json.dumps(top(old), ensure_ascii=False, indent=2))
    lines.append("\n=== NEW TOP ===")
    lines.append(json.dumps(top(new), ensure_ascii=False, indent=2))

    lines.append("\n=== OLD STEPS ===")
    for s in old.get("steps") or []:
        lines.append(json.dumps(step_brief(s), ensure_ascii=False, indent=2))

    lines.append("\n=== NEW STEPS ===")
    for s in new.get("steps") or []:
        lines.append(json.dumps(step_brief(s), ensure_ascii=False, indent=2))

    # First failing iteration detail for new
    for s in new.get("steps") or []:
        for it in s.get("iterations") or []:
            vr = it.get("verification_result") or {}
            if vr.get("status") == "failed":
                lines.append("\n=== NEW FIRST FAIL VERIFY FULL ===")
                lines.append(json.dumps(vr, ensure_ascii=False, indent=2)[:4000])
                lines.append("\n=== NEW FIRST FAIL ACTION ===")
                lines.append(
                    json.dumps(
                        {
                            "semantic": it.get("semantic_action"),
                            "executable": it.get("executable_action"),
                            "execution_result": it.get("execution_result"),
                            "action_effect_status": (it.get("action_effect") or {}).get("status"),
                            "after_frame": it.get("after_frame_path"),
                            "before_frame": it.get("before_frame_path"),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )[:3000]
                )
                break
        else:
            continue
        break

    # First success iteration for old add-shopping-bag
    for s in old.get("steps") or []:
        sid = s.get("step_id") or s.get("id")
        if sid != "add-shopping-bag":
            continue
        for it in s.get("iterations") or []:
            vr = it.get("verification_result") or {}
            if vr.get("status") == "passed":
                lines.append("\n=== OLD PASSING VERIFY FULL (add-shopping-bag) ===")
                lines.append(json.dumps(vr, ensure_ascii=False, indent=2)[:4000])
                lines.append("\n=== OLD PASSING ACTION ===")
                lines.append(
                    json.dumps(
                        {
                            "semantic": it.get("semantic_action"),
                            "executable": it.get("executable_action"),
                            "execution_result": it.get("execution_result"),
                            "action_effect_status": (it.get("action_effect") or {}).get("status"),
                            "after_frame": it.get("after_frame_path"),
                            "before_frame": it.get("before_frame_path"),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )[:3000]
                )
                break

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
