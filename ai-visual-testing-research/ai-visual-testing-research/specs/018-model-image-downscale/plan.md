# Implementation Plan: Downscale Planner-Bound Screenshots Before Model Upload

**Branch**: `018-model-image-downscale` | **Date**: 2026-07-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/018-model-image-downscale/spec.md`

## Summary

Introduce `models/image_payload.py` holding (a) the verbatim-moved passthrough
`_image_url_content_part` (re-exported from `planner_client.py` so
`mimo_grounder.py`'s import — and therefore the grounder's byte-identical
payload — is untouched) and (b) a new `planner_image_url_content_part` that
reads the screenshot with OpenCV, proportionally downscales to
`planner_image_max_width` (default 1024, never upscales), JPEG-encodes at
`planner_image_jpeg_quality` (default 80), and returns a
`data:image/jpeg;base64,...` content part — with byte-identical passthrough
when disabled or when decode/encode fails. Wire it into
`HttpPlannerClient.describe_screen()` only (`plan()` verifiably carries no
image). Three new `PlannerModelConfig` fields, no answer-cache key change
(justified in spec), no new dependencies.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed project in `vnc_agent/`)

**Primary Dependencies**: opencv-python (`cv2.imread`/`resize`/`imencode` — existing), httpx, pydantic

**Storage**: N/A

**Testing**: pytest + pytest-asyncio; offline fixtures use `httpx.MockTransport`; real PNGs synthesized with numpy + `cv2.imwrite`

**Target Platform**: same as project (Windows/Linux CLI)

**Project Type**: CLI agent library

**Performance Goals**: ~order-of-magnitude smaller vision payloads → ~1–2 s less upload+model latency per `describe_screen()` call

**Constraints**: grounder payload byte-identical (red line); `enabled=false` byte-identical to pre-018; no new dependencies; no changes to runtime/perception/verification wiring

**Scale/Scope**: 1 new source module, 2 edited source files (planner_client.py, config.py), 1 config yaml, 1 new test file, spec docs

## Constitution Check

*GATE: passed.*

- Principle I (deterministic runtime control): untouched — pure payload-encoding change on the model boundary.
- Principle II (Planner/Grounder separation): reinforced — the planner (no coordinates) gets lossy-but-cheap images; the grounder (coordinates) keeps pixel-exact images, enforced by test.
- Resource constraint (弱配置电脑 / avoid waste): directly served — less bandwidth and model latency per vision call.
- 凭据与隐私: unaffected — same image content, different encoding.

**Domain-Agnostic Core gate (Principle VI)**:

- [x] No business-specific fields/states/branches — generic image-preprocessing capability.
- [x] No scenario semantics introduced.
- [x] Validated by provider-level fixture tests, not scenario fixtures.

## Phase 0 — Research (inline; no open unknowns)

- **`plan()` image audit**: `PlannerRequest` has no image field; `plan()`'s user content is a JSON text dump. No image part exists → no change. Documented in spec Clarifications.
- **Grounder import chain**: `mimo_grounder.py` does `from vnc_agent.models.planner_client import _KEEPALIVE_LIMITS, _image_url_content_part`. Moving the function body to `image_payload.py` and re-exporting the same name from `planner_client.py` keeps the grounder file byte-identical and its payload byte-identical (same function object semantics: raw bytes → base64 → mime-guessed data URI).
- **OpenCV mechanics**: `cv2.imread(path)` returns `None` on failure (→ passthrough fallback); `cv2.resize(..., interpolation=cv2.INTER_AREA)` is the correct shrink filter; `cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])` returns `(ok, buf)`; `ok=False` → passthrough fallback. Height rounds to `max(1, round(h * max_width / w))`.
- **Existing fixture safety**: `test_planner_client_describe_screen.py` sends fake PNG bytes and asserts byte-equality of the decoded URI — the undecodable-input fallback preserves exactly that, so the test stays green unmodified (SC-004 requires this).
- **008 cache**: `AnalysisResultCache` is in-memory, bounded (3..5 frames), never persisted; downscale params are process-immutable → key change would be a no-op today and unwireable within the change boundary. Decision: no `answer_cache.py` change; constraint recorded in spec for any future persistent cache.

## Phase 1 — Design

### Changes by file

1. **NEW `vnc_agent/src/vnc_agent/models/image_payload.py`**
   - `_image_url_content_part(image_path) -> dict` — moved verbatim from `planner_client.py` (raw bytes, mime guess, base64 data URI). This *is* the grounder/fallback/disabled path.
   - `planner_image_url_content_part(image_path, *, enabled=True, max_width=1024, jpeg_quality=80) -> dict`:
     - `not enabled` → return `_image_url_content_part(image_path)`.
     - `cv2.imread` → `None` → passthrough fallback.
     - `w > max_width` → `cv2.resize` to `(max_width, max(1, round(h*max_width/w)))` with `INTER_AREA`; else keep geometry.
     - `cv2.imencode(".jpg", ..., IMWRITE_JPEG_QUALITY=jpeg_quality)`; failure → passthrough fallback.
     - Return `{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,<b64>"}}`.
2. **`vnc_agent/src/vnc_agent/models/planner_client.py`**
   - Replace the local `_image_url_content_part` definition with a re-export from `image_payload` (same public name — `mimo_grounder.py` import untouched); import `planner_image_url_content_part`.
   - `describe_screen()`: image part built via `planner_image_url_content_part(request.image_ref, enabled=cfg.planner_image_downscale_enabled, max_width=cfg.planner_image_max_width, jpeg_quality=cfg.planner_image_jpeg_quality)`.
   - `plan()`: unchanged (comment notes any future image part must use the helper).
3. **`vnc_agent/src/vnc_agent/config.py`**
   - `PlannerModelConfig` += `planner_image_downscale_enabled: bool = True`, `planner_image_max_width: int = Field(1024, ge=1)`, `planner_image_jpeg_quality: int = Field(80, ge=1, le=100)`.
4. **`vnc_agent/config/models.yaml`**
   - Document the three new keys (commented defaults) under `planner:`.
5. **NEW `vnc_agent/tests/fixtures/test_planner_image_downscale.py`** — see tasks.

### Non-changes (explicit)

- `mimo_grounder.py`: zero edits; payload byte-identity locked by a new test.
- `verification/answer_cache.py`: zero edits (spec §Interaction with Feature 008).
- `runtime/`, `perception/`, image *selection* (masked/unmasked) logic: untouched.
- `StubPlanner`/`StubGrounder`, provider protocols: untouched.

## Project Structure

### Documentation (this feature)

```text
specs/018-model-image-downscale/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
vnc_agent/
├── config/
│   └── models.yaml                      # + 3 documented planner image keys
├── src/vnc_agent/
│   ├── config.py                        # PlannerModelConfig + 3 fields
│   └── models/
│       ├── image_payload.py             # NEW: passthrough + downscale helpers
│       └── planner_client.py            # re-export + describe_screen wiring
└── tests/
    └── fixtures/
        └── test_planner_image_downscale.py   # NEW
```

**Structure Decision**: single-project layout as-is; new test lives beside the
other model-client fixture tests.

## Complexity Tracking

No constitution violations; table not needed.
