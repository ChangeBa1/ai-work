<!--
Sync Impact Report
====================
Version: 1.0.1 → 2.0.0 [MAJOR · 全面日语化＋基于第一性原理重制]
Ratification: 2026-07-16 | Last Amended: 2026-07-18

修订依据（用户指示 2026-07-18「SDD 开发流程重大改进」）:
  1. 治理语言全面日语化——新设「言語規約（语言规约）」章节。SDD 产物、流程文件、
     代码注释等语言对齐 stpos-backend-kugelpos（正式代码仓＝日语）惯例。
     全部模板/skill/知识层同步日语化（同一提交）。
  2. 明文化第一性原理（F1〜F5），并从中重新推导 8 条基本原则。
     原则 I〜VIII 的实质（编号·意图·具体约束）自 v1.0.1 保全
     ——v1.0.1 已经用户批准，事实基盘（实测）未变。
  3. 工作流新增「人工门控表」（AI 不可代替）与「commit 规约」
     （Conventional Commits＋[spec:] 追溯标签）。

MAJOR 理由: 治理语言变更属向后不兼容的治理变更（适用于此后全部产物）。
-->

# POS4U（trialpos）开发宪章 · Constitution（中文 · 参考译文）

> **本文件是参考译文。** 正本 = `trialpos-snapshots/.specify/memory/constitution.md`（**v2.0.0·日语**）。齟齬时**以正本为准**；改此副本不会反映到正本。三语版本（zh/ja/en）需手工保持同步。

> **适用对象**：`trialpos-snapshots`（POS4U 代码库，C#/.NET Framework + SQL Server）的 SDD 代码开发。
> **性质**：POS4U 是 TRIAL **現行·運用中**的 POS 系统，本仓为其内网 GitLab 正本的克隆。本宪章治理其代码开发（**新功能 + bug 修复**），项目预计余命 **2〜3 年**（将被 ST-POS 置换）。
> **最高精神**：在運用中的遗留系统上，做**行为保全的渐进开发**——不是重写，而是有纪律地改。
> **权威**：本宪章是最高治理文件；与真值基线相关的事实以 `trialpos-snapshots` 实测代码为准（基线分支 `release20260728_Local`＝202607 已发布版）。

---

## 第一性原理 (First Principles)

本宪章的全部原则由以下 5 条不可动摇的事实（第一性原理）推导而来。对原则的解释有疑义时，回到这里。

- **F1 — 系统在运行**：POS4U 正在全部门店实际运行。回归＝营业事故（收银停摆·会计不一致）。须守护的最高价值是「不让门店的会计停下、不让它算错」。
- **F2 — 余命短**：2〜3 年内被 ST-POS 置换。大规模重构·深度现代化无法收回投资。改修以必要最小限·渐进为经济理性。
- **F3 — 全量验证不可能**：173 个项目·存量测试 0·`POS4U.Framework.dll` 无源码·终端横跨 Windows XP〜11。「一切皆可验证」的前提不成立，只能诚实对待可验证性的边界。
- **F4 — 知识是散逸的**：现行行为的知识散落在部落知识与逆向工程文档中。不记录判断与教训的开发会重复同样的事故。**判断的记录＝知识资产**。
- **F5 — 正本在日语团队**：正本在内网 GitLab，团队的作业语言·代码惯例是日语。产物若非可回流正本的形态（日语·遵循团队惯例），价值减半。

---

## 基本原则 (Core Principles)

### I. 行为保全第一 (Behavior Preservation First) [NON-NEGOTIABLE]

〔导出: F1〕现行 POS 运行中，回归风险即生产事故。任何改动**默认不得改变既有可观察行为**——UI 操作流、交易结果、状态迁移、数据落盘、集计结果。

- 修改遗留代码**前**，先用**仕様化测试（characterization test）钉住现行行为**，再动手。
- 行为变更**仅限**spec 明示且经承认的意图；不得作为「顺手优化」混入。
- 无法加测试即改的遗留区（如强耦合 UI），须在 spec/plan 显式声明风险与手动验证方针。

