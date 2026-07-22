---
title: trialpos 代码库 SDD 开发流程 · 实现计划 + 执行记录
genre: proposal
audience: [POS4U 开发者, Tech Lead, 中国开发团队]
status: 已执行（P0–P5 落地：P4' 装置全面增强 + P5 全面日语化·宪章 v2.0.0；dogfood 构建/测试 Windows-pending）
scope: 为 trialpos-snapshots（POS4U 代码库，C#/.NET Framework + SQL Server）建立 SDD 代码开发流程
spec_kit_base: github/spec-kit 0.8.2.dev0（全新装最新）+ 定制经原生扩展钩子(.specify/extensions.yml)+ speckit-* skill；逻辑零 fork core（P5 起基座 skill 本文日语化=语言层 fork，升级需重译，见台账）；kugelpos 仅作设计参考
knowledge_source: trialpos-trec-docs（知识库 · 仅供参考 · SDD 知识层的"拷贝素材来源"）
lifecycle: 项目预计余命 2–3 年 → 右尺寸投入
owner: jinianxiang
created: 2026-07-15
updated: 2026-07-18
---

# trialpos 代码库 SDD 开发流程 · 实现计划 + 执行记录

> **范围修正说明**：本报告初版曾把治理对象误设为「文档」（为 `trialpos-trec-docs` 建 docs-as-code SDD）。**已修正**：
> - **治理对象 = `trialpos-snapshots`（POS4U 代码库）**，目标是为**代码开发**建立 SDD 流程。
> - **`trialpos-trec-docs` 是知识库、仅供参考**，在本计划中降为「SDD 知识层的拷贝素材来源」，**不是**治理对象。

---

## 0. 一句话定位

把成熟的 SDD 工序链（以 kugelpos 为设计参考、以**最新标准 spec-kit** 为工具基座）落到 POS4U 代码库（`trialpos-snapshots`）——这次是**代码→代码**，命令链**不用语义翻转**。真正的工作有四块：①在最新 spec-kit 上重实现 kugelpos 验证过的定制；②技术栈改写（Python/Dapr → C#/.NET/SQL Server）；③遗留棕地适配（173 项目 / 0 测试 / 老框架）；④从 trec-docs 播种知识层。因项目余命约 2–3 年，投入**右尺寸**（见 §13-4）。

---

## 执行进展（2026-07-18 · 已落地 P0–P5）

> 本节是「计划 → 执行」的落地记录；§1–§13 保留为**原始提案/计划之记**。执行在 `trialpos-snapshots` 本地 git（**无 remote**），main 6 提交，工作树干净。

| 阶段 | 提交 | 落地内容 |
|---|---|---|
| P0 地基 | `ca451ac` + 基线 `5b679b6` | 本地 git-init（无 remote）+ 全新装 spec-kit + CLAUDE.md + .gitignore；代码基线单独提交（CSV/大文件已忽略，`.git` 49M） |
| P1 治理 | `bef373b` `1420d6f` | 宪章 **v1.0（Ratified 2026-07-16）** + `architecture-principles.md`（9 节·代码锚定）+ `testing-strategy.md` |
| P2 知识 | `ced3466` | `adr/0001~0004` + `domain-knowledge` 4 模块（sales/discount/payment/return）×{checklist,blind-spots} |
| P3 命令定制 | `03e84be` | `.specify/extensions.yml`（context-preload **mandatory 钩子**）+ 5 定制 skill（context-preload/adr/approve-spec/feedback/test-spec） |
| P4 dogfood | `6468b18`（分支） | 一条真实缺陷 authoring 半程跑通 → **附录 B** |

