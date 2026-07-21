<!--
Sync Impact Report
- Version change: (template) → 1.0.0
- Rationale: Initial ratification. Constitution file previously contained only
  unfilled template placeholders; this is the first concrete adoption, derived
  from `overall_design.md` (VNC 黑盒 GUI 自动化测试 Agent 总体设计说明书).
- Modified principles: N/A (initial fill, no prior named principles existed)
- Added sections:
  - Core Principles I–V (Deterministic Runtime Control, Planner/Grounder/
    Executor/Verifier Separation, Keyboard-First Execution Priority,
    Independent Observe-Act-Verify Loop, Controlled Self-Evolution)
  - 工程与安全约束 (Engineering & Safety Constraints)
  - 质量门禁与开发工作流 (Quality Gates & Development Workflow)
  - Governance
- Removed sections: none
- Templates requiring updates:
  - ✅ .specify/templates/plan-template.md — "Constitution Check" gate is
    generic ("[Gates determined based on constitution file]"); no edit needed,
    remains compatible.
  - ✅ .specify/templates/spec-template.md — no hardcoded principle references
    found; no edit needed.
  - ✅ .specify/templates/tasks-template.md — no hardcoded principle
    references found; no edit needed.
  - ⚠ No `speckit-*` command/skill files contained project-specific
    principle text requiring sync; none found needing changes at this time.
- Follow-up TODOs:
  - TODO(RATIFICATION_DATE): confirmed as 2026-07-20 (date of first fill from
    overall_design.md); update if an earlier internal approval date is found.
-->

# VNC 黑盒 GUI 自动化测试 Agent (vnc-test-agent) Constitution

## Core Principles

### I. 确定性运行时控制模型 (Deterministic Runtime Control)
测试执行流程 MUST 由代码状态机控制，而非由模型自主驱动。模型仅可承担以下职责：理解复杂
截图、生成语义计划、定位动态目标、分析未知异常、执行低确定性的语义验证。模型 MUST NOT：
自行决定无限重试、自行判定测试最终通过、直接控制底层 VNC 会话、修改正式测试基线、修改
正式模型版本、绕过危险操作策略。
理由：测试系统的可信度依赖于结果的可复现性和可审计性；若允许模型自主控制流程或判定结果，
测试将失去作为回归基线的价值。

### II. Planner / Grounder / Executor / Verifier 职责分离 (Separation of Concerns)
系统 MUST 将决策拆分为四个独立角色：Planner（决定“下一步做什么”）、Grounder（决定
“目标具体在哪里”）、Executor（决定“如何通过 VNC 执行”）、Verifier（判断“操作是否真的
成功”）。Planner MUST NOT 直接输出裸坐标；Grounder MUST NOT 自行决定测试流程；Verifier
MUST NOT 仅凭 Planner 或 Grounder 的自我判断而放行。
理由：职责混合会导致定位错误、误判成功、以及无法定位问题根因；分离后每一层都可以独立
替换、独立测试、独立度量准确率。

### III. 键盘优先，视觉点击兜底 (Keyboard-First Execution Priority)
动作解析 MUST 按以下优先级顺序尝试候选执行方案：已验证回放动作 → 快捷键 → Tab/Shift+Tab
焦点导航 → Win+R + PowerShell 配方 → OCR 文本定位 → 模板或视觉锚点 → MiMo Grounding →
强模型异常分析。系统 MUST NOT 在存在更高优先级、更确定性的可用路径时，直接跳转到视觉
Grounding 或模型调用。
理由：键盘和已验证路径的确定性、速度和成本均优于视觉定位；将视觉手段保留为兜底可以降低
误点击风险、降低模型调用成本，并提升低配置环境下的执行效率。

### IV. 观察-执行-验证独立闭环 (Independent Observe-Act-Verify Loop)
每个动作 MUST 遵循 Observe → Understand → Plan → Ground → Act → Wait → Observe Again →
Verify 的闭环，验证 MUST 基于操作后重新采集的截图与独立证据，而不是执行模型或定位模型
自身的置信声明。验证结果为 `uncertain` 时 MUST NOT 被视为通过，须触发更强验证器、局部
高清复检、恢复流程或人工确认。
理由：黑盒 GUI 环境下唯一可信的成功证据来自观察到的真实屏幕变化；允许模型自证会掩盖
真实失败，破坏测试的可信度。

### V. 受控自进化 (Controlled Self-Evolution)
系统 MAY 在运行时实时更新经验类数据：页面记忆、元素记忆、失败记忆、模板、策略成功率、
置信度校准数据、相似页面索引。系统 MUST NOT 在运行时：自动训练或替换生产模型、自动修改
正式测试断言、自动覆盖正式回放脚本、无条件自动接受所有 UI 变化。回放自愈 MUST 仅生成
待审核的候选补丁（`pending` 状态），补丁转为 `approved` 前 MUST NOT 影响正式基线。
理由：测试基线和生产模型的变更具有高影响面，必须保留人工审核关卡，防止经验数据的噪声
或模型漂移悄然侵蚀测试的可信度。

## 工程与安全约束 (Engineering & Safety Constraints)

**黑盒边界**：系统 MUST 仅通过 VNC 获取屏幕像素、发送键盘鼠标事件；MUST NOT 读取 Windows
UIA 控件树、进程信息、文件系统、注册表、浏览器 DOM 或被测应用内部接口。

