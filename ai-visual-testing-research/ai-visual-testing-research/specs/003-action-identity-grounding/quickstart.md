# Quickstart: 验证通用动作身份、目标一致性与坐标空间安全

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Data Model**: [data-model.md](./data-model.md)

**重新基线说明**：本文件替换 2026-07-21 版本。旧版本以 POS 购物袋事故复现作为
唯一验收路径；本版本以三个互不相关的通用离线场景（表单提交、图标菜单、弹窗/
滚动微动作）作为主要验收证据，POS 场景保留为第四个附加回归 fixture，不再是
唯一或首要依据（FR-040、Constitution Principle VI）。

本指南给出无需连接真实/在线环境即可验证本 feature 是否达成 spec.md Success
Criteria 的运行步骤（FR-039、SC-011）。所有命令均在 `vnc_agent/` 目录下执行。
真实/在线环境验收步骤单独列在文末，MUST NOT 在常规 `pytest` 运行中执行。

## 前置条件

```bash
cd vnc_agent
python -m venv .venv && source .venv/bin/activate   # 或已有的项目虚拟环境
pip install -e ".[dev]"
```

无需任何 VNC 服务、无需模型 API Key——本 feature 的全部离线测试基于固定/程序化
构造的数据运行。

## 场景 1：表单提交——同一非幂等提交动作在措辞改写下不应被重复执行（SC-001）

```bash
pytest tests/fixtures/test_scenario_form_submit.py -k "submit_reworded_not_duplicated" -v
```

**预期**：构造同一测试步骤内两轮迭代（`action_type="click"`、`action_id="submit-1"`
固定，`intent`/`target.description` 改写），断言 `identity_match()` 返回
`"action_id_match"`，`has_target_evidence_conflict()` 为 `False`（角色/空间证据
未变），`RepeatGuard.check()` 拦截第二轮的直接执行。

## 场景 1b：action_id 相同但目标证据冲突——仍必须运行一致性检查（安全问题 A，SC-007）

```bash
pytest tests/fixtures/test_scenario_form_submit.py -k "action_id_match_but_conflicting_target" -v
```

**预期**：构造两轮 `action_id`/`action_type` 均相同、但 `target.role` 从
"button" 变为一个非交互角色、且已解析区域相距很远的场景，断言
`has_target_evidence_conflict()` 为 `True`，`RepeatGuard.check()` 转入
`evaluate_target_consistency()` 而非直接沿用 no_effect-only 规则；同时构造
前一轮 `ActionEffect` 已为 `no_effect` 的变体，断言该 `no_effect` 状态不豁免
本次一致性检查（安全问题 A 的第二个不变量）。

## 场景 2：无文字图标打开菜单——视觉目标身份与坐标空间安全（SC-002/003）

```bash
pytest tests/fixtures/test_scenario_icon_menu.py -k "icon_only_target_and_coordinate_space" -v
```

**预期**：构造一个 `target.text=None`、`target.role="icon_button"` 的工具栏
按钮场景，`GroundingCandidate` 声明 `coordinate_space="normalized_1000"`，画面
分辨率为非正方形、纵向尺寸超过 1000（示例分辨率 1024×1568，仅作几何测试数值，
不代表任何业务绑定）；断言：(a) 缺乏文字锚点时仍能正确识别视觉目标身份；
(b) 换算后坐标落在正确的像素范围内且换算有且仅发生一次；(c) 点击动作严格
执行 1 次。

## 场景 3：弹窗关闭或滚动后再操作目标——合法微动作不应被误杀（安全问题 B，SC-004/005/006）

```bash
pytest tests/fixtures/test_scenario_popup_scroll.py -k "legitimate_micro_action_not_misclassified" -v
```

**预期**：构造 `proposed_action.micro_action_purpose="dismiss_overlay"`（关闭
遮挡弹窗）与 `="scroll_reveal"`（滚动显现目标）两组场景，`risk_level="low"`，
`action_type` 与前一轮不同；断言 `evaluate_target_consistency()` 返回
`"legitimate_micro_action"` 而非 `"dangerous_drift"`——验证"`action_type` 改变
只是风险信号，不无条件等于 dangerous_drift"。同一测试文件中另一组用例构造
`proposed_action.micro_action_purpose=None` 且未通过步骤 intent 一致性检查，
断言此时返回 `"dangerous_drift"`，用于确认 AND 语义的两侧都被覆盖（既不误杀
合法微动作，也不放过真正的危险漂移）。

## 场景 4：危险目标漂移——控件到非交互元素/另一个不相关控件均被拦截（SC-005）

```bash
pytest tests/fixtures/test_target_consistency.py -k "button_to_result_row_drift or control_to_unrelated_control_drift" -v
```