### II. 渐进改修·尊重现行架构 (Incremental & Respect AS-IS)

〔导出: F2〕对余命 2〜3 年的系统，不做大爆炸重写·深度现代化（不划算）。新代码在既有框架与分层结构内书写。

- **分层（实测）**：Business(22) / Device(78) / WinPOS(38) / LogicService(6) / POS4ULogicService(11 Controller) / POS4UBackground(16)；框架基类在 `POS4U.Framework.dll`。
- **既有决定（ADR·必守）**：ADR-0001 五元组复合主键 · ADR-0002 WCF net.tcp 本机 IPC · ADR-0003 离线降级 · ADR-0004 TransactionLog XML 持久化。
- 需要偏离既有架构时 → **停工，走 `/speckit-adr` 协议**。禁止「小例外」的独断处理。

### III. 测试战略：仕様化测试 + touch-only（非全面 TDD）

〔导出: F1×F3〕存量测试 0 ＋ 173 项目，全量补测既不现实也不经济。规则：

- **触及的遗留逻辑**：改前用仕様化测试（characterization）钉住行为。
- **新增/变更逻辑**：其行为契约须有测试覆盖（禁恒真断言，1 测试＝1 契约）。
- 不为未触及的代码**写测试**（touch-only）。
- **不设覆盖率数值门槛**（全量·局部均不设）。只要求「触到的都被测到」，靠代码评审＋ `/speckit-analyze` 把关。不做数字游戏。
- **测试框架＝NUnit**（与 .NET Framework 4.x 兼容良好，characterization/参数化友好）。测试项目为 `<被测项目>.Tests`，不混入生产项目。
- **平台分离**：spec/plan/写码/analyze 可在任意环境；**构建＋测试须在 Windows + MSBuild/VS 验证合格**方可合并（authoring ↔ build-verify 分离）。
- 详见 `.claude/knowledge/testing-strategy.md`。

### IV. 数据契约稳定 (Data Contract Stability)

〔导出: F1×F2〕数据层是 SQL Server·**存储过程中心**（实测 160 表 / 405+ SP / 24 视图 / 19 UDT）。

- **五元组复合主键**（CompanyCode / StoreCode / TerminalNo / ManagedNo / TransactionNo）是交易身份的根基，不得擅动。
- 表 / SP / UDT 契约变更须保持**向后兼容**并经评审。**改/建 SP 须明示建在哪个库**（Master / Tran 双库）。
- 跨侧 BO 业务后端 SP（`usp_BO*`）位于**店端 tran DB**。改动须评估店/云双侧影响。

### V. 离线韧性不可侵 (Offline Resilience)

〔导出: F1〕门店断网仍可营业是 POS 的核心特性（ADR-0003 离线降级）。改动**不得破坏离线运行路径及其后续同步·集计**。

- 典型陷阱（既知 gotcha）：新增支付方式 → 若不连动修正 Azure / Background 集计路径，离线补账·日次集计会漏。

### VI. 进程·IPC 边界纪律 (Process & IPC Discipline)

〔导出: F1×F2〕进程构成（实测）：`POS4U`（WPF 前台）↔ `TRAN4U`（WinForms 守护 / 外设宿主）经 **WCF net.tcp:8012（超时 5 分钟，ADR-0002）** 连接；另有 `POS4UTwoOperatorsCH`（双人制副屏）。

- **仅同机进程间用 WCF net.tcp；跨机通信一律 HTTP Web API，不用 WCF**（`.svc` 只是 URL 兼容痕迹）。
- 跨进程 / WCF 契约变更须保持**版本兼容**。**Device 相关改动须经评审再 commit**（既知 gotcha）。

### VII. 不可验证边界的诚实 (Uncheckable Boundary Honesty)

〔导出: F3〕`Application/POS4UCloud/ExternalModule/Framework/POS4U.Framework.dll` **无源码** → 内部行为为 **`uncheckable`**。