### 执行中与计划的关键出入（诚实记录）
1. **spec-kit 版本**：实际 `0.8.2.dev0`（`specify init` 装的最新 bundled），**非**计划设想的 v0.11.x。定制经其**原生扩展钩子**（`.specify/extensions.yml` 的 `before_*` hook，基座自动 EXECUTE）+ `.claude/skills/speckit-*` 实现，**非** preset/extension 模型——但同样**零 fork core**，达成初衷。详见 `.specify/SPECKIT_BASELINE.md`。Claude 集成用 **skills**（`.claude/skills/`）而非 §7/§8 设想的 `commands/`。
2. **决策定稿**（§13 之后由用户拍板）：⚠️ **.NET 目标版本不得变动**（设备横跨 Windows XP/7/10/11，v4.0=XP 兼容上限，已入宪法技术制約）；测试框架 = **NUnit**；**不设覆盖率硬门槛**（touch-only）。
3. **git**：仅本地、**无 remote**（用户定；副本改动回流 GitLab 正本走团队既有通道）。
4. **代码目录零改动约束**：P0–P3 全程不碰 `Application/Database/`·`Application/POS4UCloud/`·`Application/Source/`；仅 P4 dogfood 在 feature 分支改了 1 个文件（`DiscountMaker.cs`，见附录 B）。

### 统合到 GitLab 真克隆 @202607（2026-07-16 追补）

原 `trialpos-snapshots`（ver202606 冻结副本 + 上述 SDD 装置）已归档至 `z-archive/trialpos-snapshots-ver202606-20260716/`；工作仓改以内网 GitLab 正本的**真实克隆**替代，基线切至 `release20260728_Local`（202607 已发布版）。要点：

- **git 性质变更**：由「本地·无 remote」→「origin 保留仅供 fetch/切版本、**push 已禁用**、任何 push 须明确许可」；SDD 工作在 `sdd/main` 分支，`release*` 镜像分支保持与 origin 干净。（上文 P0–P4 的「无 remote」为当时事实，保留为历史记录。）
- **结构变更**：`pos-store/·pos-cloud/·database/` → `Application/{Source,POS4UCloud,Database}`（trial 真实布局）。
- **SDD 装置迁移 + 重锚**：宪章 v1.0.0→v1.0.1（PATCH 事实订正）；202606→202607 delta 极小（2 增/2 删），全部 file:line 锚点验证仍有效；dogfood `001-fix-discount-maker-nre` 已在 202607 重建（NRE 缺陷仍在、行号一致）。
- **本知识库同步**：01-/overview/README/70-workspace 的代码引用路径已刷新为 `Application/Source/…`；90-verification 审计报告保持时点原貌；各文档 `code_baseline: pos-store-ver202606` 作为验证溯源保留不改。

### SDD 装置 P4' 全面增强（2026-07-17 追补）

在 `sdd/main` 上对装置做了**全面增强**（4 提交 `580dafc`→`109e0a3`，对照 kugelpos 成熟装置按遗留棕地改写；详见 `.specify/SPECKIT_BASELINE.md` §P4 台账）：

- **模板层**：13 个模板 POS4U 化（重写 spec/plan/tasks/checklist；新建 research/data-model/contracts/quickstart/test-spec/test-results/spec-nfr/spec-cross-cutting；adr/template）。
- **知识层**：新建 `legacy-sdd-disciplines.md`（规模 Gate S/M/L·全链追溯+显式负空间·同型全棚卸·同步门·**两速 ADR**·blind-spots 学习闭环·index-link/系谱）。
- **skill/钩子**：新增 `approve-adr`（承认+回填 architecture-principles）、`test-results`（`after_implement` 钩子·TC-ID 1:1·Windows-pending）；plan/implement/analyze 加 POS4U 补充块（派生产物 Gate / characterization 先行 / **Pass-G**）。
- 原计划所谓"adr 自动内联路径 + approve-adr"在此阶段落地（两速 ADR 协议）。

### P5 全面日语化 + 宪章 v2.0.0（2026-07-18 追补）

依用户指示对齐 `stpos-backend-kugelpos` 语言惯例（代码仓=正式向=日语；trec-docs=内部=中文），单提交 `5083156` 完成（51 文件；台账 §P5）：

