# Phase 1 Data Model: VNC 黑盒 GUI 自动化测试核心执行闭环

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

本文件把 spec.md 的 Key Entities 落成具体的字段定义、校验规则与状态转移，作为
`src/vnc_agent/domain/*` 中 Pydantic 模型与 `storage/` 中数据表的实现依据。字段类型使用
Python/Pydantic 风格表示，*不*包含具体的类定义代码（实现细节留给 `/speckit-tasks` 与
implementation 阶段）。

## 1. TestCase（测试用例）— 对应 FR-001~004

| 字段 | 类型 | 说明 / 校验规则 |
|---|---|---|
| `id` | str | 全局唯一，非空 |
| `name` | str | 非空 |
| `target_id` | str | 引用 `VNCTarget.id`，必须存在于配置中 |
| `mode` | Literal["explicit"] | 本切片仅支持 `explicit`（明确步骤型），拒绝其他取值（FR-004） |
| `steps` | list[TestStep] | 至少 1 个元素 |
| `timeout_seconds` | int | 整个用例的总超时，默认取配置项 `默认步骤超时 × 步骤数` 的上界，可显式覆盖 |

**校验规则**：加载时若 `steps` 为空、`mode` 非法或必填字段缺失，MUST 在运行开始前拒绝
（FR-003），返回字段级错误而非在运行中途失败。

## 2. TestStep（测试步骤）— 对应 FR-002

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | str | 用例内唯一 |
| `name` | str | 可读名称 |
| `intent` | str | 自然语言操作意图，传给 Planner 作为上下文 |
| `expected` | VerificationSpec | 预期结果（见 §7） |
| `timeout_seconds` | int | 默认取自配置 `默认步骤超时` |
| `max_retries` | int | 默认取自配置 `默认最大重试次数`；MUST ≥ 0 |
| `status` | Literal["pending","running","passed","failed","cancelled"] | 步骤最终状态 |

**`status` 取值的进入条件（需求质量门禁 2026-07-21 澄清，补充 §12 状态机与本表的显式关联）**：

| 取值 | 进入条件 |
|---|---|
| `pending` | 初始值；`TestRun` 尚未调度到该步骤，或该步骤所属 `TestRun` 已因更早的步骤 `failed`/`cancelled` 而不再继续调度（§12 `STEP_COMPLETED_FAILED`/取消分支） |
| `running` | Runtime 将该步骤调度进入其第一轮 `ActionIteration` 的 `OBSERVING`（即 §12 中 `STEP_COMPLETED_PASSED → OBSERVING` 或用例的第一个步骤开始执行）时，MUST 由 `pending` 转为 `running` |
| `passed` | 该步骤某一轮 `ActionIteration.verification_result.status = passed`（§12 `STEP_COMPLETED_PASSED`）时，MUST 由 `running` 转为 `passed` |
| `failed` | 该步骤预算耗尽仍为 `failed`/`uncertain`（§12 `STEP_COMPLETED_FAILED`）时，MUST 由 `running` 转为 `failed` |
| `cancelled` | 该步骤处于 `running` 时被用户/系统取消，MUST 由 `running` 转为 `cancelled`（§12 `TestRun.status` 聚合规则）；`pending` 的步骤在其所属 `TestRun` 被取消时 MUST 保持 `pending`，不转为 `cancelled`（避免"从未开始执行"与"执行到一半被打断"这两种取消语义被混淆） |

**步骤粒度不变量（Clarification 2026-07-20）**：一个 `TestStep` 在运行时 MAY 对应多轮
`ActionIteration`（见 §9）——Planner 可在 `intent` 声明目标之外自主插入必要前置微动作
（聚焦、滚动、关闭安全弹窗等），并在验证未通过且预算未耗尽时继续下一轮迭代。`max_retries`
是该步骤"重新尝试达成 `expected`"的统一预算，同时覆盖：验证失败后的常规重试、步骤内的
微动作迭代、以及 VNC 断线重连后的整步重新执行（FR-039）——三者共享同一计数器，不单独
开辟额外的重试上限，避免预算口径不一致。

## 3. StructuredScreen（结构化屏幕观察）— 对应 FR-005~011

