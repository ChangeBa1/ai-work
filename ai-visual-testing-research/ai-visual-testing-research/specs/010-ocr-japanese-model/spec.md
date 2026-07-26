# Feature Specification: OCR Japanese Recognition Model

**Feature Branch**: `010-ocr-japanese-model`

**Created**: 2026-07-26

**Status**: Implemented (see tasks.md — all 21 tasks complete; before/after evidence in evidence.md)

**Input**: User description: "OCR engine Japanese recognition model support: make the OCR recognition language/model configurable in the perception layer (config.py + config/agent.yaml), default this deployment to Japanese PP-OCRv4 rec model for RapidOCR, keep run_ocr/run_ocr_array interface and OCRItem output unchanged, model files placed in-project with documented source, plus a failed-needle ROI 2x upscale re-OCR retry in the text verifier"

## Problem Statement

The agent tests a Japanese-language Windows GUI over VNC, but the OCR
recognition component currently uses its bundled Chinese-oriented recognition
model. Real runs against the Japanese system produced systematic
misrecognition of Japanese UI vocabulary — e.g. `預り金` read as `預以金`,
`レジ袋` truncated to `ジ袋` (which also shifts the clickable bbox center),
`単価` missed entirely, and `お釣り` read as garbage (`x二1-`). The existing
mitigation is a simplified/traditional-glyph confusion mapping applied at
text-verification time, which patches individual symptoms but cannot recover
characters the recognizer never emitted.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configurable OCR recognition language/model (Priority: P1)

As a test operator running the agent against a deployment whose UI language is
not covered well by the default OCR model, I can declare the OCR recognition
language (and/or an explicit recognition model file) in the agent
configuration, so that on-screen text in that language is recognized correctly
without any code change.

**Why this priority**: All downstream behavior — text-appears verification,
OCR-based grounding, click-coordinate derivation from text bboxes — depends
on OCR emitting the correct characters. This is the root-cause fix.

**Independent Test**: Point the configuration at the Japanese recognition
model, run OCR over archived real POS frames, and confirm previously
misrecognized Japanese terms are now emitted verbatim; remove the
configuration and confirm behavior is byte-identical to today's default.

**Acceptance Scenarios**:

1. **Given** a configuration that selects the Japanese recognition model,
   **When** OCR runs over an archived Japanese POS frame, **Then** the OCR
   item list contains the Japanese terms that the default model previously
   misread (measured over the regression word list, see SC-001).
2. **Given** no OCR language/model configuration at all, **When** OCR runs,
   **Then** the engine behaves exactly as before this feature (bundled
   default model, same output shape).
3. **Given** a configuration naming a recognition-model file that does not
   exist on disk, **When** the agent composes its runtime, **Then** startup
   fails immediately with an error naming the missing path (no silent
   fallback to the wrong-language model mid-run).

---

### User Story 2 - In-project model files with documented provenance (Priority: P2)

As a maintainer deploying the agent onto an offline/weak machine, I need the
non-bundled recognition model files to live inside the project tree with their
source and placement documented, so a deployment never depends on an implicit
runtime download.

**Why this priority**: Without a documented, in-repo model the P1 capability
is not reproducible on the target machines.

**Independent Test**: Fresh clone + dependency sync on a machine with no
model cache: the configured Japanese model file is already present at the
documented in-repo path and OCR uses it without network access.

**Acceptance Scenarios**:

1. **Given** a fresh checkout, **When** the operator reads the project
   documentation, **Then** the model file's source URL, version and expected
   in-repo path are stated, and the file at that path matches.
2. **Given** the model files are present at the documented path, **When** the
   agent starts with the shipped default configuration, **Then** no network
   download is attempted for OCR models.

---

### User Story 3 - Failed-needle ROI upscale re-OCR retry (Priority: P3)

As a test author whose `text_appears` assertion targets small on-screen text
inside a declared region, I want the verifier — when the needle is not found
in the full-frame OCR result — to re-OCR just that region at 2x magnification
once before declaring failure, so that small-glyph misses do not fail steps
spuriously.

**Why this priority**: Secondary robustness layer on top of the P1 model fix;
valuable but not required for the root-cause correction.

**Independent Test**: Feed a frame where the needle is only recoverable at 2x
magnification within the condition's region; verify the condition passes with
the retry and fails without it, and that conditions without a region never
trigger the retry.

**Acceptance Scenarios**:

1. **Given** a `text_appears` condition with a declared region whose needle is
   absent from full-frame OCR but recoverable from a 2x-upscaled crop of that
   region, **When** verification runs, **Then** the condition passes and the
   retry happens at most once.
2. **Given** a `text_appears` condition without a region, **When** the needle
   is not found, **Then** no upscale retry is attempted and the condition
   fails as today.
3. **Given** a `text_disappears` condition, **When** verification runs,
   **Then** the upscale retry is never used to flip a pass into a fail
   (retry applies only to recovering missed text for `text_appears`).

---

### Edge Cases

- Configured language has no packaged model mapping and no explicit model
  path: configuration load fails with a clear error (unknown language value).
- Explicit model path is set but the language field is absent: the explicit
  path wins; language is only a convenience for resolving packaged defaults.
- Recognition model file exists but its character dictionary companion is
  required and missing: startup fails with an error naming the missing path.
