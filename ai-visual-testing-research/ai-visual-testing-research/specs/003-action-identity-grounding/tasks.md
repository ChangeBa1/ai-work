---

description: "Task list for 通用动作身份、目标一致性与坐标空间安全 (003, Constitution v1.1.0 rebaseline)"
---

# Tasks: 通用动作身份、目标一致性与坐标空间安全

**Input**: Design documents from `/specs/003-action-identity-grounding/`
(spec.md、plan.md、research.md、data-model.md、contracts/、quickstart.md — 全部于
2026-07-22 按 Constitution v1.1.0 Principle VI 重新基线)

**重新基线说明**：本文件完全替换 2026-07-21 版本的 tasks.md，不保留旧任务的完成
勾选状态，不在旧任务之后追加。旧版本任务（`T001`～`T05x`）围绕单一 POS 购物袋
场景与已被判定违反 Constitution Principle VI 的固定业务字段设计，已随 spec.md/
plan.md 的重新基线一并失效。全部任务重新编号，从 `T001` 开始。

**Prerequisites**: plan.md（必需）、spec.md（必需，含 8 个 User Story 与优先级）、
research.md（§0 业务泄漏清单、§13 场景设计）、data-model.md（新增/删除实体）、
contracts/（4 份，2 份重写、2 份保留）

**Tests**: 本 feature 采用测试先行（TDD）——`plan.md::Testing` 明确要求"每个实现
任务前必须先有一个失败测试"，spec.md 的全部 Success Criteria 也要求离线可验证；
因此每个 Phase 均包含 Tests（先写，确认失败）→ Implementation 两个子阶段。

**Organization**: 任务按 spec.md 的 8 个 User Story 分组（US1～US3 为 P1，US4～US7
为 P2，US8 为 P3），每个 Story 均可独立测试。

## Format: `[ID] [P?] [Story] Description`

- **[P]**：可并行执行（不同文件、无未完成依赖）
- **[Story]**：映射到 spec.md 的 User Story（US1～US8）
- 每个任务均标注对应的 FR/SC 编号与具体文件路径

## 业务泄漏清单（对应 research.md §0，供全部实现任务对照）

| 移除 | 替换 | 相关任务 |
|---|---|---|
| `HumanStartStateConfirmation`/`ObservedStartState`/`StartStatePrecondition`（`domain/run.py`） | `DeclaredFact`/`RunPrecondition`/`FactEvaluation`/`PreconditionEvaluation`/`HumanConfirmedFact` | T021 |
| `extract_cart_state()`/`evaluate_start_state_precondition()`（`verification/business_resolver.py`） | `evaluate_precondition()` 复用 `VerificationEngine.verify()` | T023 |
| `--confirmed-cart-items`/`--confirmed-cart-amount`/`--confirm-start-state`（`api/cli.py`） | `--confirm-precondition key=value`（可重复）+ `--confirm-screenshot` | T025 |
| `ReportingConfig.category_keywords` 固定四分类校验器（`config.py`） | `ReportingConfig.action_tags: list[ActionTagRule] = []` | T031 |
| `_CATEGORY_KEYWORDS` 固定聚合（`reporting/json_report.py`） | 按声明 `ActionTagRule` 聚合的 `declared_tag_counts` | T032 |
| `PlanningConfig.result_display_keywords`/`dismissal_keywords`（`config.py`） | `SemanticAction.micro_action_purpose` + `PlanningConfig.micro_action_risk_thresholds` | T013、T014 |
| `execution/target_consistency.py::_RESULT_DISPLAY_KEYWORDS`/`_DISMISSAL_KEYWORDS` | 声明字段驱动的 AND 判定，无关键词表 | T015 |
| `action_id_match` 跳过一致性检查（旧 `action-identity-contract.md`） | `has_target_evidence_conflict()` 前置门 | T007、T009 |
| `action_type` 不同→无条件 `dangerous_drift`（旧 `data-model.md`） | AND(purpose, intent 一致性, risk 阈值) | T015 |
| `planning/action_classification.py::_DEFAULT_NON_IDEMPOTENT_KEYWORDS`（含业务词） | **明确排除在本 feature 范围外**（spec.md Assumptions），不安排任务 | — |

---

## Phase 1: Setup

**Purpose**：确认环境前提，无需新增依赖

- [X] T001 确认本 feature 不引入任何新的第三方依赖（`research.md` 决策）；核对
      `vnc_agent/pyproject.toml` 无需变更。[无关联 FR — 环境前提确认，
      research.md §0]

---

## Phase 2: Foundational（阻塞性前提，MUST 先于全部 User Story 完成）

**Purpose**：建立跨 Story 的质量门禁——业务关键词泄漏静态扫描与真实环境零依赖
扫描的通用化，两者均先写成会在当前代码上失败的测试（TDD），作为后续全部移除
任务的验收标准。

- [X] T002 [P] 在 `vnc_agent/tests/unit/test_no_business_keywords_in_core.py`
      新增静态扫描测试：断言 `src/vnc_agent/{domain,config.py,execution,
      reporting,verification,api,planning/action_policy.py,runtime}` 目录下
      不出现 `confirmed_cart`、`cart_items`、`cart_amount`、`add_to_bag`、
      `subtotal`、`clear_or_reset`、`extract_cart_state`、
      `result_display_keywords`、`dismissal_keywords`、`category_keywords`
      （`planning/action_classification.py` 按 spec.md Assumptions 明确排除
      在外）。本测试此刻 MUST 失败（当前代码仍含全部这些符号）。[Constitution
      Principle VI；对应本文件"业务泄漏清单"全部行]（对应任务 12）
