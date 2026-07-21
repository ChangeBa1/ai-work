# Contract: ActionEffect 判定 / StepVerificationResult 分离 / Repeat Guard 内部接口

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md)

对应 FR-001~019、FR-028/029。本项目无对外 HTTP API（沿用 001 的"单一项目、CLI 驱动"
结构），本契约定义的是**模块间**的内部 Python 接口——`perception/`、`verification/`、
`execution/` 三层新增函数的输入输出结构与不变量，作为其它模块（尤其是
`runtime/agent_runtime.py`）调用它们时可依赖的契约，以及未来单元测试可以直接针对的边界。

## 1. `perception.action_effect.classify_action_effect`

```python
def classify_action_effect(
    before: StructuredScreen,
    after: StructuredScreen,
    *,
    intent: str,
    mask_regions: list[Region] | None = None,
    local_blob_min_ratio: float = 0.0005,
    error_keywords: list[str] | None = None,
) -> ActionEffect: ...
```

**契约保证**：

- 纯函数，MUST NOT 发起任何 VNC 操作、MUST NOT 调用视觉模型（确定性证据组合，见
  research.md §2）。
- 输出的 `ActionEffect.status` MUST 是 data-model.md §3 四值枚举之一，MUST NOT 出现
  枚举外的取值。
- 当 `before`/`after` 完全一致（无 OCR/模板/局部像素差异）时 MUST 返回 `no_effect`；
  MUST NOT 因为调用方传入的 `intent` 暗示"应该发生变化"就臆测出一个非 `no_effect`
  结果——判定只依据实际观测证据，不依据意图本身。
- `mask_regions` 内的局部差异 MUST 被排除在 `evidence.local_blobs` 之外（复用稳定性
  等待的动态区域屏蔽约定）。

## 2. `verification.business_resolver.resolve_step_result`

```python
async def resolve_step_result(
    spec: VerificationSpec,
    verification_mode: Literal["business", "effect_only"] | None,
    action_effect: ActionEffect,
    screen: StructuredScreen,
    *,
    planner: PlannerProvider | None,
    reobserve: Callable[[], Awaitable[StructuredScreen]],
) -> VerificationResult: ...
```

**契约保证**：

- 输出的 `VerificationResult.status` 与 `weak_assertion_warning`/`basis` 字段 MUST 严格
  遵循 data-model.md §4 的判定表；`effect_only` 模式下 MUST NOT 产生
  `weak_assertion_warning=True`（该标记专用于"未声明 effect_only 却只有弱证据"的场景）。
- 当确定性业务断言与视觉模型（`visual_question` 或加强验证阶段发起的补充问答）结论冲突
  时，MUST 采用确定性断言结论（research.md §8）；调用方 MUST NOT 在本函数之外再次用
  视觉模型结果覆盖返回值。
- 加强验证（`reobserve` 回调）MUST 至多在一次 `resolve_step_result` 调用内触发一次
  重新观察 + 一次可选的视觉模型问答，MUST NOT 在本函数内部形成循环重试（重试节奏由
  `runtime/agent_runtime.py` 的 `ActionIteration` 循环与 `StepController` 预算统一控制，
  避免出现脱离步骤预算的隐藏重试通道，呼应宪法"恢复与重试门禁"）。
- 本函数 MUST NOT 发起任何 `ExecutableAction`（不得触发键鼠操作）；它只读取观察结果，
  是 Verifier 职责的一部分（FR-028）。

## 3. `execution.repeat_guard.RepeatGuard.check`

```python
class RepeatGuard:
    def check(
        self,
        proposed_action: SemanticAction,
        previous_iteration: ActionIteration | None,
    ) -> RepeatGuardDecision: ...
```

**契约保证**：

- `previous_iteration is None`（步骤第一轮）MUST 总是返回 `allowed=True,
  reason="first_attempt"`。
- 仅当 `previous_iteration.action_effect.status != "no_effect"` 且
  `previous_iteration.verification_result.status == "uncertain"` 且
  `proposed_action.action_kind == "non_idempotent"` 且 `proposed_action` 与
  `previous_iteration.semantic_action` 语义等价（同 `action_type` + 归一化 `target`/
  `intent` 文本一致）时，MUST 返回 `allowed=False`（`blocked_effect_pending` 或
  `blocked_uncertain`，二者取决于是否已经过一轮加强验证）。
- `allowed=False` 时，`RepeatGuard` 自身 MUST NOT 触发加强验证或视觉模型调用——它只做
  "是否放行"的判断；触发加强验证是调用方（`AgentRuntime`）在收到 `allowed=False` 后的
  后续动作，职责边界保持单一（FR-028/029）。
- 本函数 MUST NOT 修改 `StepController` 的预算计数，预算消耗仍完全由
  `StepController.start_iteration()` 统一管理，避免出现两套独立的重试计数口径。

## 4. `planning.action_policy.ActionPolicy.resolve`（签名变更）

```python
def resolve(
    self,
    action: SemanticAction,
    screen: StructuredScreen,
    *,
    grounding_result: GroundingResult | None = None,
    prefer_keyboard: bool = False,
    focus_path: VerifiedFocusNavigationPath | None = None,  # 新增参数（FR-020~024）
    candidate_index: int = 0,
) -> PolicyResult: ...
```

**契约保证（对 001 既有契约的增量约束）**：

- `prefer_keyboard=True` 且 `focus_path is None` 时，MUST NOT 返回
  `outcome="focus", executable.keys=["tab"]`；MUST 回退到该动作原本会得到的结果
  （通常是继续走 OCR/模板/Grounding 分支，或在均不可用时返回 `stop_recover`）。
- `prefer_keyboard=True` 且 `focus_path` 非 `None` 时，MAY 返回
  `outcome="focus", executable.keys=focus_path.tab_sequence`；返回的
  `executable.keys` MUST 与 `focus_path.tab_sequence` 完全一致，不得另行猜测按键次数。
- 除 `focus_path` 参数带来的上述行为变化外，001 既有的候选优先级顺序（① 显式快捷键
  ② 焦点导航 ③ 唯一 OCR/模板 ④ MiMo Grounding ⑤ 停止恢复）MUST 保持不变，本 feature
  MUST NOT 重排该优先级。

## 5. 调用顺序不变量（对 `runtime/agent_runtime.py::run_action_iteration` 的约束）

每轮 `ActionIteration` 的调用顺序 MUST 满足：

```text
OBSERVING(before) → PLANNING(semantic_action, action_kind)
  → RepeatGuard.check(semantic_action, previous_iteration)
      allowed=False → business_resolver.resolve_step_result(..., reobserve=...) → RECORDING（不执行动作）
      allowed=True  → RESOLVING_ACTION(ActionPolicy.resolve(..., focus_path))
                        → EXECUTING → WAITING → OBSERVING(after)
                        → perception.classify_action_effect(before, after, intent)
                        → verification.resolve_step_result(spec, verification_mode, action_effect, after, ...)
                        → RECORDING
```

`RepeatGuard.check` MUST 在 `RESOLVING_ACTION`（即可能产生真实键鼠动作的阶段）之前完成
判断，不得在动作已经发送之后才做"要不要算作重复"的事后补救。
