# Configuration

| File | Purpose |
|------|---------|
| `agent.yaml` | Runtime defaults: step timeout/retries, wait/stability, perception flags, artifact paths, security mask regions, grounding thresholds, **per-`FailureType` recovery budgets** (`recovery.<type>.max_retries` / `cooldown_ms`) |
| `models.yaml` | Planner & Grounder providers, base URLs, models, timeouts (`describe_screen_timeout_seconds` defaults to planner `timeout_seconds`) |
| `vnc-targets.yaml` | VNC host/port/`password_env` (password value is never stored here) |

## Environment variables (secrets)

| Variable | Used by |
|----------|---------|
| `VNC_AGENT_VNC_PASSWORD` | VNC target `password_env` |
| `VNC_AGENT_PLANNER_API_KEY` | Planner `api_key_env` |
| `VNC_AGENT_GROUNDER_API_KEY` | Grounder `api_key_env` |

Aligns with quickstart.md prerequisites and FR-047 (no plaintext secrets in config or logs).

## Local validation checklist (T095 / quickstart)

1. Start a local test VNC server on the host/port in `vnc-targets.yaml`.
2. `vnc-agent run testcases/smoke-connect.yaml --dry-run` → exit 0.
3. Run scenarios in `specs/001-vnc-core-execution-loop/quickstart.md` (1–9).
4. Offline tests: `pytest` (unit/fixtures/e2e with fakes).
5. Integration: `VNC_AGENT_INTEGRATION=1 pytest tests/integration`.
6. During long runs, watch process RSS/handles for SC-009 (frame buffer ≤5).

## Screenshot dedup / analysis cache / zh-CN report config (feature 004)

`agent.yaml` adds two new keys:

```yaml
perception:
  cache_max_frames: 5   # bounded analysis-cache window; only 3, 4, or 5 accepted

reporting:
  locale: zh-CN          # default and currently only registered resource bundle
```

- **`perception.cache_max_frames`** bounds how many recent logical frames' analysis-cache
  entries (OCR/template/vision_describe pure results) stay referenceable. It is validated
  at config-load time to the closed range `[3, 5]` — any other integer (including `0`, `1`,
  `2`, or anything `> 5`) fails to load. This is a memory bound, not a business setting: a
  bigger window does not change *what* gets cached (only strictly-adjacent duplicate frames
  are ever cache-eligible), only how long a source result survives a gap in references.
- **`reporting.locale`** selects the zh-CN resource bundle used by both the JSON
  `display_status`/`localized_message` fields and the fully-localized HTML report. `zh-CN`
  is the only registered locale today; setting anything else (e.g. `fr-FR`, `en-US`) fails
  config load immediately — `load_agent_config()` raises before any run starts, there is no
  silent fallback to English. Adding a new language means registering a complete resource
  bundle in `reporting/localization.py`, not adding a partial override.
- **Cache invalidation dimensions**: besides the frame's own pixel content hash and full
  `CaptureScope` (kind/coordinates/resolution/pixel format/mask identity/private-policy),
  each component adds its own identity fields that also invalidate a would-be hit — OCR:
  backend/version/language/preprocessing; template: matcher revision + a content fingerprint
  of the whole template set (never a path/mtime); vision: provider + requested
  model/version/prompt/schema-revision/structured-hint fingerprint. Changing any of these
  config-driven identities (e.g. bumping the Planner/Grounder model, editing a template
  file) invalidates future cache hits without needing a manual cache clear.