| 字段 | 类型 | 说明 |
|---|---|---|
| `frame_id` | str | 关联的 `ScreenFrame.id` |
| `resolution` | tuple[int,int] | 实际屏幕分辨率（宽,高） |
| `captured_at` | datetime | 采集时间 |
| `ocr_items` | list[OCRItem] | 见下 |
| `template_matches` | list[TemplateMatch] | 已配置模板的匹配结果 |
| `changed_since_last` | bool | 相较上一帧是否变化（FR-007） |
| `changed_regions` | list[Region] | 具体变化区域（若适用） |
| `vision_understanding` | VisionUnderstanding \| None | 仅当常规手段无法理解页面时填充（FR-010），MUST NOT 替代结构化字段，只作为补充 |

**ScreenFrame** 子实体：`id, run_id, step_id, image_path, width, height, timestamp`（FR-009）。

**OCRItem**：`text, bbox(x1,y1,x2,y2), confidence(0~1), normalized_text`。

**TemplateMatch**：`template_id, bbox, confidence`。

**Region**：`x1,y1,x2,y2`，MUST 满足 `x1<x2 且 y1<y2`，且落在屏幕分辨率范围内。

**VisionUnderstanding**（视觉模型补充理解结果，对应 FR-010，模型调用契约见
contracts/model-provider-contract.md 的 `PlannerProvider.describe_screen`）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `description` | str | 视觉模型对当前页面的结构化文字描述（如页面类型、主要控件、当前焦点） |
| `confidence` | float(0~1) | 模型对该描述的置信度 |
| `model_name` | str | 补充理解所用模型名称 |
| `raw_response_ref` | str | 原始响应存档路径（用于证据留存，对应 FR-040） |

**触发前提（FR-010）**：仅当图像哈希比较、OCR、模板匹配均无法确定页面含义时才 MUST 调用，
调用方式为 `PlannerProvider.describe_screen(mode="describe")`；`vision_understanding`
MUST NOT 替代 `ocr_items`/`template_matches`/`changed_regions` 等结构化字段，只作为它们
均不足以判断时的补充信息。

## 4. SemanticAction（语义动作）— 对应 FR-012~014

| 字段 | 类型 | 说明 |
|---|---|---|
| `action_id` | str | 唯一 |
| `intent` | str | 如"点击登录按钮" |
| `action_type` | Literal["click","double_click","right_click","type_text","press_key","hotkey","scroll","drag","wait","finish"] | |
| `target` | TargetDescription \| None | 仅当 `action_type` 需要定位目标时必填 |
| `text_value` | str \| None | 文本输入内容（敏感值通过引用传入，见 §9） |
| `keys` | list[str] | 组合键（如 `["ctrl","s"]`） |
| `risk_level` | Literal["low"] | 本切片不含 medium/high 风险动作 |

**不变量**：`SemanticAction` MUST NOT 包含裸坐标字段（FR-013）——领域模型层面即不提供
`x`/`y` 字段，坐标只出现在 `ExecutableAction`（执行层，见 §6）中，从类型层面强制该约束。

**TargetDescription**：`role: str|None, text: str|None, description: str, nearby_texts: list[str]`。

## 5. GroundingResult（视觉定位结果）— 对应 FR-015~019

| 字段 | 类型 | 说明 |
|---|---|---|
| `found` | bool | 目标是否存在（FR-016/018） |
| `candidates` | list[GroundingCandidate] | 最多 3 个（FR-016），`found=False` 时 MUST 为空列表 |
| `model_name` | str | 定位所用模型名称 |
| `raw_response_ref` | str | 原始响应存档路径（用于证据留存） |

**GroundingCandidate**：`bbox(还原后的原始屏幕像素坐标), confidence(0~1), label: str|None, reason: str`。

**校验规则**：`bbox` MUST 位于 `StructuredScreen.resolution` 范围内（FR-019）；越界的候选
在进入 Action Policy 选择前 MUST 被过滤，不进入候选集合。

## 6. ExecutableAction / ExecutionResult（执行方案与执行结果）— 对应 FR-020~024

**ExecutableAction**：`method: Literal["keyboard","mouse"], operation: str, coordinates: tuple[int,int]|None, keys: list[str], text: str|None`。
本切片不含 `replay`、`powershell_recipe` 方法（超出范围）。