- [X] T003 [P] 泛化 `vnc_agent/tests/unit/test_no_real_vnc_in_offline_tests.py`：
      改为对 `tests/fixtures/*.py`、`tests/unit/*.py`、`tests/e2e/*.py` 做
      glob 扫描（而非硬编码文件名列表），确保后续新增的场景测试文件自动被
      本项静态扫描覆盖，无需逐文件更新。[FR-039、SC-011]（对应任务 14）

**Checkpoint**：T002/T003 均已写好且当前失败（T002）或已验证通过（T003，因为
现有测试文件本就未连接真实 VNC）。

---

## Phase 3: User Story 1 - 稳定动作身份用于非幂等重复执行防护，但不证明目标安全 (Priority: P1)

**Goal**：`action_id` 相同（强匹配）只证明"同一逻辑动作尝试"，MUST NOT 被当作
新目标安全的证明；目标证据（角色/交互性质/空间）冲突时，无论身份是否匹配、
无论前一轮是否 `no_effect`，都必须运行一致性检查（安全问题 A）。

**Independent Test**：运行 T004～T006 全部通过，无需其余 Story 的改动。

### Tests for User Story 1

- [X] T004 [P] [US1] 在 `vnc_agent/tests/fixtures/test_target_consistency.py`
      新增 `has_target_evidence_conflict()` 单元测试：(a) 角色冲突（归一化后
      `target.role` 不相等）；(b) 交互性质冲突（可交互/非交互分类结果不同）；
      (c) 空间证据冲突（已解析区域 IoU 低于阈值）；(d) 任一区域缺失时该维度
      不参与判断，不误判为冲突。[FR-003]
- [X] T005 [P] [US1] 在 `vnc_agent/tests/fixtures/test_repeat_guard.py` 新增
      `RepeatGuard.check()` 组合逻辑测试：(a) `action_id_match` 但
      `conflict=True` 时仍调用 `evaluate_target_consistency()`，不直接沿用
      no_effect-only 规则；(b) 前一轮 `ActionEffect` 已为 `no_effect` 时，
      `conflict=True` 依然不豁免该检查；(c) 回归——`action_id_match` 且
      `conflict=False`（含 `intent`/`target.description` 同义改写但
      `action_id`/`action_type`/角色/空间证据均一致的场景，验证 FR-002 的
      强匹配鲁棒性）时仍沿用既有 no_effect-only 重试许可规则（同时验证
      FR-010 是允许重新执行非幂等动作的唯一条件）。[FR-002、FR-003、FR-004、
      FR-010]
- [X] T006 [P] [US1] 确认/扩展 `vnc_agent/tests/fixtures/test_action_identity.py`
      中回归测试：(a) 不同测试步骤恰好使用相同 `action_id` 时不被跨步骤阻止
      （`identity_match()` 未改动，验证契约未被破坏，FR-001）；(b) 一次真正
      不同的语义动作（`action_type` 不同，或目标明确指向不同已声明目的）
      不会被错误合并为同一稳定动作身份（FR-011）。[FR-001、FR-011]

### Implementation for User Story 1

- [X] T007 [US1] 在 `vnc_agent/src/vnc_agent/execution/target_consistency.py`
      新增 `has_target_evidence_conflict(previous_action, proposed_action, *,
      previous_resolved_region=None, proposed_resolved_region=None) -> bool`：
      角色/交互性质/空间证据三维度判断，MUST NOT 依赖任何关键词列表（依赖
      T004 先失败）。[FR-003]
- [X] T008 [US1] 在 `vnc_agent/src/vnc_agent/config.py` 新增
      `PlanningConfig.target_region_conflict_iou_threshold: float`（默认
      `0.10`）；同步更新 `vnc_agent/config/agent.yaml` 默认值。[FR-003]
- [X] T009 [US1] 重写 `vnc_agent/src/vnc_agent/execution/repeat_guard.py::
      RepeatGuard.check()`：新增 `previous_resolved_region`/
      `proposed_resolved_region` 入参；组合逻辑新增无条件冲突门——仅当
      `identity_match()` 匹配且 `has_target_evidence_conflict()` 为 `False`
      时才直接沿用既有 no_effect-only 规则，否则转入
      `evaluate_target_consistency()`（依赖 T007；依赖 T004/T005 先失败）。
      [FR-003、FR-004]
- [X] T010 [US1] 在 `vnc_agent/src/vnc_agent/runtime/agent_runtime.py::
      run_action_iteration()` 中，将当前轮与前一轮的已解析目标区域传入
      `RepeatGuard.check()` 调用（依赖 T009）。[FR-003]

**Checkpoint**：T004～T006 全部通过，US1 可独立验证。

---

## Phase 4: User Story 2 - 危险目标漂移由风险信号与声明目的共同判定，而非单一信号直接等价 (Priority: P1)

**Goal**：`action_type` 变化仅是触发一致性检查的风险信号，MUST NOT 无条件等于
`dangerous_drift`；最终判定由声明目的（`micro_action_purpose`）、声明风险级别
（`risk_level`）、步骤 intent 一致性三者的 AND 组合决定（安全问题 B），且不再
依赖任何硬编码关键词列表（业务泄漏清单：`_RESULT_DISPLAY_KEYWORDS`/
`_DISMISSAL_KEYWORDS`）。

