# Phase 1 Data Model: 自适应动作效果检测与可信业务验证

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

本文件把 spec.md 的 Key Entities 落成具体字段定义，作为 `src/vnc_agent/domain/*` 中新增/
修改 Pydantic 模型的实现依据。本 feature 建立在 001 `data-model.md` 已交付的实体之上——
下列各节只描述**新增**实体，以及对 001 既有实体的**增量修改**（新增字段/新增取值），不
重复 001 中未变更的部分（`TestCase`、`ScreenFrame`、`OCRItem`、`TemplateMatch`、
`WaitResult`、`RecoveryAttempt`、`TestRun` 等结构保持不变）。

## 1. TestStep（增量修改）— 对应 FR-007~012

在 001 `TestStep`（`domain/testcase.py`）基础上新增一个字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `verification_mode` | `Literal["business", "effect_only"] \| None` | 默认 `None`（省略）。`"effect_only"` 显式声明该步骤只关心动作效果；`"business"` 显式声明该步骤为正式业务步骤且要求加载时立即校验业务断言（新建步骤的推荐写法，见 research.md §7）；`None`（省略）在行为上等价于正式业务模式，但加载器 MUST NOT 因此拒绝加载（向后兼容旧用例，FR-025），运行时按 §6 兜底 |

**加载时校验规则（`load_test_case`，FR-008/011）**：

| `verification_mode` | `expected.conditions` 只含 `screen_changed`/`region_changed` | 加载结果 |
|---|---|---|
| `"effect_only"` | 允许 | 接受 |
| `"business"`（显式） | **不允许** | 拒绝，字段级错误指向 `steps[i].expected.conditions` |
| `None`（省略） | 允许（无法在加载时区分新旧） | 接受，运行时按 §6 产生 `uncertain` + 弱断言警告 |

## 2. VerificationCondition / ConditionType（增量语义分类，无字段变更）— 对应 FR-006/007

001 `domain/verification.py::ConditionType` 的既有取值不变；本 feature 新增一层**纯语义
分类**（不改变数据结构，作为 `verification/business_resolver.py` 内部常量使用）：

| 分组 | 包含的 `ConditionType` | 用途 |
|---|---|---|
| 业务结果断言（Business Result Assertion） | `text_appears`、`text_disappears`、`template_appears`、`template_disappears`、`region_changed`（当其 `region` 指向业务语义区域且与其它业务断言组合使用时，仍需至少一个非弱证据类型存在）、`visual_question` | 至少一个属于此组，才能使 `verification_mode="business"`（或省略）的步骤在 §6 中判定为 `passed` |
| 弱动作效果证据（Weak Action Effect Evidence） | `screen_changed`、`region_changed`（单独出现、不伴随任何业务断言时） | MAY 驱动 ActionEffect（§3），MUST NOT 单独驱动 StepVerificationResult 为 `passed`（`effect_only` 步骤除外） |

`region_changed` 分类到哪一组取决于上下文：若步骤的 `expected.conditions` 中除
`region_changed`/`screen_changed` 外还有其他真正的业务断言类型，则 `region_changed` 只是
辅助的弱证据；若 `expected.conditions` 全部由 `region_changed`/`screen_changed` 组成，则
整体判定为"仅含弱证据"，触发 FR-008（`business` 显式模式）或 FR-026（省略模式）。

## 3. ActionEffect（新增）— 对应 FR-001~005

新增 `domain/action_effect.py`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | `Literal["no_effect", "expected_effect", "unexpected_effect", "effect_uncertain"]` | ActionEffect 四态结果 |
| `evidence` | `ActionEffectEvidence` | 见下 |
| `reason` | str | 简短人类可读说明（如"local_blob@(412,88,44,40) ratio=0.0026 while global_ratio=0.00424"） |

`ActionEffectEvidence`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `global_diff_ratio` | float | 全屏像素变化比例（弱证据，来自 `compute_diff` 的 `diff_ratio`） |
| `local_blobs` | `list[Region]` | 不受全屏阈值门控的局部连通域列表（research.md §1），已排除动态噪声区域 |
| `ocr_added` | `list[str]` | 操作后新增的 `OCRItem.normalized_text` |
| `ocr_removed` | `list[str]` | 操作后消失的 `OCRItem.normalized_text` |
| `template_added` | `list[str]` | 操作后新增的 `TemplateMatch.template_id` |
| `template_removed` | `list[str]` | 操作后消失的 `TemplateMatch.template_id` |
| `structured_state_changed` | bool | `vision_understanding.description` 或其它结构化页面状态摘要是否发生变化 |
| `error_popup_signal` | `Literal["ocr_keyword", "template", "none"]` | research.md §6 的错误弹窗信号来源，命中即视为 `unexpected_effect` 的直接证据 |

**判定规则（research.md §2 的落地）**：

