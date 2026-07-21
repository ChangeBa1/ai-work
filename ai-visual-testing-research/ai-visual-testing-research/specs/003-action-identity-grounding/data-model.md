# Phase 1 Data Model: 稳定动作身份与坐标空间定位纠正

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

本文件把 spec.md 的 Key Entities 落成具体字段定义。本 feature 建立在 001/002
`data-model.md` 已交付的实体之上——下列各节只描述**新增**实体，以及对既有实体的
**增量修改**，不重复未变更的部分（`ActionEffect`、`StepVerificationResult` 的判定表、
`TestStep.verification_mode` 字段本身等均沿用 002，不在本文件重复）。

## 1. CanonicalActionIdentity（新增）— 对应 FR-001~007

新增 `domain/action_identity.py`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `step_id` | str | 所属测试步骤 ID；不同 `step_id` 之间的身份永远不匹配（FR-001） |
| `action_type` | `ActionType`（复用 `domain/action.py`） | 语义动作类型 |
| `action_id` | `str \| None` | 语义动作携带的 `action_id`；缺失/空字符串时为 `None` |
| `normalized_target` | str | 规范化核心业务目标：优先取 `target.text` 归一化结果（容忍
  OCR 噪声，FR-005），`target` 为空或 `text` 为空时退化为 `normalized(intent)` |

**身份匹配结果（`IdentityMatch`，`execution/action_identity.py::identity_match()` 的
返回类型）**：

| 取值 | 触发条件 |
|---|---|
| `"different_step"` | `prev.step_id != curr.step_id`（FR-001，优先级最高） |
| `"action_id_match"` | 二者 `step_id` 相同，`action_id` 均非 `None` 且相等，**且
  `action_type` 相等**（FR-002/FR-007，决定性证据，不再比较 `normalized_target`）。
  `action_id` 相等但 `action_type` 不同时 MUST NOT 命中本分支——一个
  `click`/`type_text` 之类的类型差异本身就是异常信号，下沉为
  `"no_action_id_ambiguous"`，由 §2 `evaluate_target_consistency()` 判定为
  `"dangerous_drift"`（见下方 TargetConsistencyResult 表新增行，FR-007 的具体
  落地——防止 `identity_match()` 把 `action_type` 不同的两个动作过度宽松合并） |
| `"normalized_target_match"` | `step_id`/`action_type` 相同，但 `action_id`
  缺失或不相等，且 `normalized_target` 经 OCR 容忍比较（互为子串或编辑距离 ≤ 1）
  判定为同一目标（FR-005 的具体落地；证据强度弱于 `action_id_match`，RepeatGuard
  层面用带 `_normalized_target` 后缀的 `reason` 变体区分审计记录，见 §3） |
| `"no_action_id_ambiguous"` | `action_type` 不同，或 `action_id`/`normalized_target`
  均无法判定为同一目标（FR-003 的触发条件，交由 §2 的一致性检查处理） |

## 2. TargetConsistencyResult（新增）— 对应 FR-003/FR-008

新增 `execution/target_consistency.py::evaluate_target_consistency()` 返回类型
`ConsistencyOutcome`：

| 取值 | 说明 |
|---|---|
| `"legitimate_micro_action"` | 新目标具有独立于此前动作的交互目的，且符合步骤 intent
  （FR-003 正例分支，含步骤内第一轮） |
| `"dangerous_drift"` | 不满足步骤 intent 一致性验证，归类为危险动作漂移（FR-008，
  覆盖"可交互控件→非交互结果展示元素"与"可交互控件→另一个不符合 intent 的可交互
  控件"两种方向；**以及 `previous_action.action_type != proposed_action.action_type`
  的情形，此时 MUST 无条件直接判定为 `"dangerous_drift"`，优先于其余角色/关键词
  信号判断**，FR-007） |
| `"ambiguous"` | 现有信号不足以判断属于上述哪一类（触发 FR-004 fail-safe） |

