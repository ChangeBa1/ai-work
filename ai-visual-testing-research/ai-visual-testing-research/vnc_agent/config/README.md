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
