# OCR recognition model assets (feature 010-ocr-japanese-model)

Recognition-stage models for `rapidocr_onnxruntime`. Text *detection* and
orientation models stay on the ones bundled with the pip package; only the
language-specific *recognition* model is swapped via configuration
(`config/agent.yaml` → `perception.ocr_rec_model_path` /
`perception.ocr_rec_keys_path`, or just `perception.ocr_lang: japan` which
maps to the files below).

## Files

| File | Bytes | Provenance |
|---|---|---|
| `japan_PP-OCRv4_rec_mobile.onnx` | 9,753,335 | ModelScope repo `RapidAI/RapidOCR`, branch `master`, path `onnx/PP-OCRv4/rec/japan_PP-OCRv4_rec_mobile.onnx` (RapidOCR project's official ONNX conversion of PaddleOCR PP-OCRv4 Japanese mobile recognition model). Download URL: `https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/master/onnx/PP-OCRv4/rec/japan_PP-OCRv4_rec_mobile.onnx` |
| `japan_dict.txt` | 17,332 | Same repo/branch, path `paddle/PP-OCRv4/rec/japan_PP-OCRv4_rec_mobile/japan_dict.txt`. Download URL: `https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/master/paddle/PP-OCRv4/rec/japan_PP-OCRv4_rec_mobile/japan_dict.txt` |

Retrieved: 2026-07-26. License: Apache-2.0 (PaddleOCR / RapidOCR model
conversions).

Note: the ONNX file embeds its character dictionary in ONNX custom metadata
(key `character`), which the runtime prefers; `japan_dict.txt` is kept both
as the documented companion and as the explicit `rec_keys_path` fallback for
runtimes/models without embedded metadata.

## Manual placement (offline environments)

If these files are missing (e.g. a partial checkout), download them from the
URLs above and place them at exactly these paths. With
`perception.ocr_lang`/model paths configured, agent composition fails fast
with a `FileNotFoundError` naming the missing path until the files are in
place. Runtime never downloads models (constitution: no implicit runtime
model management).