`evaluate_target_consistency(step_intent: str, previous_action: SemanticAction | None,
proposed_action: SemanticAction) -> ConsistencyOutcome`：纯函数，判定规则见
research.md §4；依赖的关键词信号列表（结果展示元素关键词、独立交互目的/微动作关键词）
作为新增配置项 `config/agent.yaml::planning.result_display_keywords`、
`planning.dismissal_keywords`，不固化在代码中。

## 3. RepeatGuardDecision（增量修改）— 对应 FR-001~007

001/002 `domain/repeat_guard.py::RepeatGuardDecision` 保留既有字段
（`allowed`、`previous_action_effect_status`），`reason` 枚举取值调整：

| 变更 | 说明 |
|---|---|
| 移除 | `"different_action"`（002 遗留取值，003 不再产生——003 的整个动机就是"文本不同
  不能再单独作为放行理由"，保留该取值会让审计报告产生误导性归因） |
| 保留 | `"first_attempt"`、`"idempotent_action"`、`"no_effect_confirmed"`、
  `"blocked_effect_pending"`、`"blocked_uncertain"`（002 既有，含义不变；这五个值
  专用于 §1 `"action_id_match"` 分支——`action_id` 决定性证据） |
| **新增** | `"no_effect_confirmed_normalized_target"`、
  `"blocked_effect_pending_normalized_target"`、
  `"blocked_uncertain_normalized_target"`（§1 `"normalized_target_match"` 分支的
  对应变体——语义与不带后缀的三个值完全相同，仅证据来源不同：不是凭 `action_id`
  决定性证据，而是凭 OCR 容忍的规范化目标匹配，FR-005/FR-025 要求报告能区分这两种
  证据强度） |
| **新增** | `"dangerous_drift"`（对应 §2 `"dangerous_drift"` → `allowed=False`，
  含 `action_type` 不同这一新增触发条件） |
| **新增** | `"legitimate_micro_action"`（对应 §2 `"legitimate_micro_action"` →
  `allowed=True`） |
| **新增** | `"ambiguous_fail_safe"`（对应 §2 `"ambiguous"` 或 §1
  `"no_action_id_ambiguous"` 且一致性检查本身也无法判断时，统一走 FR-004 fail-safe →
  `allowed=False`，除非上一轮已被可靠判定为 `no_effect` 且预算剩余，此时复用 002
  既有的 `"no_effect_confirmed"` 放行分支） |

`ActionIteration`（`domain/run.py`）新增字段：

| 新增字段 | 类型 | 说明 |
|---|---|---|
| `canonical_identity` | `CanonicalActionIdentity \| None` | 本轮计算得到的稳定动作
  身份，供报告审计（FR-025） |

## 4. GroundingCandidate（增量修改）— 对应 FR-012~017

001/002 `domain/grounding.py::GroundingCandidate` 保留既有字段
（`bbox`、`confidence`、`label`、`reason`），新增两个字段：

| 新增字段 | 类型 | 说明 |
|---|---|---|
| `coordinate_space` | `Literal["pixel", "normalized_1000"] \| None` | 候选声明的坐标
  空间；`None` 表示历史响应未声明（FR-012/015）。**注意**：该字段记录的是"声明值"，
  用于审计；`bbox` 字段本身在 `GroundingCandidate` 离开 `models/mimo_grounder.py`
  时已经**永远是换算后的原始像素坐标**（research.md §6），下游模块（`ActionPolicy`/
  `Executor`）不需要、也不应该再次判断坐标空间。 |
| `raw_bbox` | `tuple[int,int,int,int] \| None` | 换算前的原始候选坐标（未经
  `resolve_pixel_bbox()` 处理），仅用于报告审计（FR-026/036）；候选在换算阶段即被
  拒绝时，该候选**不会**出现在最终 `GroundingResult.candidates` 中（见 §5），
  `raw_bbox` 因此只对**成功换算**的候选有意义。 |