**预期**：分别构造"可交互按钮 → 非交互结果展示元素"与"可交互按钮 → 另一个
不符合 step_intent 的可交互按钮"两种漂移，均未声明 `micro_action_purpose`，
断言 `evaluate_target_consistency()` 均返回 `"dangerous_drift"`，且该判定在
动作发送执行之前生效（不产生任何 `mouse` 类型的 `ExecutableAction`）。

## 场景 5：真正不同测试步骤的动作不被跨步骤阻止

```bash
pytest tests/fixtures/test_action_identity.py -k "different_step_never_blocks" -v
```

**预期**：构造两个不同 `step_id` 但恰好使用相同 `action_id` 的场景，断言
`identity_match()` 返回 `"different_step"`，`RepeatGuard.check()` 对第二个
步骤的第一轮动作正常返回 `allowed=True, reason="first_attempt"`。

## 场景 6：normalized_1000 → 像素坐标换算，非正方形画面

```bash
pytest tests/fixtures/test_coordinate_space.py -k "normalized_1000_on_non_square_resolution" -v
```

**预期**：把候选 `bbox` 分别按 `coordinate_space="pixel"`（错误假设）与
`coordinate_space="normalized_1000"`（正确假设）两种声明输入
`resolve_pixel_bbox()`，断言归一化假设换算后的坐标落在正确范围内，且换算
结果落在画面分辨率范围内。

## 场景 7：坐标空间缺失/矛盾/未知取值/越界一律拒绝，不猜测

```bash
pytest tests/fixtures/test_coordinate_space.py -k "missing_or_contradictory_or_unknown_rejected" -v
```

**预期**：分别构造"未声明 `coordinate_space` 且两种解释都不越界（无法消歧）"、
"声明 `pixel` 但数值超出分辨率"、"声明了既非 `pixel` 也非 `normalized_1000`
的未知取值"三类候选，断言 `resolve_pixel_bbox()` 均返回 `None`，且该候选不
出现在最终 `GroundingResult.candidates` 中。

## 场景 8：同一响应内不同候选独立声明不同坐标空间，逐候选换算

```bash
pytest tests/fixtures/test_coordinate_space.py -k "mixed_coordinate_space_per_candidate" -v
```

**预期**：构造一个响应，候选 A 声明 `pixel`、候选 B 声明 `normalized_1000`，
断言二者分别使用各自声明的坐标空间换算，互不影响。

## 场景 9：换算有且仅发生一次

```bash
pytest tests/fixtures/test_coordinate_space.py -k "conversion_happens_exactly_once" -v
```

**预期**：验证同一候选的坐标数值在离开 `models/` 边界后不会被下游模块二次
换算/二次归一化。

## 场景 10：执行前 OCR 合理性核对——矛盾证据时拒绝而非点击

```bash
pytest tests/fixtures/test_action_policy_sanity_check.py -k "ocr_mismatch_rejected" -v
```

**预期**：构造换算后候选中心点与唯一匹配的 OCR 锚点相距超出容差的场景，断言
`ActionPolicy` 拒绝该候选并转入既有失败/恢复流程。

## 场景 11：声明式运行前置条件——匹配通过、不匹配/不可读/冲突零输入停止（SC-008/009）

```bash
pytest tests/fixtures/test_run_precondition.py -k "declared_facts_matched_and_mismatched" -v
```

**预期**：构造一个声明 `precondition.facts=[DeclaredFact(key="example_state",
spec=VerificationSpec(operator="all", conditions=[...]))]` 的测试用例（业务
内容为任意通用示例，不限定为任何具体行业），驱动 `evaluate_precondition()`：
(a) 首帧观察满足声明条件时，`status="passed"`，运行正常进入第一个 PLANNING；
(b) 首帧观察不满足、或声明的断言判定为 `uncertain`、或存在冲突证据时，
`status="failed"`，断言运行在首个键盘/鼠标事件发送前停止，实际发送动作次数
为 `0`，且未触发任何自动重置/清理动作。

## 场景 12：声明式动作 tag 审计——自定义 tag 与拦截提案的计数边界（SC-009 之一）

```bash
pytest tests/fixtures/test_declared_action_tags.py -k "custom_tags_and_blocked_proposals" -v
```

**预期**：声明两条 `ActionTagRule`（如 `tag="primary_submit"` 匹配
`action_type="click"` 且 `target_role="button"`；`tag="navigation"` 匹配
`intent_contains="menu"`），驱动一组含已发送与被拦截动作的迭代，断言
`declared_tag_counts` 仅从确实发送的动作聚合、被拦截提案计数为 `0` 但仍出现
在逐轮审计记录中；断言核心 `ReportingConfig` 默认 `action_tags=[]`，不含任何
固定业务分类。

