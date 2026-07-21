# Contract: CanonicalActionIdentity / RepeatGuard / TargetConsistency 内部接口

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md)

对应 FR-001~011、FR-028/029。本项目无对外 HTTP API，本契约定义
`domain/action_identity.py`、`execution/action_identity.py`、
`execution/target_consistency.py`、`execution/repeat_guard.py` 之间的内部 Python
接口，作为 `runtime/agent_runtime.py` 调用它们时可依赖的契约，以及单元测试可以直接
针对的边界。

## 1. `execution.action_identity.compute_identity`

```python
def compute_identity(
    step_id: str,
    action: SemanticAction,
) -> CanonicalActionIdentity: ...
```

**契约保证**：

- 纯函数，MUST NOT 访问任何全局/跨调用状态。
- `normalized_target` 的计算 MUST 优先取 `action.target.text`（经归一化：去除首尾
  空白、统一大小写、容忍中间空白差异）；`action.target` 为 `None` 或 `target.text`
  为空/空白时，MUST 退化为归一化后的 `action.intent`。
- 输出结构 MUST 与 data-model.md §1 完全一致，`action_id` 字段 MUST 原样保留
  `action.action_id` 的空值语义（空字符串与 `None` 一律归一化为 `None`）。

## 2. `execution.action_identity.identity_match`

```python
def identity_match(
    prev: CanonicalActionIdentity,
    curr: CanonicalActionIdentity,
) -> Literal[
    "different_step",
    "action_id_match",
    "normalized_target_match",
    "no_action_id_ambiguous",
]: ...
```

**契约保证**：

- `prev.step_id != curr.step_id` 时 MUST 优先返回 `"different_step"`，不再检查
  `action_id`（FR-001 的判断优先级最高）。
- 仅当二者 `step_id` 相同、`action_id` 均非 `None` 且字符串相等、**且
  `action_type` 相等**时，MUST 返回 `"action_id_match"`；此时 MUST NOT 再比较
  `normalized_target`/`intent`（FR-002，`action_id` 相同即决定性证据，覆盖自由
  文本改写）。**`action_type` 相等是本分支的必要前提**（FR-007）——`action_id`
  相同但 `action_type` 不同（例如前一轮是 `click`、本轮变成 `type_text`）MUST NOT
  返回 `"action_id_match"`，因为二者不可能是"同一个逻辑点击动作的措辞改写"，这种
  组合本身就是异常信号，MUST 下沉为 `"no_action_id_ambiguous"`，交给 §3
  `evaluate_target_consistency()` 处理（该函数 MUST 将 `action_type` 不同的情形
  直接判定为 `"dangerous_drift"`，见 §3）。
- 当 `step_id` 相同、`action_type` 相同，但 `action_id` 缺失或不相等时，MUST 检查
  `prev.normalized_target` 与 `curr.normalized_target` 是否为 OCR 噪声容忍意义下的
  同一目标（归一化后互为子串关系，或字符编辑距离 ≤ 1）；满足时 MUST 返回
  `"normalized_target_match"`（FR-005 的具体落地——`action_id` 缺席时，规范化目标
  的 OCR 容忍匹配作为**弱于 `action_id_match`、但仍视为强证据**的第二判定层级，
  与 `"action_id_match"` 一样交由 §4 RepeatGuard 的 no_effect-only 重试许可规则
  处理，但 `reason` 必须可区分记录以便审计，见 §4）。
- 其余情况（`action_type` 不同，或 `action_id`/`normalized_target` 均无法判定为
  同一目标）MUST 返回 `"no_action_id_ambiguous"`，MUST NOT 在本函数内部尝试用
  角色/关键词等其它信号兜底判断"是否相同"——那是 `evaluate_target_consistency()`
  （§3）的职责，本函数只负责"能否凭 `action_id`/`normalized_target` 直接确定"。

## 3. `execution.target_consistency.evaluate_target_consistency`

```python
def evaluate_target_consistency(
    step_intent: str,
    previous_action: SemanticAction | None,
    proposed_action: SemanticAction,
) -> Literal["legitimate_micro_action", "dangerous_drift", "ambiguous"]: ...
```

**契约保证**：

- `previous_action is None` 时 MUST 返回 `"legitimate_micro_action"`（步骤内第一轮，
  FR-003）。
- **`previous_action.action_type != proposed_action.action_type` 时 MUST 无条件
  返回 `"dangerous_drift"`，优先于以下所有角色/关键词判断**（FR-007）——一个
  `click` 不可能"合法漂移"成 `type_text` 之类的另一种动作类型，`action_type` 不同
  本身就是决定性的危险信号，不需要、也 MUST NOT 再用角色/关键词信号去尝试判断这是否
  "合法"。这条规则同时是 §2 `identity_match()` 把 `action_id` 相同但 `action_type`
  不同的组合下沉到本函数处理时的接收方保证。
