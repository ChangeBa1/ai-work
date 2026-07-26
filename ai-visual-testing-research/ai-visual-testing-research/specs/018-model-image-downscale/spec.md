# Feature Specification: Downscale Planner-Bound Screenshots Before Model Upload

**Feature Branch**: `018-model-image-downscale`

**Created**: 2026-07-27

**Status**: Draft

**Input**: User description: "`models/planner_client.py::_image_url_content_part` inlines every local screenshot as a full-resolution base64 PNG into each model request. The planner's `plan()`/`describe_screen()` (including Feature 008 cache-miss verification questions and Feature 011 reviews) never output coordinates, so they do not need the original resolution; the full-size PNG costs 1~2s each on upload and on model-side processing. Add an image-preprocessing helper (read → proportional downscale to a configurable max width, default 1024, never upscale → JPEG encode at configurable quality, default 80 → data URI) and wire it into the planner's image path only. The Grounder (`mimo_grounder.py`) outputs coordinates and MUST keep receiving the byte-identical original image payload."

## Clarifications

### Session 2026-07-27 (self-resolved; fully automated run — decisions recorded here instead of asked)

- Q: Does `plan()` need the helper? → A: No code change. Verified against `HttpPlannerClient.plan()`: its user message is `json.dumps(request.model_dump(...))` — a plain text JSON dump of `PlannerRequest`, which has **no image field at all** (`step_intent`, `expected`, `structured_screen`, hints…). `plan()` never attaches an `image_url` content part today, so there is nothing to downscale. Only `describe_screen()` carries an image, and every image-bearing planner path funnels through it: Feature 008 `CachedVisualAnswerer.answer()` (visual_question condition eval + business-resolver escalation) and the Feature 011 arbitration review all call `planner.describe_screen(...)`. They all benefit automatically with a single change site. Feature 015/016 paths that do not call `describe_screen` are untouched by construction.
- Q: Where does the helper live? → A: New module `src/vnc_agent/models/image_payload.py`. The existing `_image_url_content_part` **moves there verbatim** (same bytes-in → dict-out behavior) and `planner_client.py` re-exports it under the same name, so `mimo_grounder.py`'s existing `from vnc_agent.models.planner_client import _image_url_content_part` keeps resolving without touching the grounder file. The new `planner_image_url_content_part(...)` lives beside it.
- Q: What happens when the file cannot be decoded as an image (e.g. truncated/fake bytes)? → A: Fall back to the original passthrough part (base64 of raw file bytes, PNG mime guess) instead of raising. Rationale: the pre-018 behavior never decoded pixels, so a request that used to go out must keep going out; a downscale failure must never turn a working model call into a hard error. Same fallback if JPEG encoding fails.
- Q: Downscale a smaller-than-max-width image? → A: Never upscale. Geometry is kept 1:1 when `width <= max_width`, but the image is still re-encoded as JPEG (quality applies) — the payload-size win comes mostly from PNG→JPEG, and a single output format keeps the wire contract uniform when enabled.
- Q: Config location and names? → A: `PlannerModelConfig` (config `models.yaml`, `planner:` section) gains `planner_image_downscale_enabled` (default `true`), `planner_image_max_width` (default `1024`), `planner_image_jpeg_quality` (default `80`). Grounder config is untouched — there is deliberately no grounder-side switch to misconfigure.
- Q: Feature 008 answer-cache key — must the downscale parameters join `component_identity`? → A: **No key change; justified in "Interaction with Feature 008" below.** The cache is strictly in-memory and per-run, and the downscale parameters cannot change within a cache lifetime, so adding them to the key can never change any lookup outcome today. (Option A — additive `component_identity` fields — was rejected as unwireable dead weight: `CachedVisualAnswerer` is constructed in `runtime/agent_runtime.py`, which is outside this feature's change boundary, so the "parameters" added to the key could only ever be static defaults with zero discriminating power.)
- Q: Mask semantics? → A: Unchanged. The helper receives exactly the path the caller passes today (`screen.path_for_model() or screen.image_path` on the 008 path — the unmasked/safe image per FR-049). Only geometry and encoding of that same image change; which image is chosen is out of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Planner vision calls upload a downscaled JPEG (Priority: P1)

Every `describe_screen()` call (screen description, verification visual questions on 008 cache miss, 011 arbitration reviews) sends a proportionally downscaled (max width 1024 by default, never upscaled) JPEG (quality 80 by default) data URI instead of a full-resolution PNG, cutting upload and model-side processing time by roughly 1~2 s per call.

**Why this priority**: This is the entire point of the feature — the payload shrink on every image-bearing planner call in every run.

**Independent Test**: Point `describe_screen()` at a real 2000-px-wide PNG through an injected `httpx.MockTransport`, decode the captured `image_url` data URI, and assert it is a JPEG whose width equals the configured max width with aspect ratio preserved.

**Acceptance Scenarios**:

1. **Given** a screenshot wider than `planner_image_max_width`, **When** `describe_screen()` sends it, **Then** the request carries a `data:image/jpeg;base64,...` URI whose decoded width equals `planner_image_max_width` and whose aspect ratio matches the original.
2. **Given** a screenshot narrower than or equal to `planner_image_max_width`, **When** `describe_screen()` sends it, **Then** the decoded image keeps its original dimensions (no upscaling) while still being JPEG-encoded.
3. **Given** a file that cannot be decoded as an image, **When** `describe_screen()` sends it, **Then** the request carries the original passthrough payload (byte-identical to the pre-018 part) and no error is raised by the preprocessing step.

---

### User Story 2 - Grounder payload stays byte-identical (Priority: P1)

The Grounder outputs pixel coordinates against the image it is shown; its request payload must remain byte-for-byte what it is today — base64 of the raw original file bytes, PNG mime — regardless of any planner downscale configuration.

**Why this priority**: A resized grounder image would silently corrupt every grounded click coordinate. This is a hard red line, enforced by test.

**Independent Test**: Build `MimoGrounderClient._build_payload(...)` against a real PNG and assert the `image_url` equals `"data:image/png;base64," + base64(raw file bytes)` exactly.

**Acceptance Scenarios**:

1. **Given** any planner downscale configuration (enabled or not, any width/quality), **When** the grounder builds its payload, **Then** the image data URI is byte-identical to `base64(original file bytes)` with the original mime type.

---

### User Story 3 - Kill switch restores pre-018 bytes (Priority: P2)

An operator sets `planner_image_downscale_enabled: false` and the planner's image payload is byte-for-byte identical to the pre-018 output (raw file bytes base64, mime guessed from the filename), for debugging or when a model version turns out to need full resolution.

**Acceptance Scenarios**:

1. **Given** `planner_image_downscale_enabled: false`, **When** `describe_screen()` sends any image, **Then** the produced content part equals the pre-018 `_image_url_content_part(path)` output exactly (same dict, same URI bytes).

### Edge Cases

- Unreadable/undecodable image file → passthrough fallback (US1 scenario 3); `cv2.imencode` failure → same fallback.
- Extremely wide, 1-px-tall image → proportional height is rounded but floored at 1 px (never a 0-dimension image).
- `plan()` requests → no image part exists today; nothing is (or needs to be) processed there. If a future change adds an image part to `plan()`, it must go through the same helper (noted in code comment).
- Alpha channels: JPEG carries no alpha; `cv2.imread` default (BGR) drops it. VNC screenshots are opaque, so this is a non-issue; the passthrough fallback covers any exotic input that fails to decode.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A helper module `models/image_payload.py` MUST provide `planner_image_url_content_part(image_path, *, enabled, max_width, jpeg_quality)` that reads the image, proportionally downscales it to at most `max_width` pixels wide (never upscaling), encodes it as JPEG at `jpeg_quality`, and returns an OpenAI-compatible `image_url` content part with a `data:image/jpeg;base64,...` URI. It MUST use OpenCV only (existing dependency, no new dependencies).
- **FR-002**: With `enabled=false`, the helper MUST return output byte-identical to the pre-018 `_image_url_content_part(image_path)`; with `enabled=true` but an undecodable image or a failed JPEG encode, it MUST fall back to that same passthrough output instead of raising.
- **FR-003**: `HttpPlannerClient.describe_screen()` MUST build its image content part via the helper, driven by the planner config values; `plan()` is verified to carry no image part and MUST remain unchanged. All paths that call `describe_screen()` (008 cached visual answers, 011 reviews, plain describes) thereby receive downscaled payloads with no per-caller change.
- **FR-004**: `MimoGrounderClient`'s image payload MUST remain byte-identical to today's output (base64 of raw original file bytes, original mime). `mimo_grounder.py`'s image-payload logic MUST NOT change; a test MUST assert its data URI equals the raw-bytes encoding exactly.
- **FR-005**: `PlannerModelConfig` MUST gain `planner_image_downscale_enabled: bool = true`, `planner_image_max_width: int = 1024` (≥ 1), `planner_image_jpeg_quality: int = 80` (1..100), loadable from `config/models.yaml` `planner:` section.
- **FR-006**: The image *selection* semantics MUST NOT change: the helper operates on exactly the path callers already pass (unmasked/safe image per FR-049 rules); only geometry and encoding are transformed.
- **FR-007**: The Feature 008 answer-cache key MUST remain unchanged (see below); `verification/answer_cache.py` is not modified by this feature.

### Interaction with Feature 008 (vision answer cache) — why the key does not change

The 008 cache key (`CachedVisualAnswerer._key`) is built from the frame's
`content_hash` + `scope_key` (pixel/mask identity) + question sha + request-side
model identity. It never encoded the wire *encoding* of the image payload, so
downscaling does not make any existing key semantically wrong: two lookups that
collide still refer to the same pixels and the same question.

The residual risk named in the feature request — "changing downscale parameters
may change the model's answer, so a cached answer produced under different
parameters could be replayed" — cannot occur with the current cache design:

1. `AnalysisResultCache` is **in-memory only** (a bounded `deque` of 3..5
   frames in `perception/cache.py`; "no pixels/paths stored", never persisted to
   disk). Every process/run starts with an empty cache.
2. The downscale parameters come from `PlannerModelConfig`, loaded **once** at
   composition time; they are immutable for the lifetime of the process and
   therefore for the lifetime of any cache entry.
3. Hence within any single cache lifetime there is exactly one parameter set;
   a lookup under parameters different from the stored entry's is impossible.

Adding the parameters to `component_identity` today would therefore never
change any lookup outcome. Worse, it cannot even be wired honestly:
`CachedVisualAnswerer` is constructed in `runtime/agent_runtime.py` (outside
this feature's change boundary), so the key could only carry hardcoded
defaults — a false identity that *looks* discriminating but is not.

**Recorded constraint for the future**: if the answer cache ever becomes
persistent across runs (or parameters become mutable at runtime), the downscale
parameters (`enabled`, `max_width`, `jpeg_quality`) MUST at that point be added
to `component_identity` (additive) or covered by an `ALGORITHM_REVISION` bump.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a screenshot wider than the configured max width, the planner-bound payload is a JPEG data URI at exactly the configured width with preserved aspect ratio (asserted by test); for a 1920×1080 PNG screenshot the base64 payload shrinks by an order of magnitude, removing ~1–2 s of upload+processing per vision call in production (design property; not measured in offline CI).
- **SC-002**: Grounder payload data URI is byte-identical to `base64(raw file bytes)` (asserted by test).
- **SC-003**: With `planner_image_downscale_enabled: false`, the planner part is byte-identical to the pre-018 output (asserted by test).
- **SC-004**: Full offline regression (`tests/unit tests/fixtures tests/e2e tests/integration`) passes with no existing test modified (1 pre-existing skip allowed).

## Assumptions

- VNC screenshots are opaque RGB; JPEG's lack of alpha loses nothing.
- The planner model (`describe_screen` consumer) never returns coordinates, so resolution loss is semantically safe there; the system prompt already forbids coordinates in planner output.
- The existing fixture `tests/fixtures/test_planner_client_describe_screen.py` writes deliberately fake PNG bytes; it stays green through the undecodable-input passthrough fallback (its byte-equality assertion is exactly the fallback's contract).
- Out of scope: grounder-side compression of any kind, changing which image (masked/unmasked) is sent, `plan()` payload changes, persistent caching.