- 不得臆测其内部实现。扩展**只经公开挂接点**（`TranBase` / `CommandBase` / `Observer` / `EventCode` / `CheckDigitM10W31`）。
- 关于框架行为的假设须**实机/实测验证**；不能验证时在 spec/plan 明示 `[NEEDS CLARIFICATION]` / `unverified`。

### VIII. 合规与审计可追溯 (Compliance & Audit Traceability)

〔导出: F1〕POS 涉税·交易·结算，不得损害审计可能性。

- 不破坏 `TransactionLog` 完整性、销售状态机（实测 SalesTranStates 28 / SelfStates 39 / CloseCountTranStates 28）的一致性。
- 金额 / 数量 / 税的处理遵循既有域规则（金额列为 `[money]`；详见 `.claude/knowledge/domain-knowledge/`）。
- 凭据不入代码；SQL 一律参数化（SP 调用防注入）。

---

## 技术制约 (Mandatory Stack · 实测)

| 项目 | 约束 |
|---|---|
| 语言/运行时 | C# on **.NET Framework**（v4.0 为主 + v4.6.1）。⚠️ **目标版本不得变动**：POS 终端横跨 **Windows XP / 7 / 10 / 11**，**v4.0 是 XP 兼容上限**，升级将使 XP 终端无法运行。新代码沿用所属项目现行目标；确需新项目时按部署终端 OS 选兼容目标（触及 XP 终端者必须 v4.0）。 |
| 前端 UI | **WPF**（POS4U）+ **WinForms**（TRAN4U） |
| 云端 BO | **ASP.NET MVC5**（POS4UBO·Backoffice） |
| IPC | **WCF net.tcp**（仅店内进程间） |
| 边缘 API | **ASP.NET Web API（HTTP）**（POS4ULogicService，非 WCF） |
| 数据 | **SQL Server（SQLEXPRESS）**·SP 中心；同实例双库（Master / Tran） |
| 测试 | **NUnit**；characterization + touch-only，无覆盖率数值门槛（原则 III / testing-strategy.md） |
| 代码规范 | **StyleCop**（`POS4U.ruleset`）；1 Class 1 File；全程序集强命名 |
| 构建 | **Visual Studio / MSBuild（Windows）**；3 sln：`POS4U_V4` / `POS4UBackground` / `POS4UBO_V4` |
| CI | 现无 → 将来课题（GitLab CI / Azure） |

---

## 言語規約（语言规约 · Language Conventions）

〔导出: F5〕产物能回流正本团队（日语）是最优先事项。对齐 `stpos-backend-kugelpos`（正式代码仓＝日语）惯例。

| 对象 | 语言 |
|---|---|
| SDD 产物（`specs/` 下：spec / plan / tasks / research / data-model / contracts / quickstart / test-spec / test-results / spec_review / checklists） | **日语** |
| SDD 流程文件（`.specify/` 模板·台账、`.claude/skills/`、`.claude/knowledge/`、`CLAUDE.md`） | **日语** |
| 宪章·ADR·知识层 | **日语** |
| 代码注释 | **日语**（遵循既有代码惯例；说明「为什么」，「做什么」由代码表达） |
| 变量·函数·类名 | **英语** |
| 日志消息 | 遵循既有惯例（新增对齐周边代码模式） |
| commit 消息 | **Conventional Commits**：type/scope 英语、说明日语、附 `[spec:NNN-名]` 标签（见下方工作流） |
| ID·技术标签 | 保持英语（FR/SC/TC/BP/ADR、verified / unverified / uncheckable、characterization / touch-only 等） |
| 对话语言 | 随用户设定（默认＝简体中文），**与产物语言独立** |

> 边界注意：`trialpos-trec-docs`（团队内部知识库）以简体中文为主，不在本规约适用范围内。勿混淆其与本仓（正式代码侧）分属不同语言圈。`/speckit-analyze` 会检查产物的语言一致性（违反 = MEDIUM）。