`bbox` 字段的合法性不变量（延续 001，明确 FR-013 的闭区间边界）：换算后的
`bbox` 四角与 `GroundingCandidate.center()` 计算出的中心点，MUST 全部落在
`GroundingResult` 所属截图的实际分辨率范围内（`[0, width) × [0, height)`，像素坐标
本身不存在"闭区间"歧义——闭区间约束只作用于换算**前**的 `normalized_1000` 数值
范围 `[0, 1000]`，详见 §5）。

## 5. `resolve_pixel_bbox()`（新增纯函数）— 对应 FR-013~017

新增 `models/coordinate_space.py`：

```python
def resolve_pixel_bbox(
    raw_bbox: tuple[int, int, int, int],
    declared_space: Literal["pixel", "normalized_1000"] | None,
    resolution: tuple[int, int],
    *,
    siblings: Sequence[GroundingCandidate] = (),
) -> tuple[int, int, int, int] | None: ...
```

| 场景 | 输出 |
|---|---|
| `declared_space == "pixel"` | 校验 `raw_bbox` 四角落在 `resolution` 范围内；越界
  返回 `None`，否则原样返回 |
| `declared_space == "normalized_1000"` | 校验 `raw_bbox` 四个坐标分量均落在闭区间
  `[0, 1000]`（0 与 1000 本身合法）；越界返回 `None`；否则 X 轴按 `resolution[0]/1000`、
  Y 轴按 `resolution[1]/1000` 独立换算，换算结果四舍五入取整后返回 |
| `declared_space is None`（历史响应） | 分别按 `"pixel"`、`"normalized_1000"` 两种
  解释试算；仅当**恰好一种**解释同时满足"换算/校验后落在分辨率范围内"与"和
  `siblings` 中已声明坐标空间的候选不矛盾"时，返回该解释的换算结果；两种都满足、
  都不满足、或 `siblings` 本身证据冲突时，返回 `None`（拒绝，research.md §7） |

**调用点不变量**：本函数在整个代码库中 MUST 只有一个调用点——
`models/mimo_grounder.py::MimoGrounderClient.ground()` 内、紧跟 `_apply_crop_and_cap()`
之后；`models/mimo_grounder.py::StubGrounder`（离线测试用双）复用同一个函数产出
`bbox`，不重新实现换算逻辑。凡是 `resolve_pixel_bbox()` 返回 `None` 的候选，直接从
最终 `GroundingResult.candidates` 中剔除，不进入 `ActionPolicy`。

## 6. Executor 前置合理性核对（无独立数据类型）— 对应 FR-013 精神延伸

不引入新的 Pydantic 类型；`planning/action_policy.py::ActionPolicy._from_grounding()`
在候选已通过 §5 换算后，新增一个可选的 OCR 交叉核对：当 `SemanticAction.target.text`
非空且 `StructuredScreen.ocr_items` 中存在与之唯一匹配的锚点时，候选中心点与该 OCR
锚点中心的像素距离超过阈值（`config/agent.yaml::planning.ocr_sanity_check_ratio`，
默认取截图较短边的 10%）即视为该候选与已有 OCR 证据矛盾，MUST 被拒绝并转入既有失败
分类与恢复流程；缺乏可比对的 OCR 锚点时不触发本项核对（不产生新的误杀，
research.md §8）。

## 7. TestStep.verification_mode（无变化，仅使用方式变化）

001/002 已定义的 `TestStep.verification_mode: Literal["business","effect_only"] |
None` 字段与 `load_test_case()` 的三支加载规则**均不改变**。本 feature 只是把
`pos-buy-bag-checkout.yaml` 这一份具体用例的 `verification_mode` 从省略改为显式
`business`，并把其 `expected.conditions` 从仅含 `screen_changed` 扩展为包含至少
一个业务结果断言（具体断言文本设计见 research.md §9）；`load_test_case()` 因此会
对该文件按"显式 business 模式"校验通过（因为已经补上了业务断言），不涉及加载器
代码本身的修改。

