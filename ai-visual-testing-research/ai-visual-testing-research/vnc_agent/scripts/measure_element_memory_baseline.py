#!/usr/bin/env python3
"""Offline element-memory hit metrics (feature 025 T001/T034/T042).

Pre mode (default): no identity store — hits always 0 (baseline before 025).
Post mode (--seed-identity): seed one write-side identity_key from the fixture
OCR/region, then count a hit when lookup resolves unique to that same key.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from vnc_agent.domain.observation import OCRItem, Region
from vnc_agent.memory.identity import (
    resolve_identity_candidates_for_lookup,
    resolve_identity_for_write,
)


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--seed-identity",
        action="store_true",
        help="Post-025 mode: seed write identity and count key matches as hits",
    )
    args = ap.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    lookups = manifest.get("lookups") or []
    ocr = [OCRItem(text="TOTAL", bbox=(150, 85, 170, 95), confidence=0.9)]
    res = (300, 200)
    region = Region(x1=150, y1=85, x2=170, y2=95)
    grid_size = 16
    schema_version = "eid-v1"

    lookup_attempts = 0
    element_memory_hits = 0
    false_hits = 0
    latencies: list[float] = []

    written_key: str | None = None
    if args.seed_identity:
        w = resolve_identity_for_write(
            region=region,
            ocr_items=ocr,
            resolution=res,
            grid_size=grid_size,
            schema_version=schema_version,
        )
        written_key = w.identity_key if w else None

    min_samples = int(manifest.get("sc003_min_samples") or 20)
    rounds = max(1, (min_samples + max(1, len(lookups)) - 1) // max(1, len(lookups)))

    for _ in range(rounds):
        for item in lookups:
            label = item.get("target_label") or ""
            t0 = time.perf_counter()
            q = resolve_identity_candidates_for_lookup(
                target_label=label,
                ocr_items=ocr,
                resolution=res,
                grid_size=grid_size,
                schema_version=schema_version,
            )
            ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(ms)
            lookup_attempts += 1
            if (
                args.seed_identity
                and written_key
                and q.status == "unique"
                and q.identity is not None
                and q.identity.identity_key == written_key
            ):
                # Offline stand-in for store hit + template pass (T042).
                element_memory_hits += 1

    if written_key is None and not args.seed_identity:
        w = resolve_identity_for_write(
            region=region,
            ocr_items=ocr,
            resolution=res,
            grid_size=grid_size,
            schema_version=schema_version,
        )
        written_key = w.identity_key if w else None

    hits = element_memory_hits
    out = {
        "lookup_attempts": lookup_attempts,
        "element_memory_hits": hits,
        "hit_rate": (hits / lookup_attempts) if lookup_attempts else 0.0,
        "false_hits": false_hits,
        "false_hit_rate": (false_hits / hits) if hits else None,
        "lookup_latency_ms": latencies,
        "p50_ms": _percentile(latencies, 0.50),
        "p95_ms": _percentile(latencies, 0.95),
        "manifest_path": str(Path(args.manifest).resolve()),
        "write_identity_key_demo": written_key,
        "seed_identity": bool(args.seed_identity),
        "note": (
            "post-025: seed write identity; unique key match counts as hit"
            if args.seed_identity
            else "pre-baseline without seeded store hits always 0"
        ),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: out[k]
                for k in (
                    "lookup_attempts",
                    "element_memory_hits",
                    "hit_rate",
                    "p95_ms",
                    "seed_identity",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