**Independent Test**：运行 T011～T012 全部通过，无需其余 Story 的改动。

### Tests for User Story 2

- [X] T011 [P] [US2] 在 `vnc_agent/tests/fixtures/test_target_consistency.py`
      新增 `evaluate_target_consistency()` 测试：(a) AND 语义——声明目的、
      步骤 intent 一致性、风险级别阈值三者同时满足才返回
      `"legitimate_micro_action"`（同时验证 FR-006 定义的步骤 intent 一致性
      检查与合法微动作判定），任一不满足即不返回该值；(b) 回归——
      "可交互控件→非交互结果展示元素"与"可交互控件→另一个不符合 intent 的
      可交互控件"两种漂移方向仍能被正确判定为 `"dangerous_drift"`（验证
      SC-005 的 100% 拦截率），且判定过程不涉及任何关键词文本匹配；(c)（
      /speckit-analyze 2026-07-22 发现的 HIGH 缺口补充）**`"ambiguous"` 分支
      **——构造一个既不满足 AND 条件、也不构成"可交互→非交互"或"控件→不符合
      intent 控件"任一漂移方向的信号不足场景（例如新目标角色未知、
      `step_intent` 与新旧目标重合度均不明确），断言
      `evaluate_target_consistency()` 返回 `"ambiguous"`，不被强行归类到
      `"legitimate_micro_action"` 或 `"dangerous_drift"`；并断言该 `"ambiguous"`
      结果经 `RepeatGuard.check()`（依赖 T009）正确路由：前一轮 `no_effect` 且
      预算充足时 `allowed=True, reason="no_effect_confirmed"`，否则
      `allowed=False, reason="ambiguous_fail_safe"`。[FR-006、FR-007、FR-012、
      FR-013、FR-014、FR-017、SC-005]
- [X] T012 [P] [US2] 在 `vnc_agent/tests/fixtures/test_feature003_config.py`
      新增配置测试：`PlanningConfig` 不再暴露 `result_display_keywords`/
      `dismissal_keywords` 字段；暴露 `micro_action_risk_thresholds`，其默认
      键值均为通用 UI 交互类别（非业务词汇）。[Constitution Principle VI]

### Implementation for User Story 2

- [X] T013 [US2] 在 `vnc_agent/src/vnc_agent/domain/action.py::SemanticAction`
      扩展 `risk_level` 为 `Literal["low","medium","high"] = "low"`（原仅
      `Literal["low"]`）；新增 `micro_action_purpose: Literal["dismiss_overlay",
      "scroll_reveal","refocus","wait","re_observe"] | None = None`。[FR-012、
      FR-013]
- [X] T014 [US2] 在 `vnc_agent/src/vnc_agent/config.py` 新增
      `PlanningConfig.micro_action_risk_thresholds: dict[str, Literal["low",
      "medium","high"]]`（通用 UI 类别默认阈值）；**删除**
      `result_display_keywords`/`dismissal_keywords` 两个字段及其硬编码默认值；
      同步更新 `vnc_agent/config/agent.yaml`（依赖 T008，同文件顺序执行）。
      [FR-012、FR-013、Constitution Principle VI]
- [X] T015 [US2] 重写 `vnc_agent/src/vnc_agent/execution/target_consistency.py::
      evaluate_target_consistency()`：**删除**模块级常量
      `_RESULT_DISPLAY_KEYWORDS`/`_DISMISSAL_KEYWORDS` 与
      `action_type` 不同即无条件返回 `"dangerous_drift"` 的分支；实现
      AND(声明目的 ∈ 合法微动作枚举, 步骤 intent 一致性, 风险级别 ≤ 阈值) 的
      组合判定（依赖 T007 同文件、T013、T014；依赖 T011/T012 先失败）。
      [FR-012、FR-013]

**Checkpoint**：T011～T012 全部通过，US2 可独立验证。

---

## Phase 5: User Story 3 - Grounder 坐标必须遵循显式坐标空间协议 (Priority: P1)

**Goal**：坐标空间协议（`coordinate_space`/`resolve_pixel_bbox()`）本身业务
无关，2026-07-22 重新基线**原样保留**（plan.md/research.md §8 已确认），本
Phase 只做回归验证，不涉及实现改动。

**Independent Test**：运行 T016～T017 全部通过（既有代码，验证契约未被
其它 Story 的改动意外破坏）。

### Tests for User Story 3

- [X] T016 [P] [US3] 在 `vnc_agent/tests/fixtures/test_coordinate_space.py`
      补充/确认回归测试：(a) `normalized_1000` → 像素坐标在非正方形分辨率下
      换算正确；(b) 坐标空间缺失/矛盾/未知取值/越界的候选一律拒绝，不猜测
      （含闭区间 `[0,1000]` 边界值 0/1000 本身合法、bbox 四角与最终点击点
      越界拒绝，验证 FR-023 与 SC-003 的 100% 拒绝率）；(c) 同一响应内不同
      候选独立声明不同坐标空间，逐候选换算，且换算有且仅发生一次。[FR-018、
      FR-019、FR-020、FR-021、FR-022、FR-023、SC-003]
- [X] T017 [P] [US3] 在 `vnc_agent/tests/fixtures/test_action_policy_sanity_
      check.py` 确认执行前 OCR 合理性核对（矛盾证据拒绝）回归测试仍然通过。
      [FR-019 延伸]

