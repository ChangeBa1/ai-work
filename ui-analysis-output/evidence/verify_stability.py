from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(r"D:\POJ\NodeMaster")
BUNDLE = ROOT / "ui-analysis-output" / "ui-analysis-bundle-v1"
EVIDENCE = ROOT / "ui-analysis-output" / "evidence"
FILES = (
    "screens.jsonl", "elements.jsonl", "transitions.jsonl",
    "flows.jsonl", "diagnostics.jsonl",
)


def capture() -> dict[str, dict]:
    result = {}
    for name in FILES:
        raw = (BUNDLE / name).read_bytes()
        result[name] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "record_count": sum(bool(line.strip()) for line in raw.splitlines()),
        }
    return result


before = capture()
subprocess.run(
    ["python", str(EVIDENCE / "build_ui_analysis.py")],
    cwd=ROOT,
    check=True,
    capture_output=True,
)
after = capture()
files = [
    {
        "file": name,
        "before_sha256": before[name]["sha256"],
        "after_sha256": after[name]["sha256"],
        "hash_equal": before[name]["sha256"] == after[name]["sha256"],
        "before_count": before[name]["record_count"],
        "after_count": after[name]["record_count"],
        "count_equal": before[name]["record_count"] == after[name]["record_count"],
    }
    for name in FILES
]
report = {
    "stable": all(row["hash_equal"] and row["count_equal"] for row in files),
    "note": (
        "Identical JSONL bytes across two complete generations prove stable IDs "
        "and deterministic records for the same input."
    ),
    "files": files,
}
(EVIDENCE / "stability-before.json").write_bytes(
    (json.dumps({"files": before}, indent=2) + "\n").encode("utf-8")
)
(EVIDENCE / "stability-report.json").write_bytes(
    (json.dumps(report, indent=2) + "\n").encode("utf-8")
)
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["stable"] else 1)