## 8. 报告字段扩展（无独立数据类型，复用 §1/§4/§5 已定义结构）

`reporting/json_report.py::build_report_dict()` 每轮 `IterationReport` 新增两个键
（不引入新的 Pydantic 模型，直接从 §1/§5 的字段序列化）：

| 新增键 | 内容 |
|---|---|
| `canonical_action_identity` | `it.canonical_identity.model_dump()`（§1，`None` 时
  为 `null`） |
| `coordinate_space_audit` | 列表，元素为
  `{"coordinate_space": ..., "raw_bbox": ..., "resolved_bbox": ..., "accepted": bool}`，
  覆盖本轮 Grounding 请求中**全部**被评估过的候选（含被拒绝、未进入最终
  `grounding_candidates` 列表的候选，二者共同满足 FR-036"完整动作执行清单"对
  Grounding 决策过程的可审计要求） |

`reporting/html_report.py` 复用 `build_report_dict()` 的同一份数据，新增一个折叠区块
展示上述两个字段，不重复提取逻辑（延续 002 "JSON 报告是 HTML 报告的唯一数据来源"的
既有约束）。

## 8b. 真实 VNC 起始状态门禁与动作执行审计 — 对应 FR-036/038、SC-012/013

为保证 CLI → Runtime → Report 的数据链路闭合，新增三个 Pydantic 值对象并直接挂到
`TestRun`，`build_report_dict(run: TestRun)` 无需读取 `RunContext` 临时属性或额外首帧参数：

| 类型/字段 | 结构 | 约束 |
|---|---|---|
| `HumanStartStateConfirmation` | `confirmed_cart_items: int`、`confirmed_cart_amount: int`、`screenshot_ref: str`、`confirmed_at: datetime` | 仅在完整提供 CLI 参数组且截图文件存在时创建 |
| `ObservedStartState` | `cart_items: int \| None`、`cart_amount: int \| None`、`evidence_refs: list[str]` | 由首次独立观察的 `StructuredScreen` 确定性提取，不得猜测缺失值 |
| `StartStatePrecondition` | `status: Literal["not_required","passed","failed"]`、`reason: Literal["matched","missing_confirmation","unreadable_observation","state_mismatch","conflicting_evidence"] \| None`、`checked_at: datetime \| None` | 提供人工确认时，只有两项观察值非空且与确认值完全相等才可 `passed`；其余均 `failed` |

`TestRun` 新增：

| 字段 | 类型 | 来源/用途 |
|---|---|---|
| `human_start_state_confirmation` | `HumanStartStateConfirmation \| None` | CLI 在连接前写入 `RunContext.test_run` |
| `observed_start_state` | `ObservedStartState \| None` | Runtime 首次 Observe/Understand 后写入 |
| `start_state_precondition` | `StartStatePrecondition` | Runtime 在任何 `ExecutableAction` 生成前完成自动比较 |

前置条件为 `failed` 时，运行直接进入失败记录/报告生成，全部 `ActionIteration.execution_result`
保持 `None`，不得调用恢复动作尝试纠正环境。未提供人工确认的普通离线运行使用
`status="not_required"`，不改变 001/002 的执行语义。

报告运行级输出新增：

| 新增键 | 内容 | 计数规则 |
|---|---|---|
| `human_start_state_confirmation` | 直接序列化同名 `TestRun` 字段 | 缺失时为 `null` |
| `observed_start_state` | 直接序列化同名 `TestRun` 字段 | 保留 `None` 与证据引用 |
| `start_state_precondition` | 直接序列化同名 `TestRun` 字段 | 失败原因必须可审计 |
| `executed_action_log` | 每个实际发送动作的 step/iteration、canonical identity、executable action、execution result 与分类 | 仅收录 `execution_result.success is True` 的迭代 |
| `action_category_counts` | `add_to_bag`/`subtotal`/`payment`/`clear_or_reset` 四类整数 | 仅从 `executed_action_log` 聚合；被拦截提案不得计数 |

