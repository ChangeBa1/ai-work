# Contract: 声明式运行前置条件与动作审计

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md) §8/§8b

**重新基线说明**：本文件替换 2026-07-21 版本（原名沿用，内容全文重写）。旧版本
第 13-14 行的 `--confirmed-cart-items`/`--confirmed-cart-amount` 与第 49 行的
`add_to_bag`/`subtotal`/`payment`/`clear_or_reset` 四分类要求，已被 `checklists/
domain-independence.md` CHK001/CHK005 判定为直接违反 Constitution v1.1.0
Principle VI。本文件全文替换为业务无关的声明式前置条件与声明式动作 tag 审计
契约，旧文件不再作为权威设计。

对应 FR-024~028、FR-035~038、SC-008/009/012。本契约定义测试用例/场景 profile
如何声明运行前置条件（命名 fact + 复用既有断言机制）与动作审计 tag，人工确认
CLI 参数的通用形式，以及只统计实际发送动作的报告口径。

## 1. `TestCase.precondition`（声明式运行前置条件，复用既有断言类型）

```python
class DeclaredFact(BaseModel):
    key: str
    spec: VerificationSpec   # 复用 domain/verification.py 既有类型，不新增断言语法

class RunPrecondition(BaseModel):
    facts: list[DeclaredFact] = Field(default_factory=list)
```

- 测试用例/场景 profile 顶层 MAY 声明 `precondition: RunPrecondition`；`key`
  由声明方自由命名（如 `"queue_empty"`、`"session_logged_out"`），核心 MUST NOT
  为任何具体业务预置固定 key。
- `spec` 直接复用既有 `VerificationSpec`/`VerificationCondition`（`text_appears`/
  `template_appears`/`region_changed` 等既有断言类型），**不新增任何断言语法**。
- 未声明 `precondition` 的测试用例（含全部旧格式用例）视为无前置条件，行为与
  001/002 完全一致（FR-029 向后兼容零改动）。

## 2. 自动前置条件评估（复用既有 VerificationEngine，不新增提取函数）

```python
async def evaluate_precondition(
    precondition: RunPrecondition | None,
    first_observed_screen: StructuredScreen,
    engine: VerificationEngine,
) -> PreconditionEvaluation: ...
```

- `precondition is None` 时 MUST 直接返回
  `PreconditionEvaluation(status="not_required", fact_evaluations=[], checked_at=None)`，
  MUST NOT 阻塞运行。
- `precondition` 非 `None` 时，MUST 对每个 `DeclaredFact` 调用既有
  `VerificationEngine.verify(fact.spec, first_observed_screen)`（与步骤级业务
  断言完全相同的评估器，仅触发时机不同——运行开始前一次性触发，而非步骤执行后
  触发），得到 `FactEvaluation(key=fact.key, result=verification_result)`。
- 全部 `fact_evaluations[].result.status == "passed"` 时 `status="passed"`；
  任一 `"failed"`/`"uncertain"` 时 `status="failed"`（与既有
  `aggregate_conditions(operator="all", ...)` 的语义天然一致，不新增聚合规则）。
- Runtime MUST 只在完成首次独立 Observe/Understand 之后、任何
  `PLANNING`/`RESOLVING_ACTION` 或 `ExecutableAction` 生成之前调用本函数。
- `status="failed"` 时运行 MUST 停止并生成报告，全部实际发送动作次数 MUST 为
  `0`；MUST NOT 进入恢复引擎尝试纠正现场，MUST NOT 自动执行任何状态变更类的
  重置/清理动作来重新满足前置条件（FR-026）。
- MUST NOT 存在任何为特定业务场景单独编写的状态提取函数（如旧版本的
  `extract_cart_state()`）——"从截图判断一个命名 fact 是否成立"完全由 §1 的
  `VerificationSpec` 与既有 `VerificationEngine` 承担。

## 3. 人工确认 CLI 参数（通用 key/value，替换固定业务参数）

```text
vnc-agent run <test-case-file> [--target <target-id>] [--config <config-dir>]
              [--dry-run] [--json-only]
              [--confirm-precondition key=value ...]
              [--confirm-screenshot <path>]
```

- `--confirm-precondition key=value` MAY 重复提供，聚合为
  `list[HumanConfirmedFact]`（`key`/`confirmed_value`/`confirmed_at`/
  `screenshot_ref`）。
- CLI MUST 校验每个提供的 `key` 能在 `TestCase.precondition.facts` 中找到匹配
  的 `DeclaredFact.key`；找不到匹配时 MUST 在连接目标环境前以非零退出码失败
  （防止对测试用例未声明的字段产生虚假的"已确认"记录）。
