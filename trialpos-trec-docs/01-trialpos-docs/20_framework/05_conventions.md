---
title: 编码规约 · 分层 / 1 Class 1 File / StyleCop / POS4U.ruleset
layer: 20_framework
module: WinPOS
audience: [重构开发, 读码]
genre: explanation
code_baseline: latest
code_refs:
  - Application/Source/POS4U.ruleset
  - Application/Source/POS4U/POS4U.csproj
verification: verified
verified_by: ../90_traceability/verification-status.md
related:
  framework: [./index.md, ./04_base_classes.md]
owner: jinianxiang
updated: 2026-07-14
---

# 编码规约：分层 / 1 Class 1 File / StyleCop / POS4U.ruleset

> POS4U 通过**统一规则集 + StyleCop 静态分析**强制一致的代码风格，并以**职责分层**约束组织方式。本篇是这些规约的可核清单。

## 1. 职责分层（"MVC 式"，非 ASP.NET MVC）

前台 WinPOS 的分层 = **View / Command / Model** 的职责分离，靠 [Event→Command→Observer→State 引擎](./01_event_command_observer.md)串起，而**非** ASP.NET MVC 框架：

| 角色 | 承担者 | 目录 |
|---|---|---|
| View | WPF 画面 + 映射 | `WinPOS/UI/*View`、`WinPOS.UI.UIMapper` |
| Controller 式 | 命令 | `WinPOS/Command/*`（继承 `CommandWinPOSBase`） |
| Model | 全局状态 + 业务 | `POSData` / `State` / `Business/*` |

> ⚠️ **真正的 ASP.NET MVC5 在云端 `POS4UBO`**（→ [60_services/cloud](../60_services/cloud/index.md)），与前台 WinPOS 不是一回事，勿混。命名空间统一 `ForYouApplications.POS4U.*`。

## 2. POS4U.ruleset（统一代码分析规则集）

`Application/Source/POS4U.ruleset`：`<RuleSet Name="POS4U の規則" ToolsVersion="14.0">`，含 **71** 条 `<Rule>`，跨 **2 个分析器**：

| 分析器命名空间 | 规则 | 说明 |
|---|---|---|
| `Microsoft.Rules.Managed` | `CA*`（约 59 条，如 `CA1001`/`CA1063`…全为 `Warning`） | .NET 托管代码分析 |
| `StyleCop.Analyzers` | `SA*`（12 条，`POS4U.ruleset:64` 段） | 代码风格 |

- **157** 个 `.csproj` 声明 `<CodeAnalysisRuleSet>..\POS4U.ruleset</CodeAnalysisRuleSet>`（如 `POS4U/POS4U.csproj`）——全仓统一。

## 3. StyleCop.Analyzers

- 以 NuGet 引入：`StyleCop.Analyzers` **1.0.2**（`developmentDependency="true"`，`POS4U/packages.config`），**132** 个 `.csproj` 引用。
- 仓内**无 `stylecop.json`、无 `GlobalSuppressions.cs`** —— 即除 ruleset 显式调整外，采用 StyleCop **默认规则集**。
- ruleset 中被显式**关闭**（`Action="None"`）的 12 条 SA 规则，反映了实际编码习惯：

| 关闭的规则 | 含义 | 因此允许 |
|---|---|---|
| `SA1309` | 字段不得以下划线开头 | ✅ 允许 `_controller` / `_provider` 私有字段前缀 |
| `SA1633` | 文件必须含 header | ✅ 不强制文件版权头 |
| `SA1101` | 本地调用需 `this.` | （但基类内多处仍写 `this.`，属自愿） |
| `SA1200` | `using` 放 namespace 内 | ✅ 允许 `using` 置于文件顶 |
| 其余 | `SA1028`/`SA1124`/`SA1310`/`SA1401`/`SA1623`/`SA1642`/`SA1643`/`SA1650` | 见 `POS4U.ruleset` |

## 4. 1 Class 1 File

- **`SA1402`（一个文件仅一个类型）未被 ruleset 关闭** → StyleCop 默认启用 → 事实上强制 **1 Class 1 File**。
- 抽验：`WinPOS/Command/WinPOS.CommandSales` 目录 **186** 个 `.cs`，其中 **184** 个含 `public class`（其余为 `AssemblyInfo` 等）——基本一一对应。
- 命名亦随之：文件名 = 类名（如 `Sales_ChangePrice.cs` ↔ `Sales_ChangePrice` 命令）。

## 5. 目标框架（补充，见架构篇）

- 多数项目 `TargetFrameworkVersion=v4.0`（154/168），少数 `v4.6.1`（14/168）——详见 → [10_architecture/02_containers](../10_architecture/02_containers.md#5-运行环境net-framework)。

## 6. 可信度与核查

- **verified**：ruleset 71 规则/2 分析器、157 项目引用、StyleCop 1.0.2/132 引用、12 条 SA 关闭清单、SA1402 未关闭、1-class-1-file 抽验均带 file:line。
- **说明**：SA1402 的"启用"是 StyleCop 工具默认行为（未显式关闭即生效），非本仓显式声明；StyleCop 工具内部规则实现属外部（uncheckable），但"是否被 ruleset 关闭"可核。
