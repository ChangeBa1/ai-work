# GitHub Spec Kit 中文教程

> 基于 GitHub 官方 [Spec Kit 文档](https://github.github.com/spec-kit/) 与 [github/spec-kit 仓库](https://github.com/github/spec-kit) 编写。核对日期：2026-07-19；当时最新稳定版为 [v0.13.0](https://github.com/github/spec-kit/releases/tag/v0.13.0)。Spec Kit 仍在快速演进，实际使用时请先运行 `specify version` 和 `specify self check`。

## 目录

- [1. Spec Kit 是什么](#1-spec-kit-是什么)
- [2. 核心工作方式](#2-核心工作方式)
- [3. 环境要求与安装](#3-环境要求与安装)
- [4. 初始化项目](#4-初始化项目)
- [5. 完整实战：开发一个任务管理功能](#5-完整实战开发一个任务管理功能)
- [6. 产物与目录结构](#6-产物与目录结构)
- [7. 命令速查](#7-命令速查)
- [8. 如何写出高质量输入](#8-如何写出高质量输入)
- [9. 已有项目与需求变更](#9-已有项目与需求变更)
- [10. 多功能并行、Git 与 Monorepo](#10-多功能并行git-与-monorepo)
- [11. AI 编程工具集成](#11-ai-编程工具集成)
- [12. 扩展、预设、Bundle 与 Workflow](#12-扩展预设bundle-与-workflow)
- [13. 团队落地建议](#13-团队落地建议)
- [14. 常见问题与排错](#14-常见问题与排错)
- [15. 最佳实践检查表](#15-最佳实践检查表)

## 1. Spec Kit 是什么

Spec Kit 是 GitHub 开源的“规范驱动开发”（Spec-Driven Development，SDD）工具包。它的核心思想是：**先把要构建的东西写清楚，再让 AI 编程代理依据结构化产物实现，而不是直接用一句模糊提示生成代码。**

传统的 AI 编程常见流程是：

```text
一句需求 → AI 直接写代码 → 反复补充提示 → 需求、设计和代码逐渐失去一致性
```

Spec Kit 将流程改成：

```text
项目原则 → 功能规范 → 澄清 → 技术计划 → 质量清单
        → 可执行任务 → 一致性分析 → 实现 → 收敛检查
```

每个阶段产生 Markdown 产物，后一个阶段以前一个阶段为上下文。这样做的价值包括：

- 将“要什么、为什么要”与“如何实现”分开；
- 在写代码前暴露歧义、遗漏、冲突和不可测试的要求；
- 让需求、技术设计、任务和实现可审查、可追溯；
- 给 AI 稳定而结构化的上下文，减少一轮轮临时提示造成的漂移；
- 同一套方法可搭配多种 AI 编程工具，不绑定单一代理。

Spec Kit 不是项目管理平台，也不是自动保证正确性的魔法工具。最终仍需要工程师确认需求、架构、安全性、测试结果和代码质量。

## 2. 核心工作方式

### 2.1 两种推荐流程

小功能可以采用短流程：

```text
specify → plan → tasks → implement → converge
```

生产功能建议采用完整流程：

```text
constitution
    ↓
specify → clarify → plan → checklist → tasks → analyze → implement ⇄ converge
```

各阶段职责如下：

| 阶段 | 解决的问题 | 主要产物/结果 |
| --- | --- | --- |
| `constitution` | 团队必须长期遵守什么原则？ | `.specify/memory/constitution.md` |
| `specify` | 构建什么？为什么构建？ | 功能目录与 `spec.md` |
| `clarify` | 需求里还有哪些关键歧义？ | 回答写回 `spec.md` |
| `plan` | 用什么技术和架构实现？ | `plan.md` 及研究、数据模型、契约等设计产物 |
| `checklist` | 需求本身是否完整、明确、可验证？ | `checklists/*.md` |
| `tasks` | 具体按什么顺序工作？ | `tasks.md` |
| `analyze` | spec、plan、tasks 是否冲突或漏项？ | 只读分析报告 |
| `implement` | 如何执行任务并产出代码？ | 代码、测试和任务状态更新 |
| `converge` | 代码是否真正满足所有产物？ | 收敛结果；若有缺口则向 `tasks.md` 追加任务 |

### 2.2 两类命令不要混淆

Spec Kit 有两类入口：

1. **终端 CLI 命令**：安装、初始化和维护 Spec Kit，例如 `specify init`、`specify version`。
2. **AI 编程代理命令**：在 Copilot、Claude、Codex 等代理对话中执行 SDD 阶段，例如 `/speckit.specify`。

不同代理的调用形式可能不同：

| 集成方式 | 示例 |
| --- | --- |
| 大多数 slash command 集成 | `/speckit.specify` |
| Codex 等 skills 模式 | `$speckit-specify` |
| Kimi skills 模式 | `/skill:speckit-specify` |

下文统一写成 `/speckit.*`。如果你的代理安装的是 skill，请换成该代理显示的形式，步骤和含义不变。

## 3. 环境要求与安装

### 3.1 前置条件

官方当前要求/建议：

- Windows、macOS 或 Linux；
- Python 3.11+；
- 推荐使用 [uv](https://docs.astral.sh/uv/) 管理工具，也可使用 pipx 或 pip；
- 一个受支持的 AI 编程代理；
- Git 为可选项，只有启用 `git` 扩展时才是必需的。

先检查环境：

```bash
python --version
uv --version
git --version
```

### 3.2 推荐：固定 GitHub 发布版安装

固定版本更适合团队和可复现环境。以下版本号只是本教程核对时的最新值：

```bash
uv tool install specify-cli \
  --from git+https://github.com/github/spec-kit.git@v0.13.0
```

升级时应先查看 [Releases](https://github.com/github/spec-kit/releases)，并保留 tag 前面的 `v`。

### 3.3 从 PyPI 安装

```bash
# 推荐
uv tool install specify-cli

# 或
pipx install specify-cli

# 也可以，但隔离性较弱
pip install specify-cli
```

固定 PyPI 版本：

```bash
uv tool install specify-cli==0.13.0
```

### 3.4 验证、检查与升级

```bash
# 本地版本、Python、平台和架构信息
specify version

# 查看本地 CLI 支持的能力，不访问网络
specify version --features
specify version --features --json

# 检查代理工具，保持离线
specify check

# 只检查 Spec Kit 是否有新版，不修改安装
specify self check

# 预览升级动作
specify self upgrade --dry-run

# 升级到最新稳定版；该命令会立即执行
specify self upgrade

# 固定到指定 tag
specify self upgrade --tag v0.13.0
```

注意：一次性 `uvx` 运行只使用临时副本，不会升级 PATH 上持久安装的 `specify`。

## 4. 初始化项目

### 4.1 新建项目

```bash
specify init taskify --integration copilot
cd taskify
```

如果不写 `--integration`，交互式终端会提示选择；非交互环境默认选择 Copilot，因此在 CI 中最好显式指定。

常见集成示例：

```bash
specify init taskify --integration claude
specify init taskify --integration gemini
specify init taskify --integration copilot
specify init taskify --integration codex
```

可用 key 会随版本变化，以本机输出为准：

```bash
specify integration list
specify integration search
```

### 4.2 初始化当前目录

```bash
cd existing-project
specify init --here --integration codex

# 等价的项目路径写法
specify init . --integration codex
```

若目录非空并需要合并/覆盖托管文件：

```bash
specify init --here --force --integration codex
```

`--force` 可能覆盖共享模板、脚本或 constitution。执行前应提交或备份 `.specify/` 中的自定义内容，并检查 diff。

### 4.3 其他常用选项

```bash
# Windows 或明确使用 PowerShell 脚本
specify init taskify --integration copilot --script ps

# Linux/macOS 或明确使用 shell 脚本
specify init taskify --integration copilot --script sh

# 只生成模板，不检查对应 AI 代理是否已安装
specify init taskify --integration claude --ignore-agent-tools

# 初始化时安装预设
specify init taskify --integration copilot --preset compliance
```

初始化后，启动所选 AI 编程代理，并确认它能看到 `speckit` 命令。Linux/macOS 的脚本位于 `.specify/scripts/bash/`，Windows 默认脚本位于 `.specify/scripts/powershell/`。

## 5. 完整实战：开发一个任务管理功能

下面以已有项目中增加一个轻量任务看板为例。命令输入到 **AI 编程代理的对话框**，不是普通 shell。

### 5.1 建立项目宪章

宪章是跨功能的工程规则，应稳定、可验证、少而精。首次使用项目时运行：

```text
/speckit.constitution
项目原则：
1. 所有外部输入必须在系统边界验证；
2. 核心业务逻辑必须有单元测试，关键用户流程必须有集成测试；
3. API 变更必须向后兼容，破坏性变更需显式版本化；
4. 可访问性满足 WCAG 2.2 AA；
5. 不记录令牌、密码和用户私密内容；
6. 优先选择简单、可维护的设计，新增依赖必须说明理由。
```

检查 `.specify/memory/constitution.md`：原则是否明确？是否能在 plan、tasks 和评审中被实际验证？不要把短期功能需求写进宪章。

### 5.2 编写功能规范

`specify` 阶段只描述“做什么、为何做、边界是什么”，不要提前指定框架和数据库。

```text
/speckit.specify
为 5～20 人的小团队增加任务看板。团队成员可以创建任务、指派负责人、
设置截止日期、评论，并把任务在“待处理、进行中、评审中、已完成”四列之间移动。
产品负责人可以调整任务优先级。普通成员不能删除其他人创建的任务。

第一版不包含：文件附件、子任务、跨团队共享、工时统计。

验收重点：
- 新任务创建后立即出现在“待处理”；
- 移动任务后，其他在线成员在 2 秒内看到新状态；
- 每次状态和负责人变化都保留操作者及时间；
- 网络失败时显示明确错误，不允许界面静默展示未保存状态。
```

审查生成的 `spec.md`，重点看：

- 用户故事是否按价值独立排序；
- 每个故事能否单独演示和验收；
- 功能需求是否无歧义且可测试；
- 边界情况、失败场景、权限和非目标是否明确；
- 成功标准是否技术无关且可度量。

### 5.3 澄清歧义

```text
/speckit.clarify
重点澄清权限、并发编辑、实时更新失败、任务删除策略和截止日期时区。
```

代理会提出少量高价值问题。回答时给出明确选择及理由，例如：

```text
采用软删除，仅产品负责人可以删除；所有日期以 UTC 存储，界面按用户时区显示；
并发更新采用乐观并发控制，冲突时不自动覆盖，提示用户刷新后重试。
```

确认答案已经回写 `spec.md`。如果仍存在高风险模糊点，可再次聚焦运行 `clarify`，但不要用它替代团队的产品决策。

### 5.4 制定技术计划

现在才描述“如何实现”：

```text
/speckit.plan
后端使用 TypeScript、Node.js 22、Fastify 和 PostgreSQL 16；
前端使用 React、Vite 和 TypeScript；实时更新使用 Server-Sent Events；
沿用仓库现有测试、日志和鉴权方案，不引入新的 ORM。
REST API 使用 OpenAPI 描述。数据库迁移必须可回滚。
```

检查 `plan.md` 和相关设计产物：

- 技术选择是否满足 constitution；
- 数据模型、API 契约和错误模型是否覆盖 spec；
- 不确定技术点是否有研究结论，而非未经验证的假设；
- 是否复用项目现有模式；
- 安全、可观测性、迁移、回滚和测试策略是否明确；
- 是否出现无需求支撑的过度设计。

### 5.5 生成需求质量清单

```text
/speckit.checklist
为权限、并发一致性、实时更新、可访问性和错误恢复生成需求质量清单。
```

Checklist 检查的是“需求写得好不好”，不是测试应用运行是否正确。例如“是否定义了连接中断后的界面行为？”是需求质量问题；“断网后点击保存能否显示错误？”属于实现后的测试。

如果清单暴露缺口，先改 `spec.md`，不要带着已知缺口继续拆任务。

### 5.6 拆解任务

```text
/speckit.tasks
```

高质量 `tasks.md` 应具备：

- 按依赖和用户故事排序；
- 初始化、基础设施、故事实现、收尾阶段清楚；
- 每个任务包含可定位的文件路径；
- 可并行任务有明确标记；
- 测试任务与功能任务关联；
- 每个用户故事可以独立完成和验证；
- 数据迁移、文档、监控和回滚没有被漏掉。

### 5.7 跨产物一致性分析

```text
/speckit.analyze
```

`analyze` 是只读质量门，检查 `spec.md`、`plan.md`、`tasks.md` 以及 constitution 之间的冲突、重复、歧义和覆盖缺口。发现问题时按源头修复：

- 需求错了，改 `spec.md`；
- 技术方案错了，改 `plan.md`；
- 工作漏了，改 `tasks.md`；
- 修改后重新生成下游产物并再次分析。

不要要求 `analyze` 直接悄悄改掉所有内容，否则会失去对需求决策的控制。

### 5.8 分阶段实现

小功能可直接运行：

```text
/speckit.implement
```

大型功能建议一次执行一个阶段或一个用户故事：

```text
/speckit.implement 只完成基础设施阶段，运行相关测试后停止并汇报改动。
```

每个阶段后都应人工检查：

```bash
git diff --stat
git diff
# 再运行项目自己的 lint、类型检查和测试命令
```

不要把任务被勾选等同于验收通过。至少验证代码、测试、迁移、安全边界和实际用户流程。

### 5.9 收敛检查

```text
/speckit.converge
```

`converge` 将当前代码与 spec、plan、tasks 对照。如果发现缺口，会向 `tasks.md` 追加剩余任务。继续执行：

```text
/speckit.implement
/speckit.converge
```

直到报告已收敛，再进入代码评审和 PR。它是完成性检查，不替代独立测试、安全审查和人工验收。

## 6. 产物与目录结构

典型项目结构大致如下；具体文件会因版本、集成和功能复杂度而不同：

```text
project/
├── .specify/
│   ├── feature.json              # 当前活动功能状态
│   ├── memory/
│   │   └── constitution.md       # 项目宪章
│   ├── scripts/
│   │   ├── bash/                 # shell 自动化脚本
│   │   └── powershell/           # PowerShell 自动化脚本
│   ├── templates/                # 核心模板
│   │   └── overrides/            # 项目级模板覆盖
│   ├── extensions/               # 扩展相关内容
│   └── presets/                  # 预设相关内容
├── specs/
│   └── 001-task-board/
│       ├── spec.md               # 功能需求、用户故事、成功标准
│       ├── plan.md               # 技术实现计划
│       ├── research.md           # 技术研究与决策（按需）
│       ├── data-model.md         # 数据模型（按需）
│       ├── quickstart.md          # 验证/使用说明（按需）
│       ├── contracts/            # API/接口契约（按需）
│       ├── checklists/           # 需求质量清单
│       └── tasks.md              # 依赖排序的实施任务
└── <agent-specific-directory>/   # 代理命令或 skill 文件
```

重要认知：新版 Spec Kit 默认不依赖 Git 分支来判断活动功能。活动功能主要记录在 `.specify/feature.json`，可用 `SPECIFY_FEATURE_DIRECTORY` 覆盖。仅切换 Git 分支不会自动切换 Spec Kit 的活动功能。

## 7. 命令速查

### 7.1 AI 代理核心命令

| 命令 | 用途 | 推荐时机 |
| --- | --- | --- |
| `/speckit.constitution` | 创建/更新项目原则 | 项目首次采用或原则变更时 |
| `/speckit.specify` | 创建功能规范 | 每个新功能开始时 |
| `/speckit.clarify` | 识别并消除歧义 | `specify` 后、`plan` 前 |
| `/speckit.plan` | 生成技术实现计划 | 需求稳定后 |
| `/speckit.checklist` | 生成需求质量清单 | 拆任务前 |
| `/speckit.tasks` | 生成依赖排序任务 | plan 完成后 |
| `/speckit.analyze` | 跨产物只读分析 | tasks 后、implement 前 |
| `/speckit.implement` | 按任务实现 | 质量门通过后 |
| `/speckit.converge` | 对照代码与产物、补充剩余任务 | 实现后反复运行至收敛 |
| `/speckit.taskstoissues` | 将任务转换为 GitHub Issues | 团队用 Issues 跟踪执行时 |

`taskstoissues` 会产生外部状态变更。使用前检查目标仓库、任务粒度、标签和权限，并先让代理展示拟创建内容。

### 7.2 终端 CLI 常用命令

```bash
# 初始化与诊断
specify init --help
specify version
specify check
specify self check

# 集成
specify integration list
specify integration status
specify integration status --json
specify integration install <key>
specify integration use <key>
specify integration switch <key>
specify integration upgrade <key>
specify integration uninstall <key>

# 发现扩展/预设/Bundle
specify extension search
specify preset search
specify bundle search
specify bundle info <bundle-id>
```

准确选项以当前安装版本的 `--help` 和[官方 CLI 参考](https://github.github.com/spec-kit/reference/core.html)为准。

## 8. 如何写出高质量输入

各阶段命令都可以直接跟一段结构化文本作为输入。总原则是：只给出该阶段真正需要决策的信息，不要越权提供下一阶段才该决定的内容（例如在 `specify` 里定技术栈，在 `constitution` 里定 UI 框架）。以下按工作流顺序给出每个命令的模板与好、差例子。

### 8.1 `/speckit.constitution` 输入模板

宪章条款应是稳定、可验证、可追责的规则，而不是口号。每条建议包含规则、理由、验证方式、例外审批四要素。

```text
/speckit.constitution
原则 1：<一句话规则>
理由：<为什么需要，不写会出什么问题>
验证方式：<在哪个环节、用什么方法检查是否遵守>
例外：<什么情况可以偏离，谁能批准>

原则 2：...
```

好例子：

```text
/speckit.constitution
原则 1：所有外部输入必须在系统边界完成校验。
理由：未校验输入是历史上多次安全和数据错误事故的根源。
验证方式：code review 检查每个 API 入口是否有校验逻辑；新增端点缺少校验视为阻断项。
例外：内部服务间调用若已在网关层统一校验，可在 plan 中说明并豁免。

原则 2：核心业务逻辑必须有单元测试，关键用户流程必须有集成测试。
理由：没有第二个人做人工回归测试，靠自动化测试防止回归。
验证方式：tasks 阶段每个业务逻辑任务必须关联对应测试任务；implement 后检查覆盖率报告。
例外：纯展示性、无业务规则的组件可以豁免。
```

差例子：

```text
/speckit.constitution
1. 代码要写得优雅、可读性强；
2. 系统性能要好，用户体验要流畅；
3. 尽量使用最新最好的技术栈。
```

问题：三条都无法验证（什么叫“优雅”？“好”？“最新最好”？）；第 3 条还把技术选型这种应该留到 `plan` 阶段的决定提前混进了宪章，一旦技术栈变化就要跟着改，失去了稳定性。

### 8.2 `/speckit.specify` 输入模板

只描述“做什么、为何做、边界是什么”，不要提前指定框架和数据库。

```text
/speckit.specify
目标用户：<谁使用>
问题与目标：<为什么需要>
核心场景：<用户如何使用>
业务规则：<权限、状态、约束>
成功标准：<可度量、与具体技术无关>
失败与边界：<异常、空状态、并发、限制>
明确不做：<本期非目标>
```

好例子：

```text
用户提交订单后 2 秒内看到确认状态；重复点击不能产生重复订单；
支付结果未知时显示“处理中”，不得显示“支付失败”。第一版不支持拆单。
```

差例子：

```text
用 React 和 Redis 做一个漂亮、快速、完善的订单系统。
```

问题：混入了技术方案（React、Redis 属于 `plan` 阶段），且“漂亮、快速、完善”不可验收。

### 8.3 `/speckit.clarify` 输入模板

指出你想聚焦澄清的具体风险点，不要只说“帮我看看还有什么问题”——那样等于把决策权完全交给 AI 猜，容易问出一堆低价值问题，却漏掉真正的高风险歧义。

```text
/speckit.clarify
重点澄清：<列出你判断风险最高、最容易产生歧义的几个方面>
```

好例子：

```text
/speckit.clarify
重点澄清权限、并发编辑、实时更新失败、任务删除策略和截止日期时区。
```

差例子：

```text
/speckit.clarify
帮我看看这个 spec 还有什么问题。
```

问题：没有指出你自己已经意识到的风险点，AI 只能均匀地在全文范围内提问，容易在你已经想清楚的地方浪费问题配额，漏问你自己没意识到、但其实该问的地方。

### 8.4 `/speckit.plan` 输入模板

现在才描述“如何实现”。要明确复用约束，不要让 AI 在没有仓库上下文的情况下自由发挥。

```text
/speckit.plan
现有技术栈：<语言、框架、运行时>
必须复用：<鉴权、日志、数据库、组件库>
架构约束：<部署边界、兼容性、合规要求>
接口与存储：<协议、数据库、迁移要求>
质量要求：<测试、性能、安全、可观测性>
禁止事项：<不能引入的依赖或服务>
```

好例子：

```text
后端使用 TypeScript、Node.js 22、Fastify 和 PostgreSQL 16；
前端使用 React、Vite 和 TypeScript；实时更新使用 Server-Sent Events；
沿用仓库现有测试、日志和鉴权方案，不引入新的 ORM。
REST API 使用 OpenAPI 描述。数据库迁移必须可回滚。
```

差例子：

```text
帮我选个最好的技术栈，越快做完越好。
```

问题：没有给出现有技术栈和复用约束，AI 只能凭空假设一套架构，极可能与仓库现状冲突；“最好”“越快”无法作为设计输入，也无法在后续 `analyze` 阶段验证是否达成。

### 8.5 `/speckit.checklist` 输入模板

指定要检查的需求维度，而不是笼统地说“检查一下”。

```text
/speckit.checklist
为<维度1、维度2、维度3...>生成需求质量清单。
```

好例子：

```text
为权限、并发一致性、实时更新、可访问性和错误恢复生成需求质量清单。
```

差例子：

```text
帮我检查一下这个功能写得完不完整。
```

问题：没有指定维度，checklist 容易停留在泛泛的完整性检查（有没有写标题、有没有写验收标准），漏掉真正容易出问题的高风险维度，比如并发一致性或权限边界。

### 8.6 `/speckit.tasks` 输入模板

多数情况下直接运行 `/speckit.tasks` 即可，但如果希望控制任务的组织方式，可以显式说明。

```text
/speckit.tasks
拆分方式：<按用户故事 / 按技术层，通常建议按用户故事>
并行标记：<是否需要标注可并行任务>
其他要求：<迁移、监控、文档等是否必须单独立项>
```

好例子：

```text
/speckit.tasks
按用户故事拆分任务，不要按技术层（前端/后端/数据库）拆分；
标注可并行执行的任务；数据迁移和监控告警需要单独任务，不要隐藏在某个功能任务里。
```

差例子：

```text
/speckit.tasks 快点弄完
```

问题：没有说明期望的组织方式，容易生成按技术层划分的任务列表（比如“写后端接口”“写前端页面”），导致每个用户故事无法独立完成和验收，与 5.6 节的高质量标准相悖。

### 8.7 `/speckit.analyze` 输入模板

`analyze` 是只读质量门，通常无需额外输入；项目较大时，可以指定本轮重点核对的产物关系。

```text
/speckit.analyze
本轮重点核对：<例如 spec 与 plan 之间关于某个主题的一致性>
```

好例子：

```text
/speckit.analyze
重点核对 spec 和 plan 之间关于并发编辑处理方式的一致性，以及 constitution 中测试要求是否都已体现在 tasks 里。
```

差例子：

```text
/speckit.analyze 有问题就直接都改了
```

问题：`analyze` 的职责是只读分析、暴露冲突，不是代为决策修改。要求它“直接都改了”会让你失去对需求和技术决策的控制权，应按 5.7 节的做法自己判断问题源头（spec/plan/tasks）后手动或分步修正。

### 8.8 `/speckit.implement` 输入模板

大功能必须给出阶段边界和验证要求，不要一次性全做。

```text
/speckit.implement
范围：<本次只做哪个阶段或哪个用户故事>
验证要求：<完成后运行哪些测试、达到什么条件才算完成>
停止条件：<做完后是否需要停下汇报，而不是继续下一阶段>
```

好例子：

```text
/speckit.implement 只完成基础设施阶段，运行相关测试后停止并汇报改动。
```

差例子：

```text
/speckit.implement 全部做完
```

问题：没有阶段边界，容易一次产生大量改动，难以逐段审查和回滚；也没有要求运行测试，任务被勾选不等于验收通过（5.8 节）。

### 8.9 `/speckit.converge` 输入模板

通常直接运行即可；需要聚焦复查时，可以指定关注的验收标准范围。

```text
/speckit.converge
本轮重点核对：<哪些验收标准或用户故事需要重点确认代码是否真正实现>
```

好例子：

```text
/speckit.converge
重点核对权限控制和并发冲突提示这两条验收标准是否都已在代码中体现。
```

差例子：

```text
/speckit.converge 有缺口就算了，先发布
```

问题：`converge` 存在的意义就是发现代码与产物之间的缺口并追加任务；主动跳过缺口去发布，等于放弃了这道收敛检查门禁，违背了它在工作流中的作用（5.9 节）。

### 8.10 `/speckit.taskstoissues` 输入模板

会产生外部状态变更（创建仓库 issue），必须明确目标、粒度和预览要求。

```text
/speckit.taskstoissues
目标仓库：<org/repo>
粒度：<按任务级别 / 按用户故事级别>
标签：<需要打上的标签>
是否先预览：<是，先展示拟创建内容，确认后再创建>
```

好例子：

```text
/speckit.taskstoissues
目标仓库 org/repo，按用户故事级别创建 issue（不要按单个任务），
添加标签 area:task-board，先展示将创建的 issue 列表，确认后再实际创建。
```

差例子：

```text
/speckit.taskstoissues 帮我建好 issue
```

问题：没有指定目标仓库、粒度和标签，也没有要求先预览，容易在错误的仓库里产生大量难以撤销的外部状态变更（7.1 节提示该命令使用前应先让代理展示拟创建内容）。

## 9. 已有项目与需求变更

官方将规格持续维护概括为三种模型。

### 9.1 Flow-forward：旧规格作为历史记录

适合按功能目录保留审计历史。每次重要新增或后续变化都新建功能规格：

```text
新 specify → plan → tasks → implement → converge
```

旧功能目录保持不变，并在新旧规格间建立链接。优点是历史清楚；缺点是当前完整行为可能分散在多个目录。

### 9.2 Living spec：spec.md 是持续更新的契约

适合希望一个规格始终代表当前预期行为的团队：

1. 在干净工作树或专用分支中开始；
2. 用 `clarify` 或显式编辑更新 `spec.md`；
3. 重新生成或更新 `plan.md`；
4. 重新生成或更新 `tasks.md`；
5. 运行 `analyze`；
6. `implement` 后同时审查代码与产物 diff；
7. 反复 `converge` 与 `implement` 直到收敛。

重生成前把仍然有效的重要技术决策带入新产物，避免覆盖时丢失。

### 9.3 Flow-back：实现发现反向修正规格

适合探索性较强的工作。新认识可以先出现在代码、任务、计划或规格中，但必须判断它影响的是行为、方案还是任务，然后同步所有受影响产物并运行 `analyze`。

关键规则：如果 `spec.md` 被团队视为可信契约，就不能让代码已经改变而 spec 仍描述旧行为。

### 9.4 Brownfield 使用建议

在已有代码库中，不要让代理从空白假设架构：

- 在 plan 中明确要求先阅读现有模块、测试、ADR 和约定；
- constitution 只写仓库真实执行的规则；
- 先选择一个边界清楚的中小功能试点；
- 强调兼容性、迁移和回滚；
- 分阶段 implement，每阶段审查 diff；
- 不要用 `--force` 无检查地刷新已有自定义模板。

## 10. 多功能并行、Git 与 Monorepo

### 10.1 活动功能由状态决定

Spec Kit 通过 `.specify/feature.json` 记录活动功能，也可通过环境变量明确指定：

```bash
export SPECIFY_FEATURE_DIRECTORY=specs/002-notifications
```

不要认为 `git checkout feature-x` 就会切换活动规格。执行命令前检查目标功能目录，尤其在多个功能并行时。

### 10.2 Git 是可选扩展

核心 Spec Kit 不默认创建 Git 仓库或功能分支。需要编号功能分支工作流时安装 git 扩展：

```bash
specify extension add git
```

安装社区或扩展代码前先查看来源和内容。Git 扩展创建分支后，活动功能仍以 Spec Kit 状态为准。

### 10.3 Monorepo

Spec Kit 项目以包含 `.specify/` 的目录为边界。同一个 monorepo 可有多个独立 Spec Kit 项目：

```text
my-monorepo/
├── .git/
├── apps/web/.specify/
├── apps/api/.specify/
└── packages/ui/.specify/
```

分别初始化：

```bash
specify init apps/web --integration codex
specify init apps/api --integration codex
```

从仓库根目录定位成员项目：

```bash
export SPECIFY_INIT_DIR=apps/web
specify integration status
```

`SPECIFY_INIT_DIR` 必须指向包含 `.specify/` 的项目根目录；写错会直接报错，不会回退到当前目录。它选择“项目”，`SPECIFY_FEATURE_DIRECTORY` 选择该项目中的“功能”，二者可以组合。

单一 Git 仓库的 monorepo 中，即使各成员项目有独立 `.specify/` 和 `specs/`，Git 分支仍属于共享的根仓库。

## 11. AI 编程工具集成

Spec Kit 支持 30 多种代理，实际列表以当前 CLI 为准：

```bash
specify integration list
specify integration info <key>
```

### 11.1 查看状态

```bash
specify integration status
specify integration status --json
```

状态报告可显示默认集成、已安装集成、托管文件缺失或被修改、共享基础设施健康度等。JSON 形式适合 CI。

### 11.2 安装、切换和升级

```bash
# 增加另一个集成，不改变默认集成
specify integration install <key>

# 将已安装集成设为默认
specify integration use <key>

# 切换；目标未安装时会完成卸载/安装流程
specify integration switch <key>

# CLI 升级后刷新集成模板
specify integration upgrade <key>
```

Spec Kit 会记录托管文件原始哈希。卸载时，未修改文件可自动删除，手工修改过的文件默认保留；`--force` 会提高覆盖或删除风险，应先检查状态和版本控制 diff。

### 11.3 多集成团队

一个项目可以安装多个集成，适合团队成员使用不同代理。不过只有声明为 multi-install safe 的组合才会自动允许；其他组合需要显式 `--force`。共享模板仍跟随一个默认集成，因此团队应约定：

- 默认集成是什么；
- 哪些代理目录提交到仓库；
- 谁负责 CLI 与集成模板升级；
- 如何审查生成文件变化。

## 12. 扩展、预设、Bundle 与 Workflow

### 12.1 Extension：增加新能力

扩展适合新增命令、阶段或外部服务集成：

```bash
specify extension search
specify extension add <extension-name>
```

例如 Git 工作流、Jira 集成、代码评审阶段、测试追踪或架构治理。

### 12.2 Preset：改变现有流程和模板

预设不一定增加新能力，主要覆盖核心或扩展的模板与命令：

```bash
specify preset search
specify preset add <preset-name>
```

适合组织规范、监管追踪、测试优先任务顺序、领域术语和本地化。多个预设可按优先级叠加。

模板解析优先级从高到低为：

```text
项目本地覆盖 .specify/templates/overrides/
    ↓
Preset 模板 .specify/presets/templates/
    ↓
Extension 模板 .specify/extensions/templates/
    ↓
Spec Kit 核心模板 .specify/templates/
```

只为单个项目调整模板时，优先使用项目本地 overrides，不必创建完整 preset。

### 12.3 Bundle：一次配置一个角色或团队

Bundle 将扩展、预设、步骤和工作流组合为带版本的角色配置：

```bash
specify bundle search
specify bundle info <bundle-id>
specify bundle install <bundle-id>
specify bundle list
specify bundle update <bundle-id>
specify bundle remove <bundle-id>
```

安装前先用 `info` 查看精确组件集合。官方设计保证 `info` 展示的内容与 `install` 一致，重复安装应保持幂等，删除某 Bundle 时不会删除仍被其他 Bundle 使用的组件。

### 12.4 如何选择

| 目标 | 选择 |
| --- | --- |
| 新增命令、阶段或外部服务集成 | Extension |
| 改写 spec/plan/tasks 格式或组织规则 | Preset |
| 单项目一次性模板调整 | Project-local override |
| 一键配置产品经理、开发者等完整角色环境 | Bundle |
| 编排多个已有步骤的执行顺序 | Workflow |

社区内容由各作者独立维护。安装前应阅读源码、锁定版本，并评估脚本、网络访问、凭据和供应链风险。

## 13. 团队落地建议

### 13.1 从一个试点功能开始

选择 2～5 天可完成、边界清楚、能独立验收的功能。记录以下指标：

- 澄清前后减少了多少返工；
- `analyze` 找出多少真实缺口；
- 产物审查耗时；
- implement 后人工修正量；
- 从开始到验收的总体周期。

### 13.2 把产物纳入代码评审

建议将 `.specify/` 中需要共享的规则、`specs/` 和代理配置纳入版本控制。PR 不只审代码，还审：

- spec 是否表达真实意图；
- plan 是否存在不必要复杂度；
- tasks 是否覆盖迁移、测试、文档和运维；
- 实现变化是否反向更新了可信规格；
- constitution 是否被遵守。

### 13.3 设置质量门

一个实用的生产门禁顺序：

```text
需求负责人批准 spec
→ 技术负责人批准 plan
→ checklist 无关键缺口
→ analyze 无高严重度问题
→ 分阶段 implement + 自动化测试
→ converge 收敛
→ 独立代码评审与验收
```

### 13.4 控制上下文和变更范围

- 一个功能目录聚焦一个可独立交付的价值单元；
- 大型功能按用户故事分阶段实施；
- 每阶段后运行测试并审查 diff；
- 不把未确认产品决策交给 AI 擅自决定；
- 对数据库迁移、生产发布、外部 issue 创建等高影响动作单独确认。

## 14. 常见问题与排错

### 14.1 `specify: command not found`

```bash
uv tool list
uv tool update-shell
```

重新打开终端，再运行 `specify version`。如果用 pipx，检查 `pipx ensurepath`；如果用 pip，确认脚本目录在 PATH 中。

### 14.2 `uv: command not found`

先按 [uv 官方安装说明](https://docs.astral.sh/uv/getting-started/installation/)安装。也可改用 pipx，但不要混装多个来源后误判当前执行版本：

```bash
command -v specify     # Windows PowerShell 使用 Get-Command specify
specify version
```

### 14.3 AI 代理看不到 `/speckit.*`

依次检查：

1. 是否在包含 `.specify/` 的正确项目中启动代理；
2. 初始化时的 `--integration` 是否与当前代理一致；
3. 使用的是 slash command、`$speckit-*` 还是 `/skill:speckit-*`；
4. `specify integration status` 是否报告缺失/修改文件；
5. CLI 升级后是否需要 `specify integration upgrade <key>`；
6. 重启代理，让它重新加载命令或 skills。

### 14.4 命令作用到了错误功能

检查 `.specify/feature.json` 和环境变量：

```bash
printenv SPECIFY_INIT_DIR
printenv SPECIFY_FEATURE_DIRECTORY
```

不要用 Git 分支名推断当前活动功能。明确设置目标后再运行 agent 命令。

### 14.5 `analyze` 报告大量冲突

不要直接跳过。先按层级找源头：产品意图归 spec，技术方案归 plan，执行遗漏归 tasks。修正上游后再生成下游产物，最后重新运行 `analyze`。

### 14.6 `implement` 一次改动过大

让代理按阶段或用户故事执行，并要求每阶段运行相关测试后停止。确保工作树起点干净，以便准确审查和回滚单阶段变化。

### 14.7 强制刷新后担心自定义内容被覆盖

重点检查：

```text
.specify/memory/constitution.md
.specify/templates/
.specify/scripts/
代理专属命令或 skills 目录
```

用版本控制恢复或手工合并。下一次执行 `specify init --here --force` 前，先提交/备份并阅读升级说明。

### 14.8 企业离线环境

官方支持从仓库构建 wheel 并建立离线包集合。参考[离线安装指南](https://github.github.com/spec-kit/install/air-gapped.html)，同时固定 Spec Kit、Python 依赖、扩展、预设和 Bundle 的来源及版本。

## 15. 最佳实践检查表

开始前：

- [ ] `specify version` 符合团队锁定版本；
- [ ] `specify integration status` 正常；
- [ ] 当前项目与活动功能目录正确；
- [ ] 工作树干净或位于专用分支；
- [ ] constitution 是真实、可验证的规则。

规划阶段：

- [ ] spec 只写 what/why，边界和非目标明确；
- [ ] 关键歧义已通过 clarify 解决；
- [ ] plan 才引入技术栈与架构决策；
- [ ] checklist 的关键缺口已回写 spec；
- [ ] tasks 按依赖和用户故事组织；
- [ ] analyze 无未处理的高严重度问题。

实现阶段：

- [ ] 大功能分阶段执行；
- [ ] 每阶段审查 diff 并运行对应测试；
- [ ] 数据迁移、回滚、监控和文档有明确任务；
- [ ] 任务勾选结果经过人工验证；
- [ ] 实现发现已同步回可信产物。

完成阶段：

- [ ] `converge` 已报告收敛；
- [ ] lint、类型检查、单元/集成/E2E 测试通过；
- [ ] 安全、性能、可访问性按需求验证；
- [ ] spec、plan、tasks 与最终代码一并评审；
- [ ] PR/发布说明能够追溯到用户故事和验收标准。

## 参考资料

- [Spec Kit 官方文档首页](https://github.github.com/spec-kit/)
- [官方快速入门](https://github.github.com/spec-kit/quickstart.html)
- [官方安装指南](https://github.github.com/spec-kit/installation.html)
- [核心 CLI 参考](https://github.github.com/spec-kit/reference/core.html)
- [AI 代理集成参考](https://github.github.com/spec-kit/reference/integrations.html)
- [Agentic SDD 命令详解](https://github.github.com/spec-kit/reference/agentic-sdd.html)
- [已有项目规格演进指南](https://github.github.com/spec-kit/guides/evolving-specs.html)
- [Monorepo 指南](https://github.github.com/spec-kit/guides/monorepo.html)
- [GitHub 源码仓库](https://github.com/github/spec-kit)
- [版本发布页](https://github.com/github/spec-kit/releases)

---

本教程是对官方英文资料的中文解释和实践性重组，并非 GitHub 官方中文翻译。命令和行为出现差异时，以你当前安装版本的 `--help`、官方文档和发布说明为准。
