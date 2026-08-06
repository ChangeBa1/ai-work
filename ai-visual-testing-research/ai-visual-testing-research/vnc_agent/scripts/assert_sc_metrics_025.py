#!/usr/bin/env python3
"""Assert SC-001/002/003 gates (feature 025 T034)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SC002_MIN_HITS = 20
SC003_MIN_SAMPLES = 20


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", required=True)
    args = ap.parse_args()
    data = json.loads(Path(args.post).read_text(encoding="utf-8"))
    hits = int(data.get("element_memory_hits") or 0)
    attempts = int(data.get("lookup_attempts") or 0)
    hit_rate = float(data.get("hit_rate") or 0.0)
    false_hits = int(data.get("false_hits") or 0)
    fhr = data.get("false_hit_rate")
    lat = data.get("lookup_latency_ms") or []
    p95 = float(data.get("p95_ms") or 0.0)
    n_lat = len(lat)

    failed = []
    # SC-001
    if not (hits > 0 and hit_rate >= 0.30):
        failed.append(f"SC-001 fail hits={hits} hit_rate={hit_rate}")
    # SC-002
    sc002 = "skip"
    if hits == 0:
        sc002 = "skip"
    elif hits < SC002_MIN_HITS:
        sc002 = "sc002_inconclusive"
    else:
        rate = float(fhr) if fhr is not None else false_hits / hits
        if rate > 0.10:
            failed.append(f"SC-002 fail false_hit_rate={rate}")
        else:
            sc002 = "pass"
    # SC-003
    sc003 = "pass"
    if n_lat < SC003_MIN_SAMPLES:
        sc003 = "sc003_inconclusive"
    elif p95 > 50.0:
        failed.append(f"SC-003 fail p95_ms={p95}")
        sc003 = "fail"

    summary = {
        "sc001": "fail" if any(x.startswith("SC-001") for x in failed) else "pass",
        "sc002": sc002 if sc002 != "skip" else ("pass" if hits == 0 and not failed else sc002),
        "sc003": sc003,
        "failed": failed,
    }
    print(json.dumps(summary, indent=2))
    if failed:
        return 1
    # inconclusive is not failure
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