- 提供 `--confirm-precondition` 且测试用例声明了 `precondition` 时，
  `--confirm-screenshot` SHOULD 同时提供（作为该次人工确认的证据截图引用）；
  未提供不阻塞运行，但 `HumanConfirmedFact.screenshot_ref` 记为 `None`。
- 人工确认值 MUST NOT 参与 §2 自动前置条件评估的通过/失败决策——评估结果完全
  基于 `VerificationEngine.verify()` 对声明 `spec` 的独立判定；人工确认值只是
  写入报告的**独立第二来源证据**，供人工事后交叉核对"人工确认的值"与"程序独立
  观察并判定的结果"是否一致。
- 未提供任何 `--confirm-precondition` 的运行（包括全部离线回归测试）：
  `human_confirmed_facts` 为空列表，§2 的自动评估行为不受影响（自动评估不依赖
  人工确认值是否提供）。
- 参数组本身 MUST NOT 触发任何 VNC 输入事件、清理或重置操作。

## 4. Typed reporting 配置（声明式动作 tag，替换固定四分类）

```python
class ActionMatcher(BaseModel):
    action_type: ActionType | None = None
    target_role: str | None = None
    target_text_contains: str | None = None
    intent_contains: str | None = None

class ActionTagRule(BaseModel):
    tag: str
    matcher: ActionMatcher

class ReportingConfig(BaseModel):
    action_tags: list[ActionTagRule] = Field(default_factory=list)
```

- `config.py::ReportingConfig` MUST 默认 `action_tags=[]`——**核心不含任何固定
  业务分类**，不存在类似旧版本"必须恰好包含四个特定 key"的校验器。
- 测试用例/场景 profile MAY 在顶层声明 `action_tags: list[ActionTagRule]`，与
  `AgentConfig.reporting.action_tags` 合并（测试用例声明优先，同名 `tag` 以
  测试用例为准）。
- `ActionMatcher` 的四个字段均为可选，声明的字段之间为 AND 关系；
  `target_text_contains`/`intent_contains` 的具体子串完全由声明方提供，核心
  代码本身 MUST NOT 包含任何硬编码的业务子串。
- 一个动作 MAY 同时匹配 0 个、1 个或多个 `ActionTagRule`（非互斥），不再是
  固定四选一分类。

## 5. `build_report_dict` 运行级字段与计数

报告新增：

- `precondition_evaluation`（§2 结果，含 `fact_evaluations` 逐条）
- `human_confirmed_facts`（§3 结果，MAY 为空列表）
- `executed_action_log`
- `declared_tag_counts`

`executed_action_log` MUST 只收录满足
`iteration.execution_result is not None and iteration.execution_result.success is True`
的迭代；在本项目中该 `success` 仅表示输入事件已发送，不表示步骤通过。每条记录
包含 step/iteration、canonical identity、`ExecutableAction`、`ExecutionResult`。

`declared_tag_counts` MUST 仅从 `executed_action_log` 聚合，按每条记录匹配的
全部 `ActionTagRule.tag` 分别计数（一条记录可同时增加多个 tag 的计数）。
RepeatGuard/ActionPolicy 拦截、坐标拒绝、前置条件失败等未产生成功
`ExecutionResult` 的提案不得计数，但仍保留在逐轮审计数据中。未匹配任何声明
`ActionTagRule` 的已发送动作保留在 `executed_action_log` 中，不增加任何 tag
计数（不设"未分类"兜底桶——tag 匹配本身就是开放的零到多集合）。

HTML 报告 MUST 复用同一份 `build_report_dict()` 输出，不得重新提取或计算。

## 6. 契约总结：不可违反的不变量

1. **前置条件评估与人工确认解耦**：`status` 完全由 `VerificationEngine`
   对声明 `spec` 的判定决定，人工确认值仅为交叉证据，MUST NOT 参与判定。
2. **零固定分类**：`ReportingConfig.action_tags` 默认空、无校验器强制特定
   key；核心 MUST NOT 硬编码任何业务子串或分类名称。
3. **只统计已发送动作**：`declared_tag_counts`/`executed_action_log` MUST 仅
   从 `execution_result.success is True` 的迭代聚合，被拦截提案计数为 0 但仍
   保留在逐轮审计中。
4. **前置条件失败零输入**：`status="failed"` 时 MUST NOT 发送任何业务或恢复
   动作，MUST NOT 自动重置/清理环境。