1. `error_popup_signal != "none"` → `status = "unexpected_effect"`。
2. 否则若 `local_blobs`、`ocr_added/removed`、`template_added/removed`、
   `structured_state_changed` 全部为空/`False` → `status = "no_effect"`。
3. 否则若上述任一信号达到"确定性局部阈值"（`local_blobs` 中最大连通域面积占比 ≥
   可配置的 `perception.local_blob_min_ratio`，默认 0.05%；或 OCR/模板差集非空；或
   `structured_state_changed = True`）→ `status = "expected_effect"`。
4. 否则（存在信号但均低于确定性局部阈值）→ `status = "effect_uncertain"`。

## 4. StepVerificationResult（复用 001 `VerificationResult`，增量修改）— 对应 FR-001/006/009/026/027

001 `domain/verification.py::VerificationResult` 保留原有字段
（`status`、`evidence_refs`、`matched_conditions`、`failed_conditions`、
`uncertain_conditions`、`reason`），新增两个字段，正式承担 spec 中
"StepVerificationResult"这一角色（与 `ActionEffect` 并列、互相独立，FR-001）：

| 新增字段 | 类型 | 说明 |
|---|---|---|
| `weak_assertion_warning` | bool（默认 `False`） | 当该步骤仅凭弱动作效果证据（§2）判定、且未声明 `verification_mode="effect_only"` 时 MUST 为 `True`（FR-026） |
| `basis` | `Literal["business_assertion", "action_effect_only", "mixed"]` | 判定依据来源：`business_assertion`（至少一个业务断言驱动结果）、`action_effect_only`（仅弱证据驱动，含 `effect_only` 步骤与旧用例兜底两种场景）、`mixed`（业务断言与弱证据共同参与但业务断言起决定作用） |

**判定规则（`verification/business_resolver.py`，取代原先 `VerificationEngine.verify()`
的直接输出，`VerificationEngine` 仍负责逐条件求值，本层负责组合与模式判断）**：

| 场景 | `status` | `weak_assertion_warning` | `basis` |
|---|---|---|---|
| 存在业务断言且聚合结果为 `passed` | `passed` | `False` | `business_assertion` 或 `mixed` |
| 存在业务断言且聚合结果为 `failed` | `failed` | `False` | `business_assertion` 或 `mixed` |
| 存在业务断言但聚合结果为 `uncertain`，且加强验证（§5）后仍无法收敛 | `uncertain` | `False` | `business_assertion` 或 `mixed` |
| `verification_mode="effect_only"`，仅弱证据，聚合结果为 `passed` | `passed` | `False` | `action_effect_only` |
| 仅弱证据（无业务断言）、且未声明 `effect_only`（含旧用例省略字段场景），即使弱证据聚合为 `passed` | `uncertain` | `True` | `action_effect_only` |

## 5. NonIdempotentActionClassification（增量修改 SemanticAction）— 对应 FR-013

001 `domain/action.py::SemanticAction` 新增字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `action_kind` | `Literal["idempotent", "non_idempotent"] \| None` | Planner 可显式给出；缺省时由 `planning/action_classification.py::classify_action_kind()` 按 `intent` 关键词表默认识别，两者都缺失时保守取 `"non_idempotent"`（research.md §3） |

## 6. RepeatGuardDecision（新增，逻辑实体，不落库）— 对应 FR-014~017

`execution/repeat_guard.py` 内部使用的判定结果（不需要持久化为独立数据表，作为
`ActionIteration.recovery_attempts` 之外的一个轻量记录追加到该迭代的日志字段）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `allowed` | bool | 是否允许本轮执行该（语义等价的）非幂等动作 |
| `reason` | `Literal["first_attempt", "different_action", "idempotent_action", "no_effect_confirmed", "blocked_effect_pending", "blocked_uncertain"]` | `blocked_effect_pending`/`blocked_uncertain` 对应 FR-015/016 的拒绝原因；`no_effect_confirmed` 对应 FR-016 的放行条件 |
| `previous_action_effect_status` | `ActionEffectStatus \| None` | 参与本次判断的上一轮 ActionEffect |

`ActionIteration`（`domain/run.py`）新增字段：

| 新增字段 | 类型 | 说明 |
|---|---|---|
| `action_effect` | `ActionEffect \| None` | 本轮动作效果判定结果 |
| `repeat_guard_decision` | `RepeatGuardDecision \| None` | 本轮是否被重复执行防护拦截 |

## 7. WeakAssertionWarning（复用 §4 的 `weak_assertion_warning` 字段，无独立类型）

不引入独立的 Pydantic 类型；`weak_assertion_warning: bool` + 现有 `VerificationResult.reason`
字段（追加说明文案，如"仅凭 screen_changed 证据判定，业务结果未经验证"）已足够表达，
避免为一个布尔标记 + 一句文案单独建模。报告层（`reporting/`）读取该字段渲染醒目的警告
标注（FR-027）。

