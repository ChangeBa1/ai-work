<!--
Sync Impact Report
- Version change: 1.1.0 → 1.2.0
- Rationale: MINOR bump — engineering and privacy constraints now define
  content-addressed screenshot persistence, logical-capture audit records, and
  explicit no-private-persistence behavior for sensitive-input steps. No Core
  Principle was removed or weakened.
- Modified principles: none.
- Modified constraints:
  - 资源约束（弱配置电脑）— a successfully captured image MUST be durably
    represented immediately, but an exact duplicate MAY reuse an already
    persisted physical image when a new immutable logical record is written.
  - 凭据与隐私 — steps that prohibit post-input screenshot persistence MUST
    also prohibit private/unmasked physical artifacts; in-memory use remains
    subject to the declared policy and must be released promptly.
  - 制品与可观测性 — complete trace explicitly separates logical capture
    records from content-addressed physical image files.
- Added sections: none.
- Removed sections: none.
- Governance changes:
  - 合规性审查 now requires screenshot-storage changes to verify logical trace
    completeness, physical deduplication references, and sensitive-step
    persistence policy.
- Templates requiring updates:
  - ✅ .specify/templates/plan-template.md — generic Constitution Check already
    derives project-specific gates from this file; no edit required.
  - ✅ .specify/templates/spec-template.md — no hardcoded persistence rule; no
    edit required.
  - ✅ .specify/templates/tasks-template.md — existing security, observability,
    and cross-cutting task categories remain compatible; no edit required.
  - ✅ .specify/templates/checklist-template.md — no hardcoded persistence rule;
    no edit required.
  - ✅ `.agents/skills/speckit-*/SKILL.md` — commands read the Constitution
    generically; no project-specific wording required synchronization.
- Follow-up TODOs: none.
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

### VI. 业务无关核心与声明式场景隔离 (Domain-Agnostic Core and Declarative Scenario Isolation)
本项目是通用的、业务无关的、基于 GUI 的 AI 规范驱动测试框架。生产核心代码——包括
domain、runtime、planning、grounding、execution、verification、reporting、recovery、
config——MUST NOT 包含任何被测应用、行业、页面或测试场景专用的字段、关键词、状态、
操作类别、期望值或流程分支。

POS、购物车、支付、登录、订单、文件上传等业务语义，只允许存在于：(1) 测试用例 YAML；
(2) 示例和离线回归 fixture；(3) 通过通用接口注册的可选场景 profile。业务语义 MUST NOT
成为核心模型的固定字段或默认行为。

运行前置条件、状态事实、动作审计分类、禁止动作和计数规则，MUST 使用用户声明的通用
key/value、tag、matcher 和 assertion 表达，MUST NOT 为具体业务创建固定字段。

事故场景 MAY 作为回归样本，但规范性需求和公共接口 MUST 从事故中抽象出通用不变量，
MUST NOT 将事故的业务细节直接固化进核心契约。任何声称为通用框架能力的变更，MUST 至少
使用两个互不相关的 GUI 场景（例如不同行业或不同页面流程）验证，防止实现只适配单一
测试用例。

理由：本项目的核心价值是可复用于任意 GUI 被测应用的通用测试能力；一旦核心代码渗入
特定业务语义，框架就退化为单一场景的脚本集合，丧失可移植性、可维护性以及作为通用
产品的可信度。

## 工程与安全约束 (Engineering & Safety Constraints)

**黑盒边界**：系统 MUST 仅通过 VNC 获取屏幕像素、发送键盘鼠标事件；MUST NOT 读取 Windows
UIA 控件树、进程信息、文件系统、注册表、浏览器 DOM 或被测应用内部接口。

**架构约束**：MVP 阶段 MUST 采用单进程模块化单体架构，仅运行一个 Agent 进程、一个 VNC
会话、一个测试任务、一个 SQLite 数据库、一个本地产物目录。MVP 阶段 MUST NOT 引入 MCP、
LangGraph、Temporal、Kafka、Kubernetes、分布式数据库或本地大型视觉模型；模块间 MUST 通过
Python Protocol 与内部注册表解耦，理由是高频截图与键鼠调用不适合承受远程协议开销。

**资源约束（弱配置电脑）**：系统 MUST 同时只处理一个 VNC 会话、及时释放截图内存、仅保留
最近 3～5 帧于内存。每次成功截图 MUST 立即形成不可变逻辑采集记录；首次出现的唯一像素内容
MUST 立即持久化为物理图片，严格相同且符合复用边界的后续截图 MAY 通过内容寻址引用已持久化
图片而不重复写入，但 MUST 保留独立时间戳、步骤关联、内容身份与复用来源。系统 MUST 按需加载
OCR 模型、不同时加载多个本地模型；页面
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
日志 MUST 自动过滤敏感字段；截图 MUST 支持敏感区域打码。密码输入或其他声明禁止持久化的
步骤默认 MUST NOT 保存输入后的未遮罩局部截图，也 MUST NOT 创建 private/unmasked 物理制品；
若策略允许模型使用该画面，只能在内存中短暂使用并及时释放，报告和公开制品仍只能引用安全
遮罩证据。

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

**制品与可观测性**：每次运行 MUST 保存完整运行轨迹（状态迁移、每次截图的逻辑采集记录、
内容寻址物理图片引用、模型请求/响应、验证证据），并 MUST 能生成 HTML 与 JSON 报告。多个
逻辑采集记录 MAY 引用同一份已认证物理图片，但 MUST NOT 合并、删除或隐去任一次采集；日志
MUST 采用结构化 JSON Lines 格式，至少包含 run_id、step_id、state、event、耗时等字段。

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
偏离原因、替代方案评估与移除时间表。涉及 domain、runtime、planning、grounding、
execution、verification、reporting、recovery、config 的 PR 与代码评审 MUST 另外显式
检查：核心代码是否出现业务专用字段或关键词（违反 Principle VI）；业务数据是否仅存在于
testcase/fixture/profile 而非核心模型固定字段；声称通用的框架能力变更是否附带至少两个
互不相关 GUI 场景的跨场景契约测试。涉及截图存储的变更还 MUST 检查：每次成功采集是否有
独立逻辑记录；重复物理图片是否有可追溯来源；禁止 private 持久化的敏感步骤是否未产生未遮罩
物理制品。

**Version**: 1.2.0 | **Ratified**: 2026-07-20 | **Last Amended**: 2026-07-22