**Checkpoint**：T016～T017 全部通过，确认坐标空间能力在本次重新基线后依然
成立，US3 可独立验证。无实现任务——`models/coordinate_space.py`、
`domain/grounding.py` 保持不变（对应任务 9）。

---

## Phase 6: User Story 4 - 声明式运行前置条件 (Priority: P2)

**Goal**：用复用既有 `VerificationSpec`/`VerificationEngine` 的通用命名 fact
机制，替换固定的购物车专用起始状态字段与提取函数（业务泄漏清单：
`HumanStartStateConfirmation`/`ObservedStartState`/`extract_cart_state()`）。

**Independent Test**：运行 T018～T020 全部通过。

### Tests for User Story 4

- [X] T018 [P] [US4] 在 `vnc_agent/tests/fixtures/test_run_precondition.py`
      （新建）编写声明式前置条件测试：(a) 声明的 fact 与首帧观察证据全部
      匹配 → `status="passed"`；(b) 任一不匹配/`uncertain`/证据冲突 →
      `status="failed"`，零输入发送，不自动重置环境；(c) 未声明
      `precondition` 的测试用例 → `status="not_required"`，与 001/002 行为
      完全一致。[FR-024、FR-025、FR-026]
- [X] T019 [P] [US4] 在 `vnc_agent/tests/unit/test_cli_precondition_
      confirmation.py`（新建，替代旧
      `test_cli_start_state_confirmation.py`）编写测试：`--confirm-precondition
      key=value` 可重复解析为 `list[HumanConfirmedFact]`；提供的 `key` 在
      `TestCase.precondition.facts` 中找不到匹配时，在连接目标环境前以非零
      退出码失败。[FR-024]
- [X] T020 [US4] 在 `vnc_agent/tests/e2e/test_run_precondition_e2e.py`（新建，
      替代旧 `test_start_state_precondition.py`）编写固定帧序列端到端测试，
      覆盖 §T018 的匹配/不匹配两种结果。[FR-025、SC-008]

### Implementation for User Story 4

- [X] T021 [US4] 重写 `vnc_agent/src/vnc_agent/domain/run.py`：**删除**
      `HumanStartStateConfirmation`/`ObservedStartState`/
      `StartStatePrecondition`；新增 `DeclaredFact(key: str, spec:
      VerificationSpec)`、`RunPrecondition(facts: list[DeclaredFact])`、
      `FactEvaluation(key: str, result: VerificationResult)`、
      `PreconditionEvaluation(status, fact_evaluations, checked_at)`、
      `HumanConfirmedFact(key, confirmed_value, confirmed_at,
      screenshot_ref)`；`TestRun` 新增 `precondition_evaluation`/
      `human_confirmed_facts` 字段（依赖 T018 先失败）。[FR-024、FR-025、
      FR-026]
- [X] T022 [US4] 在 `vnc_agent/src/vnc_agent/domain/testcase.py` 新增
      `TestCase.precondition: RunPrecondition | None = None` 字段（依赖
      T021）。[FR-024]
- [X] T023 [US4] 在 `vnc_agent/src/vnc_agent/verification/business_resolver.py`
      **删除** `extract_cart_state()`、`evaluate_start_state_precondition()`；
      新增 `evaluate_precondition(precondition, first_observed_screen, engine)
      -> PreconditionEvaluation`，逐 `DeclaredFact` 调用既有
      `VerificationEngine.verify(fact.spec, first_observed_screen)`（依赖
      T021）。[FR-025、FR-026]（对应任务 6）
- [X] T024 [US4] 在 `vnc_agent/src/vnc_agent/runtime/agent_runtime.py` 中，
      于首次独立 Observe/Understand 完成后、任何 `PLANNING`/
      `RESOLVING_ACTION` 或 `ExecutableAction` 生成前调用
      `evaluate_precondition()`；`status="failed"` 时停止并生成报告，不发送
      任何输入事件（依赖 T023）。[FR-025]
- [X] T025 [US4] 在 `vnc_agent/src/vnc_agent/api/cli.py` **删除**
      `--confirm-start-state`/`--confirmed-cart-items`/
      `--confirmed-cart-amount`/`--confirmed-screenshot`；新增
      `--confirm-precondition key=value`（可重复）+
      `--confirm-screenshot <path>`；校验提供的 `key` 均能在
      `TestCase.precondition.facts` 中找到匹配（依赖 T021、T022；依赖 T019
      先失败）。[FR-024]（对应任务 3）
- [X] T026 [US4] 在 `vnc_agent/src/vnc_agent/runtime/run_context.py` 中，将
      CLI 解析得到的 `HumanConfirmedFact` 列表写入
      `TestRun.human_confirmed_facts`（依赖 T021）。[FR-024]

**Checkpoint**：T018～T020 全部通过，US4 可独立验证。

---

## Phase 7: User Story 5 - 声明式已发送动作审计 (Priority: P2)

**Goal**：用测试用例/场景 profile 声明的 `ActionTagRule`（结构化谓词），替换
`ReportingConfig.category_keywords` 固定四分类与其硬编码关键词表（业务泄漏
清单：`add_to_bag`/`subtotal`/`payment`/`clear_or_reset`）。

**Independent Test**：运行 T027～T029 全部通过。

### Tests for User Story 5

