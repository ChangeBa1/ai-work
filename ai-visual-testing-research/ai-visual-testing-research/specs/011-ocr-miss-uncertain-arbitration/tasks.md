# Tasks: OCR 漏读弱否定证据仲裁（FR-010 语义修订）

**Input**: Design documents from `/specs/011-ocr-miss-uncertain-arbitration/`
（spec.md、plan.md；research/data-model 已并入 plan.md Phase 0/1）

**Tests**: 本 feature 是判定语义修订，测试即验收物；按任务书要求测试任务为必选。

**Organization**: 按 User Story 分组；US1 为 MVP。所有路径相对仓库根
`ai-visual-testing-research/ai-visual-testing-research/`。

## Phase 1: Setup

- [x] T001 确认 worktree 分支 `011-ocr-miss-uncertain-arbitration`、`cd vnc_agent && uv sync --extra dev`
      建环境，跑基线 `uv run pytest tests/unit tests/fixtures -q` 与 `uv run pytest tests/e2e -q`
      记录基线结果（686 passed / e2e 基线见 quickstart.md）。

## Phase 2: Foundational（配置阈值，US1~US3 共同依赖）

- [x] T002 [FR-007] `vnc_agent/src/vnc_agent/config.py`：新增 `VerificationConfig`
      （`visual_override_confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)`），
      `AgentConfig` 增加 `verification: VerificationConfig = Field(default_factory=VerificationConfig)`。
- [x] T003 [FR-007] `vnc_agent/config/agent.yaml`：新增 `verification:` 段
      （`visual_override_confidence_threshold: 0.8`）与用途注释。
- [x] T004 [FR-007] `vnc_agent/tests/unit/test_verification_compound.py`：新增配置模型用例——
      默认 0.8、yaml 值加载、越界（<0 / >1）校验失败。

## Phase 3: User Story 1 — OCR 漏读不再制造假失败 (P1, MVP)

- [x] T005 [US1, FR-001] `vnc_agent/src/vnc_agent/verification/business_resolver.py`：
      常量 `WEAK_NEGATIVE_TYPES = frozenset({"text_appears"})` + 纯函数
      `_failed_deterministic_all_weak_negative(spec, engine_result)`（label 规则复用
      `_partition_statuses` 的 `f"{cond.type}:{cond.value or i}"`）。
- [x] T006 [US1, FR-002/003/006] 同文件：`_weak_miss_visual_override(...)` 异步辅助——
      三条件门（弱否定-only failed / vis 全 passed / `action_effect.status=="expected_effect"`）、
      用第一个非空 `visual_question` 问题做一次 `describe_screen(answer_question)` 复核、
      `answer=="passed" and confidence >= threshold` 时返回 `passed` 副本（reason 追加
      `weak_ocr_miss_overridden_by_visual(...)`，`failed_conditions` 原样保留），否则/异常时返回 None。
- [x] T007 [US1, FR-002] 同文件主流程 FR-010 应用段：`conflict=="failed"` 时先尝试 T006 辅助，
      命中采用覆盖结果，未命中走原 `deterministic_overrides_visual` 分支；
      `resolve_step_result` 新增 `visual_override_confidence_threshold: float | None = None`
      形参（None → `VerificationConfig()` 默认，planner 缺省回退 `engine.planner`）。
      其余区域零 diff。
- [x] T008 [US1] `vnc_agent/tests/fixtures/test_business_resolver.py`：新用例——
      弱否定（含 `10,000`→`10.000` 无法命中形态）+ visual passed(0.9) + expected_effect →
      `passed`、reason 含标记、failed_conditions 保留；多条弱否定同判；
      跨场景参数化（表单保存流 `保存成功` / 图标菜单流 menu 词汇）满足 Constitution VI。
- [x] T009 [US1, FR-001] `vnc_agent/tests/unit/test_verification_compound.py`：
      `_failed_deterministic_all_weak_negative` 分级单元用例（text_appears-only → True；
      含 text_disappears/template 失败 → False；无失败 → False）+
      `aggregate_conditions` 既有语义不变（现有用例保持绿）。

## Phase 4: User Story 2 — 强否定维持覆盖权 (P1)

- [x] T010 [US2, FR-004] `vnc_agent/tests/fixtures/test_business_resolver.py`：
      text_disappears failed / template_appears failed / 弱+强混合 failed 三形态 ×
      visual passed(≥0.8) × expected_effect → 全部维持 `failed`；既有 T023 两用例
      （det failed vs visual passed → failed；det passed vs visual failed → passed）
      调整为在非仲裁条件下继续成立（如低置信 stub），保持 FR-010 原语义回归。

## Phase 5: User Story 3 — 低置信/非预期效果回退旧规则 (P2)

- [x] T011 [US3, FR-005] `vnc_agent/tests/fixtures/test_business_resolver.py`：
      confidence=0.5 → failed；`action_effect=no_effect` → failed（且 no_effect 门禁语义保留）；
      `action_effect=unexpected_effect` → 非 passed；自定义阈值 0.9 + confidence 0.85 → failed；
      复核调用抛异常 → failed（fail-safe）；无 visual_question（纯 text_appears）→ failed；
      复核调用次数 ≤ 1 断言（SC-005）。

## Phase 6: Polish & 回归门禁

- [x] T012 全量回归：`uv run pytest tests/unit tests/fixtures -q` 与 `uv run pytest tests/e2e -q`
      （重点 scenario 11/12/13、uncertain propagation）全绿；`uv run ruff check src tests` 无新告警；
      `git diff` 复核 `business_resolver.py` 无关区域零 diff。
- [x] T013 specs 文档定稿 + `.specify/feature.json` 指向本 feature 目录 + commit
      （消息含 Co-Authored-By: Claude Fable 5）。

## Dependencies & Execution Order

- T001 → T002~T004（Foundational）→ T005~T007（核心）→ T008~T011（可并行 [P]）→ T012 → T013。