- **宪章 v2.0.0（MAJOR）**：明文化第一性原理 F1〜F5 并重新推导 8 原则（实质保全 v1.0.1）；**新设「言語規約」章节**（SDD 产物/流程文件/代码注释=日语，变量名/ID/技术标签=英语）；新增人工门控表（AI 不可代替）与 commit 规约（Conventional Commits + `[spec:NNN-名]` 标签）。
- **全部 SDD 流程文件日语化**：skills 16 / templates 13 / knowledge 16（含 ADR·domain-knowledge）/ CLAUDE.md / extensions.yml / SPECKIT_BASELINE；每个 skill 内嵌言語規約块（产物强制日语）。
- **流程改进**：specify 补 SPEC_TYPE 判定块（functional/nfr/cross-cutting 分流）；analyze 新增语言一致性检查（MEDIUM）；状态生命周期统一（Draft→レビュー待ち→承認済み）；approve-spec 登记列与 index 表头（7 列·系谱）对齐。
- **采用见送り（右尺寸）**：specs 归档运用 / GitHub Issue 采番 / 覆盖率数值门——理由记于台账。
- ⚠️ **语言 fork 注记**：9 个基座 skill 本文已日语化（逻辑未变）——上游 spec-kit 升级时须对照英文原版 diff 后**重译再套用**（台账 §P5 有明示）。

### 待续
- P4 dogfood 的**构建 + NUnit 测试须 Windows** 收口（宪章 III 平台分离）；
- **P6**（`.NET DevOps` 命令：MSBuild build / nunit3 test runner / SP db-review；CI）按痛点。

---

## 1. 背景：厘清「trialpos 的开发」+ 与 trec-docs 的关系

trialpos 生态里有三种「开发」活动：

| | 活动 | 现场 |
|---|---|---|
| **A ⭐本计划目标** | POS4U **代码开发** | `trialpos-snapshots`（从内网 GitLab `aipos` 仓下载的代码 copy） |
| B | AIPOS/ST-POS 新案件 | 自建 Confluence 瀑布式 SDLC（非本题） |
| C | 文档逆向工程 | `trialpos-trec-docs`（**本计划的知识源，仅供参考拷贝**） |

**A 与 C 的关系**：C（trec-docs 的 93 篇逆向文档）是对 A（POS4U 代码）现状的知识沉淀。本计划把 C 当作**现成的知识层种子**拷进 A 的 SDD——这正是 trialpos 相对 kugelpos 的最大红利（kugelpos 当年知识库从零建）。

> ✅ **已确认（§13-1）**：`trialpos-snapshots` = **从内网 GitLab `aipos` 仓下载下来的代码 copy**。故本计划把它作为 **SDD 治理的工作/试点副本**；GitLab 正本由团队持有，此副本上的 SDD 产物与代码改动如何回流正本，走团队既有通道。

---

## 2. 工具基座：最新标准 spec-kit + 定制（不 fork kugelpos 旧版）

⚠️ **关键决策（§13-3）**：kugelpos 的 spec-kit 是 2026 年初 fork 的**旧快照**、半年独立演化、难跟上游。trialpos 是绿地工具链，**直接采用最新标准 github/spec-kit 作为基座，再定制**——即 kugelpos 因"不得影响现有流程"约束而做不了的"正道"。

- **kugelpos 只作"设计参考"，不 fork 其代码**：它验证过的定制——ADR 双路径 + `approve-spec`/`feedback` 迭代 + `test-spec` + index-link 模型 + 质量闸门——作为**概念**在最新 spec-kit 上重实现，而非搬其旧命令文件。
- 命令链本身（`specify→…→analyze`）是代码 SDD，与本计划同类，无需语义翻转。

> 📌 **执行实况**（见「执行进展」）：基座实际为 `0.8.2.dev0`；定制经**原生扩展钩子 + skill** 实现（非 preset/extension），零 fork core。

**所以主要工作 = ①在最新 spec-kit 上重实现 kugelpos 验证过的定制 + ②③④ 见 §4。**

---

## 3. 遗留系统现状（实测 · 决定计划形态）

> 代码根：`trialpos-snapshots`（基准 `pos-store-ver202606`）。