- [X] T027 [P] [US5] 在 `vnc_agent/tests/fixtures/test_declared_action_tags.py`
      （新建）编写 `ActionMatcher`/`ActionTagRule` 匹配测试：(a) 四个可选字段
      之间为 AND 关系；(b) 一个动作可同时匹配 0/1/多个 `tag`（非互斥）；
      (c) `declared_tag_counts` 仅统计
      `execution_result.success is True` 的动作，被拦截提案计数为 0 但仍
      保留在逐轮审计中，且均可直接从报告字段读出（验证 SC-009 无需复核
      原始日志或重新运行）。[FR-027、FR-028、SC-009]
- [X] T028 [P] [US5] 在 `vnc_agent/tests/fixtures/test_feature003_config.py`
      新增测试：`ReportingConfig` 默认 `action_tags=[]`，不存在任何强制要求
      特定分类 key 的校验器（依赖 T012 同文件，顺序执行）。[Constitution
      Principle VI]（对应任务 5）

### Implementation for User Story 5

- [X] T029 [US5] 新增 `vnc_agent/src/vnc_agent/domain/reporting_tags.py`：
      `ActionMatcher(action_type, target_role, target_text_contains,
      intent_contains)`、`ActionTagRule(tag, matcher)`（依赖 T027 先失败）。
      [FR-027]
- [X] T030 [US5] 在 `vnc_agent/src/vnc_agent/domain/testcase.py` 新增
      `TestCase.action_tags: list[ActionTagRule] = []`，与
      `AgentConfig.reporting.action_tags` 合并（测试用例声明的同名 tag
      优先，依赖 T022 同文件、T029）。[FR-027]
- [X] T031 [US5] 在 `vnc_agent/src/vnc_agent/config.py` **删除**
      `ReportingConfig.category_keywords` 字段及其 `require_audit_categories`
      校验器；新增 `ReportingConfig.action_tags: list[ActionTagRule] = []`；
      同步更新 `vnc_agent/config/agent.yaml`（依赖 T014 同文件，顺序执行；
      依赖 T028 先失败）。[FR-027、Constitution Principle VI]（对应任务 5）
- [X] T032 [US5] 重写 `vnc_agent/src/vnc_agent/reporting/json_report.py::
      build_report_dict()`：**删除** `_CATEGORY_KEYWORDS` 常量与固定四分类
      聚合逻辑；新增按 `ActionTagRule` 逐条匹配 `executed_action_log` 生成
      `declared_tag_counts` 的聚合逻辑（依赖 T029、T031；依赖 T027 先失败）。
      [FR-027、FR-028]（对应任务 4）

**Checkpoint**：T027～T028 全部通过，US5 可独立验证。

---

## Phase 8: User Story 6 - 恢复路径不得盲目重试、额外点击或撤销已确认的业务结果 (Priority: P2)

**Goal**：`RecoveryPolicy` 六字段契约本身业务无关，2026-07-22 重新基线
**原样保留**；本 Phase 验证该契约未被破坏，并新增风险级别路由到既有契约的
验证（呼应 US2 的 AND 逻辑与 2026-07-22 clarify 决议）。

**Independent Test**：运行 T033～T035 全部通过。

### Tests for User Story 6

- [X] T033 [P] [US6] 在 `vnc_agent/tests/fixtures/test_feature003_config.py`
      确认 `RecoveryPolicy` 六字段契约回归测试仍然通过——任一字段缺失时配置
      加载失败（依赖 T028 同文件，顺序执行）。[FR-034]
- [X] T034 [P] [US6] 在 `vnc_agent/tests/fixtures/test_recovery_no_
      destructive_actions.py` 新增/确认测试：(a) 恢复路径不发送无依据的默认
      按键导航；(b) 恢复路径不执行任何不在已声明动作范围内、会改变被测应用
      状态的操作（通用措辞，非"清空购物车"）；(c) 携带较高 `risk_level` 的
      `dangerous_drift`/`ambiguous` 结果通过既有 `requires_human_
      confirmation`/`requires_strong_model` 字段路由，而非新增独立风险裁决
      分支；(d)（/speckit-analyze 2026-07-22 发现的 MEDIUM 缺口补充）
      `dangerous_drift`/坐标空间拒绝触发的停止 MUST 消耗与其它失败类型相同的
      共享步骤/全局重试预算——构造预算耗尽场景，断言不会为这两类新结果单独
      开辟脱离预算控制的独立重试通道，预算耗尽后按既有规则判定步骤失败。
      [FR-031、FR-032、FR-013、FR-033、FR-034]
- [X] T035 [US6] 在 `vnc_agent/tests/fixtures/test_testcase_loader.py` 确认
      未声明 `precondition`/`action_tags` 的旧格式测试用例仍可正常加载与
      执行，行为与 001/002 完全一致。[FR-029、FR-030]

### Implementation for User Story 6

- [X] T036 [US6] 核对 `vnc_agent/src/vnc_agent/recovery/classifier.py`：确认
      `"dangerous_drift"`/`"ambiguous_fail_safe"` 结果在 `risk_level` 较高时
      被路由到声明了 `requires_human_confirmation=True` 的恢复策略；若既有
      `FailureType` 路由已满足该要求则无需改动代码，仅需通过 T034 验证并在
      本任务中记录核对结论（依赖 T013、T015）。[FR-013、FR-034]

**Checkpoint**：T033～T035 全部通过，US6 可独立验证。

---

## Phase 9: User Story 7 - 报告可审计动作身份、RepeatGuard 判定与坐标空间换算 (Priority: P2)

**Goal**：报告新增前置条件评估与声明式 tag 审计字段，与既有动作身份/坐标空间
审计字段并列，均可从报告直接读出。

