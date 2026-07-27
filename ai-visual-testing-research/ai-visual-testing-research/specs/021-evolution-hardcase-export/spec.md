# Feature Specification: Evolution Hard-Case Mining & Dataset Export

**Feature Branch**: `021-evolution-hardcase-export`

**Created**: 2026-07-27

**Status**: Draft

**Input**: User description: "Offline, read-only hard-case mining over historical run data (overall_design.md §12.3) plus a JSONL training-dataset exporter (§12.4). The runtime already persists rich per-iteration evidence (grounding candidates + confidence, execution results, verification results, recovery attempts, memory hits) but the hard-case criteria and the offline-training export interface are entirely unimplemented — `evolution/experience_collector.py` is a write-only collector and nothing ever reads the accumulated data. Goal: mine 'model struggled here' samples from the SQLite run store and export them as one-JSON-object-per-line dataset rows (screenshot path + target semantics + correct bbox + wrong candidates + verification outcome + criteria labels) so a future fine-tuned grounder has training data. Zero runtime impact: everything runs only under a new `vnc-agent evolution export` CLI subcommand."

## Clarifications

### Session 2026-07-27 (self-resolved; fully automated run — decisions recorded here instead of asked)

- Q: What data is actually available in the SQLite store to implement the §12.3 criteria? → A: Audited (`storage/database.py`, `storage/repositories.py`). Five relevant tables: `test_runs` (run_id, test_case_id, status, started_at, full `TestRun` payload **including `frames[]`** with `safe_image.path` per frame id), `step_records` (final_status, failure_reason, full `StepRecord` payload), `action_iterations` (per-iteration payload = full `ActionIteration` dump: `grounding_result.candidates[].{bbox,confidence}`, `executable_action.{method,coordinates}`, `execution_result.{success,actual_click_point,target_region}`, `verification_result.status`, `memory_hit`, `semantic_action.target`, embedded `recovery_attempts[]`), `recovery_attempts` (failure_type, strategy, resolved, iteration_index), `visual_experiences` (outcome, payload with `failure_type`). `page_memories`/`element_memories` hold only **aggregate** success/failure counters — not traceable to a specific run/step.
- Q: Which §12.3 criteria are implementable from that data? → A: See the criteria table below. Implementable: low grounding confidence; Top-1 fail → Top-2 promoted success (via the persisted `second_candidate` recovery strategy — the runtime's `candidate_index` itself is folded into an identity hash, never stored as a plain field, so the strategy record is the faithful persisted signal); retry-then-success; zoom_reground used; memory direct-click that failed verification; verification-failed mouse iterations; FailureType hits; high-confidence prediction failure. **Not implementable (missing data, unchanged write path)**: Planner-vs-Grounder conflict and OCR-vs-MiMo conflict (feature 011 arbitration decisions are not persisted per-iteration), human correction (design §12.2 `human_correction` was never added to `VisualExperience` and nothing writes it), unknown-page (page memory has no per-run "unknown" marker). `WRONG_TARGET` is **not** a member of the codebase's `FailureType` enum (`domain/recovery.py`) — the closest persisted signals are `unexpected_dialog` / `target_not_found`, which form the default FailureType hit set.
- Q: `visual_experiences.failure_type` — usable? → A: The runtime calls `ExperienceCollector.collect()` without a `failure_type` argument (`runtime/agent_runtime.py` step loop), so the column payload is `None` in practice. The miner still reads it when non-null (forward compatible) but the FailureType criterion is primarily sourced from `recovery_attempts.payload.failure_type`.
- Q: Sample granularity — per iteration or per step? → A: Per **(run_id, step_id)**. Design §12.4 defines one sample as screenshot + target semantics + correct bbox + wrong candidates + verification result; the correct/wrong split only exists at step level (failed iterations contribute wrong candidates, the final passed iteration contributes the correct bbox).
- Q: How are screenshots referenced? → A: Path only, **never copied**. Each sample carries the before-frame's `safe_evidence` path (masked at capture time per FR-049 of feature 001) resolved from the run payload's `frames[]`, expressed relative to the artifacts root when possible (POSIX separators). Consumers resolve paths themselves; a missing/unresolvable frame yields `screenshot_path: null` and the sample is still exported (labels remain useful).
- Q: Sensitive-data handling? → A: Every exported row passes through the existing sensitive-field redaction convention (`logging_setup._redact_value` semantics: key-substring match, recursive, `***REDACTED***`), keyed by `security.sensitive_field_names` from config unioned with the built-in `DEFAULT_SENSITIVE` set (which includes `text_value` — typed text never leaks into a dataset). Screenshot files are already masked at capture time and are only referenced, not re-processed.
- Q: Where do thresholds live? → A: New additive `evolution:` config section (`config.py::EvolutionConfig` + `config/agent.yaml`): `hard_case_grounding_confidence_below` (default 0.7), `hard_case_high_confidence_at_least` (default 0.9), `hard_case_failure_types` (default `[unexpected_dialog, target_not_found]`). Omitting the section keeps all defaults (pydantic `default_factory`), so existing configs load unchanged.
- Q: `--since` comparison with SQLite naive datetimes? → A: `test_runs.started_at` round-trips through aiosqlite as a naive datetime. Both sides are normalized to UTC-aware before comparison (naive values are assumed UTC, matching the runtime's `datetime.now(UTC)` writes). Runs with `started_at IS NULL` are excluded by a `--since` filter (their age is unknowable) but included when no filter is given.

## Criteria table (§12.3 → implementable subset)

| # | Design §12.3 criterion | Label | Status | Persisted signal |
|---|---|---|---|---|
| 1 | Grounder 置信度低 | `low_grounding_confidence` | ✅ | any iteration's top-1 `grounding_result.candidates[0].confidence < hard_case_grounding_confidence_below` |
| 2 | Top-1 失败但 Top-2 成功 | `top2_promotion_success` | ✅ (proxy) | a `second_candidate` recovery strategy recorded for the step AND step `final_status == "passed"` (candidate_index itself is not persisted as a plain field) |
| 3 | 连续重试 | `retry_then_success` | ✅ | step `final_status == "passed"` AND iteration count > 1 |
| 4a | zoom_reground 兜底 (014) | `zoom_reground_used` | ✅ | a `zoom_reground` recovery strategy recorded for the step |
| 4b | 记忆兜底失败 (015) | `memory_fallback_failed` | ✅ | any iteration with non-null `memory_hit` whose `verification_result.status == "failed"` (aggregate `element_memories.failure_count` is not run-traceable) |
| 5 | 验证失败且动作是 mouse | `mouse_verification_failed` | ✅ | any iteration with `verification_result.status == "failed"` AND `executable_action.method == "mouse"` |
| 6 | WRONG_TARGET / 未知弹窗等 FailureType 命中 | `failure_type_hit` | ✅ (partial) | any `recovery_attempts.failure_type` (or non-null `visual_experiences.failure_type`) ∈ `hard_case_failure_types`. `WRONG_TARGET` does not exist in the `FailureType` enum → cannot be matched; defaults cover `unexpected_dialog` + `target_not_found` |
| 7 | 高置信度预测失败 | `high_confidence_failure` | ✅ | any iteration with top-1 confidence ≥ `hard_case_high_confidence_at_least` AND `verification_result.status == "failed"` (included because the data is fully available — "最大可实现子集") |
| — | Planner 与 Grounder 冲突 | — | ❌ not implemented | conflict decisions are not persisted per-iteration; would need a new write-path record (out of scope: write path untouched) |
| — | OCR 与 MiMo 冲突 | — | ❌ not implemented | feature 011 arbitration outcome is not persisted per-iteration; same missing-data reason |
| — | 人工纠正 | — | ❌ not implemented | no `human_correction` field is ever written (design §12.2 field absent from `VisualExperience`) |
| — | 未知页面 / 未知弹窗(页面级) | — | ❌ partial only | page memory stores no per-run "unknown page" event; unknown *dialogs* are covered via `unexpected_dialog` in criterion 6 |
| — | 自愈成功(replay patch) | — | ❌ not implemented | replay patches (016) reference script steps, not exploration iterations; linking them to a screenshot+bbox sample needs a joining record that is never written |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Export hard-case dataset from historical runs (Priority: P1)

A researcher preparing to fine-tune a dedicated grounder points the CLI at the accumulated run database and gets a JSONL dataset of exactly the steps where the current model struggled, each row carrying the screenshot reference, target semantics, correct bbox (when the step eventually passed), wrong candidates from failed iterations, verification outcome, traceability ids and the list of hard-case criteria it matched.

**Why this priority**: This is the entire feature — without the export there is no training data, and the write-only collector's accumulated evidence stays dead weight.

**Independent Test**: Seed a temporary SQLite database with a synthetic run (one step with a low-confidence failed first iteration and a successful retry, one clean step), run `vnc-agent evolution export --db ... --out dataset.jsonl`, assert exactly the struggling step is exported with the expected criteria labels and the summary JSON counts match.

**Acceptance Scenarios**:

1. **Given** a database containing a step whose first iteration had top-1 grounding confidence 0.4 and failed verification and whose second iteration passed, **When** the operator runs `evolution export`, **Then** `dataset.jsonl` contains exactly one row for that step with `low_grounding_confidence`, `retry_then_success` and `mouse_verification_failed` among its `criteria`, a `correct_bbox` from the passing iteration and one wrong-candidate entry from the failed iteration.
2. **Given** the same database, **When** the export finishes, **Then** stdout carries a single JSON summary object with `total_steps_scanned`, `exported_samples` and per-criterion hit counts consistent with the file content, and the process exits 0.
3. **Given** a database with only clean single-iteration passing steps (confidence ≥ threshold), **When** the operator exports, **Then** the JSONL file is created empty, the summary reports `exported_samples: 0` and the exit code is still 0.

---

### User Story 2 - Filter by date and by criteria (Priority: P2)

The researcher wants only recent data or only a specific failure family: `--since 2026-07-01` restricts to runs started on/after that instant, and repeatable `--criteria` flags restrict the export to samples matching at least one named criterion.

**Independent Test**: Seed two runs with different `started_at`; assert `--since` exports only the newer one; assert `--criteria zoom_reground_used` exports only steps that used the zoom escalation; assert an unknown criterion name exits 2 with the valid names listed.

**Acceptance Scenarios**:

1. **Given** runs started 2026-06-01 and 2026-07-10, **When** exporting with `--since 2026-07-01`, **Then** only the July run's steps are scanned/exported.
2. **Given** `--criteria low_grounding_confidence`, **When** a step matches only `retry_then_success`, **Then** it is not exported (but a step matching both filters in its full label list).
3. **Given** `--criteria not_a_criterion`, **When** invoked, **Then** the command exits 2 and names the valid criteria.

---

### User Story 3 - Deployment-tunable thresholds (Priority: P3)

An operator tunes what "low confidence" means for their deployment by editing the additive `evolution:` config section; omitting the section entirely keeps shipped defaults and existing configs keep loading unchanged.

**Acceptance Scenarios**:

1. **Given** no `evolution:` section in `agent.yaml`, **When** config loads, **Then** `evolution.hard_case_grounding_confidence_below == 0.7`, `hard_case_high_confidence_at_least == 0.9`, `hard_case_failure_types == ["unexpected_dialog", "target_not_found"]`.
2. **Given** `evolution: {hard_case_grounding_confidence_below: 0.5}`, **When** exporting a step whose top-1 confidence was 0.6, **Then** the `low_grounding_confidence` label is not applied.

### Edge Cases

- **Empty/missing tables**: a fresh database (schema created, zero rows) exports 0 samples, writes an empty JSONL file, exits 0.
- **Iteration without grounding_result / executable_action / verification_result** (e.g. keyboard-only or crashed iteration): every predicate treats missing sub-objects as "no signal" — never a crash, never a false positive.
- **Frame id not resolvable to a screenshot** (frames list pruned, artifacts deleted): `screenshot_path: null`, sample still exported.
- **Boundary confidence exactly at threshold**: `low_grounding_confidence` is strict (`<` 0.7 ⇒ 0.7 itself does not match); `high_confidence_failure` is inclusive (`>=` 0.9 matches at 0.9).
- **Sensitive keys anywhere in a row** (e.g. a `text_value` surfacing through semantic-action fields in future schema drift): the whole-row recursive redaction pass replaces them with `***REDACTED***` — belt-and-braces even though the v1 row schema does not export typed text.
- **Runs with `started_at IS NULL`**: included without `--since`, excluded by any `--since` filter.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A new module `evolution/hard_case_miner.py` MUST implement the eight implementable criteria of the table above as pure, individually-testable predicates over persisted row payloads (plain dicts), plus an aggregator returning the sorted list of matched labels for one step's data.
- **FR-002**: A new module `evolution/dataset_exporter.py` MUST scan the run store read-only, group `action_iterations` (plus recovery/experience rows) per (run_id, step_id), evaluate the miner, and write one JSON object per matched step to the `--out` JSONL file (UTF-8, `ensure_ascii=False`, one line per sample).
- **FR-003**: Each exported row MUST carry: `schema_version: "hard-case-v1"`, `run_id`, `test_case_id`, `step_id`, `criteria` (sorted labels), `screenshot_path` (relative to the artifacts root when resolvable, POSIX separators, else null — file content is never copied), `target` (role/text/description/nearby_texts of the step's semantic target, when present), `intent`, `correct_bbox` (from the final passed iteration: `execution_result.target_region`, else its top grounding candidate bbox; null when the step never passed), `wrong_candidates` (per failed/uncertain iteration: iteration_index, candidate bboxes+confidences, actual click point), `page_memory_id` (from a memory hit when present, else null), `verification` (final iteration's status+reason), `final_status`, `iteration_count`, `failure_types` (distinct persisted FailureType strings observed for the step).
- **FR-004**: Every row MUST pass a recursive sensitive-field redaction using the union of `security.sensitive_field_names` (config) and the logging module's `DEFAULT_SENSITIVE` set, with the existing key-substring semantics, before serialization.
- **FR-005**: A new `vnc-agent evolution export` subcommand MUST accept `--out` (required), `--db` (default: config `artifacts.db_path`), `--config` (default `config`), `--artifacts-root` (default: config `artifacts.root_dir`), `--since` (ISO date/datetime), repeatable `--criteria`; it MUST print exactly one JSON summary object to stdout (`total_runs_scanned`, `total_steps_scanned`, `exported_samples`, `criteria_counts`, `output`) and exit 0 on success (including 0 samples), 2 on validation errors (unknown criterion, unparsable `--since`).
- **FR-006**: All storage access MUST be read-only: a new dedicated query-only repository class in `storage/repositories.py` (SELECTs only, no session.add/commit); no schema change; no modification to any existing repository write method.
- **FR-007**: Zero runtime impact: no changes to `runtime/`, `perception/`, `verification/`, `planning/`, `execution/`, `recovery/`, `memory/`, `replay/`; `evolution/experience_collector.py` stays byte-identical and the write-only guard test `tests/unit/test_experience_collector_write_only.py` passes unmodified; the new modules are imported only inside the CLI subcommand path.
- **FR-008**: Threshold configuration MUST be an additive `evolution:` section (`EvolutionConfig` on `AgentConfig` + shipped `config/agent.yaml` block) with the defaults of Clarification 8; absent section ⇒ defaults; existing configs load unchanged.
- **FR-009**: Criteria not implementable from persisted data (table above) MUST NOT be silently faked — they are absent from the exposed criteria set and documented here with the missing-data reason.

### Key Entities

- **HardCaseCriterion**: a named predicate (label above) over one step's persisted evidence; the closed set of labels is the CLI `--criteria` vocabulary.
- **StepEvidence**: the per-(run_id, step_id) aggregation of iteration payloads (sorted by iteration_index), recovery-attempt payloads, experience failure types and the step row's final_status/failure_reason.
- **HardCaseSample**: one JSONL row (schema `hard-case-v1`, FR-003) — the offline-training exchange format of design §12.4.
- **ExportSummary**: the stdout JSON object (FR-005).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given a seeded database containing at least one step matching each implementable criterion, the export labels every such step with exactly the expected criteria set (unit + integration asserted).
- **SC-002**: End-to-end CLI export over a synthetic two-run database produces a JSONL file whose row count, per-row schema keys and criteria labels match the seeded ground truth, and a stdout summary whose counts equal the file content.
- **SC-003**: The full offline regression `uv run pytest tests/unit tests/fixtures tests/e2e tests/integration -q` passes (1 pre-existing skip) with `test_experience_collector_write_only.py` unmodified.
- **SC-004**: A run of the exporter against a database performs zero INSERT/UPDATE/DELETE (query-only repository; asserted structurally by the repository containing no write calls and behaviorally by row counts being identical before/after export in the integration test).

## Assumptions

- `step_id` is unique within a run (runtime generates one `StepRecordRow` per step).
- Screenshot files under the artifacts root are already masked at capture time (feature 001 FR-049 / feature 004 bundles); referencing their paths adds no new exposure.
- Naive datetimes in SQLite are UTC (the runtime writes `datetime.now(UTC)`).
- The dataset consumer resolves `screenshot_path` against its own copy of the artifacts tree; absolute fallback paths (when a stored path is outside the given root) are passed through as-is.
- Out of scope: training itself, any write-back of mined labels, replay-patch ("自愈") samples, per-iteration sample granularity, dataset versioning beyond the `schema_version` field.
