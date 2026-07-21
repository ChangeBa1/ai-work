# Quickstart: 验证稳定动作身份与坐标空间定位纠正

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Data Model**: [data-model.md](./data-model.md)

本指南给出无需连接真实 VNC 环境即可验证本 feature 是否达成 spec.md Success Criteria
的运行步骤（FR-032、SC-009）。所有命令均在 `vnc_agent/` 目录下执行。真实 VNC 验收
步骤单独列在文末，MUST NOT 在常规 `pytest` 运行中执行。

## 前置条件

```bash
cd vnc_agent
python -m venv .venv && source .venv/bin/activate   # 或已有的项目虚拟环境
pip install -e ".[dev]"
```

无需任何 VNC 服务、无需模型 API Key——本 feature 的全部离线测试基于固定/程序化构造
的数据运行；场景 1 直接使用真实事故报告（Run ID
`cefe36a9-f5c3-4622-9998-ef06690a5ab6`）的原始字段作为测试字面量，不读取外部文件。

## 场景 1：真实事故重放——action_id 相同但措辞逐轮改写，不应被误判为不同动作（SC-006）

```bash
pytest tests/fixtures/test_action_identity.py -k "real_incident_replay" -v
```

**预期**：把该次真实运行三轮 `semantic_action`（`action_id` 均为 `"act-1"`，
`intent`/`target.description` 逐轮改写）作为字面量输入，断言
`identity_match()` 对第 2、3 轮相对第 1 轮均返回 `"action_id_match"`，
`RepeatGuard.check()` 对第 2、3 轮均返回 `allowed=False`（`reason` 为
`"blocked_effect_pending"` 或经加强验证后的相应值），而不是 002 之前的
`"different_action"` / `allowed=True`。

## 场景 2：危险目标漂移——"按钮"改写为"已添加的商品行"必须被拦截（SC-006）

```bash
pytest tests/fixtures/test_target_consistency.py -k "button_to_result_row_drift" -v
```

**预期**：使用该次真实运行第三轮"点击购物袋（レジ袋）商品行"的目标描述作为输入，
断言 `evaluate_target_consistency()` 返回 `"dangerous_drift"`，且 `ActionPolicy`
不会为该候选产生任何 `mouse` 类型的 `ExecutableAction`。

## 场景 2b：可交互控件→另一个不符合 intent 的可交互控件同样被拦截

```bash
pytest tests/fixtures/test_target_consistency.py -k "control_to_unrelated_control_drift" -v
```

**预期**：构造一个从"购物袋按钮"漂移到"删除按钮"这类另一个不相关可交互控件的场景，
断言同样返回 `"dangerous_drift"`（覆盖 FR-008 的第二种漂移方向，而不仅是"控件→
非交互元素"这一种）。

## 场景 3：合法前置微动作不应被 fail-safe 误伤

```bash
pytest tests/fixtures/test_target_consistency.py -k "legitimate_micro_action_not_blocked" -v
```

**预期**：构造一个"先关闭遮挡弹窗、再继续原定点击"的场景（`action_id` 不同、目标
具有独立交互目的且符合步骤 intent），断言 `evaluate_target_consistency()` 返回
`"legitimate_micro_action"`，`RepeatGuard.check()` 返回 `allowed=True`。

## 场景 4：真正不同测试步骤的动作不被跨步骤阻止（SC-006 的反例验证）

```bash
pytest tests/fixtures/test_action_identity.py -k "different_step_never_blocks" -v
```

**预期**：构造两个不同 `step_id` 但恰好使用相同 `action_id` 的场景，断言
`identity_match()` 返回 `"different_step"`，`RepeatGuard.check()` 对第二个步骤的
第一轮动作正常返回 `allowed=True, reason="first_attempt"`，不受第一个步骤历史的
任何影响。

## 场景 5：normalized_1000 → 像素坐标换算，1024×1568 纵向画面

```bash
pytest tests/fixtures/test_coordinate_space.py -k "normalized_1000_on_1024x1568" -v
```

**预期**：把该次真实运行第二轮候选 `bbox=[251,402,405,459]` 分别按
`coordinate_space="pixel"`（错误假设）与 `coordinate_space="normalized_1000"`
（假设的真实语义）两种声明输入 `resolve_pixel_bbox()`，断言归一化假设换算后的 Y
坐标落在约 630～720 像素范围内（贴近第一轮真实点击位置 y≈678，验证归一化假说的
换算方向正确），且换算结果落在 `[0,1024)×[0,1568)` 范围内。

## 场景 5b：0.4669% 局部变化仍判定为 expected_effect（SC-007）

```bash
pytest tests/e2e/test_scenario_15_pos_bag_business_acceptance.py -k "low_ratio_expected_effect" -v
```

