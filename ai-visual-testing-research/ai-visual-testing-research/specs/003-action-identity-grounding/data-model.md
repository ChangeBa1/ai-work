# Phase 1 Data Model: 通用动作身份、目标一致性与坐标空间安全

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

**重新基线说明**：本文件替换 2026-07-21 版本。本文件把 spec.md 的 Key Entities
落成具体字段定义，全部实体 MUST 通过 `checklists/domain-independence.md` 的
业务无关性检查——不含任何 `cart`/`bag`/`subtotal`/`payment`/`clear_or_reset`
等固定业务字段，不含任何硬编码业务关键词表。本 feature 建立在 001/002
`data-model.md` 已交付的实体之上——下列各节只描述**新增**实体，以及对既有实体的
**增量修改**，不重复未变更的部分。

## 1. CanonicalActionIdentity（保留，无变化）— 对应 FR-001/002/005/007/009/011

`domain/action_identity.py`（现状实现，本次不改动）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `step_id` | str | 所属测试步骤 ID；不同 `step_id` 之间的身份永远不匹配（FR-001） |
| `action_type` | `ActionType`（复用 `domain/action.py`） | 语义动作类型 |
| `action_id` | `str \| None` | 语义动作携带的 `action_id`；缺失/空字符串时为 `None` |
| `normalized_target` | str | 规范化核心目标：优先取 `target.text` 归一化结果（容忍文字识别噪声，FR-008），`target` 为空或 `text` 为空时退化为 `normalized(intent)` |

**身份匹配结果（`IdentityMatch`，`execution/action_identity.py::identity_match()` 的
返回类型，保留不变）**：

| 取值 | 触发条件 |
|---|---|
| `"different_step"` | `prev.step_id != curr.step_id`（FR-001，优先级最高） |
| `"action_id_match"` | 二者 `step_id` 相同，`action_id` 均非 `None` 且相等，且 `action_type` 相等（FR-002/011，"同一逻辑动作尝试"的强匹配证据）。**重要（安全问题 A）**：本取值只表示"同一逻辑动作尝试"，MUST NOT 被 §3 `RepeatGuard.check()` 直接当作"新目标安全"的证明——见 §3 的 `has_target_evidence_conflict()` 前置门 |
| `"normalized_target_match"` | `step_id`/`action_type` 相同，但 `action_id` 缺失或不相等，且 `normalized_target` 经容忍匹配判定为同一目标（FR-008 的具体落地；证据强度弱于 `action_id_match`） |
| `"no_action_id_ambiguous"` | `action_id`/`normalized_target` 均无法判定为同一目标（FR-005 的触发条件，交由 §2 的一致性检查处理） |

## 2. `SemanticAction` 新增字段 — 对应 FR-012/013（安全问题 B）

`domain/action.py::SemanticAction`（增量修改，保留全部既有字段）：

| 新增字段 | 类型 | 说明 |
|---|---|---|
| `risk_level` | `Literal["low", "medium", "high"] = "low"`（**扩展**既有的 `Literal["low"]`） | 复用 Constitution 已确立的"动作安全分级 low/medium/high"这一通用概念，不新增概念 |
| `micro_action_purpose` | `Literal["dismiss_overlay", "scroll_reveal", "refocus", "wait", "re_observe"] \| None = None` | Planner 声明的、封闭的 UI 交互目的枚举；MUST NOT 是自由文本或业务关键词。Planner 提出一个独立于当前非幂等动作的新目标时 MAY 声明本字段 |

`micro_action_risk_thresholds`（新增，`config.py::PlanningConfig`）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `micro_action_risk_thresholds` | `dict[Literal["dismiss_overlay","scroll_reveal","refocus","wait","re_observe"], Literal["low","medium","high"]]` | 每个微动作类别被允许直接执行所要求的**最高**风险级别；核心提供合理的通用默认值（如 `wait`/`re_observe` 默认 `high`，`dismiss_overlay`/`scroll_reveal`/`refocus` 默认 `medium`），MAY 被具体部署覆盖，不含任何业务专用键 |