**ExecutionResult**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `success` | bool | 仅表示"动作已发送"（FR-024），MUST NOT 被解读为步骤通过 |
| `started_at` / `ended_at` | datetime | 用于计算耗时 |
| `timed_out` | bool | 是否触发动作级超时（FR-021） |
| `target_region` | Region \| None | 点击前记录的目标区域（FR-023） |
| `actual_click_point` | tuple[int,int] \| None | 实际点击点（FR-023） |
| `error_code` / `error_message` | str \| None | |

**运行时不变量**：动作因异常提前结束时，Executor MUST 在返回 `ExecutionResult` 之前调用
修饰键释放例程（FR-022）；该调用本身不建模为独立字段，而是作为 Executor 的强制副作用，
由集成测试断言验证。

## 7. WaitResult / VerificationSpec / VerificationResult — 对应 FR-025~035

**WaitResult**：`waited_ms: int, stable: bool, end_reason: Literal["stable","expected_condition","timeout","vnc_error","cancelled"]`。

**VerificationSpec**（预期结果，来自 TestStep.expected）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `operator` | Literal["all","any"] | 复合断言组合方式 |
| `conditions` | list[VerificationCondition] | 至少 1 个 |
| `timeout_seconds` | int | 独立于步骤超时，可覆盖默认值 |

**VerificationCondition**：`type: Literal["text_appears","text_disappears","template_appears","template_disappears","region_changed","screen_changed","visual_question"], value: str, region: Region|None`（FR-031）。
`type="visual_question"` 时，`value` 为向视觉模型提出的明确页面状态问题（如"是否出现欢迎
文字？"），求值方式为调用 `PlannerProvider.describe_screen(mode="answer_question",
question=value)`（契约见 contracts/model-provider-contract.md），其响应的 `answer` 字段
直接对应该子条件的 `passed`/`failed`/`uncertain` 三态判定（FR-032）。**`visual_question`
是测试用例作者在编写 `expected` 时显式声明的条件类型之一，MUST NOT 被实现为其余六种
确定性类型判定为 `uncertain` 时的运行时自动升级路径**——验证引擎（`verification/engine.py`）
按 `VerificationCondition.type` 逐条分发求值，不存在"某条件求值不确定后改用视觉模型重新
判断同一条件"的隐式逻辑；FR-032"只有确定性方法无法判断时才使用视觉模型"是对测试用例
编写者的指引（SHOULD NOT 在确定性类型足以表达时声明 `visual_question`），详见 FR-032。

**VerificationResult**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | Literal["passed","failed","uncertain"] | `uncertain` MUST NOT 被上游当作 `passed`（FR-033） |
| `evidence_refs` | list[str] | 指向操作后新截图/OCR/模板等独立证据（FR-034） |
| `matched_conditions` / `failed_conditions` / `uncertain_conditions` | list[str] | 复合断言下每个子条件各自的判定去向 |
| `reason` | str | |

**运行时不变量**：`VerificationResult` 的生成 MUST 以本次动作执行**之后**新采集的
`StructuredScreen` 为输入；不得接受 Planner/Grounder/Executor 自身的成功声明作为输入
（FR-034，宪法 Core Principle IV）。

**复合断言求值算法（Clarification 2026-07-20，对应 FR-033）**：对 `VerificationSpec` 中的
每个 `VerificationCondition` 独立求值为 `passed`/`failed`/`uncertain` 三态之一后，按
`operator` 聚合：

```text
operator = "all":
  若存在任一子条件 = failed         → 整体 = failed
  否则若存在任一子条件 = uncertain    → 整体 = uncertain
  否则（全部子条件 = passed）        → 整体 = passed

operator = "any":
  若存在任一子条件 = passed          → 整体 = passed
  否则若存在任一子条件 = uncertain    → 整体 = uncertain
  否则（全部子条件 = failed）        → 整体 = failed