**预期**：使用固定的动作前/后帧，断言整屏变化比例约为 `0.004669`，且独立
`ActionEffect.status == "expected_effect"`；该断言不得由坐标换算测试替代。

## 场景 6：坐标空间缺失/矛盾/未知取值/越界一律拒绝，不猜测

```bash
pytest tests/fixtures/test_coordinate_space.py -k "missing_or_contradictory_or_unknown_rejected" -v
```

**预期**：分别构造"未声明 coordinate_space 且两种解释都不越界（无法消歧）"、
"声明 pixel 但数值超出分辨率"、"声明了既非 pixel 也非 normalized_1000 的未知取值"
三类候选，断言 `resolve_pixel_bbox()` 均返回 `None`，且该候选不出现在最终
`GroundingResult.candidates` 中。

## 场景 7：同一响应内不同候选独立声明不同坐标空间，逐候选换算

```bash
pytest tests/fixtures/test_coordinate_space.py -k "mixed_coordinate_space_per_candidate" -v
```

**预期**：构造一个响应，候选 A 声明 `pixel`、候选 B 声明 `normalized_1000`，断言
`MimoGrounderClient.ground()`（或其换算逻辑单元）对二者分别使用各自声明的坐标空间
换算，互不影响。

## 场景 8：换算有且仅发生一次

```bash
pytest tests/fixtures/test_coordinate_space.py -k "conversion_happens_exactly_once" -v
```

**预期**：对同一个候选连续调用两次 Grounding 管线中涉及坐标处理的路径（如
`StubGrounder` 返回已换算的候选后，`ActionPolicy` 再次读取），断言第二次读取到的
`bbox` 数值与第一次完全一致（未被二次换算/二次归一化），验证"单一换算点"架构
不变量。

## 场景 9：执行前 OCR 合理性核对——矛盾证据时拒绝而非点击

```bash
pytest tests/fixtures/test_action_policy_sanity_check.py -k "ocr_mismatch_rejected" -v
```

**预期**：构造一个换算后候选中心点与唯一匹配的 OCR 锚点相距超出容差的场景，断言
`ActionPolicy` 拒绝该候选并转入既有失败/恢复流程，不产生 `mouse` 类型的
`ExecutableAction`。

## 场景 10：pos-buy-bag-checkout.yaml 升级为可信业务用例（SC-001~005/008）

```bash
pytest tests/fixtures/test_testcase_loader.py -k "pos_buy_bag_checkout_business_mode" -v
pytest tests/e2e/test_scenario_15_pos_bag_business_acceptance.py -v
```

**预期**：`pos-buy-bag-checkout.yaml` 声明 `verification_mode: business`，
`load_test_case()` 正常加载（因为已包含确定性业务断言，不再仅有 `screen_changed`）；
离线端到端场景（固定帧序列模拟购物车从 0 件 0 円变为 1 件 5 円）驱动完整
`AgentRuntime.run()`，断言：加入购物袋步骤 `ExecutionRouter.execute()` 恰好调用 1
次、`StepVerificationResult.status == "passed"` 且 `weak_assertion_warning is
False`；小計步骤点击恰好 1 次且同样 `passed`；整次运行中支付相关动作调用次数为 0；
`AgentRuntime` 全程未发送额外鼠标点击或键盘 Tab。

## 场景 11：报告包含动作身份与坐标转换审计证据（FR-025/026）

```bash
pytest tests/fixtures/test_report_builder.py -k "action_identity_and_coordinate_audit" -v
```

**预期**：驱动一次含 Grounding 与 RepeatGuard 拦截的离线迭代，断言
`build_report_dict()` 输出的每轮记录包含 `canonical_action_identity`（含
`step_id`/`action_id`/`normalized_target`）与 `coordinate_space_audit`（含声明的
坐标空间、换算前后坐标、是否被采纳），且 HTML 报告的对应折叠区块能正确渲染这些字段。

## 场景 11b：起始状态门禁与实际发送动作审计（FR-036/038、SC-012/013）

```bash
pytest tests/unit/test_cli_start_state_confirmation.py -v
pytest tests/fixtures/test_report_builder.py -k "run_level_audit_fields" -v
pytest tests/e2e/test_start_state_precondition.py -v
```

**预期**：使用 `--confirm-start-state --confirmed-cart-items 0 --confirmed-cart-amount
0 --confirmed-screenshot <固定测试截图路径>` 驱动 `vnc-agent run` 的 CLI 入口，断言
`RunContext.test_run` 正确记录 `human_start_state_confirmation`（含时间戳）；离线端到端
场景断言固定首帧产生 `observed_start_state`，匹配时 `start_state_precondition=passed`，
不匹配/不可读/冲突时在首个输入事件前失败且 `executed_action_log` 为空。报告的
`action_category_counts` 只从 `execution_result.success=True` 的已发送动作聚合；被
RepeatGuard/ActionPolicy 拦截的提案仍在逐轮审计中，但不增加计数。未提供
`--confirm-start-state` 时门禁为 `not_required`。详见
contracts/real-vnc-audit-contract.md。