**删除**（相对旧版本）：`PlanningConfig.result_display_keywords`、
`PlanningConfig.dismissal_keywords` 两个字段与其硬编码的日文/中文默认值全部
删除——不再需要任何关键词列表，见 research.md §4/§7。

## 3. TargetConsistency：`has_target_evidence_conflict()` + `evaluate_target_consistency()`（重写）— 对应 FR-003/004/012/013/014

`execution/target_consistency.py` 新增/重写两个纯函数：

**`has_target_evidence_conflict()`（新增，落实安全问题 A）**：

```python
def has_target_evidence_conflict(
    previous_action: SemanticAction,
    proposed_action: SemanticAction,
    *,
    previous_resolved_region: Region | None = None,
    proposed_resolved_region: Region | None = None,
) -> bool: ...
```

| 冲突维度 | 判断依据 |
|---|---|
| 角色冲突 | 归一化后 `previous_action.target.role != proposed_action.target.role` |
| 交互性质冲突 | 二者角色分别映射到"可交互"/"非交互"分类结果不同（复用下方 `_is_interactive()`） |
| 空间证据冲突 | 若两个已解析区域均存在，IoU 低于 `config.agent.planning.target_region_conflict_iou_threshold`（默认 `0.10`）；任一区域缺失则本维度不参与判断 |

三个维度任一为真即返回 `True`。MUST NOT 依赖任何关键词列表。

**`evaluate_target_consistency()`（重写，落实安全问题 B）**：

```python
def evaluate_target_consistency(
    step_intent: str,
    previous_action: SemanticAction | None,
    proposed_action: SemanticAction,
) -> ConsistencyOutcome: ...
```

`ConsistencyOutcome`（取值不变，判定逻辑重写）：

| 取值 | 触发条件（AND 语义，见 research.md §7） |
|---|---|
| `"legitimate_micro_action"` | `proposed_action.micro_action_purpose is not None` **且** 步骤 intent 一致性检查通过 **且** `proposed_action.risk_level` 不超过 `micro_action_risk_thresholds[purpose]`——三者必须同时满足 |
| `"dangerous_drift"` | 上述 AND 条件不满足，且（前一动作可交互而新目标非交互）或（两者均可交互但未通过步骤 intent 一致性检查）——**不再**有"`action_type` 不同即无条件返回本值"的分支 |
| `"ambiguous"` | 现有信号不足以判断（触发 FR-004/007 fail-safe，或路由到 FR-034 恢复策略契约的人工确认/强模型字段） |

**删除**（相对旧版本）：模块级常量 `_RESULT_DISPLAY_KEYWORDS`、
`_DISMISSAL_KEYWORDS` 及其业务/语言专用默认值全部删除；`evaluate_target_
consistency()` 的 `result_display_keywords`/`dismissal_keywords` 关键字参数
删除（不再需要，见 research.md §7）。步骤 intent 一致性的"重合度量"算法本身
（规范化文本重叠比较）保留，但职责收窄为"新目标是否仍符合 step_intent"，不再
兼任"是否为合法微动作"的判断（该判断已改由 `micro_action_purpose` 字段承担）。

## 4. RepeatGuardDecision（增量修改，安全问题 A 落地）— 对应 FR-003/004/006/010

`domain/repeat_guard.py::RepeatGuardDecision` 保留既有字段
（`allowed`、`previous_action_effect_status`），`reason` 枚举取值：

