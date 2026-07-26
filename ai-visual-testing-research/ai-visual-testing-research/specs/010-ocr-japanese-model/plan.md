# Implementation Plan: OCR Japanese Recognition Model

**Branch**: `010-ocr-japanese-model` | **Date**: 2026-07-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/010-ocr-japanese-model/spec.md`

## Summary

Replace the OCR recognition-stage model with a configurable one and default
this deployment to the Japanese PP-OCRv4 recognition model, fixing systematic
Japanese misrecognition (`預り金`→`預以金`, `レジ袋`→`ジ袋`, `単価` missed,
`お釣り`→`x二1-`) at the root instead of patching it in the verifier.
Technical approach: keep `rapidocr_onnxruntime` 1.4.4 and pass
`rec_model_path`/`rec_keys_path` into its `RapidOCR(**kwargs)` constructor
(supported since 1.3); add `ocr_lang`/`ocr_rec_model_path`/
`ocr_rec_keys_path` to `PerceptionConfig`; wire them at the existing CLI
composition root via a new module-level `configure_ocr()` in the engine
module; commit the Japanese ONNX model + dict under `vnc_agent/models/ocr/`;
and add a bounded ROI 2x-upscale re-OCR retry for failed regioned
`text_appears` conditions (engine helper + `ocr_verifier` call site only).

## Technical Context

**Language/Version**: Python 3.12 (uv-managed project in `vnc_agent/`)

**Primary Dependencies**: `rapidocr_onnxruntime==1.4.4` (already pinned via
uv.lock), `opencv-python`, `numpy`, `pydantic` v2 (config models), Typer CLI

**Storage**: N/A (model assets are static files committed under
`vnc_agent/models/ocr/`; no DB schema change)

**Testing**: pytest (`uv run pytest tests/unit tests/fixtures -q`,
`uv run pytest tests/e2e -q`); offline fixtures use the injectable stub
engine (`set_engine`), so no test requires the real ONNX runtime

**Target Platform**: Windows (weak/offline machines), single-process agent

**Project Type**: Single Python package (`vnc_agent/src/vnc_agent`)

**Performance Goals**: No regression in OCR latency budget; ROI retry adds at
most one extra OCR pass per failed regioned condition (bounded)

**Constraints**: `run_ocr`/`run_ocr_array` signatures and `OCRItem` shape
frozen; forbidden modules (owned by parallel features): 
`verification/engine.py`, `verification/business_resolver.py`,
`runtime/agent_runtime.py`, `perception/cache.py`; `_OCR_CONFUSABLES`
retained; no runtime model download

**Scale/Scope**: ~5 source files touched (`perception/ocr/engine.py`,
`config.py`, `api/cli.py`, `verification/ocr_verifier.py`,
`perception/structured_screen.py`), 2 committed model assets, config +
README docs, new unit/fixture tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Deterministic Runtime Control**: no model-driven flow change; OCR
      stays a deterministic perception component. ROI retry is a fixed,
      code-controlled single pass — no unbounded retry (also satisfies the
      recovery/no-infinite-retry gate).
- [x] **II. Role separation**: only the perception (OCR) layer and the
      Verifier's evidence-gathering improve; no Planner/Grounder/Executor
      responsibility shifts.
- [x] **III. Keyboard-first**: untouched.
- [x] **IV. Independent verify loop**: ROI retry re-derives evidence from the
      captured frame image itself (independent evidence), never from model
      self-assessment; `uncertain` semantics unchanged.
- [x] **V. Controlled self-evolution**: no runtime model swapping — the
      recognition model is fixed at composition time from declarative config;
      runtime never downloads or replaces models (explicitly forbidden by
      FR-006).
- [x] **VI. Domain-agnostic core**: new config fields are generic
      (`ocr_lang`, model paths — language is not business vocabulary); no
      business tokens enter core modules (the `test_no_business_keywords_in_core`
      scan covers `config.py`, `perception`, `verification`, `api`). The
      Japanese *default* lives in `config/agent.yaml` (deployment config),
      not in code defaults — code defaults keep pre-feature behavior.
      Cross-scenario validation: ROI-retry contract tests use two unrelated
      generic scenarios (small-text region recovery in two different fake
      screens), not POS vocabulary.
- [x] **Engineering constraints**: single OCR engine instance at a time
      (rebuilt only on settings change — "按需加载 OCR 模型、不同时加载多个
      本地模型"); black-box boundary untouched; no new processes/services.
- [x] **Credentials/privacy**: no credentials involved; model paths are not
      secrets.
- [x] **Quality gates**: fail-fast on missing configured model file names the
      offending path (explicit, auditable); offline fixture tests cover the
      new config matrix.

**Domain-Agnostic Core gate (Principle VI)**:

- [x] No business-specific fields/keywords added to core modules — `ocr_lang`
      is a locale/technology setting, equivalent in kind to the existing
      `reporting.locale`.
- [x] Deployment-specific choice (Japanese) lives only in `config/agent.yaml`
      (deployment config file), test needles live only in artifacts/probe
      scripts and spec docs.
- [x] ROI retry capability validated with two unrelated generic scenarios in
      tests (form-like screen and menu-like screen fixtures already exist as
      the project's cross-scenario convention; the new tests follow it with
      synthetic frames).

## Project Structure

### Documentation (this feature)

```text
specs/010-ocr-japanese-model/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── ocr-engine-config-contract.md
├── checklists/requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
vnc_agent/
├── config/
│   └── agent.yaml                      # perception.ocr_lang etc. (deployment default: japan)
├── models/
│   └── ocr/
│       ├── README.md                   # provenance: source URLs, revision, placement
│       ├── japan_PP-OCRv4_rec_mobile.onnx   # committed model asset
│       └── japan_dict.txt              # committed character dictionary
├── src/vnc_agent/
│   ├── config.py                       # PerceptionConfig: +ocr_lang, +ocr_rec_model_path, +ocr_rec_keys_path
│   ├── api/cli.py                      # composition root: configure_ocr(cfg.agent.perception)
│   ├── perception/
│   │   ├── ocr/engine.py               # configure_ocr(), settings-aware _get_engine(),
│   │   │                               #   ocr_component_identity(), run_ocr_array_scaled()
│   │   └── structured_screen.py        # OCR component identity reflects configured language (FR-011)
│   └── verification/ocr_verifier.py    # ROI 2x re-OCR retry call site (text_appears + region only)
└── tests/
    ├── unit/test_config_ocr.py         # config-load matrix (default/lang/path/missing-file)
    └── fixtures/test_ocr.py            # + configure/rebuild + scaled-ROI helper tests
    └── fixtures/test_ocr_template_verifiers.py  # + ROI retry behavior via stub engine
```

**Structure Decision**: single existing Python package; no new modules beyond
one static asset directory (`vnc_agent/models/ocr/`). `models/ocr` sits at
the project root next to `config/` and `artifacts/` (it is data, not code —
the `src/vnc_agent/models` Python package is unrelated and untouched).

## Complexity Tracking

No constitution violations to justify. One scope-discipline note: feature
briefs for parallel features own `verification/engine.py`,
`verification/business_resolver.py`, `runtime/agent_runtime.py`,
`perception/cache.py` — this feature must not modify them, which is why
engine configuration is applied at the CLI composition root
(`api/cli.py::_execute`) instead of inside `AgentRuntime`.
