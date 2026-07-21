# Quickstart: VNC 黑盒 GUI 自动化测试核心执行闭环

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Data Model**: [data-model.md](./data-model.md) | **Contracts**: [contracts/](./contracts/)

本指南用于**验证**本功能的纵向切片是否真正跑通（观察→理解→选择动作→定位→执行→等待→
验证→保存证据），对应 spec.md 的验收场景一至九。这里不重复模型字段定义（见 data-model.md）
或接口细节（见 contracts/），只给出可执行的验证步骤与预期现象。

## 前置条件

1. **被测环境**：一台已开启 VNC 服务、分辨率与 DPI 固定的 Windows 10 桌面（或用于集成
   测试的本地 VNC 服务器，见 research.md §9），不安装任何辅助 Agent/UIA 相关组件。
2. **控制端**：一台无独立显卡的普通办公电脑，已安装 Python 3.12+ 与项目依赖
   （`pip install -e .`，详见 `pyproject.toml`）。
3. **模型访问**：
   - Grounder：可访问 OpenCode Go API 上的 MiMo-V2.5（`models.grounder.*` 配置齐全）。
   - Planner：可访问一个已配置的强视觉/推理模型 API（`models.planner.*` 配置齐全，
     provider 可替换，见 contracts/model-provider-contract.md）。
   - 两者的 API Key 均通过环境变量提供（**不要**写入 `config/*.yaml` 明文），例如：
     `export VNC_AGENT_PLANNER_API_KEY=...`、`export VNC_AGENT_GROUNDER_API_KEY=...`。
4. **配置文件**：复制并按需修改 `config/vnc-targets.yaml`（VNC 地址/端口/密码环境变量名）、
   `config/models.yaml`（Planner/Grounder provider 与超时）、`config/agent.yaml`（等待/
   重试/截图策略默认值）。
5. **参考测试用例**：`testcases/` 下准备至少一份最小 YAML 用例（结构见
   `contracts/test-case-schema.md`），覆盖一个可通过快捷键完成的步骤和一个需要视觉定位
   的步骤。

## 场景一：建立 VNC 连接（验收场景一）

```bash
vnc-agent run testcases/smoke-connect.yaml --dry-run   # 先只做用例格式校验
vnc-agent run testcases/smoke-connect.yaml              # 再真正连接并执行
```

**预期**：`--dry-run` 不连接 VNC、立即返回校验结果；正式运行时命令行输出中出现连接成功、
实际屏幕分辨率的日志行；`artifacts/runs/<run-id>/frames/` 下出现首帧截图。

## 场景二：键盘优先执行（验收场景二）

使用一个 intent 为"保存当前文档"、且被测应用支持 Ctrl+S 的步骤运行。

**预期**：`artifacts/runs/<run-id>/logs/events.jsonl` 中该步骤的 `ActionIteration` 显示
`executable_action.method = "keyboard"`，且日志中不出现该步骤调用 Grounder 的记录
（对照 `raw_model_response_refs` 应为空或不含 grounder 响应）。

## 场景三：视觉定位并点击（验收场景三）

使用一个 intent 为"点击登录按钮"、OCR/模板均无法唯一定位（例如按钮无文字、或页面含多个
相似按钮）的步骤运行。

**预期**：对应 `ActionIteration.grounding_result.model_name = "mimo-v2.5"`，
`candidates` 长度 ≤ 3 且每个候选带 `confidence`/`reason`；`executable_action.method =
"mouse"` 且 `execution_result.actual_click_point` 落在被选候选 `bbox` 内。

## 场景四：点击后验证（验收场景四）

使用登录步骤，`expected` 声明"欢迎"文字出现。

**预期**：该步骤只有一轮 `ActionIteration`，其 `verification_result.status = "passed"`
且 `evidence_refs` 指向点击**之后**新采集的截图；步骤 `status = "passed"` 后才会看到下一
步骤开始执行的日志。

## 场景五：点击无效果、多轮迭代与预算耗尽（验收场景五，含 Clarification 2026-07-20 的
步骤内迭代行为）

人为让第一次点击不产生预期变化（如临时遮挡按钮），观察系统是否：

1. 第 1 轮 `ActionIteration.verification_result.status` 为 `failed`/`uncertain`；
2. 触发 `second_candidate` 或 `re_ground` 恢复策略，开启第 2 轮 `ActionIteration`
   （`iteration_index = 1`）；
3. 若始终未通过，达到该步骤 `max_retries` 后，`StepRecord.final_status = "failed"`，
   且 `iterations` 数组保留了每一轮的完整证据（而不是只保留最后一轮）。

## 场景六：等待动态页面（验收场景六）

对一个点击后出现加载动画的步骤运行。

**预期**：`wait_result.waited_ms` 明显大于配置的 `min_delay_ms`，`end_reason` 为
`"stable"` 或 `"expected_condition"`；日志中不出现"等待期间就已进入 VERIFYING"的记录。

