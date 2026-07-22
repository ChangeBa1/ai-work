---
title: 文档体系规范（宪法）· frontmatter / 命名 / 链接 / 模板 / 真值基线
layer: 00_portal
genre: meta
audience: [文档作者, 维护者]
code_baseline: latest
verification: verified
owner: jinianxiang
updated: 2026-07-14
---

# 文档体系规范（宪法）

> 本文件是 `01-trialpos-docs` 全体文档的**唯一写作契约**。任何人（含 AI 协作者）新增/修改文档，必须遵守本文。它同时是"为什么这样组织"的依据（详细论证见 [`architecture-redesign-proposal.md`](./architecture-redesign-proposal.md)）。

---

## 1. 九条硬原则

1. **单一真相源**：一个事实只有一个"家"文档；跨主题只用相对链接"→ 详见 X"，**绝不复制正文**。
2. **代码锚定**：每篇 frontmatter 声明 `code_baseline`+`code_refs`；每条事实性断言给 `路径:行号`。无代码依据者不得写成事实。
3. **版本无关链接**：代码路径一律用 `Application/Source/...` 前缀，**约定其默认指向最新发布版本**（`trialpos-snapshots` 现为内网 GitLab 真克隆，随最新 release 分支）；不硬编码版本号。
4. **可信度分级**：frontmatter 标 `verification: verified | unverified | uncheckable`，并可 `verified_by` 指向核查证据。
5. **量化诚实**：所有计数/规模带来源（"实测 最新发布：160 表"）；估算显式标"估算/未实测"；**绝不把推测写成实测**。
6. **体裁分离（Diátaxis）**：reference / explanation / how-to / adr / meta 五类不混写（见 §5）。
7. **范围 = POS4U AS-IS**：只写 POS4U 现状；ST-POS 只允许出现在末尾"迁移提示"callout 且**只外链**。
8. **核查不能须显式标注**：`POS4U.Framework.dll`（无源码）、外部系统等标 `uncheckable`，不静默断言。
9. **docs-as-code**：Markdown + frontmatter + 相对链接 + mermaid；可 lint、可回归。

---

## 2. 真值基线（实测 · 全体文档共享 · 勿再推导）

> 代码根：`../trialpos-snapshots`（内网 GitLab 真克隆，随最新 release 分支）。店舗端 `Application/Source/`（本体系约定 = 最新发布版；历史版本快照已归档至 `z-archive/`）。云端 `Application/POS4UCloud/`。DB 脚本 `Application/Database/`。

| 事实 | 权威值 | 证据 |
|---|---|---|
| 店舗端 DB 引擎 | **SQL Server（SQLEXPRESS）**，非 SQLite | `sqlite` 引用=0；`SqlClient/SqlConnection` 数百处；`Data/Data.Container/app.config`=`Data Source=(local)\SQLEXPRESS;Initial Catalog=POS4U_Trial_Master/Tran` |
| DB 对象 | **160 表 / 405 SP / 24 视图 / ~27 UDT**（+10_BI ~21 SP） | `Application/Database/01_Tables`·`04_StoredProcedures`·`03_Views` |
| 五元组联合主键 | CompanyCode/StoreCode/TerminalNo/ManagedNo/TransactionNo | `dbo.TransactionLog.Table.sql` PK CLUSTERED |
| Business 模块 | **22** | `Application/Source/Business/*/` |
| Device 模块 | **78** `.csproj` | `Application/Source/Device/` |
| WinPOS 框架项目 | **38** `.csproj` | `Application/Source/WinPOS/`（Command/Observer/UI/Library/Common/Background/Batch） |
| 边缘逻辑 | LogicService **6** 项目（ApiLogic/ApiConverter/CommandSales/CommandCommon/Common/ServiceAccessor） | `Application/Source/LogicService/` |
| 内部 WebAPI | POS4ULogicService（IIS 宿主）**11** Controller | `Application/Source/POS4ULogicService/Controllers/` |
| 后台/批处理 | POS4UBackground **16** 项目 | `Application/Source/POS4UBackground/`（Console.MasterSync/VersionUp + WindowsService.Administrator + Background.Business.*×10） |
| 店舗端 C# 项目 | **168** `.csproj` | `find Application/Source -name *.csproj` |
| 进程构成 | POS4U(WPF 前台) + TRAN4U(WinForms 守护/外设宿主) + POS4UTwoOperatorsCH(双人副屏) | 各 `.csproj` OutputType=WinExe |
| IPC | **WCF net.tcp**(POS4U↔TRAN4U, 端口 8012, 超时 5min) | `Application/Source/WinPOS/Batch/WinPOS.Batch/TranRemoteControllerLibrary.cs:131-132`；`TRAN4U/RemoteController/RemoteServiceController.cs:104-105` |
| 边缘 API 协议 | **ASP.NET Web API（HTTP）**，非 WCF | `POS4ULogicService/Global.asax.cs:31`→`WebApiConfig`；Web.config 无 serviceModel |
| 销售状态 | SalesTranStates=**28**（18 TranState+10 State）；SelfStates=**39**；CloseCountTranStates=**28** | `Application/Source/Common/Common.Const/State/*.cs` |
| 框架基类 | TranBase/CommandBase/Observer/EventCode/CheckDigitM10W31 在 **`Application/POS4UCloud/ExternalModule/Framework/POS4U.Framework.dll`（无源码）** | → `uncheckable` |
| 云端 BO | POS4UBO（ASP.NET **MVC5** 前端）；BO 业务后端 SP `usp_BO_*` 在店端 tran DB | `Application/POS4UCloud/Source/POS4UBO/POS4UBackoffice/` |

