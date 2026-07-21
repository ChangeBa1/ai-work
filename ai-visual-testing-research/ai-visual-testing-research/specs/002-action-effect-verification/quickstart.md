# Quickstart: 验证自适应动作效果检测与可信业务验证

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Data Model**: [data-model.md](./data-model.md)

本指南给出无需连接真实 VNC 环境即可验证本 feature 是否达成 spec.md 验收场景的运行步骤
（对应 FR-030、SC-009：常规自动化测试不得操作真实 VNC）。所有命令均在 `vnc_agent/`
目录下执行。

## 前置条件

```bash
cd vnc_agent
python -m venv .venv && source .venv/bin/activate   # 或已有的项目虚拟环境
pip install -e ".[dev]"
```

无需任何 VNC 服务、无需模型 API Key——本 feature 的全部验收测试基于固定/程序化构造的
截图与录制数据离线运行（FR-030、research.md §9）。

## 场景 1：整屏变化约 0.424%、局部购物车区域已变化 → expected_effect（SC-001）

```bash
pytest tests/fixtures/test_action_effect.py -k "low_global_ratio_local_change" -v
```

**预期**：断言 `classify_action_effect(...).status == "expected_effect"`；同一测试内
额外断言全屏 `diff_ratio` 确实 `< 0.02`（复现事故条件），证明判定不是靠"提高全屏阈值"
这种取巧方式通过。

## 场景 1b：局部变化落在动态噪声屏蔽区域内 → no_effect（FR-005）

```bash
pytest tests/fixtures/test_action_effect.py -k "noise_region_excluded" -v
```

**预期**：局部像素变化完全落在已配置的动态噪声屏蔽区域（如任务栏时钟）内时，判定为
`no_effect` 而非 `expected_effect`，证明新的局部证据路径同样排除已知动态噪声干扰，
而不仅仅是复用旧的整屏阈值屏蔽逻辑。

## 场景 2：购物袋从 0 变为 1 后不得重复点击（SC-002，本次事故的直接回归测试）

```bash
pytest tests/e2e/test_scenario_10_no_duplicate_action.py -v
```

**预期**：使用 mock `PlannerProvider`（对同一未完成意图连续两次提议语义等价的
"点击レジ袋"动作）与固定截图序列驱动 `AgentRuntime`；断言 `ExecutionRouter.execute()`
在整条测试运行中，对该语义动作只被调用一次（第二次被 `RepeatGuard` 拦截，转入加强
验证分支），而不是两次。

## 场景 3：效果已知但业务结果未定 → effect_uncertain，先加强验证再判定（SC-003）

```bash
pytest tests/fixtures/test_repeat_guard.py -k "effect_uncertain_escalates" -v
```

**预期**：断言在给出最终 `effect_uncertain`/`uncertain` 之前，`business_resolver` 的
`reobserve` 回调与（mock）`describe_screen` 均被调用过至少一次；断言执行动作
（`ExecutionRouter.execute`）在该测试用例内只被调用一次（未被重复触发）。

## 场景 3b：加强验证收敛为 no_effect 后允许重试（FR-016 的放行分支）

```bash
pytest tests/fixtures/test_repeat_guard.py -k "no_effect_confirmed" -v
```

**预期**：与场景 3 相反的分支——当上一轮 `ActionEffect` 经加强验证后被可靠收敛为
`no_effect`、且步骤重试预算仍有剩余时，`RepeatGuard.check()` 返回
`allowed=True, reason="no_effect_confirmed"`；`effect_uncertain` 本身不得触发该放行。

## 场景 3c：确定性业务断言优先于视觉模型冲突结论（FR-010/SC-010）

```bash
pytest tests/fixtures/test_business_resolver.py -k "deterministic_overrides_visual" -v
```

**预期**：构造一个同时包含确定性断言（如 `text_appears`）与 `visual_question` 的步骤，
分别验证确定性断言给出 `failed`/视觉模型给出 `passed`、以及确定性断言给出 `passed`/
视觉模型给出 `failed` 两种冲突场景下，最终 `StepVerificationResult.status` 始终采用
确定性断言的结论，不被视觉模型的相反结论推翻。

## 场景 4：错误弹窗不得因画面变化而通过（SC-004，本次事故的另一半根因回归测试）