```

即"failed 在 all 下优先于 uncertain，passed 在 any 下优先于 uncertain"，但只要没有更强的
反例/正例把结果锁定为 failed/passed，`uncertain` MUST 原样向上传播，MUST NOT 被聚合逻辑
悄悄归并为 `failed` 或 `passed`。

## 8. FailureType / RecoveryAttempt — 对应 FR-036~039

**FailureType**（枚举，FR-036）：
`vnc_connect_failed, vnc_disconnected, black_screen, page_not_stable, target_not_found,
grounding_low_confidence, action_no_effect, focus_error, input_method_error,
unexpected_dialog, verification_failed, timeout`

**GroundingLowConfidenceReason**（`grounding_low_confidence` 的子原因，Clarification
2026-07-20，供恢复记录与 §10 视觉经验样本区分记录，不是独立的 `FailureType`）：
`Literal["overall_low_confidence", "top1_top2_close"]`。判定规则：Grounding 显式返回
`found=false` → 归类为 `target_not_found`（非本枚举）；`found=true` 但 Top-1 候选置信度低于
配置阈值 → `overall_low_confidence`；`found=true` 且 Top-1 置信度达标但与 Top-2 的差值小于
配置阈值 → `top1_top2_close`。

**RecoveryAttempt**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `failure_type` | FailureType | |
| `sub_reason` | GroundingLowConfidenceReason \| None | 仅当 `failure_type = grounding_low_confidence` 时填充（Clarification 2026-07-20） |
| `strategy` | Literal["recapture","extra_wait","second_candidate","re_ground","switch_to_keyboard","release_modifiers","press_escape","win_d_reset","restart_step"] | 对应 FR-037；`restart_step` 专用于 `vnc_disconnected` 重连成功后重新执行整个步骤（FR-039） |
| `attempt_index` | int | 该失败类型下的第几次尝试 |
| `max_retries` | int | 该失败类型的配置上限（FR-038），达到后步骤 MUST 标记为 `failed`；`restart_step` 消耗的是 `TestStep.max_retries` 这一共享预算（见 §2），不单独计数 |
| `resolved` | bool | 本次尝试后是否解决 |

**恢复策略路由（完整版，需求质量门禁 2026-07-21 补全——原 Clarification 2026-07-20 仅给出
3/12 种失败类型的路由，以下补齐全部 12 种，并标注每种策略是否消耗 Tier-1 共享预算，对应
宪法"恢复与重试门禁"要求的"是否消耗全局重试额度"标注项）**：

| `FailureType` | 首选 `strategy`（Tier-2，独立计数） | 次选 `strategy`（Tier-2 用尽后） |
|---|---|---|
| `vnc_connect_failed` | `recapture`（等价于重试初次连接，发生在 `CONNECTING`，尚无 `TestStep` 上下文） | 无——`vnc.reconnect_attempts` 用尽后运行 MUST 直接 `FAILED`，对应 cli-contract.md 退出码 4 |
| `vnc_disconnected` | — | `restart_step`（Tier-1 直接消耗，见下方"预算层级"，不设独立 Tier-2 计数） |
| `black_screen` | `recapture` | `extra_wait` |
| `page_not_stable` | `extra_wait` | `recapture`（延长等待仍不稳定时，重新截图核实是否黑屏/断线等更严重情形） |
| `target_not_found` | `recapture`（重新观察） | `re_ground`（局部放大再定位） |
| `grounding_low_confidence`（含两种 `sub_reason`） | `second_candidate` | `re_ground` |
| `action_no_effect` | `second_candidate`（若上次为 Grounding 候选点击） | `switch_to_keyboard`（改走键盘路径重新进入 Action Policy 优先级） |
| `focus_error` | `press_escape`（重置可能异常的焦点/弹窗状态） | `switch_to_keyboard`（改用 Tab/Shift+Tab 焦点导航） |
| `input_method_error` | `release_modifiers`（释放可能卡住的修饰键/输入法组合键状态） | `switch_to_keyboard`（改用逐字符按键而非整段文本输入） |
| `unexpected_dialog` | `press_escape` | `win_d_reset`（Escape 无效时回到桌面重新观察） |
| `verification_failed` | `recapture`（核实是否只是截图未及时更新） | `extra_wait`（给页面更多收敛时间后再验证一次） |
| `timeout` | 按发生阶段路由：Grounding/Planner 调用超时 → `re_ground`/交由 Planner 下一轮重新决策；动作执行超时 → `switch_to_keyboard`；等待超时 → 不重试，直接以现有证据进入 `VERIFYING` | `release_modifiers`（任意超时后统一执行，防止修饰键遗留按下状态） |

**预算层级（需求质量门禁 2026-07-21 澄清，回答"两个上限谁优先生效"）**：恢复预算分两层，
互不共享计数器，但存在单向折算关系：

1. **Tier-1（步骤级，`TestStep.max_retries`，见 §2）**：统计"这个 `TestStep` 还能开启多少轮
   新的 `ActionIteration`"，覆盖验证失败重试、微动作迭代、`restart_step` 三种情形（研究见
   research.md §10）。
2. **Tier-2（失败类型级，`RecoveryAttempt.max_retries`，本节）**：统计"在**当前**这一轮
   `ActionIteration` 内，针对某个具体 `FailureType`，还能尝试多少次上表中的恢复策略"，
   `restart_step` 例外（不设独立 Tier-2，直接记为一次 Tier-1 消耗，见下）。
3. **折算规则**：当某个 `FailureType` 的 Tier-2 预算在当前 `ActionIteration` 内耗尽、仍未
   解决（`resolved=false`）时，本轮 `ActionIteration` MUST 视为以 `failed` 结束（即使尚未
   到达 `EXECUTING`/`VERIFYING` 阶段），并据此消耗**一个** Tier-1 单位；若 Tier-1 预算
   仍有剩余，进入下一轮 `ActionIteration`（`iteration_index+1`）重新从 `OBSERVING` 开始，
   该新一轮为该 `FailureType` 重新获得一份完整的 Tier-2 预算（Tier-2 预算按 `ActionIteration`
   重置，不跨轮累积）；若 Tier-1 预算同时也已耗尽，该 `TestStep` 直接标记为
   `failed`（`STEP_COMPLETED_FAILED`，见 §12）。此规则保证两层预算均为有限值时，最坏情况
   下一个步骤的总恢复尝试次数上界为 `TestStep.max_retries × max(各 FailureType 的
   RecoveryAttempt.max_retries)`，MUST NOT 出现无上限的组合爆炸或死循环（对齐宪法"恢复与
   重试门禁"）。
4. **恢复动作自身的失败（需求质量门禁 2026-07-21 澄清）**：执行上表中任一 `strategy`
   本身（如发送 Escape 按键、切换到第二候选）MUST 复用 FR-021 规定的动作级超时；若恢复
   动作执行本身超时或抛出异常，MUST 将其归类为一次新的失败发生（通常为 `timeout` 或触发
   异常的具体类型），计入触发该恢复动作的原 `FailureType` 的同一个 Tier-2 `attempt_index`
   序列，不额外开辟"恢复的恢复"这一无界的第三层预算。
5. **VNC 断线的特殊性**：`restart_step` 不设独立 Tier-2 计数器，每次触发直接消耗一个
   Tier-1 单位（与"预算层级"第 1 点一致，对应 §2 与 §12 已有表述）。

## 9. 测试运行证据聚合 — 对应 FR-040~042

**ActionIteration**（Clarification 2026-07-20 新增：一个测试步骤内的一轮"选择动作→定位→
执行→等待→验证"迭代，对应用户故事三的"步骤粒度说明"）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `iteration_index` | int | 该步骤内的第几轮迭代，从 0 开始 |
| `before_frame_id` / `after_frame_id` | str | 本轮迭代的操作前后截图 |
| `semantic_action` | SemanticAction | 本轮 Planner 产出的语义动作（可能是 intent 之外的
  必要前置微动作） |
| `grounding_result` | GroundingResult \| None | 仅当本轮需要视觉定位时填充 |
| `executable_action` | ExecutableAction | |
| `execution_result` | ExecutionResult | |
| `wait_result` | WaitResult | |
| `verification_result` | VerificationResult | 本轮针对 `TestStep.expected` 的独立验证
  结果；`passed` 时该步骤立即结束迭代并整体判定为通过，`failed`/`uncertain` 且预算未耗尽
  时才会产生下一轮 `ActionIteration` |
| `recovery_attempts` | list[RecoveryAttempt] | 本轮迭代内发生的恢复尝试 |

**被取消迭代的记录规则（需求质量门禁 2026-07-21 澄清）**：若用户/系统取消发生在某一轮
`ActionIteration` 执行中途（例如已完成 `OBSERVING`/`PLANNING` 但尚未到达
`VERIFYING`），该轮 `ActionIteration` MUST 仍作为 `StepRecord.iterations` 的最后一个元素
被保留写入（不得因未走完全部阶段而丢弃整条记录，对应 FR-040 的证据完整性要求）；尚未
执行到的字段（如取消发生在 `EXECUTING` 之前时的 `execution_result`/`wait_result`/
`verification_result`）MUST 保持为 `None`，MUST NOT 编造占位值；该轮不产生
`verification_result.status`，因此不参与 §7 的三态判定，也不消耗 Tier-1/Tier-2 预算
（因为它并未走到失败/通过判定这一步，只是被外部中断）。

**StepRecord**（一个测试步骤的完整证据集合）：
`step_id, iterations: list[ActionIteration], final_status: Literal["passed","failed",
"cancelled"], ocr_result_ref, model_names: dict[str,str], raw_model_response_refs: list[str],
stage_durations_ms: dict[str,int]`。`final_status` MUST 等于最后一轮 `ActionIteration.
verification_result.status`（`uncertain` 在预算耗尽时归为 `failed`）或 `cancelled`；
FR-040 所列的"操作前后截图、OCR 结果、Planner 结构化动作、Grounding 候选、实际执行动作、
实际点击坐标、等待结果、验证结果、重试和恢复记录"均可从 `iterations` 中逐轮取得，不再
要求每步骤只有一份。

**`stage_durations_ms` 的精度要求（需求质量门禁 2026-07-21 澄清）**：单位为整数毫秒；
计时 MUST 使用单调时钟（如 Python `time.monotonic()`），MUST NOT 直接使用系统墙钟
（`time.time()`）以避免 NTP 时间校正或时区/夏令时调整导致耗时出现负值或跳变；耗时数据
仅要求在同一次 `TestRun` 进程生命周期内可比较，MUST NOT 要求跨进程重启后仍可比较（与
`started_at`/`ended_at` 等墙钟时间戳字段的用途不同，后者仍使用墙钟以便与外部日志对齐）。

**TestRun**：`run_id, test_case_id, status: Literal["passed","failed","cancelled"],
started_at, ended_at, steps: list[StepRecord], report_json_path, report_html_path`。
`status` 从 `steps` 聚合得出的规则见 §12"TestRun.status 聚合规则"：任一 `StepRecord.
final_status="failed"` 即整条 `TestRun.status="failed"` 且该步骤之后的步骤不再执行
（对应 FR-035）。

**敏感信息处理（Clarification 2026-07-20，对应 FR-049）**：`StepRecord`/`TestRun` 序列化为
**本地持久化制品与 JSON/HTML 报告**前，MUST 对已配置的敏感区域截图打码、对已知敏感字段
（密码类 `text_value_ref` 对应的明文）做屏蔽（FR-047，宪法"凭据与隐私"）；该遮罩逻辑仅
作用于落盘与报告渲染这两个出口，MUST NOT 应用于 §5/§4 中构造的、发往 Planner/Grounder
模型 API 的请求体截图——两者共享同一份原始 `ScreenFrame`，但在各自的序列化/导出路径上
分别决定是否打码。

## 10. VisualExperience（面向未来自进化的数据采集）— 对应 FR-043~044

| 字段 | 类型 | 说明 |
|---|---|---|
| `run_id` / `step_id` | str | |
| `before_frame_id` / `after_frame_id` | str | |
| `semantic_action` | dict | `SemanticAction` 的序列化快照 |
| `grounding_candidates` | list[dict] | 供未来构建 Grounding 正负样本 |
| `selected_candidate` | dict \| None | |
| `execution_result` | dict | |
| `verification_result` | dict | |
| `outcome` | Literal["success","failure","uncertain"] | |
| `failure_type` | str \| None | |

**运行时不变量（FR-044）**：本功能对 `VisualExperience` 的处理 MUST 只包含"写入"，代码
路径中 MUST NOT 出现修改模型权重、修改 `VerificationSpec`/测试断言、覆盖回放脚本、或
"仅因一次成功即固化为新基线"的逻辑；这些均属于后续功能范围。

## 11. 配置实体 — 对应 FR-045~047

| 字段 | 类型 | 说明 |
|---|---|---|
| `vnc.host` / `vnc.port` | str / int | |
| `vnc.connect_timeout_seconds` / `vnc.reconnect_attempts` | int | |
| `models.planner.provider` / `models.planner.timeout_seconds` | str / int | Planner 可替换（FR-046） |
| `models.grounder.provider="opencode-go"` / `models.grounder.model="mimo-v2.5"` / `models.grounder.top_k` | | Grounder 固定实现 |
| `perception.ocr_enabled` / `perception.template_enabled` | bool | |
| `wait.stable_frame_count` / `wait.pixel_diff_threshold` | int / float | 页面稳定阈值 |
| `step.default_timeout_seconds` / `step.default_max_retries` | int | |
| `artifacts.screenshot_policy` | Literal["step","all","on_failure"] | |
| `security.mask_regions` | list[Region] | 敏感信息遮罩区域 |
| `vnc.password_env` / `models.*.api_key_env` | str | 只存环境变量名，不存明文（FR-047） |
| `recovery.<failure_type>.max_retries` | int，MUST ≥ 1 | 需求质量门禁 2026-07-21 新增：§8 表中 12 种 `FailureType` 各自的 Tier-2 恢复预算上限（对应 FR-038、Constitution"恢复与重试门禁"），具体数值由实现阶段依据实测调优，处理方式与 research.md §11 的置信度阈值一致——不在规格/数据模型阶段固化具体数字 |
| `recovery.<failure_type>.cooldown_ms` | int，MUST ≥ 0 | 需求质量门禁 2026-07-21 新增：同一 `FailureType` 连续两次恢复尝试之间的最短间隔（毫秒），对应 Constitution"恢复与重试门禁"的"冷却时间"要求；默认值同样由实现阶段依据实测给出 |
| `models.planner.describe_screen_timeout_seconds` | int，默认取 `models.planner.timeout_seconds` | 需求质量门禁 2026-07-21 新增：`describe_screen` 方法的调用超时，未显式配置时 MUST 复用 `plan` 方法的超时值（见 contracts/model-provider-contract.md），不引入第二套默认值 |

## 12. 状态转移（Agent Runtime，对应宪法 Core Principle I）

```text
CREATED → CONNECTING → PREPARING → OBSERVING