| 变更 | 说明 |
|---|---|
| 保留 | `"first_attempt"`、`"idempotent_action"`、`"no_effect_confirmed"`、`"blocked_effect_pending"`、`"blocked_uncertain"`、`"no_effect_confirmed_normalized_target"`、`"blocked_effect_pending_normalized_target"`、`"blocked_uncertain_normalized_target"`、`"dangerous_drift"`、`"legitimate_micro_action"`、`"ambiguous_fail_safe"`（含义不变，均为既有取值） |
| 不再产生 | `"different_action"`（002 遗留取值，早已不再产生） |
| **组合逻辑变更** | `"action_id_match"`/`"normalized_target_match"` 分支新增前置门：仅当 `has_target_evidence_conflict()` 为 `False` 时才直接走 no_effect-only 重试许可规则；为 `True` 时（即使 identity 匹配、即使前一轮已 `no_effect`）MUST 转入 `evaluate_target_consistency()`，与 `"no_action_id_ambiguous"` 分支共用同一套后续路由（见 §3 与 research.md §6） |

`ActionIteration`（`domain/run.py`）字段不变：`canonical_identity:
CanonicalActionIdentity | None`（供报告审计，FR-035）。

## 5. GroundingCandidate / `resolve_pixel_bbox()`（保留，无变化）— 对应 FR-018~023

`domain/grounding.py::GroundingCandidate`（`bbox`、`coordinate_space:
Literal["pixel","normalized_1000"] | None`、`raw_bbox`）与
`models/coordinate_space.py::resolve_pixel_bbox()`（唯一换算点，闭区间
`[0,1000]`、越界/矛盾/未知值拒绝、历史响应双解释推断规则）现状实现**原样
保留**——`checklists/domain-independence.md` 未在此模块发现业务泄漏。详见
research.md §8，唯一改动是 `contracts/coordinate-space-contract.md` 示例标签
去业务化（纯编辑性）。

## 6. Executor 前置合理性核对（保留，无变化）— 对应 FR-019 精神延伸

`planning/action_policy.py::ActionPolicy._from_grounding()` 的 OCR 交叉核对
（`config/agent.yaml::planning.ocr_sanity_check_ratio`）现状实现**原样保留**，
不含业务专用逻辑。

## 7. `TestStep.verification_mode`（无变化）

001/002 已定义的 `TestStep.verification_mode: Literal["business","effect_only"]
| None` 字段与 `load_test_case()` 的三支加载规则均不改变（FR-029/030 向后兼容）。

## 8. 声明式运行前置条件（重写，替换固定购物车字段）— 对应 FR-024/025/026

**删除**：`domain/run.py::HumanStartStateConfirmation`（含
`confirmed_cart_items`/`confirmed_cart_amount`）、`ObservedStartState`（含
`cart_items`/`cart_amount`）、`StartStatePrecondition`；
`verification/business_resolver.py::extract_cart_state()`、
`evaluate_start_state_precondition()`。

**新增**（复用既有 `domain/verification.py::VerificationSpec`/
`VerificationCondition`/`VerificationResult`，不新增断言语法）：

| 类型/字段 | 结构 | 说明 |
|---|---|---|
| `DeclaredFact` | `key: str`、`spec: VerificationSpec` | 测试用例/场景 profile 声明的一条命名前置条件；`spec` 直接复用步骤级业务断言已在用的类型 |
| `RunPrecondition` | `facts: list[DeclaredFact] = []` | 由 `TestCase.precondition: RunPrecondition \| None` 顶层可选声明 |
| `FactEvaluation` | `key: str`、`result: VerificationResult` | 对每个 `DeclaredFact` 调用既有 `VerificationEngine.verify(fact.spec, first_observed_screen)` 的结果，直接复用既有类型 |
| `PreconditionEvaluation` | `status: Literal["not_required","passed","failed"]`、`fact_evaluations: list[FactEvaluation]`、`checked_at: datetime \| None` | 全部 `fact_evaluations[].result.status == "passed"` 时 `status="passed"`；任一非 `passed` 时 `status="failed"`；未声明 `precondition` 时 `status="not_required"` |
| `HumanConfirmedFact`（新增，真实/在线环境可选） | `key: str`、`confirmed_value: str`、`confirmed_at: datetime`、`screenshot_ref: str \| None` | 人工对任意声明 fact key 的独立确认值，仅作交叉证据，MUST NOT 参与 `PreconditionEvaluation` 的自动判定（见 research.md §12） |