```bash
pytest tests/fixtures/test_error_popup_classification.py -v
pytest tests/e2e/test_scenario_11_error_popup_not_passed.py -v
```

**预期**：构造一对"点击后出现错误弹窗"的截图（全屏变化远超 2%），断言
`classify_action_effect(...).status == "unexpected_effect"`；端到端场景断言该步骤最终
`StepVerificationResult.status` 为 `failed` 或 `uncertain`，MUST NOT 为 `passed`。

## 场景 4b：业务断言本身就是"应出现错误提示"时仍正常判定（FR-021）

```bash
pytest tests/fixtures/test_business_resolver.py -k "expected_error_assertion_still_evaluated" -v
```

**预期**：步骤的业务断言为 `text_appears: "<错误提示文字>"`（即错误提示本身是预期业务
结果）；即便该步骤的 `ActionEffect` 被判定为 `unexpected_effect`，`resolve_step_result()`
仍按该断言的定义正常判定，错误文字确实出现时可以返回 `passed`——证明 FR-020 的默认拒绝
规则不会无差别拒绝这类预期内的场景。

## 场景 5：局部变化出现在画面任意九宫格区域（SC-005）

```bash
pytest tests/fixtures/test_action_effect.py -k "nine_grid_positions" -v
```

**预期**：对 1024×1568 画布九个不同象限分别注入局部变化（均未配置为任何 ROI），
9/9 均判定为 `expected_effect`。

## 场景 6：列表更新 / 表单更新 / 弹窗出现 / 页面跳转四类场景（SC-006）

```bash
pytest tests/fixtures/test_action_effect.py -k "list_update or form_update or dialog_appear or page_navigation" -v
```

## 场景 7：旧用例仅含 screen_changed → 弱断言警告 + uncertain（SC-007，含 pos-buy-bag-checkout.yaml 本身）

```bash
pytest tests/fixtures/test_testcase_loader.py -k "legacy_effect_only_warning" -v
pytest tests/e2e/test_scenario_12_legacy_weak_assertion.py -v
```

**预期**：`testcases/pos-buy-bag-checkout.yaml`（未修改，仍只含 `screen_changed`）可以
被 `load_test_case()` 正常加载（不抛 `FieldValidationError`）；驱动一次离线端到端运行后，
其步骤最终 `StepVerificationResult.status == "uncertain"` 且 `weak_assertion_warning
is True`，MUST NOT 为 `passed`。

## 场景 7b：报告中三种通过/警告状态可区分（FR-027）

```bash
pytest tests/fixtures/test_report_builder.py -k "trusted_pass or effect_only_pass or weak_assertion_warning" -v
```

**预期**：分别构造业务断言支撑的 `passed`、`effect_only` 支撑的 `passed`、以及仅弱证据
支撑的 `uncertain`（弱断言警告）三类步骤，断言 `json_report`/`html_report` 的输出对三者
分别给出可区分的标注；弱断言警告不得被静默省略，也不得与真正经业务断言验证的通过在报告
中呈现为同等可信。

## 场景 8：本次事故的完整离线回归（FR-031，串联场景 1/2/4）

```bash
pytest tests/e2e/test_scenario_13_pos_bag_regression.py -v
```

**预期**：单个端到端测试内串联复现"点击 → 0.424% 全屏/局部购物车变化 →
expected_effect → 不重复点击 → （模拟后续错误弹窗分支）unexpected_effect → 不因画面
变化通过"完整链路，作为本 feature 的核心交付验收标准。

## 场景 9：确认无真实 VNC 依赖（SC-009）

```bash
grep -rL "MockVNCDriver\|fixture" tests/fixtures tests/unit | xargs grep -l "VNCDriver(" 2>/dev/null || echo "无匹配：本 feature 新增测试均未直接实例化真实 VNCDriver"
```

真实 VNC 上的最终验证 MUST 作为独立于上述离线测试之外的人工批准环节单独执行（FR-032），
不在本 quickstart 覆盖范围内、也不在 CI 中自动触发。

## 全量回归（含 001 既有测试，SC-008）

```bash
pytest -q
```

**预期**：001 交付的全部既有测试（含 `tests/e2e/test_scenario_01`~`09`）与本 feature
新增的全部测试一并通过，退出码为 0。
