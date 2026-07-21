# Contract: 真实 VNC 起始状态门禁与动作执行审计

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md) §8b

对应 FR-036/038、SC-012/013。本契约定义人工确认 CLI 参数、首次观察的自动前置比较、
`TestRun` 数据流，以及只统计实际发送动作的报告口径。

## 1. `vnc-agent run` 参数

```text
vnc-agent run <test-case-file> [--target <vnc-target-id>] [--config <config-dir>]
              [--dry-run] [--json-only]
              [--confirm-start-state --confirmed-cart-items <int>
               --confirmed-cart-amount <int> --confirmed-screenshot <path>]
```

- 提供 `--confirm-start-state` 时，另外三个参数 MUST 同时提供，截图路径 MUST 存在；
  否则在连接 VNC 前以退出码 `2` 失败。
- CLI MUST 创建 `HumanStartStateConfirmation` 并直接写入
  `RunContext.test_run.human_start_state_confirmation`，含 ISO 8601 时间戳。
- 参数组只记录人工已经确认的状态，MUST NOT 触发清理、重置或任何 VNC 输入事件。
- 未提供参数组时字段为 `None`，普通离线运行的前置状态为 `not_required`。

## 2. `extract_cart_state` 与自动前置比较

```python
def extract_cart_state(screen: StructuredScreen) -> ObservedStartState: ...

def evaluate_start_state_precondition(
    confirmation: HumanStartStateConfirmation,
    observed: ObservedStartState,
) -> StartStatePrecondition: ...
```

- 两个函数均为确定性纯函数，MUST NOT 发起网络、模型或 VNC 操作。
- `extract_cart_state()` 复用 FR-019 的 OCR 噪声容忍规则；无法可靠提取时保留 `None`，
  MUST NOT 猜测为 `0`。
- Runtime 只允许在首次 Observe/Understand 完成后、任何 PLANNING/RESOLVING_ACTION 或
  `ExecutableAction` 生成前调用比较函数。
- 仅当观察到的件数与金额均非空且分别等于人工确认值时返回 `passed/matched`。
- 任一值缺失、不相等或证据冲突时返回 `failed`，运行 MUST 停止并生成报告；此路径
  MUST NOT 进入恢复引擎纠正现场，所有实际发送动作计数 MUST 为 0。
- `human_start_state_confirmation`、`observed_start_state`、`start_state_precondition`
  均存放于 `TestRun`，保证 `build_report_dict(run: TestRun)` 可直接读取。

## 3. Typed reporting 配置

`config.py` MUST 定义 `ReportingConfig` 并由 `AgentConfig.reporting` 引用；
`category_keywords` 必须包含按声明顺序匹配的 `add_to_bag`、`subtotal`、`payment`、
`clear_or_reset` 四组关键词。`config/agent.yaml` 必须提供默认值并通过 typed config 测试，
不得依赖 Pydantic 忽略未知 YAML 键的行为。

## 4. `build_report_dict` 运行级字段与计数

报告新增：

- `human_start_state_confirmation`
- `observed_start_state`
- `start_state_precondition`
- `executed_action_log`
- `action_category_counts`

`executed_action_log` MUST 只收录满足
`iteration.execution_result is not None and iteration.execution_result.success is True` 的迭代；
在本项目中该 `success` 仅表示输入事件已发送，不表示步骤通过。每条记录包含 step/iteration、
canonical identity、`ExecutableAction`、`ExecutionResult` 和最终分类。

`action_category_counts` MUST 仅从 `executed_action_log` 聚合。RepeatGuard/ActionPolicy 拦截、
坐标拒绝、起始状态门禁失败等未产生成功 `ExecutionResult` 的提案不得计数，但仍保留在逐轮
审计数据中。无法分类的已发送动作保留在清单并标记 `unclassified`，不得静默丢失。

HTML 报告 MUST 复用同一份 `build_report_dict()` 输出，不得重新提取或计算。