> 更多逐 file:line 证据：[`../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md`](../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md) 及 `slice-reverse-docs-detail.md`。

---

## 3. frontmatter schema（每篇必带）

```yaml
---
title: <标题>
layer: 30_domain                 # 所属层目录名
module: Business.Sales           # 对应代码模块（域/设备/服务篇），可空
audience: [重构开发, 读码]        # 主受众
genre: reference                 # reference | explanation | how-to | adr | meta
code_baseline: latest
code_refs:                       # 关联代码（Application/Source/ 前缀 = 最新版约定，不写版本号）
  - Application/Source/Business/Business.Sales/SalesTran.cs
verification: verified           # verified | unverified | uncheckable
verified_by: ../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md   # 可空
related:                         # 交叉链接（只链接不复制）
  flows: [../70_flows/sale_end_to_end.md]
  data:  [../40_data/03_tran_tables.md]
owner: jinianxiang
updated: 2026-07-14
---
```

必填：`title` `layer` `genre` `code_baseline` `verification` `owner` `updated`。

---

## 4. 命名约定

- 目录：`NN_kebab`（十进制层号 + 英文）。层间留空位（10/20/…）便于插入。
- 域/设备/服务篇文件：`<snake_case>.md`，与代码模块对应（`sales.md` ↔ `Business.Sales`）。
- 流程篇：`<scenario>_<qualifier>.md`。ADR：`adr-NNN-<slug>.md`。
- 文件名/目录名小写；H1 标题可中日英；正文术语保留原文（PascalCase 类名、日文 UI 词等）。

---

## 5. 体裁（Diátaxis）与各层归属

| 体裁 | 回答 | 所在层 |
|---|---|---|
| **reference** | "它是什么" | 30_domain · 40_data · 50_devices · 60_services · 90_traceability |
| **explanation** | "它怎么运作/为何如此组织" | 10_architecture · 20_framework · 70_flows |
| **how-to** | "怎么做一件事" | 15_howto |
| **adr** | "当初为什么这样决定" | 80_decisions |
| **meta** | 门户/规范/索引 | 00_portal |

---

## 6. 交叉链接规则（治重叠的核心）

- 单一真相源：事实只在"家"层详写，其它层只 `→ 详见 [X](相对路径)`，**禁止复制正文段落**。
- 例：流程篇写"第 3 步算折扣"→ 只 `→ 详见 [折扣域](../30_domain/discount.md#案分)`，不重述折扣算法。
- 全部**相对路径**；代码链接用 `Application/Source/` 前缀。

---

## 7. 领域模块文档模板（`30_domain/<模块>.md` 统一骨架）

```markdown
# <模块中文名>（Business.<Module>）
（frontmatter 见 §3）

## 1. 模块定位          一句话职责 + 系统角色 + 上下游依赖
## 2. 代码结构          子目录 + 关键类清单（路径:行号 + 一句职责）；计数标来源
## 3. 状态机（如有）    TranState/State 节点(file:line) + 迁移边(注可核性) + mermaid
## 4. 业务规则(BR/合规)  BR-<MODULE>-NNN：规则 + 代码证据 file:line + 合规背景
## 5. 关键接口与契约    I*.cs、消费/产出 EventCode、框架挂接点
## 6. 数据依赖          读写表/SP → 链接 40_data（不复制字典）
## 7. 设备依赖（如有）  → 链接 50_devices
## 8. 参与的端到端流程  → 链接 70_flows（不复制）
## 9. 可信度与核查      verified/unverified/uncheckable；核查不能项
## 10. ST-POS 迁移提示  薄 · 只外链
```

---

## 8. 图示规范

- 统一 **mermaid**：架构用 `C4Context`/`C4Container`/`flowchart`；状态机 `stateDiagram-v2`；流程 `sequenceDiagram`。
- ⚠️ **陷阱（已踩）**：`subgraph` 标题、节点标签含 `()` `/` 等特殊字符**必须加引号或用 `id["标题"]` 形式**，否则解析失败。
- 图内节点尽量给对应代码符号（类/方法名），落实代码锚定。

---

## 9. 写作红线（吸取 90-verification 教训）

- ❌ 不得编造行数/文件数/规模；不确定就写"未实测"。
- ❌ 不得给不存在的类/属性/表名（曾出现 `IsAgeLimitProhibition`/`T_BusinessCounter` 等虚构）。
- ❌ 不得把 ST-POS(KugelPOS) 内容当 POS4U 现状。
- ❌ 不得断言 `POS4U.Framework.dll` 内部实现（标 uncheckable）。
- ✅ 宁可短而真，不可长而假。每个数字、每个类名、每条规则都要能回到 `file:line`。
