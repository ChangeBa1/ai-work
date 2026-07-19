# WBS 与 Speckit

> 概念笔记：说明工作分解结构（WBS）是什么，以及它与 GitHub Spec Kit（Speckit）的关系与用法。

## 目录

1. [WBS 是什么](#1-wbs-是什么)
2. [Speckit 是什么](#2-speckit-是什么)
3. [二者关系](#3-二者关系)
4. [对照表](#4-对照表)
5. [如何一起用](#5-如何一起用)
6. [一句话总结](#6-一句话总结)

---

## 1. WBS 是什么

**WBS**（Work Breakdown Structure，工作分解结构）是项目管理中把复杂工作拆成可管理小块的方法与产物。

把项目按层次拆解为交付物或工作包，直到每一项都可以估算、分配和跟踪：

```
项目
├── 阶段 / 主要交付物 1
│   ├── 工作包 1.1
│   └── 工作包 1.2
├── 阶段 / 主要交付物 2
│   ├── 工作包 2.1
│   └── 工作包 2.2
└── ...
```

### 1.1 主要作用

| 作用 | 说明 |
|------|------|
| 范围清晰 | 明确「做什么、不做什么」 |
| 便于估算 | 小工作包更容易估工期和成本 |
| 责任到人 | 每项工作可分配责任人 |
| 便于跟踪 | 进度、风险按节点管理 |
| 沟通统一 | 团队对项目结构有共同语言 |

### 1.2 常见拆法

1. **按交付物**（最常用）：网站 → 前端 / 后端 / 数据库 / 测试
2. **按阶段**：启动 → 设计 → 开发 → 测试 → 上线
3. **按组织 / 部门**：市场 / 研发 / 运维
4. **混合**：上层按阶段，下层按交付物

### 1.3 好的 WBS 特点

- **100% 原则**：下层合起来 = 上层全部工作，不漏不重
- **互斥**：同级项之间尽量不重叠
- **可管理**：最底层工作包大小适中（常按几天到一两周）
- **结果导向**：写「完成什么交付物」，而不是「如何做」

### 1.4 简单例子（做一个 App）

```
1.0 手机 App 项目
  1.1 需求与设计
    1.1.1 需求文档
    1.1.2 UI 设计稿
  1.2 开发
    1.2.1 用户登录模块
    1.2.2 核心业务模块
  1.3 测试与上线
    1.3.1 功能测试
    1.3.2 应用商店发布
```

> 其他领域也可能用 WBS 作缩写（如通信中的 Wide Band Spectrum），但在项目管理与软件研发语境下，几乎一定是「工作分解结构」。

---

## 2. Speckit 是什么

**Speckit** 指 [GitHub Spec Kit](https://github.com/github/spec-kit)：面向 **Spec-Driven Development（SDD，规格驱动开发）** 的开源工具包。

核心思想：先把「要建什么」写成结构化规格，再让 AI 编码代理按规格实现，而不是纯 vibe coding。

默认流水线：

```
Spec（规格） → Plan（技术方案） → Tasks（任务拆解） → Implement（实现）
```

对应命令大致为：

| 阶段 | 命令（示意） | 产物 | 关注点 |
|------|--------------|------|--------|
| Spec | `/speckit.specify` | `spec.md` | WHAT / WHY：需求、用户故事、验收标准 |
| Plan | `/speckit.plan` | `plan.md` 及 data-model、contracts 等 | HOW：技术选型、架构、接口 |
| Tasks | `/speckit.tasks` | `tasks.md` | 可执行任务列表（可标并行 `[P]`） |
| Implement | 由 coding agent 执行 | 代码与测试 | 按任务逐项实现 |

官方文档：[Spec Kit Documentation](https://github.github.com/spec-kit/)

---

## 3. 二者关系

**WBS 是「怎么把工作拆开」的通用方法；Speckit 是「以规格驱动 AI 开发」的整套流程。**

两者不是同一层概念，也不是官方从属关系，但：

**Speckit 的 Tasks 阶段 ≈ 面向 AI、可执行的 WBS。**

### 3.1 映射关系

```
传统项目管理视角              Speckit 视角
─────────────────            ─────────────────
需求 / PRD                   /speckit.specify  →  spec.md
技术方案 / 设计               /speckit.plan     →  plan.md
WBS / 任务分解                /speckit.tasks    →  tasks.md
执行与跟踪                    AI agent 按任务实现
```

### 3.2 关系图

```
                    ┌─────────────────────────┐
                    │   Speckit（整套 SDD）      │
                    │                         │
  人类意图 ──►  Spec ──► Plan ──► Tasks ──► Code
                    │              ▲          │
                    │              │          │
                    └──────────────┼──────────┘
                                   │
                          最像传统 WBS 的部分
                          （工作分解 / 任务清单）
```

- **WBS**：一种「拆工作」的通用思维与产物
- **Speckit**：把「规格 → 方案 → 任务 → 实现」产品化，并服务 AI coding
- **交集**：Tasks = Speckit 流水线中的「WBS 化」步骤，但是 **规格驱动、面向 AI、可再生成** 的

### 3.3 相同点

1. 都做分解：大目标 → 小、可执行单元
2. 都讲依赖与顺序：先做什么、后做什么
3. 都为可管理：便于分配、估算、跟踪
4. 都强调完整覆盖：尽量不漏项（类似 WBS 的 100% 原则）

### 3.4 关键差异

| 维度 | WBS | Speckit Tasks |
|------|-----|---------------|
| 驱动源 | 项目范围、阶段、交付物 | 规格 + 技术方案（spec / plan / contracts） |
| 写法 | 多为交付物导向（交付什么） | 更偏实现任务（改哪些文件、写哪些接口 / 测试） |
| 执行者 | 人（PM / 开发） | 主要给 AI agent 按序执行 |
| 产物形态 | 树、Excel、项目管理工具 | 仓库内 Markdown（如 `tasks.md`），可带并行标记 |
| 变更方式 | 人工改 WBS | 改 spec / plan 后可再生成 tasks |
| 关注点 | 范围、成本、进度、责任 | 意图清晰、可生成代码、可验证 |

传统 WBS 回答：**「为交付这个项目，我们要完成哪些工作包？」**
Speckit Tasks 回答：**「为兑现这份规格和方案，AI 应按什么顺序、做哪些具体实现任务？」**

---

## 4. 对照表

| | WBS | Speckit |
|--|-----|---------|
| 全称 | Work Breakdown Structure | Spec-Driven Development 工具包（Spec Kit） |
| 本质 | 项目管理方法 / 产物 | 开发流程 + CLI + 模板 |
| 目标 | 把项目拆成可管理的工作包 | 先定规格，再让 AI 按规格实现 |
| 核心产物 | 树状工作分解结构 | `spec.md` → `plan.md` → `tasks.md` → 代码 |
| 是否包含对方 | 不包含 Speckit | 不把 WBS 作为官方子模块；Tasks 思想上等价于 WBS |

---

## 5. 如何一起用

| 场景 | 建议 |
|------|------|
| 大项目、多团队、要排期预算 | 先用 **WBS** 做项目级拆分（模块 / 里程碑） |
| 某个功能交给 AI 实现 | 用 **Speckit** 对该功能做 Spec → Plan → Tasks |
| 已有 WBS | 把某个 WBS 工作包当作 Speckit 的一个 feature 输入 |
| 已有 Speckit tasks | 可汇总进项目 WBS，做进度 / 资源管理 |

**经验法则：**

- 项目治理、排期、跨团队协作 → **WBS**
- 单功能 / 特性的 AI 实现质量 → **Speckit**
- **Tasks** 是连接两者的桥梁：上层 WBS 管范围，下层 Speckit 管「可执行规格与任务」

---

## 6. 一句话总结

| 问题 | 答案 |
|------|------|
| WBS 是 Speckit 的一部分吗？ | **不是**官方子模块；Tasks 阶段在思想上等价于 WBS |
| Speckit 替代 WBS 吗？ | **不替代**；Speckit 偏工程实现，WBS 偏项目范围与管理 |
| 最准确的关系 | **WBS = 拆工作的方法；Speckit = 规格驱动的 AI 开发流水线；Tasks 是流水线中的「WBS 环节」** |

---

## 参考

- [GitHub Spec Kit](https://github.com/github/spec-kit)
- [Spec Kit 文档](https://github.github.com/spec-kit/)
- [Spec-Driven Development 说明（仓库内）](https://github.com/github/spec-kit/blob/main/spec-driven.md)
- [GitHub Blog：Spec-driven development with AI](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/)
