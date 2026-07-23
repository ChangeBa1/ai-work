# frame_dedup fixtures

Deterministic, regenerable PNG fixtures for feature 004 (screenshot dedup /
analysis-cache reuse / performance telemetry / zh-CN reports). No fixture is
hand-edited; regenerate with:

```sh
uv run python tests/fixtures/images/frame_dedup/generate_fixtures.py --check
```

Running it twice in a row must produce an identical working tree — every
pixel pattern is a fixed numpy computation, never random or time-based.

## Files

| File | Purpose |
|---|---|
| `baseline_full.png` | 64x48 baseline pattern, PNG compression level 1 |
| `baseline_full_alt_encoding.png` | Same pixels as baseline, compression level 9 — different `fixture_file_sha256`, identical `content_hash` |
| `single_pixel_changed.png` | Baseline with pixel (0,0) altered — must produce a different `content_hash` |
| `roi_crop.png` | Crop of baseline at `[8,8,32,32]` — different scope must not collide with full-screen `content_hash` even where pixels match |
| `diff_resolution.png` | Baseline resized to a different resolution |
| `masked.png` | Baseline with rectangle `[40,30,56,40]` blacked out — different mask identity |
| `grayscale.png` | Baseline converted to single-channel — different `pixel_format` |

`manifest.json` records, per file: `width`, `height`, `pixel_format`,
`fixture_file_sha256` (SHA-256 of the PNG bytes on disk) and `content_hash`
(SHA-256 of the versioned canonical pixel preimage from
`vnc_agent.perception.pixel_identity.pixel_content_hash`, computed after
decoding with `cv2.IMREAD_UNCHANGED` — the same decode path production
capture uses).