`TestRun` 字段（增量修改）：

| 字段 | 类型 | 来源/用途 |
|---|---|---|
| `precondition_evaluation` | `PreconditionEvaluation` | Runtime 在首次独立观察后、任何 `ExecutableAction` 生成前完成自动比较 |
| `human_confirmed_facts` | `list[HumanConfirmedFact]` | CLI `--confirm-precondition key=value` 写入（可为空列表，普通离线运行始终为空） |

前置条件为 `failed` 时，运行直接进入失败记录/报告生成，全部
`ActionIteration.execution_result` 保持 `None`，不得调用恢复动作尝试纠正环境。
未声明 `precondition` 的测试用例（含全部旧格式用例）使用
`status="not_required"`，行为与 001/002 完全一致（FR-029 向后兼容零改动）。

## 8b. 声明式动作 Tag 审计（重写，替换固定四分类）— 对应 FR-027/028

**删除**：`config.py::ReportingConfig.category_keywords`（及其"必须恰好
`{add_to_bag,subtotal,payment,clear_or_reset}`"校验器）、其硬编码默认值。

**新增**：

| 类型/字段 | 结构 | 说明 |
|---|---|---|
| `ActionMatcher` | `action_type: ActionType \| None`、`target_role: str \| None`、`target_text_contains: str \| None`、`intent_contains: str \| None` | 结构化字段谓词（AND 关系），非文本关键词表；具体子串由声明方提供 |
| `ActionTagRule` | `tag: str`、`matcher: ActionMatcher` | 测试用例/场景 profile 声明的一条审计 tag 规则 |
| `ReportingConfig.action_tags` | `list[ActionTagRule] = []` | **核心默认空列表**，不含任何业务分类；测试用例/场景 profile 可覆盖或追加（`domain/testcase.py::TestCase.action_tags` 顶层可选声明，与 `AgentConfig.reporting.action_tags` 合并，测试用例声明优先） |

报告运行级输出：

| 字段 | 内容 | 计数规则 |
|---|---|---|
| `precondition_evaluation` | 直接序列化同名 `TestRun` 字段 | 含 `fact_evaluations` 逐条结果 |
| `human_confirmed_facts` | 直接序列化同名 `TestRun` 字段 | 空列表默认 |
| `executed_action_log` | 每个实际发送动作的 step/iteration、canonical identity、executable action、execution result | 仅收录 `execution_result.success is True` 的迭代（不变） |
| `declared_tag_counts` | `dict[str, int]`，按 `ActionTagRule.tag` 聚合 | 仅从 `executed_action_log` 聚合；一个动作可同时匹配 0/1/多个 tag；被拦截提案不得计数 |

## 8c. RecoveryPolicy 六字段契约（保留，无变化）— 对应 FR-031/034

既有 `RecoveryPolicy`（`max_retries`/`cooldown_ms`/
`consumes_global_retry_budget`/`allows_action_path_change`/
`requires_strong_model`/`requires_human_confirmation`）**原样保留**。新增
一条跨引用：§3 中风险级别导致的 `"ambiguous"`/`"dangerous_drift"` 结果 MUST
通过本契约的 `requires_human_confirmation`/`requires_strong_model` 字段路由，
不得新增独立于本契约之外的风险裁决逻辑（FR-013、2026-07-22 clarify 决议）。

## 9. 状态转移与数据流小结（重写，反映安全问题 A/B 修复）