## 场景七：Grounding 无法确定 / 置信度分级（验收场景七 + Clarification 2026-07-20 的
三态处理）

准备三种截图分别触发：目标确实不存在、整体置信度偏低、Top-1/Top-2 接近。

**预期**：三种情况在 `RecoveryAttempt.failure_type` 上分别为 `target_not_found` 与
两条 `grounding_low_confidence`（`sub_reason` 分别为 `overall_low_confidence` 与
`top1_top2_close`）；任何情况下都不出现对越界或凭空坐标的点击动作。

## 场景八：VNC 中断与整步重做（验收场景八 + Clarification 2026-07-20）

在某步骤执行期间人为断开 VNC 连接（如短暂阻断网络），随后恢复网络。

**预期**：日志出现有限次数的重连尝试；重连成功后，该步骤产生一条 `sub_reason` 为空、
`strategy = "restart_step"` 的 `RecoveryAttempt`，随后从 `OBSERVING` 重新开始一轮全新的
`ActionIteration`（`iteration_index` 递增），而不是从 `WAITING`/`VERIFYING` 继续；本次
重做计入该步骤的 `max_retries`。

## 场景九：失败报告（验收场景九）

选择一个必然失败的步骤（如 `expected` 引用一个永不出现的文字）运行到超时。

**预期**：`artifacts/runs/<run-id>/report.html` 与 `report.json` 中该步骤的
`failure_reason` 非空，`iterations` 下每一轮都能看到操作前后截图、Grounding 候选（如
适用）、`verification_result.evidence_refs` 与恢复记录；报告顶层 `status` 为 `"failed"`
（不会出现"实际失败但报告 passed"）。

## 复合验证条件与"不确定"传播（Clarification 2026-07-20，补充验证）

构造一个 `operator: all` 且包含两个条件的步骤，其中一个条件命中"不确定"（例如需要视觉
模型才能判断、但视觉模型暂不可用），另一个条件为 `failed`。

**预期**：整体 `verification_result.status = "failed"`（因为 all 下 failed 优先于
uncertain）。再构造另一个用例，两个条件分别为 `passed` 与"不确定"：**预期**整体为
`"uncertain"`，而不是被静默视为 `"passed"`。

## 敏感区域遮罩与外发截图（Clarification 2026-07-20，补充验证）

配置 `security.mask_regions` 覆盖一个测试步骤操作前截图的一角，运行该步骤并同时开启
`--json-only`（跳过 HTML，加快检查）。

**预期**：`artifacts/runs/<run-id>/frames/` 下持久化的截图与 `report.json` 中引用的图片
该区域已被打码；若配置了模型请求存档（`save_model_payloads`），存档中发往 Planner/
Grounder 的请求截图**未被**打码（保持原图），与 `report-schema.md` 的契约保证一致。

## 十次连续运行验收（SC-006/SC-007）

```bash
for i in $(seq 1 10); do
  vnc-agent run testcases/reference-flow.yaml --config ./config
done
```

**预期**：10 次运行中至少 9 次的 `status` 与人工预期的通过/失败一致；且不存在任何一次
"实际操作未达成预期效果、但报告判定为 passed"的情况（人工逐条核对 `report.json` 的
`status` 与录屏/截图证据）。参考测试流程与运行前的环境重置方法由 QA 团队按 spec.md
Assumptions 另行准备，此处仅给出验证运行方式。

## Planner 供应商可替换性验收（FR-046，需求质量门禁 2026-07-21 新增）

```bash
# 1. 先用默认 Planner provider 跑一次最小用例，确认通过
vnc-agent run testcases/smoke-connect.yaml --config ./config

# 2. 仅修改 config/models.yaml 中的 models.planner.provider 字段，指向另一个已注册的
#    PlannerProvider 实现（例如切换到测试用的 mock/备用 provider），不改动任何
#    planning/ perception/ verification/ execution/ 下的调用方代码
#    （编辑 config/models.yaml ...）

# 3. 重新运行同一份用例
vnc-agent run testcases/smoke-connect.yaml --config ./config
```

**预期**：两次运行均能正常完成（`--dry-run` 校验通过、`run` 正常产生报告），过程中不需要
修改任何调用方源码，仅通过配置切换即完成 Planner 供应商替换；若新 provider 实现未正确
实现 `describe_screen`（见 contracts/model-provider-contract.md），启动阶段（进入
`PREPARING` 之前）MUST 直接报错退出，而不是运行到某个测试步骤中途才失败（对应 research.md
§13 的 Provider 启动期校验）。

## 清理

```bash
vnc-agent report <run-id> --format json   # 如需离线重新查看报告，无需重新连接 VNC
```

制品默认保留在 `artifacts/runs/<date>/<run-id>/`，按 `artifacts.retention_days` 配置
自动清理，无需手动删除。
