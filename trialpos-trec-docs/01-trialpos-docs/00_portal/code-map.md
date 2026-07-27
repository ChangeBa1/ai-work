---
title: 代码地图 · trialpos-snapshots 目录 → 文档区
layer: 00_portal
genre: meta
audience: [读码, 重构开发]
code_baseline: latest
verification: verified
owner: jinianxiang
updated: 2026-07-14
---

# 代码地图：`trialpos-snapshots` → 文档区

> 从代码定位文档、从文档回代码的双向索引。路径用 `Application/Source/` 前缀——门店端源码正规目录（约定 = 最新发布版；历史版本快照已归档至 `z-archive/`），见 [conventions §1](./conventions.md)。

## 顶层结构

```
trialpos-snapshots/
├── Application/Source/                          店舗端 POS4U（最新发布，约 168 个 .csproj）
├── Application/POS4UCloud/                          云端 BO + Framework DLL
└── Application/Database/                           SQL Server 脚本（160 表/405 SP/24 视图）

# 旧快照 pos-store-ver202601 / pos-store-ver202605 已归档至 z-archive/trialpos-snapshots/
```

## 店舗端（`Application/Source/`）目录 → 文档区

| 代码目录 | .csproj | 角色 | 文档区 |
|---|---|---|---|
| `POS4U/` | 1 | WPF 前台收银主进程 | [10_architecture](../10_architecture/) · [20_framework](../20_framework/index.md) |
| `TRAN4U/` | 1 | WinForms 守护进程（外设/流水宿主） | [10_architecture/05_ipc](../10_architecture/) · [50_devices](../50_devices/index.md) |
| `POS4UTwoOperatorsCH/` | 1 | 双人制副屏进程 | [10_architecture](../10_architecture/) |
| `WinPOS/` | 38 | 前端应用框架（Command/Observer/UI/State） | [20_framework](../20_framework/index.md) |
| `Common/Common.Const/` | 1 | 全局枚举/常量 | [40_data/06_enums](../40_data/06_enums_constants.md) |
| `Business/` | 22 | **业务域**（Sales/Payment/...） | [30_domain](../30_domain/index.md) |
| `LogicService/` | 6 | 边缘业务逻辑/命令层 | [60_services/edge-api](../60_services/edge-api/index.md) |
| `POS4ULogicService/` | 1 | IIS 宿主 · 11 Controller · Settings | [60_services/edge-api](../60_services/edge-api/index.md) |
| `POS4UBackground/` | 16 | 后台/批处理（MasterSync/Transfer/...） | [60_services/background](../60_services/background/index.md) |
| `Device/` | 78 | 设备驱动族 | [50_devices](../50_devices/index.md) |
| `Data/` | 2 | 数据容器/访问 | [40_data](../40_data/01_overview.md) |
| `Azure/` | 1 | 云连接 | [60_services/cloud](../60_services/cloud/index.md) |

## 云端（`Application/POS4UCloud/`）

| 代码 | 角色 | 文档区 |
|---|---|---|
| `Source/POS4UBO/POS4UBackoffice/` | ASP.NET MVC5 后台管理前端 | [60_services/cloud](../60_services/cloud/index.md) |
| `ExternalModule/Framework/POS4U.Framework.dll` | 框架基类（**无源码 · uncheckable**） | [20_framework/04_base_classes](../20_framework/index.md) |

## 数据库（`Application/Database/`）

| 目录 | 内容 | 文档区 |
|---|---|---|
| `01_Tables/` | 160 表（`dbo.*.Table.sql`） | [40_data/02·03](../40_data/01_overview.md) |
| `03_Views/` | 24 视图 | [40_data/04_views](../40_data/04_views.md) |
| `04_StoredProcedures/` | 405 SP + ~27 UDT | [40_data/05_stored_procedures](../40_data/05_stored_procedures.md) |
| `10_BI/` | BI 表/SP | [40_data](../40_data/01_overview.md) |