# 单轮 ActionIteration（Clarification 2026-07-20：同一 TestStep 内可多轮重复）：
OBSERVING → UNDERSTANDING → PLANNING → RESOLVING_ACTION → (GROUNDING)?
  → EXECUTING → WAITING → VERIFYING → RECORDING

VERIFYING 判定该轮 verification_result：
  passed                       → STEP_COMPLETED_PASSED（该 TestStep 整体通过）
  failed / uncertain 且预算未耗尽 → 回到 OBSERVING（开始下一轮 ActionIteration，
                                    iteration_index + 1，消耗 TestStep.max_retries）
  failed / uncertain 且预算已耗尽 → STEP_COMPLETED_FAILED（该 TestStep 整体标记为 failed）

STEP_COMPLETED_PASSED → (OBSERVING | PASSED)
  # 该步骤 status="passed"；若用例中存在下一个 TestStep，MUST 继续调度进入其 OBSERVING
  # 开启新一轮 ActionIteration（iteration_index 重置为 0）；若这是最后一个 TestStep，
  # 整条 TestRun.status MUST 置为 "passed"

STEP_COMPLETED_FAILED → FAILED
  # 该步骤 status="failed"；整条 TestRun MUST 立即终止，TestRun.status MUST 置为
  # "failed"，MUST NOT 调度任何后续 TestStep 进入 OBSERVING（对应 FR-035、SC-002：
  # "验证未通过时 MUST NOT 继续执行后续步骤"，且人工抽查此情况的发生比例 MUST 为零）。
  # 已执行完毕（passed）的前序步骤保留其各自 "passed" 状态不回滚；尚未开始的后续步骤
  # MUST 保持 "pending"（不产生任何 StepRecord.iterations），而不是被静默标记为
  # "cancelled" 或 "passed"