**架构约束**：MVP 阶段 MUST 采用单进程模块化单体架构，仅运行一个 Agent 进程、一个 VNC
会话、一个测试任务、一个 SQLite 数据库、一个本地产物目录。MVP 阶段 MUST NOT 引入 MCP、
LangGraph、Temporal、Kafka、Kubernetes、分布式数据库或本地大型视觉模型；模块间 MUST 通过
Python Protocol 与内部注册表解耦，理由是高频截图与键鼠调用不适合承受远程协议开销。

**资源约束（弱配置电脑）**：系统 MUST 同时只处理一个 VNC 会话、及时释放截图内存、仅保留
最近 3～5 帧于内存、原始截图立即写盘、按需加载 OCR 模型、不同时加载多个本地模型；页面
稳定时 MUST NOT 保持高频截图（默认间隔 500ms）；MUST NOT 进行实时视频分析或运行本地大型
视觉模型。模型调用 MUST 遵循“能用确定性手段解决就不升级到模型”的路由原则：页面未变化不
重复调用 Planner，历史经验命中时不立即调用 MiMo，OCR 能唯一定位时不调用 Grounder，回放
成功时不调用 Planner，语义验证仅作为最后手段。

**动作安全分级**：危险动作 MUST 分为 low / medium / high 三级。high 风险动作（如重启、
关机、系统配置、网络配置、批量删除）MUST 来自白名单测试步骤、通过风险策略检查、使用注册
配方，且无人值守运行时需显式允许；遇到 UAC 或安全桌面场景 MUST 立即停止并报告环境限制，
MUST NOT 尝试绕过。

**PowerShell 黑盒配方**：PowerShell MUST 仅通过 VNC 键盘打开并输入；MUST NOT 允许模型
直接提供完整命令或调用未注册配方；参数 MUST 经过长度限制、类型校验、特殊字符转义；高风险
配方默认 MUST 需要人工确认。

**凭据与隐私**：VNC 密码 MUST NOT 以明文写入 YAML；模型 API Key MUST 通过环境变量或操作
系统凭据存储管理；测试数据中的密码 MUST 通过引用传入，MUST NOT 直接写入测试用例正文；
日志 MUST 自动过滤敏感字段；截图 MUST 支持敏感区域打码，密码输入步骤默认 MUST NOT 保存
输入后的局部截图。

## 质量门禁与开发工作流 (Quality Gates & Development Workflow)

**验证独立性门禁**：任何声明测试步骤“通过”的实现变更，代码评审 MUST 确认 Verifier 的
判断依据来自操作后独立采集的证据（截图、OCR、模板、画面变化等），而非执行动作本身的
返回值或模型自评。

**恢复与重试门禁**：每个恢复策略 MUST 显式配置最大次数、冷却时间、是否消耗全局重试额度、
是否允许改变动作路径、是否需要强模型、是否需要人工确认；系统级 MUST NOT 出现无限重试
路径。

**测试覆盖门禁**：新增或变更核心模块 MUST 至少覆盖以下测试类别之一（视变更范围而定）：
坐标转换/边界计算等单元测试、基于固定截图的离线感知与解析测试、真实 VNC 集成测试、
端到端场景测试（含回放与自愈补丁生成）。

**MVP 验收门禁**：以下条件在发布前 MUST 满足，作为不可协商的完成标准：不存在无限重试；
不会自动修改正式测试断言；单会话运行不要求独立显卡；不运行本地大型视觉模型；Planner 与
Grounder 已分离；每个正式步骤均能独立验证；回放失败后仅生成待审核的自愈候选补丁而非自动
应用。

**制品与可观测性**：每次运行 MUST 保存完整运行轨迹（状态迁移、截图、模型请求/响应、验证
证据），并 MUST 能生成 HTML 与 JSON 报告；日志 MUST 采用结构化 JSON Lines 格式，至少包含
run_id、step_id、state、event、耗时等字段。

## Governance

本 Constitution 在本项目范围内的效力高于其他工程惯例、模板默认值或临时约定；当具体实践与
本文件冲突时，以本文件为准，除非通过下述修订流程正式修改。

**修订流程**：任何对 Core Principles 或 Governance 的修改 MUST 通过明确的修订提案（可以是
PR 描述、issue 或对话记录）说明变更内容与理由，并 MUST 更新本文件顶部的 Sync Impact Report
以及版本号。修订 MUST 同步检查并在必要时更新 `.specify/templates/plan-template.md`、
`spec-template.md`、`tasks-template.md` 及相关 `speckit-*` 命令/技能定义，确保无过期引用。

**版本策略**：版本号遵循语义化版本 MAJOR.MINOR.PATCH：
- MAJOR：向后不兼容的治理规则变更，或废止/重新定义现有 Core Principle；
- MINOR：新增 Principle 或章节，或对现有指导做实质性扩展；
- PATCH：措辞澄清、错别字修正、非语义性修订。

**合规性审查**：所有涉及 Agent Runtime、Planner/Grounder/Verifier、恢复引擎、自进化/回放
自愈的 PR 与代码评审 MUST 显式检查是否违反本文件的 Core Principles 与工程安全约束；如需
偏离（例如临时绕过验证独立性以支持调试），MUST 在实现计划的 Complexity Tracking 中记录
偏离原因、替代方案评估与移除时间表。

**Version**: 1.0.0 | **Ratified**: 2026-07-20 | **Last Amended**: 2026-07-20