---

## 开发工作流 (SDD Workflow)

- **命令链**：`/speckit-specify` → `clarify` → `plan`（after_plan 钩子自动生成 `test-spec`）→ `tasks` → `implement`（after_implement 钩子自动生成 `test-results` 脚手架）→ `analyze`（**PR 前必须**，CRITICAL 清零）。横向：`adr` / `approve-adr` / `feedback` / `approve-spec` / `checklist`（任意）/ `constitution`。
- **事前载入**：每个命令前由 `context-preload`（mandatory 钩子）载入本宪章＋`architecture-principles.md`＋ADR＋关联 approved-specs＋该模块 `domain-knowledge`。
- **人工门控（AI 不可代替）**：AI 只负责产物初稿生成与一致性检测。「这样可以」的最终判断永远是人的责任。

| 门控 | 阶段 | 担当 | 输出 |
|---|---|---|---|
| 仕様承认 | specify 终盘 | 有识者 / PO | spec.md → 承認済み ＋ `/speckit-approve-spec` 登记 index |
| test-spec 评审 | plan 后 | 有识者 / QA | test-spec.md → 承認済み |
| test-results 评审 | implement 后（Windows 执行后） | 有识者 / QA | test-results.md → 承認済み（**固定在 merge 前最后一次提交**，禁止事后补） |
| ADR 承认 | 随时 | 有识者 | ADR → 承認済み ＋ 反映 architecture-principles |
| 一致性检证 | PR 前 | 实装者（执行） | `/speckit-analyze` CRITICAL = 0 |

- **commit 规约**：Conventional Commits（type/scope 英语·说明日语）＋ `[spec:NNN-名]` 追溯标签。原则 **1 任务＝1 commit**。例：`fix(discount): 小計値引の按分額を LineTotal に反映 [spec:001-fix-discount]`
- **产物**：`specs/<NNN>-<名>/`（sequential 采番），index-link 模型，作为永续 SDD 产物合入 main 系。
- **分支/合并**：SDD 作业在 `sdd/main`；feature 分支自 `sdd/main` 分岔；**merge commit（不 squash）**——保留 SpecKit 子提交粒度以便追溯设计判断。`release*` 镜像分支保持与 `origin` 干净。
- **push 禁止**：origin 指向内网 GitLab 正本，**仅 fetch/切版本·push 已禁用**。**任何 push 须事前明示许可**（克隆的改动经团队既有通道回流正本）。

---

## 治理 (Governance)

- **权威优先级**：本宪章 > `architecture-principles.md` > ADR > 说明文档。下位不得与本宪章矛盾。
- **修订（SemVer）**：MAJOR ＝ 原则删除/重定义·向后不兼容的治理变更；MINOR ＝ 原则新设/大幅扩展；PATCH ＝ 措辞澄清/事实订正。每次修订更新顶部 **Sync Impact Report** 并同步依存产物（模板/skill/知识层）。
- **合规检证**：`/speckit-analyze` 于 PR 前检证 spec/plan/tasks 对本宪章的一致性。CRITICAL 违反不清零不得 PR。
- **例外即 ADR**：不允许「小例外」的独断处理——「需要判断的局面的记录」正是本项目知识资产的核心（F4）。明确条款违反 → 停工 → `/speckit-adr`；灰区岔路 → 内联记录后继续（二速 ADR，`legacy-sdd-disciplines.md` §6）。
- **适正规模原则**：治理投入以匹配余命 2〜3 年为度（F2）。重心在新功能/bug 修复的纪律与行为保全，不为遥远未来过度建制。

---

**Version**: 2.0.0 | **Ratified**: 2026-07-16 | **Last Amended**: 2026-07-18

> 本文件（正本）由 SDD 工具基座（标准 github/spec-kit）管理，可经 `/speckit-constitution` 修订。以 v1.0.1（用户承认济）为基础，依 2026-07-18 用户指示从第一性原理重新推导并全面日语化（v2.0.0）。