**TestRun.status 聚合规则**（补充 §9 未显式给出的规则）：
  - 全部 TestStep 均以 STEP_COMPLETED_PASSED 结束 → TestRun.status = "passed"
  - 任一 TestStep 以 STEP_COMPLETED_FAILED 结束（含耗尽预算后仍为 uncertain 的情形，
    uncertain 在此处按 failed 处理，见 §7）→ TestRun.status = "failed"，且该 TestStep
    之后的所有步骤不再执行
  - 运行过程中被用户/系统取消 → TestRun.status = "cancelled"，当前正在执行的 TestStep
    标记为 "cancelled"，其余未开始的步骤保持 "pending"

RECOVERING（需求质量门禁 2026-07-21 补全进入/退出条件，原表述"任意阶段失败→RECOVERING→
  (...)"过于笼统，以下明确边界）：
  - 进入条件：`OBSERVING` 到 `RECORDING` 之间任一阶段（含 `GROUNDING`）检测到 §8 枚举的
    12 种 `FailureType` 之一时，MUST 进入 `RECOVERING`；`CREATED`/`CONNECTING`/
    `PREPARING` 阶段的失败（如 `vnc_connect_failed`）同样进入 `RECOVERING`，但此时尚无
    `TestStep`/`ActionIteration` 上下文，恢复范围仅限于 §8 表中 `vnc_connect_failed` 一行
    （重试连接，无 Tier-1/Tier-2 预算，仅受 `vnc.reconnect_attempts` 约束）
  - 退出条件：MUST 按 §8"预算层级"小节的规则判定——Tier-2 预算未耗尽且本次恢复尝试
    `resolved=true` → 回到触发失败的对应阶段继续本轮 `ActionIteration`；Tier-2 预算耗尽
    → 视为本轮 `ActionIteration` 以 `failed` 结束，消耗一个 Tier-1 单位，按 VERIFYING 判定
    规则（见上）转移；`vnc_connect_failed` 达到 `vnc.reconnect_attempts` 上限 → 直接
    `FAILED`（运行从未成功开始，无 `TestStep` 可标记）