```text
声明式前置条件门禁（若 TestCase.precondition 非空）：
  首次 Observe/Understand → 对每个 DeclaredFact 调用既有 VerificationEngine.verify()
    → PreconditionEvaluation
        ├─ passed → 允许进入第一个 PLANNING
        └─ failed → 运行失败并生成报告（零 ExecutableAction / 零已发送动作）
  未声明 precondition → status="not_required"，行为与 001/002 完全一致

ActionIteration（单轮）：
  before_frame → SemanticAction(action_id, target, risk_level, micro_action_purpose)
    → CanonicalActionIdentity(step_id, action_type, action_id, normalized_target)
    → IdentityMatch（identity_match()，不变）
    → has_target_evidence_conflict(previous, proposed)  # 安全问题 A：无论 IdentityMatch 结果如何都计算
    → 组合决策（RepeatGuard.check()）：
        ├─ IdentityMatch ∈ {action_id_match, normalized_target_match} AND NOT conflict
        │     → 复用既有 no_effect-only 重试许可规则（FR-006/010）
        └─ 其余（no_action_id_ambiguous，或 conflict=True 即使 IdentityMatch 已匹配）
              → evaluate_target_consistency()  # 安全问题 B：AND(purpose, intent一致性, risk阈值)
                    ├─ legitimate_micro_action → RepeatGuardDecision(allowed=True)
                    ├─ dangerous_drift         → RepeatGuardDecision(allowed=False)
                    └─ ambiguous               → fail-safe（等同 FR-004，除非可靠 no_effect+预算剩余）；
                                                  risk 驱动的场景通过 RecoveryPolicy 六字段路由人工确认/强模型
    → （若 allowed=True 且需要 Grounding）Grounder.ground()
        → 逐候选 resolve_pixel_bbox()（唯一换算点，不变）→ 淘汰不合规候选
        → ActionPolicy（OCR 交叉核对，不变）→ ExecutableAction
    → Executor → ActionEffect → business_resolver（001/002 既有业务断言机制，不变）
    → RECORDING（写入 canonical_identity、coordinate_space_audit 供报告审计）

运行报告聚合：
  仅 execution_result.success is True 的迭代 → executed_action_log
    → 按声明的 ActionTagRule 逐条匹配 → declared_tag_counts（零到多个 tag，非互斥四分类）
  被 RepeatGuard/ActionPolicy 拦截的提案 → 保留逐轮审计，但执行计数不增加
```

`CanonicalActionIdentity`、`RepeatGuardDecision`、
`GroundingCandidate.coordinate_space`/`raw_bbox`、`PreconditionEvaluation`、
`declared_tag_counts` 均随既有 `ActionIteration`/`TestRun` 一并记录，不新增
独立的持久化表结构（延续 002 "轻量记录追加到迭代日志字段"的既有模式）。

## 10. 业务泄漏清单（本文件层面的映射表，详见 research.md §0）

| 旧实体（删除） | 新实体（替换） |
|---|---|
| `HumanStartStateConfirmation`（`confirmed_cart_items`/`confirmed_cart_amount`） | `HumanConfirmedFact`（通用 key/value，§8） |
| `ObservedStartState`（`cart_items`/`cart_amount`） | `FactEvaluation`（复用 `VerificationResult`，§8） |
| `StartStatePrecondition` | `PreconditionEvaluation`（§8） |
| `ReportingConfig.category_keywords`（固定四分类） | `ReportingConfig.action_tags`（声明式 `ActionTagRule`，§8b） |
| `PlanningConfig.result_display_keywords`/`dismissal_keywords` | `SemanticAction.micro_action_purpose` + `PlanningConfig.micro_action_risk_thresholds`（§2） |
| `_RESULT_DISPLAY_KEYWORDS`/`_DISMISSAL_KEYWORDS`（模块常量） | 删除，无替代常量（判断改为读取声明字段，§3） |
| `action_type` 不同 → 无条件 `dangerous_drift` | AND(purpose, intent 一致性, risk 阈值)（§3） |
| `action_id_match` 跳过一致性检查 | `has_target_evidence_conflict()` 前置门（§3/§4） |