- MUST NOT 调用任何模型 API 或发起 VNC 操作（确定性关键词/角色信号判断，
  research.md §4）。
- MUST 覆盖 FR-008 的两种漂移方向：可交互控件→非交互结果展示元素；可交互控件→
  另一个不符合 `step_intent` 的可交互控件。两种情形均 MUST 返回 `"dangerous_drift"`，
  MUST NOT 只实现其中一种方向。
- 当现有信号（`target.role`/`target.text`/关键词列表）不足以在
  `"legitimate_micro_action"` 与 `"dangerous_drift"` 之间判断时，MUST 返回
  `"ambiguous"`，MUST NOT 强行归类到任一确定分支。

## 4. `execution.repeat_guard.RepeatGuard.check`（签名与行为变更）

```python
class RepeatGuard:
    def check(
        self,
        step_id: str,
        step_intent: str,
        proposed_action: SemanticAction,
        previous_iteration: ActionIteration | None,
    ) -> RepeatGuardDecision: ...
```

**契约保证（对 002 既有契约的增量约束，`step_id`/`step_intent` 为新增入参）**：

- `previous_iteration is None` MUST 总是返回 `allowed=True, reason="first_attempt"`
  （不变）。
- `classify_action_kind(proposed_action) == "idempotent"` MUST 总是返回
  `allowed=True, reason="idempotent_action"`（不变）。
- 对非幂等动作，MUST 按以下顺序决策，且 MUST NOT 跳过任一步骤：
  1. 调用 §2 `identity_match()`；`"action_id_match"` 时，沿用 002 既有的
     no_effect-only 重试许可规则（`reason` 取 `"no_effect_confirmed"` 或
     `"blocked_effect_pending"`/`"blocked_uncertain"`）。
  2. `"normalized_target_match"` 时，同样沿用 002 既有的 no_effect-only 重试许可
     规则，但 `reason` MUST 取对应的 `_normalized_target` 后缀变体
     （`"no_effect_confirmed_normalized_target"` /
     `"blocked_effect_pending_normalized_target"` /
     `"blocked_uncertain_normalized_target"`），以便报告审计能区分"凭 `action_id`
     决定性证据放行/拦截"与"凭 OCR 容忍的规范化目标匹配放行/拦截"这两种证据强度
     不同的判定依据（FR-005/FR-025）。
  3. `"no_action_id_ambiguous"` 时，调用 §3 `evaluate_target_consistency()`；
     `"dangerous_drift"` → `allowed=False, reason="dangerous_drift"`；
     `"legitimate_micro_action"` → `allowed=True, reason="legitimate_micro_action"`；
     `"ambiguous"` → 按 FR-004 fail-safe 处理：若上一轮 `ActionEffect` 已被可靠
     判定为 `no_effect` 且步骤预算仍有剩余，`allowed=True,
     reason="no_effect_confirmed"`；否则 `allowed=False,
     reason="ambiguous_fail_safe"`。
- `RepeatGuardDecision.reason` 的完整合法取值集合见 data-model.md §3（新增
  `"normalized_target_match"` 变体前缀家族与 `"dangerous_drift"`、
  `"legitimate_micro_action"`、`"ambiguous_fail_safe"`）；MUST NOT 再产生
  `"different_action"` 这一 002 遗留
  取值（data-model.md §3）。
- `RepeatGuard` 自身 MUST NOT 修改 `StepController` 的预算计数、MUST NOT 触发加强
  验证或视觉模型调用（002 既有约束不变）。

## 5. 调用顺序不变量（对 `runtime/agent_runtime.py::run_action_iteration` 的约束）

延续 002 `action-effect-contract.md §5` 的调用顺序，`RepeatGuard.check()` 的入参
新增 `step_id`/`step_intent`（来自当前 `TestStep`），调用位置不变——仍在
`RESOLVING_ACTION`（可能触发 Grounding/Executor 的阶段）之前完成：

```text
OBSERVING(before) → PLANNING(semantic_action, action_kind)
  → RepeatGuard.check(step_id, step_intent, semantic_action, previous_iteration)
      allowed=False → business_resolver.resolve_step_result(...) → RECORDING（不执行动作）
      allowed=True  → RESOLVING_ACTION(ActionPolicy.resolve(...))
                        → EXECUTING → WAITING → OBSERVING(after) → ...
```