VNC 断线（vnc_disconnected）→ RECOVERING → 有限次数重连成功 → 回到 OBSERVING 并开启新一轮
  ActionIteration（`restart_step`，见 §8），MUST NOT 从 WAITING/VERIFYING 等中间阶段直接
  继续（对应 FR-039 的澄清）；重连耗尽仍失败 → 视为 Tier-1 预算耗尽处理（进入
  STEP_COMPLETED_FAILED）；若触发断线时 `TestStep.max_retries`（Tier-1）已耗尽为 0，
  MUST NOT 尝试 `restart_step`，该步骤直接判定为 `failed`（Clarification 2026-07-21，
  见下方说明与 spec.md Clarifications）

CANCELLED（需求质量门禁 2026-07-21 补全进入/退出条件）：
  - 进入条件：`CREATED` 到 `RECOVERING` 之间的**任意**状态，收到用户/系统取消请求时 MUST
    立即转移到 `CANCELLED`（不必等待当前阶段自然结束）；当前正在执行的 `ActionIteration`
    按 §9"被取消迭代的记录规则"记录部分证据
  - 退出条件：`CANCELLED` MUST 为终态，不再转移到任何其他 `AgentState`；`TestRun.status`
    按 §12"TestRun.status 聚合规则"置为 `"cancelled"`
