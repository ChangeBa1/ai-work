# Contract: RecoveryPolicy Constitution 门禁

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md) §8c

**重新基线说明**：本契约定义的六字段设计本身业务无关，`checklists/domain-
independence.md` 复核未发现问题，2026-07-22 重新基线**原样保留**全部规则；
唯一改动是移除"清空购物车"这一具体业务名词（见下方"路由与预算不变量"最后一条），
改用与 spec.md FR-032 一致的通用措辞，并新增一条关于风险级别路由的跨引用。

对应 FR-031~034（编号随 spec.md 2026-07-22 重新基线调整，规则内容不变），并直接
落实 Constitution "恢复与重试门禁"。

## 配置结构

```python
class RecoveryPolicy(BaseModel):
    max_retries: int = Field(ge=1)
    cooldown_ms: int = Field(ge=0)
    consumes_global_retry_budget: bool
    allows_action_path_change: bool
    requires_strong_model: bool
    requires_human_confirmation: bool
```

六个字段对每个 `agent.yaml::recovery.*` 策略均为无默认值的必填项；遗漏任一字段时
整个配置加载失败，不得在运行期补默认值继续。

## 路由与预算不变量

- `dangerous_drift`、`ambiguous_fail_safe` 与坐标空间拒绝 MUST 进入既有 FailureType/
  RecoveryEngine 路由，不得新建绕过共享预算的重试循环。
- RecoveryEngine 执行策略前 MUST 读取全部六个字段，并同时遵守步骤预算与全局预算。
- `consumes_global_retry_budget=True` 时每次尝试必须原子地消耗一次全局额度；额度耗尽立即停止。
- `allows_action_path_change=False` 时策略不得换用默认 Tab、额外点击或其它输入路径。
- 需要强模型或人工确认但条件未满足时必须停止，不得降级成更宽松的自动恢复。
- 任何策略不得构造任何不在该测试步骤已声明动作范围内、会改变被测应用状态的操作
  （FR-032；本条 MUST NOT 依赖任何具体业务动作名词——不论被测应用是什么，"是否
  在已声明动作范围内"这一判断本身即已充分）。
- `evaluate_target_consistency()`（action-identity-contract.md §3.2）产生的
  `"ambiguous"`/`"dangerous_drift"` 结果中，凡由 `SemanticAction.risk_level`
  驱动的额外人工确认/强模型需求，MUST 通过本契约的
  `requires_human_confirmation`/`requires_strong_model` 字段路由，MUST NOT
  新增脱离本契约之外的独立风险裁决逻辑（FR-013）。

## 验证要求

固定配置测试 MUST 遍历所有恢复策略并证明六字段齐全；参数化负例必须逐个删除字段并断言
配置加载失败。运行时测试必须证明新失败结果沿既有路由、消耗声明的预算，预算耗尽后失败停止。