## 场景 13：报告包含动作身份、坐标转换、前置条件与 tag 审计证据（FR-035/036/038）

```bash
pytest tests/fixtures/test_report_builder.py -k "action_identity_and_coordinate_audit" -v
pytest tests/fixtures/test_report_builder.py -k "run_level_precondition_and_tag_audit" -v
```

**预期**：驱动一次含 Grounding、RepeatGuard 拦截与声明式前置条件的离线迭代，
断言 `build_report_dict()` 输出包含 `canonical_action_identity`、
`coordinate_space_audit`、`precondition_evaluation`、`human_confirmed_facts`、
`declared_tag_counts` 字段，且 HTML 报告能正确渲染这些字段。

## 场景 14：恢复策略六字段 Constitution 门禁 + 风险级别路由到既有契约（FR-013/034）

```bash
pytest tests/fixtures/test_feature003_config.py -k "recovery_policy" -v
pytest tests/fixtures/test_recovery_no_destructive_actions.py -v
```

**预期**：全部恢复策略显式包含六个字段；参数化删除任一字段时配置加载失败。
构造一个 `risk_level="high"` 的合法微动作候选（超过其类别的风险阈值）场景，
断言其结果通过 `requires_human_confirmation=True` 的恢复策略路由，而不是新增
独立的风险裁决分支。危险漂移、歧义和坐标拒绝继续走共享预算，预算耗尽后失败
停止，不发送盲目按键导航或任何未声明的状态变更动作。

## 场景 15：POS 购物袋结算——附加回归 fixture，非唯一验收依据（SC-013）

```bash
pytest tests/fixtures/test_testcase_loader.py -k "pos_buy_bag_checkout_business_mode" -v
pytest tests/e2e/test_scenario_15_pos_bag_business_acceptance.py -v
```

**预期**：`pos-buy-bag-checkout.yaml` 声明 `verification_mode: business`，使用
与场景 1～14 完全相同的通用机制（`identity_match`/`has_target_evidence_conflict`/
`evaluate_target_consistency`/`resolve_pixel_bbox`/声明式前置条件/声明式 tag）
通过验证；该场景的业务断言文本与 `action_tags`/`precondition` 声明**只存在于
该 testcase 文件本身**，不依赖任何仅为该场景编写的核心代码分支（本次重新基线
后已不存在这样的分支）。该场景通过与否 MUST NOT 单独构成任何 SC 的充分验收
依据——场景 1～3 才是每项通用能力的主要证据。

## 场景 16：确认无真实/在线环境依赖（SC-011）

```bash
grep -rL "MockVNCDriver\|fixture" tests/fixtures tests/unit | xargs grep -l "VNCDriver(" 2>/dev/null || echo "无匹配：本 feature 全部测试均未直接实例化真实 VNCDriver"
```

## 全量回归（含 001/002 既有测试，SC-010）

```bash
pytest -q
```

**预期**：001/002 交付的全部既有测试与本 feature 新增的全部测试一并通过，
退出码为 0。

---

## 真实/在线环境验收步骤（人工批准环节，MUST NOT 在 `pytest` 中自动运行）

以下步骤仅在离线回归（场景 1～16）全部通过、且已获得最终人工批准后，由人工在
真实/在线环境上单独执行一次：

1. **声明前置条件（测试用例层面）**：确认待验收的测试用例已在 `precondition`
   字段中声明了运行开始前需要成立的命名 fact（内容由该测试用例的具体业务
   自行决定，框架本身不预置任何字段）。
2. **（可选）人工独立确认**：
   `vnc-agent run <test-case-file> --target <目标 ID>
   --confirm-precondition <key>=<value> --confirm-screenshot <前置截图路径>`
   （参数定义见 `contracts/real-vnc-audit-contract.md` §3；其余 CLI 参数以
   `specs/001-vnc-core-execution-loop/contracts/cli-contract.md` 为准）。程序
   连接后只允许进行首次观察；若声明的前置条件判定为 `failed`（不论是否提供了
   人工确认参数），运行必须在首个键鼠事件前停止，MUST NOT 尝试自动纠正现场。
3. **核对结果**：打开本次运行生成的 JSON/HTML 报告，核对
   `precondition_evaluation.status`、`human_confirmed_facts`（若提供）、
   `declared_tag_counts`（该测试用例声明的全部 tag 的实际发送次数）、
   `executed_action_log`，以及逐轮的动作身份、目标一致性判定与坐标转换审计
   证据均已存在，且可仅凭报告完成核对，无需重新连接目标环境复现或人工重新
   计数原始日志（SC-012）。
4. **记录验收结论**：由人工在验收记录中签署确认，作为本 feature 交付的最终
   证据。