## 8. VerifiedFocusNavigationPath（新增）— 对应 FR-020~024

新增 `domain/focus_path.py`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `from_hint` | str | 当前已知焦点位置的描述（如 OCR 文本、控件角色） |
| `to_hint` | str | 目标控件的描述，MUST 与本轮 `SemanticAction.target` 语义一致 |
| `tab_sequence` | `list[Literal["tab", "shift+tab"]]` | 从当前焦点到目标所需的具体按键序列 |
| `verification_method` | `Literal["structural_diff_confirmed", "prior_successful_replay"]` | (a) 焦点导航序列记录本身的来源；(b) 该序列当前仍然有效的验证方式：`structural_diff_confirmed` 表示本轮观察到的 OCR/模板/结构化状态与记录该序列时的页面状态一致（未发生足以使焦点顺序失效的页面结构变化）；`prior_successful_replay` 表示同一测试运行内此前已成功重放过该序列且期间页面未发生结构变化 |
| `verified_at_frame_id` | str | 验证时依据的 `ScreenFrame.id`，用于追溯 |

`ActionPolicy.resolve()`（`planning/action_policy.py`）的 `prefer_keyboard` 分支
MUST 改为接收一个 `VerifiedFocusNavigationPath | None` 参数：为 `None` 时 MUST NOT
输出 `outcome="focus", keys=["tab"]`，而是回退到既有的 `stop_recover` 结果（FR-022/024）；
非 `None` 时才 MAY 输出该键盘路径对应的 `tab_sequence`（FR-023）。

## 9. ErrorPopupClassification（并入 §3 `ActionEffectEvidence.error_popup_signal`，无独立类型）

不单独建模；`error_popup_signal` 字段（§3）已完整表达"命中来源"，判定结果本身就是
`ActionEffect.status = "unexpected_effect"`，无需额外的独立实体。

## 10. FailureType / RecoveryStrategy（无新增取值，路由行为修改）— 对应 FR-020~024

001 `domain/recovery.py::FailureType`、`RecoveryStrategy` 的取值集合不变
（`ACTION_NO_EFFECT`、`UNEXPECTED_DIALOG`、`switch_to_keyboard` 等已存在）。行为修改：

- `recovery/classifier.py::classify_action_no_effect(screen_changed: bool)` 的签名
  MUST 改为接收 `ActionEffect`（而非裸 `bool`），仅当 `status == "no_effect"` 才归类为
  `FailureType.ACTION_NO_EFFECT`；`status == "unexpected_effect"` MUST 归类为
  `FailureType.UNEXPECTED_DIALOG`（而不是复用 `ACTION_NO_EFFECT`）；
  `status == "effect_uncertain"` MUST NOT 触发 `ACTION_NO_EFFECT` 归类，改为交给 §5/§6
  的加强验证与 Repeat Guard 流程处理，不进入既有"second_candidate → switch_to_keyboard"
  恢复路由。
- `recovery/strategies.py::_run(strategy="switch_to_keyboard", ...)` 的副作用
  （`RecoveryEngine.prefer_keyboard = True`）保留，但其下游消费方
  `ActionPolicy.resolve()` 现在要求同时提供 §8 的 `VerifiedFocusNavigationPath`
  证据；`RecoveryEngine` 新增职责：在设置 `prefer_keyboard = True` 时，尝试从当前
  `StructuredScreen`（OCR/模板/结构化状态）构造该证据，构造失败则 `prefer_keyboard`
  的效果被 `ActionPolicy` 忽略（回退 `stop_recover`），不再无条件退化为发送 Tab。

## 11. 状态转移与数据流小结

```text
ActionIteration（单轮）：
  before_frame → SemanticAction(action_kind) → RepeatGuardDecision
    ├─ allowed=False → 加强验证（business_resolver）→ StepVerificationResult(uncertain,...)
    │                   不执行 ExecutableAction，本轮直接进入 RECORDING
    └─ allowed=True  → ActionPolicy.resolve(..., focus_path=VerifiedFocusNavigationPath|None)
                          → ExecutableAction → ExecutionResult → WaitResult
                          → after_frame → ActionEffect(status, evidence)
                                            │
                                            ├─ unexpected_effect → FailureType.UNEXPECTED_DIALOG
                                            │                      → StepVerificationResult(failed/uncertain)
                                            └─ 其它 → business_resolver 结合业务断言
                                                       → StepVerificationResult(status, basis, weak_assertion_warning)
```

`ActionEffect` 与 `StepVerificationResult` 在同一轮 `ActionIteration` 中并存、分别记录
（FR-001），互不覆盖；`StepRecord.final_status` 仍然只由 `StepVerificationResult.status`
序列驱动（沿用 001 §12 状态机规则），`ActionEffect` 不直接参与该状态机的迁移判定。
