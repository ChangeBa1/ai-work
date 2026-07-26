# Research: OCR Japanese Recognition Model (010)

Date: 2026-07-26. All findings verified directly against the pinned
dependency tree in this worktree and live model-hub listings (environment has
network access to both ModelScope and Hugging Face; verified HTTP 200).

## R1. How to swap the recognition model in the pinned OCR stack

**Decision**: Keep `rapidocr_onnxruntime==1.4.4` (already in `uv.lock`) and
construct the engine as
`RapidOCR(rec_model_path=<abs path>, rec_keys_path=<abs path>)`.

**Verified facts** (read from
`.venv/Lib/site-packages/rapidocr_onnxruntime/`):

- `RapidOCR.__init__(self, config_path=None, **kwargs)`; kwargs are routed by
  `utils.parse_parameters.UpdateParameters`, which maps `rec_*` keys into the
  `Rec` config section — `rec_model_path` and `rec_keys_path` are explicitly
  declared in `init_args()` and handled.
- `TextRecognizer.__init__` reads the character list from ONNX metadata if
  present (`session.have_key()`), else from `config["rec_keys_path"]`. So
  passing `rec_keys_path` is the safe universal path; if the ONNX happens to
  embed its dictionary, the metadata wins and the file is ignored.
- Detection (`Det`) and orientation (`Cls`) stages keep the bundled
  `ch_PP-OCRv4_det_infer.onnx` / `ch_ppocr_mobile_v2.0_cls_infer.onnx` —
  text *detection* is language-agnostic; only *recognition* is
  language-specific.
- Call contract is unchanged: `engine(img) -> (result, elapse)` with
  `result = [[box_points, text, confidence], ...]` — exactly what
  `run_ocr_array` already parses. No adapter needed.

**Alternatives considered**:

1. **Upgrade to the new `rapidocr` package (v2/v3) with
   `params={"Rec.lang_type": "japan"}`** — rejected: different result object
   (`RapidOCROutput` instead of tuple), models are downloaded at first run
   (runtime network dependency, forbidden by the constitution's resource
   model and by FR-006), larger dependency churn in `uv.lock`, and the
   engine-call contract in `run_ocr_array` would need rewriting.
2. **Switch OCR provider (PaddleOCR, Tesseract+jpn, manga-ocr)** — rejected:
   PaddleOCR pulls the full Paddle runtime (heavy for weak machines);
   Tesseract needs a native binary install (deployment burden, weaker on CJK
   UI screenshots); manga-ocr is recognition-only without detection. All
   break the "smallest change, same interface" requirement.
3. **Keep Chinese model + extend `_OCR_CONFUSABLES`** — rejected: cannot
   recover characters the recognizer never emits (`単価` fully missed,
   `お釣り` → `x二1-`); this is the current stopgap being replaced.

## R2. Which Japanese model, and where to get it

**Decision**: `japan_PP-OCRv4_rec_mobile.onnx` + `japan_dict.txt` from the
RapidOCR project's official model hub (ModelScope repo `RapidAI/RapidOCR`).

**Verified facts** (live API listing of
`https://www.modelscope.cn/api/v1/models/RapidAI/RapidOCR/repo/files?Recursive=true`):

- `onnx/PP-OCRv4/rec/japan_PP-OCRv4_rec_mobile.onnx` exists, 9,753,335 bytes.
- `paddle/PP-OCRv4/rec/japan_PP-OCRv4_rec_mobile/japan_dict.txt` exists,
  17,332 bytes (the matching dictionary; PP-OCR multilingual dicts include
  ASCII digits/letters, so amount matching keeps working).
- Download URL pattern:
  `https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/master/<path>`.
- Hugging Face `SWHL/RapidOCR` only hosts a PP-OCRv1 `japan_rec_crnn.onnx`
  (3.5 MB, older architecture, worse accuracy) — usable as a fallback mirror
  source only; not chosen.