```

**转移记录不变量**：每次状态迁移 MUST 记录 `run_id, step_id, iteration_index, 原状态,
新状态, 迁移原因, 时间, 当前重试次数, 当前错误类型(若有), 关联截图, 关联动作`，与 §9 的
`StepRecord.iterations` 共同构成完整证据链（FR-040）。

**实现落点**：本节 `STEP_COMPLETED_PASSED`/`STEP_COMPLETED_FAILED` 的显式区分与
`TestRun.status` 聚合规则，由 `runtime/agent_runtime.py` 中的步骤级预算与流转判定逻辑
（tasks.md T081b）实现；早期版本的状态转移表述曾将两种结局合并为单一 `STEP_COMPLETED`
状态、且未给出 `TestRun.status` 聚合规则，可能被误读为"步骤失败后仍继续下一步骤"，本节
已订正，以此处文字为准。

**VNC 断线与 Tier-1 预算耗尽的优先级（Clarification 2026-07-21，需求方已确认，见 spec.md
Clarifications）**：当 `TestStep.max_retries`（Tier-1）已耗尽为 0 的同一时刻，恰好发生
VNC 断线（`vnc_disconnected`）时，Tier-1 预算耗尽优先生效——系统 MUST NOT 尝试
`restart_step`，该步骤 MUST 直接判定为 `failed`（`STEP_COMPLETED_FAILED`）。这与"所有恢复
与迭代共享同一个步骤级预算、系统级 MUST NOT 出现无限重试路径"的既有原则完全一致，不为
`vnc_disconnected` 开设不受 Tier-1 门控的例外路径。已评估的替代方案（即使 Tier-1 预算已耗尽
也至少尝试一次重连）因需要为 `restart_step` 引入独立于 Tier-1 的特例判定顺序、与"预算层级"
第 5 点"`restart_step` 直接消耗 Tier-1"的规则产生冲突而被拒绝。
