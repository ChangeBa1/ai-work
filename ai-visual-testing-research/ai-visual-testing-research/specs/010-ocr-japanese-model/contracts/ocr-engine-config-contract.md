# Contract: OCR engine configuration & ROI retry (feature 010)

## Frozen interfaces (MUST NOT change)

```python
# perception/ocr/engine.py
def run_ocr_array(pixels: np.ndarray, *, roi: Region | None = None) -> list[OCRItem]
def run_ocr(image_path: str | Path, *, roi: Region | None = None) -> list[OCRItem]
def set_engine(engine: Any) -> None          # test seam — injected engine always wins
def reset_engine() -> None                   # drops engine instance; settings persist

# domain/observation.py
OCRItem(text, bbox, confidence, normalized_text)   # shape unchanged
```

## New surface

```python
# perception/ocr/engine.py
OCR_LANG_ASSETS: dict[str, tuple[str, str]]        # {"japan": (model, dict)}

def configure_ocr(
    *,
    lang: str | None = None,
    rec_model_path: str | Path | None = None,
    rec_keys_path: str | Path | None = None,
    base_dir: str | Path | None = None,            # resolution root for relative paths (default: cwd)
) -> None
    # - all None → settings cleared, engine behaves exactly as pre-feature
    # - lang with known mapping → resolves to project asset paths
    # - explicit rec_model_path overrides the lang mapping
    # - lang unknown AND no explicit model path → ValueError (names value + known langs)
    # - any resolved path missing on disk → FileNotFoundError (names the path)
    # - drops the cached engine only when effective settings changed

def get_ocr_settings() -> OCREngineSettings | None  # introspection for tests/probes

def ocr_component_identity() -> dict[str, Any]
    # {"backend": "rapidocr-onnxruntime", "version": "1.0",
    #  "language": <lang or "default">, "preprocess": "none"}

def run_ocr_region_scaled(
    image_path: str | Path,
    region: Region,
    *,
    scale: float = 2.0,
) -> list[OCRItem]
    # crop clamped to frame bounds → upscale → OCR → bboxes mapped back to
    # original frame coordinates; unreadable image / empty crop → []
```

```python
# config.py — PerceptionConfig additions (all default None = compat)
ocr_lang: str | None
ocr_rec_model_path: str | None
ocr_rec_keys_path: str | None
# validation: non-null ocr_lang not in known set AND no explicit model path → ValueError
```

```yaml
# config/agent.yaml — deployment default (this repo targets the Japanese system)
perception:
  ocr_lang: japan
  ocr_rec_model_path: models/ocr/japan_PP-OCRv4_rec_mobile.onnx
  ocr_rec_keys_path: models/ocr/japan_dict.txt
```

```python
# api/cli.py::_execute — composition root wiring (before driver.connect)
configure_ocr(
    lang=cfg.agent.perception.ocr_lang,
    rec_model_path=cfg.agent.perception.ocr_rec_model_path,
    rec_keys_path=cfg.agent.perception.ocr_rec_keys_path,
)
```

## Verifier call-site contract (`verification/ocr_verifier.py`)

- `verify_text(condition, screen)` signature unchanged.
- Retry fires iff: type == `text_appears` AND needle not found AND
  `condition.region` set AND `screen.image_path` truthy.
- Exactly one `run_ocr_region_scaled` call per such evaluation; its items are
  evaluated with the same normalization (`normalize_ocr_text`,
  `_haystacks`-equivalent line joining, amount keys) and never mutate
  `screen.ocr_items`.
- `text_disappears` unchanged (never consults the retry).
- `_OCR_CONFUSABLES` mapping retained.

## Forbidden-module discipline

`verification/engine.py`, `verification/business_resolver.py`,
`runtime/agent_runtime.py`, `perception/cache.py` — zero diffs.

## Error behavior summary

| Situation | Behavior |
|---|---|
| No OCR config at all | identical to pre-feature (bundled model / stub fallback) |
| `ocr_lang: japan`, assets present | Japanese rec model loaded lazily on first OCR call |
| Configured model file missing | `FileNotFoundError` at `configure_ocr` (composition, pre-VNC) naming the path |
| Unknown `ocr_lang`, no explicit path | `ValueError` at config load naming value + known languages |
| RapidOCR import unavailable | stub engine fallback, unchanged |
| ROI retry image unreadable/empty crop | retry returns `[]`, condition fails normally |
