# Tasks: OCR Japanese Recognition Model

**Input**: Design documents from `/specs/010-ocr-japanese-model/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/ocr-engine-config-contract.md, quickstart.md

All file paths below are relative to `vnc_agent/` unless prefixed with
`specs/`. Tests are included (project convention: offline pytest gates are
mandatory quality gates).

**Forbidden modules (zero diffs)**: `src/vnc_agent/verification/engine.py`,
`src/vnc_agent/verification/business_resolver.py`,
`src/vnc_agent/runtime/agent_runtime.py`, `src/vnc_agent/perception/cache.py`.

## Phase 1: Setup (model assets)

- [X] T001 Download `japan_PP-OCRv4_rec_mobile.onnx` (expect 9,753,335 bytes)
      from ModelScope `RapidAI/RapidOCR` path
      `onnx/PP-OCRv4/rec/japan_PP-OCRv4_rec_mobile.onnx` into
      `models/ocr/japan_PP-OCRv4_rec_mobile.onnx`; verify byte size.
- [X] T002 [P] Download `japan_dict.txt` (expect 17,332 bytes) from ModelScope
      `RapidAI/RapidOCR` path
      `paddle/PP-OCRv4/rec/japan_PP-OCRv4_rec_mobile/japan_dict.txt` into
      `models/ocr/japan_dict.txt`; verify byte size.
- [X] T003 [P] Write provenance doc `models/ocr/README.md` (source URLs,
      revision `master`, byte sizes, manual-placement instructions,
      config reference) per FR-006.

## Phase 2: Foundational (engine + config plumbing — blocks all stories)

- [X] T004 Add `OCREngineSettings` frozen dataclass, `OCR_LANG_ASSETS`
      mapping, `configure_ocr()` (lang resolution, explicit-path override,
      unknown-lang ValueError, missing-file FileNotFoundError, rebuild only
      on settings change), `get_ocr_settings()`, and settings-aware
      `_get_engine()` (passes `rec_model_path`/`rec_keys_path` kwargs to
      `RapidOCR`) in `src/vnc_agent/perception/ocr/engine.py`. Keep
      `run_ocr`/`run_ocr_array` signatures, stub fallback, and
      `set_engine`/`reset_engine` seam intact (contract §Frozen interfaces).
- [X] T005 Add `ocr_lang` / `ocr_rec_model_path` / `ocr_rec_keys_path`
      (all `str | None = None`) to `PerceptionConfig` in
      `src/vnc_agent/config.py` with the unknown-lang-without-path validator
      (data-model.md §1); known-language set imported from the engine module
      constant to keep a single source of truth.
- [X] T006 Add `ocr_component_identity()` to
      `src/vnc_agent/perception/ocr/engine.py` and use it in
      `src/vnc_agent/perception/structured_screen.py` when `ocr_identity` is
      not supplied (FR-011), replacing the static `_DEFAULT_OCR_IDENTITY`
      lookup at call time (keep the constant as fallback shape).

## Phase 3: User Story 1 (P1) — Configurable OCR recognition language/model

**Goal**: config selects the Japanese rec model; absent config = pre-feature
behavior; missing file fails fast pre-VNC.

**Independent test**: `uv run pytest tests/unit/test_config_ocr.py
tests/fixtures/test_ocr.py -q` green; probe script shows Japanese terms
recognized.

- [X] T007 [US1] Wire `configure_ocr(lang=…, rec_model_path=…,
      rec_keys_path=…)` from perception config at the composition root in
      `src/vnc_agent/api/cli.py::_execute` (before any VNC connect), per
      contract §composition-root wiring.
- [X] T008 [US1] Set deployment default in `config/agent.yaml` perception
      section: `ocr_lang: japan`, `ocr_rec_model_path:
      models/ocr/japan_PP-OCRv4_rec_mobile.onnx`, `ocr_rec_keys_path:
      models/ocr/japan_dict.txt` (FR-007).
- [X] T009 [P] [US1] New `tests/unit/test_config_ocr.py`: defaults are None;
      yaml round-trip loads the three fields; unknown `ocr_lang` without
      explicit path raises at config load naming known languages; unknown
      lang WITH explicit path is accepted (SC-003).
- [X] T010 [P] [US1] Extend `tests/fixtures/test_ocr.py`:
      `configure_ocr` unknown-lang ValueError and missing-file
      FileNotFoundError name the offending value/path; settings change drops
      the cached engine while identical re-configure keeps it (FR-004);
      injected `set_engine` wins over settings; `configure_ocr()` all-None
      restores compat default; `ocr_component_identity()` reflects
      configured language (FR-011).
- [X] T011 [US1] Verify config/agent.yaml default loads against the real
      committed assets: `uv run python -c "load_config('config') +
      configure_ocr(...)"` succeeds from `vnc_agent/` cwd (quickstart
      Validation 5 positive half).

