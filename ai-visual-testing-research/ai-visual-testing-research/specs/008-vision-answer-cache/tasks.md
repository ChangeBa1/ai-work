# Tasks: Vision Answer Cache

**Input**: Design documents from `/specs/008-vision-answer-cache/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/vision-answer-cache-contract.md](./contracts/vision-answer-cache-contract.md)

**Tests**: 测试先行 — 项目惯例（telemetry-contract.md "Test oracle" 的 call-count 断言）。
**Organization**: 按 User Story（US1 同帧同问缓存、US2 miss 语义、US3 有界窗口）分阶段。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行执行（不同文件、无未完成依赖）
- 每个任务含明确文件路径（相对 `vnc_agent/`）

---

## Phase 1: Foundational（所有 Story 共同依赖）

- [ ] T001 `src/vnc_agent/perception/cache.py`：`Component` Literal 增加 `"vision_answer"`
      （FR-001；仅此一处，缓存机制本体不动）。
- [ ] T002 `src/vnc_agent/domain/observation.py`：`StructuredScreen` 增加 additive 字段
      `capture_sequence: int = 0`、`scope_key: str = ""`（data-model.md §4，Feature 004 §7
      mirror 的延伸）。
- [ ] T003 `src/vnc_agent/perception/structured_screen.py`：两个 assembler
      （`assemble_structured_screen_from_pixels`、`assemble_structured_screen`）把
      `frame.capture_sequence` 与 `scope_identity(frame.scope)` 写入新字段。
- [ ] T004 [P] `src/vnc_agent/runtime/telemetry.py`：`derive_performance_summary` 的
      `cache_hits` 常驻 key 元组 `("ocr","template","vision")` 增加 `"vision_answer"`
      （FR-006）。

**Checkpoint**: 现有测试仍全绿（新字段全部默认值、Literal 扩展无行为变化）。

---

## Phase 2: US1 — 同帧同问题命中（含测试先行）

### 测试（先写，先失败）

- [ ] T005 新建 `tests/fixtures/test_vision_answer_cache.py`：SequenceDriver +
      CountingPlanner（按 `mode=="answer_question"` 计数并记录 question）基建；用真实
      `FrameCaptureService`/`ObservationPipeline` 生成去重帧序列。断言：
      N 个相同帧上对同一 `visual_question` 逐帧 `VerificationEngine.verify` ⇒ planner 恰好
      1 次调用，且各次 verdict/reason 一致（SC-001，US1-AS1/AS2）。
- [ ] T006 同文件：`performance_summary.cache_hits["vision_answer"]` 命中计数断言
      （US1-AS3，FR-006），以及未配置 cache 时行为与现状一致（每帧各调一次，FR-004）。

### 实现

- [ ] T007 新建 `src/vnc_agent/verification/answer_cache.py`：`CachedVisualAnswerer`
      （data-model.md §5：eligibility 门 → lookup → hit 事件/return；miss → 真调用 →
      `analysis_invocation` 事件 → store；错误语义 FR-007）。
- [ ] T008 `src/vnc_agent/verification/engine.py`：`VerificationEngine.__init__` 接受可选
      `answerer`（缺省构造无 cache 的 `CachedVisualAnswerer`），新增
      `answer_visual_question(screen, question, planner=None)` 委托；`_eval_one` 的
      `visual_question` 分支传入 answerer。
- [ ] T009 `src/vnc_agent/verification/visual_verifier.py`：`verify_visual_question` 增加可选
      `answerer` 参数，经其获取应答；未提供时行为不变。
- [ ] T010 `src/vnc_agent/runtime/agent_runtime.py`：构造 `VerificationEngine` 时接线
      `CachedVisualAnswerer(cache=pipeline.cache, test_run_provider=lambda:
      capture_service.test_run, provider/model=pipeline 的 vision 身份, ...)`。

**Checkpoint**: T005/T006 转绿；`uv run pytest tests/unit tests/fixtures -q` 全绿。

---

## Phase 3: US2 — miss 语义（question/帧/模型变化各自调用）

- [ ] T011 [P] `tests/fixtures/test_vision_answer_cache.py`：同帧两个不同 question ⇒ 各自 1 次
      真调用且分别缓存（US2-AS1）；帧变化后同 question ⇒ 重新调用（US2-AS2）；模型身份变化
      ⇒ 重新调用（US2-AS3，直接构造不同 model 的 answerer 断言）。
- [ ] T012 实现修正（如 T011 暴露问题）：key 组装中 question_sha256/model identity 归入
      `component_identity`（data-model.md §2），确保上述各维度独立 miss。

---

## Phase 4: US3 — 有界窗口与逃逸路径

- [ ] T013 [P] `tests/fixtures/test_vision_answer_cache.py`：窗口淘汰 — 相同内容帧序列中,
      条目最后引用超过 `cache_max_frames` 后再次求值 ⇒ 重新真调用（US3-AS1；注意 A→B→A
      本身不具 lookup 资格，用连续 duplicate 长链 + max_frames 下限构造淘汰）。
- [ ] T014 `tests/fixtures/test_vision_answer_cache.py`：escalation 路径 —
      `resolve_step_result`（uncertain + escalate）与条件求值共用 helper：同帧同 question 时
      escalation 不再重复调用；不同 question 时各自调用（FR-004b）。
- [ ] T015 `src/vnc_agent/verification/business_resolver.py`：`_maybe_escalate` 中直接
      `planner.describe_screen(...)` 调用替换为 `ver.answer_visual_question(screen,
      question, planner=planner)`；**不触碰** FR-010 仲裁逻辑（约 225-250 行）及文件其余部分
      （FR-009，diff 最小化）。

**Checkpoint**: 全部新测试绿。

---

## Phase 5: Polish / 回归

- [ ] T016 [P] 契约/文档一致性自检：`contracts/vision-answer-cache-contract.md` 与实现核对
      （key 字段、事件 kind/payload、错误语义）。
- [ ] T017 回归：`uv run pytest tests/unit tests/fixtures -q`、`uv run pytest tests/e2e -q`
      全绿；`tests/integration` 如有需真实 VNC/网络的失败仅记录原因。
