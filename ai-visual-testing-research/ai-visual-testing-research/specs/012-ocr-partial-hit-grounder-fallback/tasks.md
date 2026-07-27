# Tasks: OCR 可疑命中转 Grounding 兜底

**Input**: Design documents from `/specs/012-ocr-partial-hit-grounder-fallback/`
（spec.md、plan.md；research/data-model 已并入 plan.md Phase 0/1）

**Tests**: 判定语义类 feature，测试即验收物；测试任务为必选。

**Organization**: 按 User Story 分组。所有路径相对仓库根
`ai-visual-testing-research/ai-visual-testing-research/`。

## Phase 1: Setup

- [x] T001 确认 worktree 分支 `012-ocr-partial-hit-grounder-fallback`、`cd vnc_agent &&
      uv sync --extra dev`，记录基线：`uv run pytest tests/unit tests/fixtures -q`
      （762 passed）与 `uv run pytest tests/e2e -q`（40 passed）。

## Phase 2: Foundational（配置阈值，US1~US3 共同依赖）

- [x] T002 [FR-004] `vnc_agent/src/vnc_agent/config.py`：`PlanningConfig` 新增
      `ocr_direct_click_min_confidence: float = Field(default=0.85, ge=0.0, le=1.0)`；
      `AgentConfig.planning` 默认工厂同步补默认值。
- [x] T003 [FR-004] `vnc_agent/config/agent.yaml`：planning 段新增
      `ocr_direct_click_min_confidence: 0.85` 与用途注释。
- [x] T004 [FR-004] `vnc_agent/tests/unit/test_action_policy_ocr_suspicion.py`：配置模型
      用例——默认 0.85、显式值加载、越界（<0 / >1）校验失败。

## Phase 3: User Story 1 — 截断/部分重叠命中不再直接点击 (P1, MVP)

- [x] T005 [US1, FR-001/005] `vnc_agent/src/vnc_agent/planning/action_policy.py`：模块级
      `logger`、`_DECOR_CHARS` 装饰标点常量、`_comparable_text()` 纯函数、`OcrSuspicion`
      dataclass（reasons/ocr_text/ocr_confidence/bbox）、`PolicyResult.ocr_suspicion` 字段。
- [x] T006 [US1, FR-001] 同文件：`_find_unique_hits()`（命中收集提取，逻辑逐字保留）+
      `_ocr_hit_suspicion_reasons()`（R-A2 partial_text_overlap / R-B low_confidence /
      R-C short_text 规则表）；`_unique_ocr_or_template` 唯一 OCR 分支 reasons 非空 →
      return None（坐标表达式行零改动）。
- [x] T007 [US1, FR-005] 同文件：`_ocr_suspicion_for()`（被拦截唯一命中 → reasons；
      无命中 + 唯一真子串 item（可比长度 ≥ 2）→ truncated_ocr_read）；`resolve` 第 3/4 步
      衔接——首轮随 `needs_grounding=True` 返回 suspicion 并打 INFO 日志，二轮附到
      `_from_grounding` 返回对象（函数内部零改动）。
- [x] T008 [US1] `vnc_agent/tests/unit/test_action_policy_ocr_suspicion.py`：
      非精确包含命中（`レジ袋` vs `レジ袋合計`, conf 0.95）→ needs_grounding + reasons 含
      partial_text_overlap + 命中项 ∈ screen.ocr_items（FR-002 通道前提）；
      真子串 miss（`ジ袋` ⊂ `レジ袋`）→ needs_grounding + truncated_ocr_read；
      跨场景参数化（英文表单 `Submit Order` vs `Submit Orders`）（FR-008）。

## Phase 4: User Story 2 — 低置信/超短命中转 grounding (P1)

- [x] T009 [US2, FR-001/004] 同测试文件：精确命中 conf 0.5 → needs_grounding +
      low_confidence；单字符 `+` conf 0.99 → needs_grounding + short_text；
      `ActionPolicy(ocr_direct_click_min_confidence=0.3)` 下 conf 0.5 精确命中 → 直点
      （阈值可配置生效）；多原因叠加 reasons 全记录。

## Phase 5: User Story 3 — 可信命中与既有路径零回归 (P1)

- [x] T010 [US3, FR-003/007] 同测试文件：精确高置信命中（conf 0.9，2+ 字符）→ PolicyResult
      与现状逐字段一致（outcome/method/operation/coordinates=bbox 中心/needs_grounding=False/
      ocr_suspicion=None）；装饰标点差异（`【ログイン】`）→ 仍直点；模板唯一命中不变；
      混合分支：OCR 可疑 + 唯一模板 → 模板 bbox 直点；OCR 可信 + 模板 → 既有 confidence
      择优；二轮 resolve（带 grounding_result）→ 走既有 `_from_grounding` 防线且结果附带
      suspicion。
- [x] T011 [US3] 既有测试零修改回归：`tests/unit/test_action_policy_priority.py`、
      `tests/fixtures/test_action_policy_sanity_check.py` 保持绿。

## Phase 6: Polish & 回归门禁

- [x] T012 全量回归：`uv run pytest tests/unit tests/fixtures -q` 与
      `uv run pytest tests/e2e -q` 全绿；`uv run ruff check src tests` 无新告警；
      `git diff` 复核坐标表达式行与 `_from_grounding`/`_executable_from_candidate`/
      `_consistent_with_unique_ocr`、runtime/、models/ 零 diff。
- [x] T013 specs 文档定稿 + `.specify/feature.json` 指向本 feature 目录 + commit
      （消息含 Co-Authored-By: Claude Fable 5）。

## Dependencies & Execution Order

- T001 → T002~T004（Foundational）→ T005~T007（核心）→ T008~T010（可并行）→ T011~T012 → T013。