**Independent Test**：运行 T037 全部通过。

### Tests for User Story 7

- [X] T037 [P] [US7] 在 `vnc_agent/tests/fixtures/test_report_builder.py`
      新增测试：`build_report_dict()` 输出包含 (a) 逐轮
      `canonical_action_identity` 与一致性/漂移判定理由（既有字段，回归）；
      (b) 逐轮 `coordinate_space_audit`（既有字段，回归）；(c) 运行级
      `precondition_evaluation`/`human_confirmed_facts`；(d) 运行级
      `declared_tag_counts`。[FR-035、FR-036、FR-038]

### Implementation for User Story 7

- [X] T038 [US7] 在 `vnc_agent/src/vnc_agent/reporting/json_report.py::
      build_report_dict()` 新增运行级 `precondition_evaluation`/
      `human_confirmed_facts` 字段的序列化（依赖 T021、T032 同文件，顺序
      执行；依赖 T037 先失败）。[FR-038]
- [X] T039 [US7] 在 `vnc_agent/src/vnc_agent/reporting/html_report.py` 更新
      折叠展示区块，渲染 `precondition_evaluation`/`declared_tag_counts`，
      与既有的动作身份/坐标空间区块并列（依赖 T038）。[FR-035、FR-036、
      FR-038]

**Checkpoint**：T037 通过，US7 可独立验证。

---

## Phase 10: User Story 8 - 离线优先验证，覆盖至少三个互不相关场景，POS 事故仅作附加回归 (Priority: P3)

**Goal**：新增三个业务无关的离线场景证明每项通用能力，POS 场景迁移为使用相同
通用机制的第四个附加回归 fixture，不再是唯一验收依据。

**Independent Test**：运行 T040～T042（+T045）全部通过，且不依赖 T043～T044
（POS 场景）是否通过。

### Implementation for User Story 8

- [X] T040 [P] [US8] 新增 `vnc_agent/tests/fixtures/test_scenario_form_
      submit.py`：表单提交场景——同一测试步骤内非幂等提交动作在措辞改写下
      仍被识别为同一逻辑动作、不被重复执行（research.md §13 场景 1）。
      [FR-040、SC-001]
- [X] T041 [P] [US8] 新增 `vnc_agent/tests/fixtures/test_scenario_icon_
      menu.py`：无文字图标打开菜单场景——缺乏文字锚点时视觉目标身份识别与
      非正方形分辨率下的坐标空间换算仍然正确（research.md §13 场景 2）。
      [FR-040、SC-002]
- [X] T042 [P] [US8] 新增 `vnc_agent/tests/fixtures/test_scenario_popup_
      scroll.py`：弹窗关闭/滚动场景——目标使用与前一非幂等动作不同的
      `action_id`、新目标声明独立的 `micro_action_purpose="dismiss_
      overlay"`/`"scroll_reveal"`，验证该场景端到端经过 FR-005 定义的
      "`action_id` 缺失/变化时先运行步骤 intent 一致性检查"路径
      （`RepeatGuard.check()` 的 `"no_action_id_ambiguous"` 分支），且合法
      微动作不被误判为危险漂移（research.md §13 场景 3）。[FR-005、FR-006、
      FR-040、SC-004]
- [X] T043 [US8] 在 `vnc_agent/testcases/pos-buy-bag-checkout.yaml` 顶层新增
      `precondition`/`action_tags` 声明（使用 T021/T029 定义的通用机制表达
      该场景的具体业务内容），确认核心代码不存在任何仅为该文件服务的分支
      （依赖 T021、T022、T029、T030）。[FR-040、SC-013]（对应任务 10）
- [X] T044 [US8] 更新
      `vnc_agent/tests/e2e/test_scenario_15_pos_bag_business_acceptance.py`：
      断言改为读取通用的 `declared_tag_counts`/`precondition_evaluation`
      报告字段，不再引用任何专属该场景的业务字段（依赖 T043）。[SC-013]
- [X] T045 [US8] 新增
      `vnc_agent/tests/fixtures/test_cross_scenario_coverage.py`：确认每项
      声称通用的能力（身份匹配/危险漂移/坐标空间/声明式前置条件/声明式 tag
      审计）均至少有 T040～T042 中两个互不相关场景的通过证据，独立于
      T043～T044（POS 场景）是否通过（依赖 T040、T041、T042）。**同时**（
      /speckit-analyze 2026-07-22 发现的 MEDIUM 缺口补充）本任务 MUST 额外
      聚合 T040～T042 三个场景（+ T043～T044 的 POS 场景）逐场景运行的判定
      理由证据，断言：(a) **SC-006**——全部场景中，`dangerous_drift` 判定
      0 次仅由 `action_type` 变化触发，每次判定均可在报告/判定理由中追溯到
      声明目的、风险级别、一致性检查结果三者的联合依据；(b) **SC-007**——
      全部场景中，凡新一轮目标证据（角色/交互性质/空间）与前一轮冲突的
      情形，`has_target_evidence_conflict()` 触发的一致性检查 100% 被执行，
      不因 `action_id` 匹配或前一轮 `no_effect` 而被跳过。[FR-040、SC-006、
      SC-007、SC-012]

**Checkpoint**：T040～T042、T045 全部通过（不依赖 POS 场景），US8 可独立
验证；T043～T044（POS 迁移）作为附加验证一并完成。

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**：确认业务泄漏已被全部清除、真实环境零依赖、全量回归通过。

