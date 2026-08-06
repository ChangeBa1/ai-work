# Element memory identity baseline (025)

## Manifest

`regression_suite_manifest.json` — fixed lookup list for SC-001/002/003 pre/post.

## Formulas

- `hit_rate = element_memory_hits / lookup_attempts`
- `false_hit_rate = false_hits / element_memory_hits` (null if hits=0)

## Gates (T034)

| SC | Rule |
|----|------|
| SC-001 | hits>0 and hit_rate≥0.30 |
| SC-002 | hits==0 skip; 0&lt;hits&lt;20 → sc002_inconclusive; hits≥20 → false_hit_rate≤0.10 |
| SC-003 | n_latency&lt;20 → sc003_inconclusive; ≥20 → p95_ms≤50 |

## Commands

```bash
cd vnc_agent
# Pre-025 (no seeded store → hits always 0)
.venv/bin/python scripts/measure_element_memory_baseline.py \
  --manifest ../specs/025-element-identity-key/baseline/regression_suite_manifest.json \
  --out ../specs/025-element-identity-key/baseline/element_memory_hits_pre_025.json

# Post-025 (seed write identity; unique key match counts as hit)
.venv/bin/python scripts/measure_element_memory_baseline.py \
  --manifest ../specs/025-element-identity-key/baseline/regression_suite_manifest.json \
  --out ../specs/025-element-identity-key/baseline/element_memory_hits_post_025.json \
  --seed-identity

.venv/bin/python scripts/assert_sc_metrics_025.py \
  --post ../specs/025-element-identity-key/baseline/element_memory_hits_post_025.json
```

Pre-025 expected: `element_memory_hits==0`, `hit_rate==0`.

Post-025 (2026-08-06, `--seed-identity`): `hits=20`, `hit_rate=1.0`, SC-001/002/003 **pass**
(see `element_memory_hits_post_025.json`).