## 场景 11c：恢复策略六字段 Constitution 门禁（FR-037）

```bash
pytest tests/fixtures/test_feature003_config.py -k "recovery_policy" -v
pytest tests/fixtures/test_recovery_no_destructive_actions.py -v
```

**预期**：全部恢复策略显式包含六个字段；参数化删除任一字段时配置加载失败。危险漂移、
歧义和坐标拒绝继续走共享预算，预算耗尽后失败停止，不发送盲目 Tab 或破坏性动作。

## 场景 12：确认无真实 VNC 依赖（SC-009）

```bash
grep -rL "MockVNCDriver\|fixture" tests/fixtures tests/unit | xargs grep -l "VNCDriver(" 2>/dev/null || echo "无匹配：本 feature 新增测试均未直接实例化真实 VNCDriver"
```

## 全量回归（含 001/002 既有测试，SC-010）

```bash
pytest -q
```

**预期**：001/002 交付的全部既有测试与本 feature 新增的全部测试一并通过，退出码为
0；`pos-buy-bag-checkout.yaml` 相关的既有测试（若引用了旧的仅 `screen_changed`
断言文本）需要同步更新为新的业务断言期望，不允许因用例文件本身的合法升级而产生
误报的回归失败。

---

## 真实 VNC 验收步骤（人工批准环节，MUST NOT 在 `pytest` 中自动运行）

以下步骤仅在离线回归（场景 1～12）全部通过、且已获得最终人工批准后，由人工在真实
VNC 环境上单独执行一次，验证本 feature 是否真正修复了 Run ID
`cefe36a9-f5c3-4622-9998-ef06690a5ab6` 记录的真实事故：

1. **人工确认起始状态**：连接到目标 VNC 环境（`config/vnc-targets.yaml` 中的目标
   条目），人工目视确认 POS 应用当前购物车状态为 0 件 / 0 円；对该状态截一张前置
   截图。程序 MUST NOT 在此步骤自动点击"クリア"或任何清空/重置操作（FR-030）。
2. **运行更新后的用例（同时记录人工确认，FR-036）**：
   `vnc-agent run testcases/pos-buy-bag-checkout.yaml --target <真实目标 ID>
   --confirm-start-state --confirmed-cart-items 0 --confirmed-cart-amount 0
   --confirmed-screenshot <上一步的前置截图路径>`（参数定义见
   contracts/real-vnc-audit-contract.md §1；其余 CLI 参数以
   `specs/001-vnc-core-execution-loop/contracts/cli-contract.md` 为准）。
   程序连接后只允许进行首次观察；若观察到的件数/金额与人工确认不完全一致或无法可靠
   提取，运行必须在首个键鼠事件前以 `start_state_precondition_failed` 停止。人工不得
   覆盖该失败继续执行，必须先在程序外修复环境并重新开始一次新的确认与运行。
3. **核对结果**（对照本次真实事故的三个根因逐一确认已修复）：
   - 加入购物袋步骤的鼠标点击次数是否严格为 1 次（对照本次事故的"两次多余点击"）；
   - 是否有任何点击落在非"レジ袋"按钮的位置（对照本次事故第三轮误点商品行）；
   - 购物车是否确实从 0 件 0 円变为 1 件 5 円，且该判定来自业务断言而非仅
     `screen_changed`；
   - 小計步骤是否点击恰好 1 次并进入小計确认画面；
   - 全程是否未出现任何支付相关动作、盲目 Tab、或程序自动点击"クリア"的记录。
4. **核对报告审计字段**：打开本次运行生成的 JSON/HTML 报告，确认运行级字段
   `human_start_state_confirmation`（人工前置确认记录、确认时间戳、前置截图引用）、
   `observed_start_state`（程序实际观察到的起始画面结果）、`start_state_precondition`、
   `executed_action_log`、`action_category_counts`（购物袋点击/小計点击/支付相关/
   "クリア"或等效清空各类别的**实际发送**次数统计），以及
   逐轮的动作身份与坐标转换审计证据均已存在（FR-025/026/036），并可仅凭报告完成
   上述第 3 步的全部核对（例如直接比较 `action_category_counts.clear_or_reset ==
   0` 与 `start_state_precondition.status == "passed"`），
   无需重新连接 VNC 复现或人工重新计数原始日志（SC-012）。
5. **记录验收结论**：由人工在验收记录中签署确认，作为本 feature 交付的最终证据；
   该记录与本次真实事故报告（Run ID `cefe36a9-f5c3-4622-9998-ef06690a5ab6`）一并
   归档，供未来同类问题排查参考。
