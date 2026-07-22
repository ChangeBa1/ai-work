# Contract: CanonicalActionIdentity / TargetConsistency / RepeatGuard 内部接口

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md)

**重新基线说明**：本文件替换 2026-07-21 版本。旧版本第 48 行明确写"此时 MUST NOT
再比较"目标一致性——这与 spec.md 安全问题 A 的修正直接矛盾，`checklists/
domain-independence.md` CHK003/CHK010 已将其判定为最严重的两处发现。本文件不是
对旧文件的增量修改，是全文替换，旧文件不再作为权威设计。

对应 FR-001~017。本项目无对外 HTTP API，本契约定义 `domain/action_identity.py`、
`execution/action_identity.py`、`execution/target_consistency.py`、
`execution/repeat_guard.py` 之间的内部 Python 接口。

## 1. `execution.action_identity.compute_identity`（保留，无变化）

```python
def compute_identity(
    step_id: str,
    action: SemanticAction,
) -> CanonicalActionIdentity: ...
```

**契约保证**（与旧版本相同，未受安全问题 A/B 影响）：

- 纯函数，MUST NOT 访问任何全局/跨调用状态。
- `normalized_target` 的计算 MUST 优先取 `action.target.text`（经归一化）；
  `action.target` 为 `None` 或 `target.text` 为空/空白时，MUST 退化为归一化后的
  `action.intent`。
- `action_id` 字段 MUST 原样保留 `action.action_id` 的空值语义（空字符串与
  `None` 一律归一化为 `None`）。

## 2. `execution.action_identity.identity_match`（保留，无变化——但见 §3 的消费方式变更）

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

**契约保证**（本函数签名与内部判定逻辑不变；变化的是 §4 `RepeatGuard.check()`
如何消费其返回值）：

- `prev.step_id != curr.step_id` 时 MUST 优先返回 `"different_step"`。
- 仅当二者 `step_id` 相同、`action_id` 均非 `None` 且字符串相等、且 `action_type`
  相等时，MUST 返回 `"action_id_match"`。**本函数的返回值只表示"同一逻辑动作
  尝试"，MUST NOT 被解读为"新目标本身安全"——这一区分由 §4 `RepeatGuard.check()`
  的组合逻辑负责，不是本函数的职责**（安全问题 A：本函数刻意保持"只判断身份"
  这一单一职责，不承担安全判断）。
- 当 `step_id`/`action_type` 相同但 `action_id` 缺失或不相等时，MUST 检查
  `normalized_target` 是否为容忍匹配意义下的同一目标；满足时 MUST 返回
  `"normalized_target_match"`。
- 其余情况 MUST 返回 `"no_action_id_ambiguous"`，MUST NOT 在本函数内部尝试用
  角色/声明目的等其它信号兜底判断"是否相同"——那是 §3
  `evaluate_target_consistency()` 的职责。

## 3. `execution.target_consistency`：两个函数（重写，落实安全问题 A/B）

### 3.1 `has_target_evidence_conflict`（新增，落实安全问题 A）

```python
def has_target_evidence_conflict(
    previous_action: SemanticAction,
    proposed_action: SemanticAction,
    *,
    previous_resolved_region: Region | None = None,
    proposed_resolved_region: Region | None = None,
) -> bool: ...
```

**契约保证**：

- 纯函数，MUST NOT 访问任何全局/跨调用状态，MUST NOT 调用模型 API 或发起 VNC
  操作。
- MUST 检查三个独立维度，任一为真即返回 `True`：
  1. **角色冲突**：归一化后 `previous_action.target.role != proposed_action.target.role`。
  2. **交互性质冲突**：二者角色分别映射到"可交互"/"非交互"分类结果不同。
  3. **空间证据冲突**：两个已解析区域均提供时，IoU 低于配置阈值
     （`config.agent.planning.target_region_conflict_iou_threshold`，默认
     `0.10`）；任一区域缺失时本维度不参与判断（MUST NOT 因缺失证据而误判为
     冲突）。
- MUST NOT 依赖任何硬编码关键词列表——三个维度均基于结构化字段（`role`、
  分类结果、`Region` 数值）比较，不做任何文本关键词搜索。
- 本函数 MUST 在 §4 `RepeatGuard.check()` 中**无条件计算**（只要
  `previous_iteration is not None`），不因 `identity_match()` 的返回值或前一轮
  `ActionEffect` 是否为 `no_effect` 而被跳过（安全问题 A 的核心不变量：`action_id`
  相同不能作为跳过本函数的理由，`no_effect` 同样不能）。

### 3.2 `evaluate_target_consistency`（重写，落实安全问题 B）

```python
def evaluate_target_consistency(
    step_intent: str,
    previous_action: SemanticAction | None,
    proposed_action: SemanticAction,
) -> Literal["legitimate_micro_action", "dangerous_drift", "ambiguous"]: ...
```

**契约保证**：

- `previous_action is None` 时 MUST 返回 `"legitimate_micro_action"`（步骤内
  第一轮）。
- **不再有任何分支因为 `previous_action.action_type != proposed_action.action_type`
  就无条件返回 `"dangerous_drift"`**——`action_type` 差异本身 MUST 只被视为
  促使本函数运行下述 AND 判断的风险信号，MUST NOT 单独决定返回值（这是对旧
  版本第 82-87 行"无条件 `dangerous_drift`"分支的直接修正，安全问题 B）。
- `"legitimate_micro_action"` MUST 仅当以下三个条件**同时**满足才返回：
  1. `proposed_action.micro_action_purpose is not None`（Planner 声明了一个
     封闭枚举的合法微动作类别）；
  2. 步骤 intent 一致性检查判定新目标仍符合 `step_intent`；
  3. `proposed_action.risk_level` 不高于
     `config.agent.planning.micro_action_risk_thresholds[proposed_action.micro_action_purpose]`
     声明的阈值。
  三者任一不满足，MUST NOT 返回 `"legitimate_micro_action"`，即使其余两个条件
  已经满足。
- 当上述 AND 条件不满足时，MUST 按以下规则继续判断：
  - 若 `previous_action` 指向可交互控件、`proposed_action` 指向非交互结果展示
    元素 → MUST 返回 `"dangerous_drift"`。
  - 若两者均指向可交互控件，但步骤 intent 一致性检查不通过 → MUST 返回
    `"dangerous_drift"`（覆盖"控件→另一个不符合 intent 的控件"方向，MUST NOT
    只实现"控件→非交互元素"这一种方向）。
  - 以上均不满足（信号不足以分类）→ MUST 返回 `"ambiguous"`，MUST NOT 强行
    归类到任一确定分支。
- MUST NOT 调用任何模型 API 或发起 VNC 操作。
- MUST NOT 依赖任何硬编码关键词列表判断"是否为合法微动作"——该判断完全由
  `micro_action_purpose`（声明字段）+ 阈值比较（结构化数值比较）构成，不含
  任何文本关键词搜索；步骤 intent 一致性检查本身 MAY 使用规范化文本重合度量，
  但其职责仅限于"新目标是否仍符合 step_intent"，不判断"是否为合法微动作"。

## 4. `execution.repeat_guard.RepeatGuard.check`（组合逻辑重写，落实安全问题 A）

```python
class RepeatGuard:
    def check(
        self,
        step_id: str,
        step_intent: str,
        proposed_action: SemanticAction,
        previous_iteration: ActionIteration | None,
        *,
        previous_resolved_region: Region | None = None,
        proposed_resolved_region: Region | None = None,
    ) -> RepeatGuardDecision: ...