- [X] T046 [P] 重新运行 `vnc_agent/tests/unit/test_no_business_keywords_in_
      core.py`（T002），确认在 T009/T014/T015/T021/T023/T025/T031/T032 全部
      完成后由 FAIL 转为 PASS。[Constitution Principle VI]（对应任务 12，
      最终门禁）
- [X] T047 [P] 重新运行泛化后的
      `vnc_agent/tests/unit/test_no_real_vnc_in_offline_tests.py`（T003），
      确认覆盖全部新增场景测试文件（T040～T042、T018、T027 等），真实/在线
      环境连接次数为 0。[FR-039、SC-011]（对应任务 14，最终门禁）
- [X] T048 在 `vnc_agent/` 目录运行 `pytest -q` 全量回归，确认 001/002 既有
      测试与本 feature 新增的全部测试一并通过，退出码为 0。[SC-010、
      SC-011]（对应任务 13）
- [X] T049 更新 `specs/003-action-identity-grounding/checklists/domain-
      independence.md`：将 CHK002/CHK007（tasks.md 缺少多场景任务）标记为
      已解决（T040～T045 已提供对应任务与实现），并对照 T046～T048 的结果
      重新核对其余 12 项发现是否已转为通过。[Constitution Principle VI]

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup（Phase 1）**：无依赖，立即开始。
- **Foundational（Phase 2）**：依赖 Setup 完成；T002/T003 均可并行。
- **User Stories（Phase 3+）**：均依赖 Foundational 完成。US1/US2/US3（P1）
  之间除下方"共享文件"约束外相互独立；US4/US5/US6/US7（P2）之间除下方约束
  外相互独立；US8（P3）依赖 US1～US7 的实现产出（复用 `micro_action_purpose`/
  声明式前置条件/tag 机制），故 US8 MUST 在 US1～US7 完成后进行。
- **Polish（Final Phase）**：依赖全部 User Story 完成。

### 共享文件顺序约束（同一文件被多个 Story 触及，MUST NOT 并行编辑）

- `config.py` + `config/agent.yaml`：T008（US1）→ T014（US2）→ T031（US5）
  依次编辑，MUST NOT 并行。
- `tests/fixtures/test_feature003_config.py`：T012（US2）→ T028（US5）→
  T033（US6）依次编辑。
- `domain/testcase.py`：T022（US4）→ T030（US5）依次编辑。
- `reporting/json_report.py`：T032（US5）→ T038（US7）依次编辑。
- `execution/target_consistency.py`：T007（US1）→ T015（US2）依次编辑。

### User Story Dependencies

- **US1（P1）**：Foundational 完成后可开始，无其它 Story 依赖。
- **US2（P1）**：Foundational 完成后可开始；`config.py`/
  `execution/target_consistency.py` 与 US1 共享文件，MUST 在 US1 的 T007/T008
  完成后编辑（见上表）。
- **US3（P1）**：Foundational 完成后可开始，无实现任务，仅回归验证，与其它
  Story 无文件冲突。
- **US4（P2）**：Foundational 完成后可开始，无其它 Story 依赖。
- **US5（P2）**：依赖 US4 的 `domain/testcase.py`（T022）与 US2 的
  `config.py`（T014）已完成（见共享文件约束）。
- **US6（P2）**：依赖 US2 的 `risk_level`/AND 逻辑（T013/T015）与 US5 的
  `test_feature003_config.py`（T028）已完成。
- **US7（P2）**：依赖 US4 的 `domain/run.py`（T021）与 US5 的
  `reporting/json_report.py`（T032）已完成。
- **US8（P3）**：依赖 US1～US7 全部完成（复用其声明式机制与
  `micro_action_purpose` 字段）。

### Parallel Opportunities

- Foundational 内 T002/T003 可并行。
- 每个 User Story 内标注 `[P]` 的 Tests 任务（不同文件）可并行编写。
- US1/US4 的 Tests 阶段（T004～T006 与 T018～T020）可与彼此并行开展，因为
  两者不共享任何文件。
- Polish 阶段 T046/T047 可并行。

---

## Parallel Example: User Story 1

```bash
# 并行编写 US1 的三个测试文件：
Task: "has_target_evidence_conflict() 单元测试 in tests/fixtures/test_target_consistency.py"
Task: "RepeatGuard.check() 组合逻辑测试 in tests/fixtures/test_repeat_guard.py"
Task: "different-step 回归确认 in tests/fixtures/test_action_identity.py"
```

---

## Implementation Strategy

### MVP First（US1 + US2 + US3，全部 P1）

1. 完成 Phase 1（Setup）+ Phase 2（Foundational）。
2. 完成 Phase 3（US1，安全问题 A）。
3. 完成 Phase 4（US2，安全问题 B）——依赖 US1 的 `config.py`/
   `target_consistency.py` 编辑顺序。
4. 完成 Phase 5（US3，坐标空间回归验证）。
5. **停止并验证**：三个 P1 Story 独立测试全部通过，即修复了 spec.md 全部
   三个 P1 用户故事对应的安全问题。

### Incremental Delivery

1. Setup + Foundational → 质量门禁就绪（T002 此刻应为 FAIL，作为后续任务的
   进度指示器）。