| 事实 | 实测值 | 对 SDD 的含义 |
|---|---|---|
| C# 项目数 | **173** `.csproj`（pos-store 168 + pos-cloud 5） | 巨型遗留单体 → 只能**增量绞杀**，不可能一次 spec 全系统 |
| 自动化测试 | **0** 测试工程 / **0** 处 xunit·nunit·mstest·moq | ⭐ 「TDD-first + 80% 覆盖」**不可照搬** → 改 characterization + touch-only |
| .NET 版本 | 154 项目 `v4.0` + 19 项目 `v4.6.1`（含 net45/452/46） | 老 .NET Framework → **只能 Windows + MSBuild/VS 构建**；⚠️ **版本不得变动**（XP 兼容底线，见 §13-4 定稿） |
| 平台 | 当前 Mac/AI 环境 | 可做规格/计划/写码/analyze；**构建+测试须 Windows** → authoring ↔ build-verify 分离 |
| CI/流程 | 无 CI；仅 `POS4U.ruleset`（StyleCop）×2 | CI/构建自动化 = 绿地 |
| 无源码依赖 | `Application/POS4UCloud/ExternalModule/Framework/POS4U.Framework.dll`（无源码） | 框架基类 = `uncheckable` 边界，不得断言其内部 |
| 版本管理 | 非 git、目录可写(777) | 可直接 git-init 作为 SDD 工作仓 |
| 解决方案 | `POS4U_V4.sln` / `POS4UBackground.sln` / `POS4UBO_V4.sln` | 三入口 |

---

## 4. 主要工作：四块

**① 重实现 kugelpos 验证过的定制**（§2）：在最新 spec-kit 上加回 ADR（手动路径）、approve-spec/feedback、test-spec、context-preload。
**② 技术栈改写**：kugelpos 的 Python/FastAPI/Dapr/MongoDB 内容 🔴 全丢弃，按 **C#/.NET Framework 4.0·4.6.1 + SQL Server + WCF net.tcp** 重写 constitution 原则、architecture-principles、测试策略。
**③ 遗留棕地适配（最难 · 核心是测试策略）**：不套「TDD-first + 80% 覆盖」；改动前先加 characterization test 钉行为、只测你动到的（touch-only）；无源码 `Framework.dll` = uncheckable；**平台分离**（构建+测试在 Windows）。
**④ 从 trec-docs 播种知识层**：见 §5。

---

## 5. 知识播种映射（trec-docs → trialpos-snapshots/.claude/knowledge/）

| trec-docs 来源（仅参考 · 拷入转化） | → SDD 知识层 | 作用 |
|---|---|---|
| `10_architecture/*` + `20_framework/*` | `architecture-principles.md` | AS-IS 架构约束 = 新代码必守规则 |
| `30_domain/*`（22 Business 模块） | `domain-knowledge/<模块>-{checklist,blind-spots}` | 各模块 review 观点 + 踩坑 |
| `80_decisions/adr-001~004` | `adr/0001~0004` | 既有架构决策（五元组主键/WCF/离线降级/TLog XML），新工作须尊重 |
| `40_data/*`（160 表 / 405 SP） | architecture-principles 数据规则 | 五元组主键等 DB 约束 |
| `50_devices/*`（78 设备） | （待补 `domain-knowledge/device-*`） | 设备侧约束 |
| `15_howto/*`（3 篇） | architecture-principles「必须模式」 | 「在 POS4U 框架里怎么新建一件东西」 |
| `12-gitlab-wiki` §9_9（25 gotchas，实 24 条） | `architecture-principles` 禁止事项 + `domain-knowledge` blind-spots | 真实开发踩坑清单 |

> 原则：从 trec-docs **拷贝并转化**（转成规则/清单/ADR 体裁），不是直接链接。转化时保留 `file:line` 代码锚定。
> 📌 执行实况：已播种 architecture-principles + 4 ADR + 4 核心模块（sales/discount/payment/return）；其余 18 模块 + 设备篇按 dogfood 触及再补（右尺寸）。

---

## 6. 落地决策（均已定，见 §13）

