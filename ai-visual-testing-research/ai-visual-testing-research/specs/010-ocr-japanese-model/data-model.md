# Data Model: OCR Japanese Recognition Model (010)

## 1. PerceptionConfig additions (`src/vnc_agent/config.py`)

| Field | Type | Default | Meaning |
|---|---|---|---|
| `ocr_lang` | `str \| None` | `None` | Recognition-language identifier. `None` = engine default (pre-feature behavior). Known values with project model mappings: `"japan"`. Any other non-null value without an explicit model path fails validation at config load. |
| `ocr_rec_model_path` | `str \| None` | `None` | Explicit recognition-model file path (project-relative or absolute). Overrides the `ocr_lang` mapping when set. |
| `ocr_rec_keys_path` | `str \| None` | `None` | Explicit character-dictionary file path accompanying the model. |

Validation rules (pydantic, at config load):

- All three unset → valid (compat default).
- `ocr_lang` set to a value with no project mapping **and** no
  `ocr_rec_model_path` → `ValueError` naming the value and known languages
  (mirrors the `reporting.locale` registry pattern).
- Path existence is *not* checked at pydantic validation (config objects are
  built in many offline tests with no filesystem context); existence is
  checked fail-fast by `configure_ocr()` at composition time (FR-005).

Language→asset mapping (module constant in `perception/ocr/engine.py`, not
in `config.py`, so the mapping lives beside the engine that consumes it):

```
OCR_LANG_ASSETS = {
  "japan": (
    "models/ocr/japan_PP-OCRv4_rec_mobile.onnx",
    "models/ocr/japan_dict.txt",
  ),
}
```

Relative paths resolve against the current working directory (`vnc_agent/`),
the same convention as `artifacts.root_dir` / `artifacts.db_path`.

## 2. OCREngineSettings (`src/vnc_agent/perception/ocr/engine.py`)

Frozen dataclass — the resolved, effective engine settings:

| Field | Type | Notes |
|---|---|---|
| `lang` | `str \| None` | As configured; informational + used in component identity. |
| `rec_model_path` | `str \| None` | Absolute-resolved path or `None` (bundled default model). |
| `rec_keys_path` | `str \| None` | Absolute-resolved path or `None`. |

State transitions:

- `configure_ocr(lang=None, rec_model_path=None, rec_keys_path=None)`
  resolves lang→assets, validates file existence (raises
  `FileNotFoundError` with the offending path), stores the settings, and
  drops the cached engine instance **only if** the effective settings
  changed (FR-004: rebuild-on-change, never per-invocation).
- `set_engine(obj)` (test seam) always wins over settings until
  `reset_engine()`.
- `reset_engine()` drops the engine instance only; settings persist.

## 3. OCR component identity (FR-011)

`ocr_component_identity() -> dict` in the engine module returns:

```
{"backend": "rapidocr-onnxruntime", "version": "1.0",
 "language": <lang or "default">, "preprocess": "none"}
```

`structured_screen.py` uses it in place of the static
`_DEFAULT_OCR_IDENTITY` when the caller does not pass `ocr_identity`, so the
analysis-cache key changes when the configured language changes. (Cache is
per-run in-memory; this is defensive correctness, not a persistence
migration.)

## 4. ROI retry pass (FR-008/FR-009)

Engine helper:

```
run_ocr_region_scaled(image_path, region, *, scale=2.0) -> list[OCRItem]
```

- Reads the persisted frame image (independent evidence), crops
  `region` clamped to frame bounds, upscales by `scale` (cubic), runs the
  configured engine, divides bboxes by `scale` and re-offsets into original
  frame coordinates. Empty clamped crop or unreadable image → `[]`.

Verifier call-site rule (`verification/ocr_verifier.py::verify_text`):

```
needle not found
  AND condition.type == "text_appears"
  AND condition.region is not None
  AND screen.image_path is truthy
→ retry_items = run_ocr_region_scaled(screen.image_path, condition.region)
  found = needle-match over retry_items only (same normalization pipeline)
```

- At most one retry per condition evaluation; retry items are local to the
  decision and never merged into `screen.ocr_items`.
- `text_disappears` never consults the retry.

## 5. Model assets (`vnc_agent/models/ocr/`)

| File | Size (bytes) | Source |
|---|---|---|
| `japan_PP-OCRv4_rec_mobile.onnx` | 9,753,335 | ModelScope `RapidAI/RapidOCR`, path `onnx/PP-OCRv4/rec/japan_PP-OCRv4_rec_mobile.onnx`, branch `master` |
| `japan_dict.txt` | 17,332 | ModelScope `RapidAI/RapidOCR`, path `paddle/PP-OCRv4/rec/japan_PP-OCRv4_rec_mobile/japan_dict.txt`, branch `master` |
| `README.md` | — | provenance + placement doc (FR-006) |