```

**契约保证（对旧版本契约的增量约束；新增 `previous_resolved_region`/
`proposed_resolved_region` 入参，供 §3.1 使用）**：

- `previous_iteration is None` MUST 总是返回 `allowed=True, reason="first_attempt"`
  （不变）。
- `classify_action_kind(proposed_action) == "idempotent"` MUST 总是返回
  `allowed=True, reason="idempotent_action"`（不变）。
- 对非幂等动作，MUST 按以下顺序决策，MUST NOT 跳过任一步骤：
  1. 调用 §2 `identity_match()`，得到 `match`。
  2. **无条件**调用 §3.1 `has_target_evidence_conflict()`，得到 `conflict`
     （不因 `match` 的取值而跳过——这是安全问题 A 修正的核心，任何试图"仅在
     `match == "no_action_id_ambiguous"` 时才检查冲突"的实现均 MUST 被视为
     违反本契约）。
  3. 若 `match ∈ {"action_id_match", "normalized_target_match"}` 且
     `conflict is False`：沿用既有的 no_effect-only 重试许可规则（`reason` 取
     `"no_effect_confirmed"`/`"blocked_effect_pending"`/`"blocked_uncertain"`，
     或对应的 `_normalized_target` 后缀变体）。
  4. 否则（`match == "no_action_id_ambiguous"`，**或** `match` 已匹配但
     `conflict is True`）：调用 §3.2 `evaluate_target_consistency()`；
     - `"dangerous_drift"` → `allowed=False, reason="dangerous_drift"`；
     - `"legitimate_micro_action"` → `allowed=True, reason="legitimate_micro_action"`；
     - `"ambiguous"` → 若上一轮 `ActionEffect` 已被可靠判定为 `no_effect` 且
       步骤共享重试预算仍有剩余，`allowed=True, reason="no_effect_confirmed"`；
       否则 `allowed=False, reason="ambiguous_fail_safe"`。
  **不变量**：第 3 步的"直接放行/拦截"分支 MUST NOT 在 `conflict is True` 时
  被采用，即使前一轮 `ActionEffect` 已被可靠判定为 `no_effect`——`no_effect`
  只影响第 4 步 `"ambiguous"` 结果的 fail-safe 分支，MUST NOT 被用于豁免第 2
  步计算出的 `conflict`（安全问题 A 的第二个不变量：`no_effect` 不能绕过目标
  漂移检查）。
- `RepeatGuardDecision.reason` 的完整合法取值集合见 data-model.md §4；MUST NOT
  再产生 `"different_action"` 这一 002 遗留取值。
- `RepeatGuard` 自身 MUST NOT 修改 `StepController` 的预算计数、MUST NOT 触发
  加强验证或视觉模型调用。

## 5. 调用顺序不变量（对 `runtime/agent_runtime.py::run_action_iteration` 的约束，不变）

```text
OBSERVING(before) → PLANNING(semantic_action, action_kind)
  → RepeatGuard.check(step_id, step_intent, semantic_action, previous_iteration,
                       previous_resolved_region=..., proposed_resolved_region=...)
      allowed=False → business_resolver.resolve_step_result(...) → RECORDING（不执行动作）
      allowed=True  → RESOLVING_ACTION(ActionPolicy.resolve(...))
                        → EXECUTING → WAITING → OBSERVING(after) → ...
```

调用位置不变——仍在 `RESOLVING_ACTION`（可能触发 Grounding/Executor 的阶段）
之前完成。

## 6. 契约总结：三条不可违反的不变量（新增，替代旧版本已被安全问题 A/B 否定的措辞）

1. **身份匹配不等于目标安全**：`identity_match()` 返回 `"action_id_match"`/
   `"normalized_target_match"` 只证明"同一逻辑动作尝试"，`RepeatGuard.check()`
   MUST 无条件额外计算 `has_target_evidence_conflict()`，冲突存在时 MUST 转入
   `evaluate_target_consistency()`（FR-003/004）。
2. **`no_effect` 不豁免漂移检查**：前一轮 `ActionEffect == no_effect` 只影响
   `"ambiguous"` 结果的 fail-safe 分支，MUST NOT 被用于跳过第 1 条的冲突检查
   （FR-004）。
3. **`action_type` 差异是信号，不是判决**：`dangerous_drift` 的最终判定 MUST
   由声明目的（`micro_action_purpose`）、风险级别（`risk_level`）与步骤 intent
   一致性三者的 AND 组合决定，`action_type` 差异本身 MUST NOT 单独触发该判定
   （FR-012/013）。