**Alternatives considered**: PP-OCRv3 japan (older recognition accuracy),
PP-OCRv5 (only shipped for the new `rapidocr` package's pipeline / different
input contract, not published in this hub's onnx tree at a mobile size).
PP-OCRv4 mobile is the newest ONNX japan recognition model published by the
same project that produced the bundled default models — lowest integration
risk.

## R3. Model asset placement

**Decision**: Commit both files under `vnc_agent/models/ocr/` with a
`README.md` documenting source URLs + byte sizes; reference them from
`config/agent.yaml` via project-relative paths (resolved against the
`vnc_agent/` working directory, same convention as `artifacts.root_dir` and
`artifacts.db_path`).

**Rationale**: target machines are weak/offline; the constitution requires
on-demand *loading* but forbids implicit runtime *management* of models;
~10 MB is acceptable in-repo. If a future environment cannot use the
committed file, the README URLs allow manual placement at the same path, and
config load fails fast (with the path named) until placed.

**Alternatives considered**: a download script (still a network dependency at
deploy time), git-lfs (not configured in this repo — would break plain
clones), packaging into the wheel (project is run from source via uv).

## R4. How configuration reaches the engine without touching forbidden modules

**Decision**: module-level `configure_ocr(...)` in
`perception/ocr/engine.py`, called from the existing composition root
`api/cli.py::_execute` right after `load_config()` (and mirrored in the probe
scripts). `runtime/agent_runtime.py` (forbidden, parallel feature) is not
touched; `structured_screen.py` only asks the engine module for its current
component identity (FR-011).

**Verified facts**: `api/cli.py` is the only production `load_config()`
consumer that leads to OCR execution; the engine module already exposes the
`set_engine`/`reset_engine` seam that all existing tests use — the new
settings must not break that seam (settings apply only to the lazily-built
real engine; an injected engine always wins).

**Fail-fast rule**: `configure_ocr` raises `FileNotFoundError` naming the
offending path when an explicitly configured model/dict file is missing
(SC-004: before any VNC connection — the call site runs before
`driver.connect`). Unset config → no validation, no behavior change.

## R5. ROI 2x upscale retry mechanics

**Decision**: new engine helper `run_ocr_region_scaled(pixels_or_path,
region, scale=2.0)`:
crop → clamp to frame bounds → `cv2.resize` (cubic, 2x) → run engine → map
bboxes back (`/scale` + region offset) → same `OCRItem` list shape.
`verification/ocr_verifier.py::verify_text` uses it only when: condition type
is `text_appears`, a region is declared, the needle was not found in the
already-computed items, and the screen's `image_path` exists. Exactly one
retry, results merged only for the local decision (never written back into
`StructuredScreen.ocr_items` — the cache and other verifiers see the
original items, keeping cache semantics untouched).

**Rationale for reading `image_path`**: `verify_text`'s signature
(`condition, screen`) is called from `verification/engine.py` (forbidden to
modify), so pixels must come from `StructuredScreen.image_path` — the
already-persisted frame image, an independent-evidence source consistent with
Principle IV. `text_disappears` never uses the retry (finding *more* text
could only flip pass→fail, which the spec forbids — FR-008).

## R6. Regression evidence for before/after comparison

**Decision**: use in-repo real frames
`vnc_agent/artifacts/rescue-after-pos-confirm.png` and
`vnc_agent/artifacts/_last_mixed.png` (plus `probe_click/`, `probe_stale/`
frames) with a new one-shot probe script
`vnc_agent/artifacts/_ocr_probe_japan.py` that runs both engine configs over
the same frames and reports per-term hits for `預り金`, `単価`, `レジ袋`,
`お釣り`, `確定`. Historical expected-vs-actual baselines come from
`artifacts/ocr-probe-failed-frame.txt` and `artifacts/_ocr_0272602d.txt`
(the referenced `artifacts/runs/**` PNGs from those transcripts are not in
the repo — noted as a limitation; the two committed real frames cover the
same screens/vocabulary).