| # | 决策 | 结论 |
|---|---|---|
| D1 | git-init `trialpos-snapshots` | ✅ 已做（本地·无 remote）；.gitignore 忽略 bin/obj/*.user/.vs + CSV/大文件 |
| D2 | 工具位置 | ✅ `trialpos-snapshots/` 根 `.specify/` + `.claude/` |
| D3 | 命令命名空间 | ✅ 复用 `/speckit-*`（skill 形态） |
| D4 | 工具基座 | ✅ 最新标准 spec-kit（实际 0.8.2.dev0）+ 定制经**原生钩子 + skill**；不 fork core；`SPECKIT_BASELINE.md` 记版本 |
| D5 | constitution | ✅ 「POS4U 遗留感知宪章」v1.0（首要原则 = 行为保全） |
| D6 | 测试策略 | ✅ characterization + touch-only + **NUnit** + 不设覆盖率门槛 |

---

## 7. 命令链（POS4U 语境 · **加粗 = MVP**）

每命令前置 **context-preload**（读 constitution + architecture-principles + 相关 ADR + approved-specs + 该模块 domain-knowledge）。基座 skill 命名 `/speckit-*`；定制的 `context-preload/adr/approve-spec/feedback/test-spec` 亦为 `/speckit-*` skill。

| 命令 | 在 POS4U 语境做什么 |
|---|---|
| **`/speckit-specify <需求>`** | 自然语言需求 → 要求仕様書 |
| `/speckit-clarify` | ≤5 问消歧（触及哪些模块/表/SP、是否碰 Framework.dll 边界） |
| **`/speckit-plan`** | 实装计划 + 憲章 gate + 影响面 + ADR 制约反映 |
| **`/speckit-tasks`** | 依赖排序任务（含 characterization 前置、touch-only 测试） |
| **`/speckit-implement`** | 写 C# 代码 + characterization/新测试 |
| **`/speckit-analyze`** | spec/plan/tasks ↔ 憲章一致性（PR 前必须，CRITICAL 清零） |
| **`/speckit-adr`**（手动·定制） | 明确违反 architecture-principles 时停工商议 |
| `/speckit-feedback` + `/speckit-approve-spec`（定制） | 有识者评审迭代 + 承认登记（index-link） |
| `/speckit-test-spec`（定制） | characterization 导向测试规格 |
| `/speckit-checklist` `/speckit-constitution` | 质量清单 / 维护憲章 |

---

## 8. 目标目录布局（落地后 · 已实现）

```
trialpos-snapshots/                      ← git（本地·无 remote）
├── CLAUDE.md · .gitignore
├── .specify/
│   ├── memory/constitution.md           宪章 v2.0.0（日语·第一性原理+言語規約）
│   ├── extensions.yml                    context-preload/test-spec/test-results mandatory 钩子
│   ├── SPECKIT_BASELINE.md               基座版本 + 定制台账
│   ├── scripts/ templates/ integrations/ workflows/   最新 spec-kit 基座
├── .claude/
│   ├── skills/ speckit-*(9 基座 + 7 定制，全日语)
│   └── knowledge/{architecture-principles, testing-strategy, legacy-sdd-disciplines, adr/(4+模板), domain-knowledge/(4×2), approved-specs/}（全日语）
├── specs/<NNN>-<name>/                   SDD 产物（001 dogfood 已在）
└── Application/Database/ Application/POS4UCloud/ Application/Source/       现有代码（治理对象，结构不动）
```

---

## 9. 分阶段路线（MVP 优先 · 痛点驱动）

> **执行状态**：**P0–P3 ✅ + P4 authoring ✅**（见「执行进展」）。以下为原始路线之记。

| 阶段 | 内容 | 状态 |
|---|---|---|
| **P0 地基** | git-init + 装最新 spec-kit + CLAUDE.md + .gitignore | ✅ |
| **P1 治理层** | 宪章 + architecture-principles + 测试策略 | ✅ |
| **P2 知识播种** | trec-docs → domain-knowledge + adr 种子（分批） | ✅（4 模块 + 4 ADR） |
| **P3 命令定制** | context-preload 钩子 + adr/approve/feedback/test-spec | ✅ |
| **P4 dogfood** | 真实改动端到端；**构建+测试 Windows 验证** | ✅ authoring / ⏳ Windows |
| **P4' 装置全面增强** | 13 模板 POS4U 化 + legacy-sdd-disciplines + approve-adr/test-results + 两速 ADR + Pass-G | ✅（2026-07-17 追补，见「执行进展」） |
| **P5 全面日语化** | 宪章 v2.0.0（第一性原理+言語規約）+ 全流程文件日语化 + 流程改进 | ✅（2026-07-18 追补，见「执行进展」） |
| P6 完整化 | .NET DevOps 命令 + CI | 按痛点 |

---

## 10. 遗留系统特有难点（务必正视）

1. **测试从零**：0 测试 → characterization test 是先决基建。先给「要改的那块」补特性测试锁行为，再改；不追全量。
2. **平台分离**：Mac/AI 不能构建 .NET Framework → authoring 在此、build-verify 在 Windows。dogfood 必须有 Windows 环境闭环，否则 SDD 的"测试 gate"落不了地。
3. **巨型单体**：173 项目 + WCF + 无源码 Framework.dll → 增量绞杀，一次只治理一个模块/一条改动。
4. **副本 vs 正本**：`trialpos-snapshots` 是 GitLab 正本的下载 copy → SDD 产物/改动回流正本走团队既有通道（§13-1）。

---

## 11. 风险与规避

| 风险 | 规避 |
|---|---|
| R1 照搬 80% 覆盖 → 遗留下不可行 | characterization + touch-only；憲章写明行为保全优先 |
| R2 平台错配（Mac 构建不了） | 显式 authoring↔build-verify 分离；dogfood 备 Windows 环境 |
| R3 副本与正本脱节 | 明确回流通道（团队持有 GitLab 正本） |
| R4 大单体想一次 spec 全量 | 增量绞杀，逐模块/逐改动 |
| R5 过度投入（项目仅余 2–3 年） | 右尺寸：只做新功能/bugfix 纪律 + 行为保全，不做深度现代化 |
| R6 spec-kit 定制与上游分叉 | 基于最新版 + `SPECKIT_BASELINE.md`，定制走原生钩子/skill 而非改 core；P5 起基座 skill 有**语言层 fork**（本文日语化、逻辑未变）——升级时对照英文原版重译（台账 §P5 有手顺） |

## 12. 验收标准（附 dogfood #001 对照）

- **A1** 真实改动走完 `specify→…→analyze` + Windows 构建/测试后合并 — ✅ authoring / ⏳ Windows-pending
- **A2** constitution/architecture-principles 反映 POS4U 真实约束（五元组/WCF/uncheckable/.NET-XP） — ✅
- **A3** domain-knowledge 被 context-preload 加载 — **✅ 已实证**（dogfood 钩子自动触发 + 精准挑 discount）
- **A4** characterization + touch-only、非全量覆盖 — ✅
- **A5** 基座最新 spec-kit + 定制经扩展（非 fork core），版本记于 `SPECKIT_BASELINE.md` — ✅

---

## 13. 决策记录（已定 · 2026-07-15 提出，2026-07-16 定稿）

1. **`trialpos-snapshots` 定位**：= 从内网 GitLab `aipos` 仓**下载的代码 copy**。→ 作 SDD 治理的**工作/试点副本**；GitLab 正本由团队持有，回流走团队既有通道。
2. **git-init trialpos-snapshots**：✅ 采用（本地·**无 remote**）。
3. **命令空间 & 基座**：✅ 复用 `/speckit-*`；基座用最新标准 spec-kit（实际 0.8.2.dev0）再定制，**不** fork kugelpos 旧版。
4. **开发范围 & 平台底线**：新功能 + bug 修复都有；余命 2–3 年 → 右尺寸；⚠️ **.NET 目标版本不得变动**（设备横跨 WinXP/7/10/11，v4.0=XP 兼容上限）；测试 = **NUnit**、**不设覆盖率硬门槛**。
5. **执行**：P0–P4 已落地（见「执行进展」）；构建/测试收口于 Windows。

---

## 附录 A · 调研依据（可追溯）

**参考源（设计参考，不 fork）**：`stpos-trec-docs/00-project/guides/sdd-workflow/`（7 篇 ver5.1）；`stpos-backend-kugelpos/.claude/`+`.specify/`（含 07 号"spec-kit 升级分析"——本计划采用其"绿地走上游模型"结论）。

**工具基座**：github/spec-kit `0.8.2.dev0`（`specify init` 装的最新 bundled）；原生扩展钩子（`.specify/extensions.yml` `before_*`）+ `.claude/skills/speckit-*`。

**trialpos-snapshots 侧（治理对象 · 实测）**：173 `.csproj`（154×v4.0 + 19×v4.6.1）；0 测试工程 / 0 测试框架引用；无 CI，仅 `POS4U.ruleset`；3 sln；无源码 `POS4U.Framework.dll`。

**trialpos-trec-docs 侧（知识源 · 仅供参考拷贝）**：`01-trialpos-docs/`（93 篇逆向文档）——`10_architecture`/`20_framework`/`30_domain`(22 模块)/`40_data`(160 表·405 SP)/`50_devices`(78)/`15_howto`(3 篇)/`80_decisions`(adr-001~004)/`90_traceability`/`90-verification`；`12-gitlab-wiki` §9_9(24 条 gotchas)。

---

## 附录 B · 首次 dogfood 记录（#001 · 可复用样板）

**目的**：用一条真实缺陷验证整套 SDD 在遗留库上"跑得动"（authoring 半程）。分支 `001-fix-discount-maker-nre`（**未 merge，main 未受影响**）。

**靶子缺陷**：`DiscountMaker.AddDiscountInfo`（`Application/Source/Business/Business.TranLogMaker/Maker/DiscountMaker.cs:33-34`）——`NewSalesDiscountRow()` 建游离行后，从**仍为空**的 `SalesDiscount` 表 `FirstOrDefault().TransactionNo` 取值 → **第一条折扣必 NRE、TLog 无法持久化**。即知识层 **BP-DISCOUNT-002** / gotcha **#1**（`FirstOrDefault()` 结果必须判空）的活教材。

**修复**（touch-only · 行为保全 · 对齐同文件兄弟方法）：`TransactionNo` 改从交易头取 `tranDs.TransactionHeader.FirstOrDefault().TransactionNo`（与 `AddMMDiscountInfo`/`AddGSDiscountInfo`/`AddFanCouponInfo` 一致）。

**跑通的链路 & 证据**：

| 阶段 | 命令 | 关键证据 |
|---|---|---|
| specify | `/speckit-specify` | **before_specify mandatory 钩子自动拉起 `/speckit-context-preload`（EXECUTE_COMMAND）——核心接线验证 ✅** |
| preload | `/speckit-context-preload` | 按 `discount` 精准载入域知识，surfacing BP-DISCOUNT-002 → 直指缺陷 |
| plan/tasks/test-spec | `/speckit-plan…` | 憲章 Check gate 全绿；characterization-first + touch-only；影响面明确排除 BP-DISCOUNT-001 |
| implement | `/speckit-implement` | 读实际代码确认缺陷；修复对齐兄弟方法（非臆造，"尊重现架构"实证） |
| analyze | `/speckit-analyze` | 一致性贯通、CRITICAL=0；诚实门控 **G1（characterization 基线）/ G2（Windows 构建测试）= pending → 不可 merge** |

**产物**：`specs/001-fix-discount-maker-nre/{spec,plan,tasks,test-spec,analysis}.md` + `checklists/requirements.md`。

**最大收获**：知识层不是摆设——域知识（BP-DISCOUNT-002）真把 AI 领到真实 bug，且正确修复恰是**文件自身既有模式**。这条分支即**可复用样板**：新改动照此 `/speckit-specify → … → analyze`，构建/测试落 Windows。

**遗留库 dogfood 注意**：
- authoring（规格/计划/写码/analyze）在 Mac/AI 完成；**构建 + characterization/回归测试须 Windows**（宪章 III 平台分离）——未闭环前不 merge。
- characterization 基线须先在**修复前**代码于 Windows 跑通（宪章 I）；本环境只能出 test-spec + 断言意图。
- 收口清单：Windows 上跑 `T001`（基线）→ 确认修复 → `T004`（`nunit3-console` 全绿）→ 满足 SC-001~003 → 方可回流 GitLab 正本。

---

> 本报告初为提案；**P0–P4 已落地**（见「执行进展」+ 附录 B），余下 Windows 构建验证与 P5 按痛点。落地前若与真相源出入，以真相源（`trialpos-snapshots` 代码 + `.claude/knowledge/`）为准。
