# Quickstart: OCR Japanese Recognition Model (010)

## Prerequisites

```powershell
cd vnc_agent
uv sync --extra dev
```

Model assets must exist (committed in-repo; see `models/ocr/README.md` for
provenance and manual placement if absent):

```
vnc_agent/models/ocr/japan_PP-OCRv4_rec_mobile.onnx   (9,753,335 bytes)
vnc_agent/models/ocr/japan_dict.txt                   (17,332 bytes)
```

## Validation 1 — config load matrix

```powershell
uv run pytest tests/unit/test_config_ocr.py -q
```

Expected: default(None)/japan/explicit-path/unknown-lang cases all pass.

## Validation 2 — engine + verifier behavior (offline, stub engine)

```powershell
uv run pytest tests/fixtures/test_ocr.py tests/fixtures/test_ocr_template_verifiers.py -q
```

Expected: existing OCR tests stay green; new tests cover
`configure_ocr` fail-fast, settings-change rebuild, `run_ocr_region_scaled`
bbox mapping, and the ROI retry firing rules.

## Validation 3 — full offline suites

```powershell
uv run pytest tests/unit tests/fixtures -q
uv run pytest tests/e2e -q
```

Expected: all green (e2e uses fake drivers/stub OCR; no real VNC needed).

## Validation 4 — real-frame before/after comparison (SC-001)

```powershell
uv run python artifacts/_ocr_probe_japan.py
```

Runs the default (Chinese) and Japanese-configured engines over the in-repo
real POS frames (`artifacts/rescue-after-pos-confirm.png`,
`artifacts/_last_mixed.png`, probe frames) and writes
`artifacts/ocr-japan-compare.txt` with per-term hits for
`預り金 / 単価 / レジ袋 / お釣り / 確定`. Expected: each term recognized
verbatim (or measurably improved) under the Japanese model; no term
regresses.

## Validation 5 — startup fail-fast (SC-004)

```powershell
# temporarily point config at a nonexistent model path, then:
uv run vnc-agent run testcases/pos-buy-bag-checkout.yaml --dry-run   # dry-run: validates case only
uv run python -c "from vnc_agent.config import load_config; from vnc_agent.perception.ocr.engine import configure_ocr; c=load_config('config'); configure_ocr(lang=c.agent.perception.ocr_lang, rec_model_path='models/ocr/nope.onnx')"
```

Expected: `FileNotFoundError` naming `models/ocr/nope.onnx`; no VNC
connection attempted.