## Phase 4: User Story 2 (P2) — In-project model files with documented provenance

**Goal**: fresh clone works offline; provenance documented.

**Independent test**: files exist at documented paths with expected sizes;
README states source; no runtime download code anywhere.

- [X] T012 [US2] Document the OCR language/model configuration and model
      provenance in `README.md` (vnc_agent project README): new perception
      config keys, default Japanese deployment, model file paths + source
      URLs, manual placement fallback (FR-006).
- [X] T013 [P] [US2] Add asset-presence guard test in
      `tests/unit/test_config_ocr.py`: when `config/agent.yaml` sets
      `ocr_lang`/model paths, the referenced files exist in the repo working
      tree (guards against a broken deployment default; skip cleanly if
      agent.yaml has no OCR config).

## Phase 5: User Story 3 (P3) — Failed-needle ROI upscale re-OCR retry

**Goal**: bounded single 2x-region re-OCR rescues small-text `text_appears`
conditions with a declared region.

**Independent test**: `uv run pytest
tests/fixtures/test_ocr_template_verifiers.py -q` green, retry fires only
per contract rules.

- [X] T014 [US3] Add `run_ocr_region_scaled(image_path, region, *,
      scale=2.0)` helper to `src/vnc_agent/perception/ocr/engine.py`: read
      image, clamp region to bounds, cubic 2x upscale, OCR, map bboxes back
      to frame coordinates; unreadable/empty → `[]` (data-model.md §4).
- [X] T015 [US3] Call it from
      `src/vnc_agent/verification/ocr_verifier.py::verify_text` only when
      `text_appears` + region + not found + `screen.image_path`; evaluate
      retry items with the same normalization pipeline; never mutate
      `screen.ocr_items`; `text_disappears` untouched; keep
      `_OCR_CONFUSABLES` (FR-008/009/010).
- [X] T016 [P] [US3] Tests in `tests/fixtures/test_ocr_template_verifiers.py`
      (stub engine + tmp png frames, two unrelated generic scenarios per
      Principle VI): retry rescues a regioned needle; no region → no retry;
      `text_disappears` → no retry; retry called at most once (spy);
      bbox coordinates mapped back correctly; failure still fails after
      empty retry.
- [X] T017 [P] [US3] Unit test for `run_ocr_region_scaled` geometry in
      `tests/fixtures/test_ocr.py`: out-of-bounds region clamped; fully
      outside region → `[]`; scale mapping divides bboxes and re-offsets.

## Phase 6: Polish & verification evidence

- [X] T018 Write probe script `artifacts/_ocr_probe_japan.py` running
      default vs japan-configured engine over
      `artifacts/rescue-after-pos-confirm.png`, `artifacts/_last_mixed.png`
      and probe_click/probe_stale frames; report per-term recognition for
      `預り金 / 単価 / レジ袋 / お釣り / 確定` into
      `artifacts/ocr-japan-compare.txt` (SC-001/SC-002 evidence).
- [X] T019 Run full offline gates from `vnc_agent/`:
      `uv run pytest tests/unit tests/fixtures -q` and
      `uv run pytest tests/e2e -q`; fix regressions (SC-003).
- [X] T020 [P] Run `uv run ruff check src tests` (and format touched files)
      to keep lint clean.
- [X] T021 Re-run quickstart validations 1–5 and record before/after
      comparison numbers into the feature report section of
      `specs/010-ocr-japanese-model/spec.md` (or a `report.md` alongside) —
      per-term table required by SC-001.

## Dependencies

- Phase 1 (T001–T003) → needed by T008/T011/T013/T018 (assets on disk);
  independent of T004–T006.
- Phase 2 (T004→T005→T006; T004 first) blocks all user stories.
- US1 (T007–T011) requires T004+T005; T008/T011 also require T001/T002.
- US2 (T012–T013) requires T001–T003; independent of US1 code but documents
  its config keys, so run after T008.
- US3 (T014–T017) requires T004 only — independent of US1/US2.
- Phase 6 requires all prior phases.

## Parallel execution examples

- T001 ∥ T002 ∥ T003 (different files).
- After T004/T005: T009 ∥ T010 (different test files) while T007/T008
  proceed.
- US3 (T014–T017) can proceed in parallel with US1/US2 once Phase 2 lands.

## Implementation strategy

MVP = Phase 1 + Phase 2 + US1 (root-cause fix + compat). US2 is
documentation hardening; US3 is the bounded robustness layer. Evidence
gathering (Phase 6) closes the loop with measurable before/after data.