新增 `ReportingConfig` 并挂入 `AgentConfig.reporting`，其 `category_keywords` 为上述四类的
必填 `dict[str, list[str]]`；`config/agent.yaml` 提供明确默认列表。分类输入优先使用已发送
迭代的 `canonical_identity.normalized_target`，并以 `ExecutableAction` 的方法/按键/目标
摘要作为补充；无法分类的已发送动作保留在 `executed_action_log`，但不增加四类计数。

## 8c. RecoveryPolicy 显式门禁 — 对应 FR-031/037

既有 `RecoveryPolicy` 从两字段扩展为六个全部必填的字段：

| 字段 | 类型 | 含义 |
|---|---|---|
| `max_retries` | `int >= 1` | 最大策略执行次数 |
| `cooldown_ms` | `int >= 0` | 重试冷却时间 |
| `consumes_global_retry_budget` | `bool` | 是否消耗全局额度 |
| `allows_action_path_change` | `bool` | 是否允许改变动作路径 |
| `requires_strong_model` | `bool` | 是否需要强模型 |
| `requires_human_confirmation` | `bool` | 是否需要人工确认 |

全部六个字段均不得提供模型默认值；`agent.yaml` 每个恢复策略必须显式填写。任一策略
缺字段时整个配置加载失败，确保 Constitution 的恢复与重试门禁可由配置测试直接证明。

## 9. 状态转移与数据流小结

```text
真实 VNC 验收运行前置门禁：
  CLI HumanStartStateConfirmation → TestRun
    → 首次 Observe/Understand → ObservedStartState → TestRun
    → compare_start_state_precondition()
        ├─ passed → 允许进入第一个 PLANNING
        └─ failed → 运行失败并生成报告（零 ExecutableAction / 零已发送动作）

ActionIteration（单轮）：
  before_frame → SemanticAction(action_id, target)
    → CanonicalActionIdentity(step_id, action_type, action_id, normalized_target)
    → IdentityMatch
        ├─ different_step          → （结构上不会发生，见 research.md §3）
        ├─ action_id_match         → 复用 002 no_effect-only 重试许可规则（FR-002/006/007）
        ├─ normalized_target_match → 同一规则，reason 加 _normalized_target 后缀（FR-005）
        └─ no_action_id_ambiguous  → evaluate_target_consistency()
              ├─ dangerous_drift          → RepeatGuardDecision(allowed=False)
              │     （含 action_type 不同的情形，FR-007）
              ├─ legitimate_micro_action  → RepeatGuardDecision(allowed=True)
              └─ ambiguous                → fail-safe（等同 FR-004，除非可靠 no_effect+预算剩余）
    → （若 allowed=True 且需要 Grounding）Grounder.ground()
        → 逐候选 resolve_pixel_bbox()（唯一换算点）→ 淘汰不合规候选
        → ActionPolicy（OCR 交叉核对）→ ExecutableAction
    → Executor → ActionEffect → business_resolver（002 既有，不变）
    → RECORDING（写入 canonical_identity、coordinate_space_audit 供报告审计）

运行报告聚合：
  仅 execution_result.success is True 的迭代 → executed_action_log
    → ReportingConfig.category_keywords → action_category_counts
  被 RepeatGuard/ActionPolicy 拦截的提案 → 保留逐轮审计，但执行计数不增加
```

`CanonicalActionIdentity`、`RepeatGuardDecision`、`GroundingCandidate.coordinate_space`/
`raw_bbox` 均随既有 `ActionIteration` 一并记录，不新增独立的持久化表结构（延续 002
"轻量记录追加到迭代日志字段"的既有模式）。