- ROI region lies partially outside the frame: the crop is clamped to frame
  bounds; an empty clamped region skips the retry.
- The 2x re-OCR itself returns nothing: the condition fails normally; no
  further retries or escalations occur (bounded, single retry).
- Offline stub mode (OCR library unavailable in a test environment): the
  stub path is unaffected by the new configuration and still returns empty
  results.
- The glyph-confusion mapping in the text verifier stays in place as a final
  tolerance layer; the model change must not depend on removing it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The perception configuration MUST accept an OCR recognition
  language identifier (`ocr_lang`) and optional explicit recognition model
  file path and character-dictionary file path; all three default to "unset",
  which MUST reproduce the pre-feature behavior exactly.
- **FR-002**: When `ocr_lang` names a language with a project-provided model
  mapping (at minimum: `japan`), the OCR engine MUST load that recognition
  model; an explicit model-path setting MUST override the language mapping.
- **FR-003**: The OCR entry points (`run_ocr`, `run_ocr_array`) and the OCR
  item output structure MUST remain unchanged in signature and shape;
  language/model selection is engine-internal.
- **FR-004**: Engine configuration MUST be applied at runtime-composition
  time (single composition call site), not per-invocation; the loaded engine
  MUST be rebuilt only when the effective OCR settings change.
- **FR-005**: If a configured model or dictionary file is missing at
  configuration time, composition MUST fail fast with an error that names the
  offending path. Absent configuration MUST NOT fail (compat default).
- **FR-006**: The Japanese recognition model files MUST live in the project
  tree at a documented path, with source URL and revision recorded in project
  documentation; runtime MUST NOT download models.
- **FR-007**: The shipped deployment default configuration (`agent.yaml`)
  MUST select the Japanese recognition model.
- **FR-008**: When a `text_appears` condition with a declared region is not
  satisfied by the already-computed OCR items, the text verifier MUST perform
  exactly one additional OCR pass over the region cropped from the frame
  image and upscaled 2x, and re-evaluate; this retry MUST NOT apply to
  conditions without a region and MUST NOT be used to flip `text_disappears`
  outcomes.
- **FR-009**: The ROI retry MUST only touch the OCR engine module (new
  helper) and the text-verifier call site; verification orchestration,
  business resolution, runtime, and the analysis cache MUST NOT change.
- **FR-010**: The existing glyph-confusion normalization in the text verifier
  MUST be preserved as a last-layer tolerance.
- **FR-011**: The OCR component identity reported to the analysis cache MUST
  reflect the configured recognition language so cached results can never be
  confused across differently-configured engines.

### Key Entities

- **OCR engine settings**: effective recognition configuration — language
  identifier, recognition model path, character-dictionary path; resolved
  once at composition, held by the perception OCR module.
- **Recognition model asset**: an on-disk model file (plus optional
  character dictionary) with documented provenance, referenced by
  configuration.
- **ROI retry pass**: a bounded, single re-recognition over a declared
  region at 2x scale, producing the same OCR item structure with bboxes
  mapped back to original frame coordinates.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the archived real-run regression frames, the Japanese terms
  `預り金`, `単価`, `レジ袋`, `お釣り`, `確定` are each either recognized
  verbatim or measurably improved versus the default model, with a
  before/after per-term comparison recorded in the feature report; no term
  regresses.
- **SC-002**: With configuration absent, OCR output on the same frames is
  identical to pre-feature behavior (backward compatibility).
- **SC-003**: All existing offline test suites pass; new configuration-load
  tests cover default, language-mapped, explicit-path, and missing-file
  cases.
- **SC-004**: A misconfigured (missing) model path is reported at startup
  with the offending path named, before any VNC connection is attempted.
- **SC-005**: The ROI retry adds at most one OCR pass per failed regioned
  condition evaluation (bounded work, no retry loops).

## Assumptions

- Decision (recorded, not clarified interactively — automated run): stay on
  the existing OCR library (`rapidocr_onnxruntime` 1.4.4) and swap only the
  recognition-stage model via its supported `rec_model_path` /
  `rec_keys_path` parameters, rather than migrating to a newer OCR package
  or another provider. Rationale: smallest change surface, keeps the engine
  call contract `engine(img) -> (result, elapse)` and offline-stub behavior
  intact, avoids a new runtime download dependency.
- Decision: recognition model = `japan_PP-OCRv4_rec_mobile.onnx` (PP-OCRv4
  Japanese mobile recognition model, ONNX conversion from the RapidOCR
  project's official model hub, ModelScope repo `RapidAI/RapidOCR`), with
  its `japan_dict.txt` character dictionary. Detection and orientation
  models stay on the bundled defaults — text detection is
  language-agnostic; only recognition is language-specific.
- Decision: model files are committed to the repository under
  `vnc_agent/models/ocr/` (~10 MB total), because target machines are weak/
  offline and the constitution forbids implicit runtime model management.
- The environment building this feature has network access to ModelScope;
  if a future environment does not, the documented URLs allow manual
  placement at the same path (config load will fail fast until placed).
- The `japan` recognition model also covers ASCII digits and Latin letters,
  so amount/quantity matching keeps working.
- Per-deployment language default: this repository's shipped `agent.yaml`
  targets the Japanese deployment; other deployments override or unset
  `ocr_lang` in their own config directory.