2. US1 → 独立验证 → 安全问题 A 修复完成。
3. US2 → 独立验证 → 安全问题 B 修复完成。
4. US3 → 独立验证 → 坐标空间能力确认未受影响。
5. US4 → 独立验证 → 声明式前置条件替换固定购物车字段。
6. US5 → 独立验证 → 声明式 tag 审计替换固定四分类。
7. US6 → 独立验证 → 恢复边界与风险路由确认。
8. US7 → 独立验证 → 报告可审计性完整。
9. US8 → 独立验证 → 至少两个互不相关场景证明每项通用能力，POS 降级为
   附加 fixture。
10. Polish → T046 由 FAIL 转 PASS，确认业务泄漏清单已全部清除；T048 全量
    回归通过。

---

## Notes

- `[P]` 任务 = 不同文件、无未完成依赖；同一文件内的多个测试用例合并为一个
  任务描述，不拆分为多个 `[P]` 任务（避免并行编辑同一文件产生冲突）。
- `[Story]` 标签用于将任务追溯到 spec.md 的具体 User Story。
- T002（业务关键词静态扫描）在 Foundational 阶段被有意设计为"此刻必须失败"，
  作为贯穿全部实现任务的进度指示器，在 T046 转为通过。
- 每个任务均已标注对应的 FR/SC 编号（或 Constitution 条款）与具体文件路径，
  无一遗漏。
- 提交建议：每个任务或每个逻辑分组完成后提交一次；在每个 Story 的 Checkpoint
  处停下验证，确认独立可测试性。
- **FR 覆盖说明（/speckit-analyze 2026-07-22 只读分析后补充）**：FR-008
  （文字锚点识别噪声容忍）、FR-009（重复执行判定基于 FR-001～007 的汇总
  条款）、FR-015/FR-016（危险漂移判定的执行前时序）、FR-037（业务结果断言
  判定依据，001/002 既有机制）、FR-041（真实/在线环境验证的人工批准边界）
  均为**保留不变**的既有行为（research.md §2/§8/§9、plan.md Technical
  Context 已确认），本次未新增专属这些条款的独立任务；其正确性由
  T048（全量离线回归，涵盖全部既有 001/002/pre-rebaseline 测试文件）与
  T047（真实环境零依赖静态扫描）**透传验证**，而非被静默忽略——若这些既有
  测试文件本身缺失，应作为独立于本次重新基线的技术债处理，不在本 tasks.md
  范围内新增。

---

## Phase 12: Convergence

**Purpose**：`/speckit-converge`（2026-07-22）对已完成实现（T001～T049）与
spec.md/plan.md/Constitution v1.1.0 的只读复核发现的剩余缺口。本阶段只追加
任务，不修改任何既有任务、不修改生产代码。

- [X] T050 **CRITICAL** — 泛化 `vnc_agent/src/vnc_agent/planning/
      action_classification.py::_DEFAULT_NON_IDEMPOTENT_KEYWORDS` 默认关键词
      表：该表当前仍包含"レジ袋"/"購入"/"支払い"/"支付"/"结算"/"checkout"/
      "pay"/"加购"等零售/支付业务词汇，作为 `classify_action_kind()` 的**生产
      默认值**（非仅注释或历史引用），直接违反 Constitution v1.1.0 Principle
      VI（核心模块 MUST NOT 包含业务专用关键词）。spec.md Assumptions 曾明确
      将"非幂等动作分类机制"排除在 003 自身重新定义范围之外，但 Constitution
      的效力高于单个 feature 的范围声明——`/speckit-converge` 的宪法权威规则
      要求任何违反 Constitution MUST 的代码都必须产生对应的修复任务，不因
      spec.md 的历史范围声明而豁免。修复方向：将该默认关键词表泛化为业务无关
      的表达（例如要求调用方显式声明关键词表、或改为不含业务词汇的最小通用
      默认集），并相应扩展 `tests/unit/test_no_business_keywords_in_core.py`
      的扫描范围以覆盖本文件（移除当前的排除条款）。
      per Constitution Principle VI (contradicts)
- [X] T051 **HIGH** — 新增一个非 POS 的端到端场景测试，在同一个通用测试用例
      YAML 中同时声明 `precondition`（`RunPrecondition`/`DeclaredFact`）与
      `action_tags`（`ActionTagRule`），通过 `load_test_case()` 加载、通过
      `AgentRuntime.run()`（而非直接调用内部 Python 函数）驱动完整运行，并
      断言最终报告中的 `precondition_evaluation`/`declared_tag_counts` 字段
      正确。当前 `test_scenario_form_submit.py`/`test_scenario_icon_menu.py`/
      `test_scenario_popup_scroll.py`/`test_cross_scenario_coverage.py` 均只
      直接调用内部函数（`compute_identity`/`evaluate_target_consistency`/
      `has_target_evidence_conflict`），从未通过 `load_test_case()` 加载过
      声明了 `precondition`/`action_tags` 的测试用例——这意味着 FR-024～028
      声明式前置条件/tag 审计这一**公共接口**（测试用例 YAML schema +
      `AgentRuntime.run()` 管线，而非内部函数）目前只有 POS 场景
      （`test_scenario_15_pos_bag_business_acceptance.py`）一个端到端证据，
      不满足 Constitution "至少两个互不相关场景验证"对该公共接口层面的要求
      （内部函数层面已有 ≥2 场景证据，公共接口层面尚无）。新增测试建议放在
      `vnc_agent/tests/e2e/test_declarative_interface_cross_scenario.py`，
      使用一个业务无关的通用测试用例（例如"打开设置面板并确认默认值"），
      不得引用任何 POS/购物袋相关内容。
      per Constitution Principle VI / FR-024~028 (partial)
