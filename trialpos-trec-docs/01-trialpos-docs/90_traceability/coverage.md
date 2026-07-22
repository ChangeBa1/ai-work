---
title: 文档化覆盖率 · 22 模块 / 78 设备 / 11 Controller / 405 SP 进度
layer: 90_traceability
genre: meta
audience: [PM, 重构开发]
code_baseline: latest
verification: verified
verified_by: ../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md
owner: jinianxiang
updated: 2026-07-14
---

# 文档化覆盖率

> 分母 = [conventions §2 真值基线](../00_portal/conventions.md)（实测 最新发布）。**量化诚实**：只统计 `00-` 体系内**已落盘**的文档；未建层标"建设中"，不虚报。

## 1. 分层建设状态

| 层 | 应建 | 已建 | 状态 |
|---|---|---|---|
| 00_portal | 门户/规范/术语/代码地图/动线 | 5 篇 | ✅ 完成 |
| 10_architecture | C4/IPC/数据流/横切 | 0 | 🚧 建设中（IPC/端口已 verified 素材就绪） |
| 15_howto | 教程 | 0 | 🚧 建设中 |
| 20_framework | WinPOS 引擎五要素 | 0 | 🚧 建设中 |
| 30_domain ★ | 22 个 Business.* 单篇 | 0 | 🚧 建设中（本次 flows 已锚定其链接位） |
| 40_data | 表/SP/视图/枚举字典 | 0 | 🚧 建设中 |
| 50_devices | 78 设备族 | 0 | 🚧 建设中 |
| 60_services | 边缘/后台/云 | 0 | 🚧 建设中 |
| **70_flows** | 端到端叙事 | **10 篇** | ✅ **本次交付** |
| **80_decisions** | 代码分析 ADR + 缺陷 | **4 ADR + 1 调查 + index** | ✅ **本次交付** |
| **90_traceability** | 矩阵/覆盖/可信度/迁移 | **matrix + coverage + hints + verification-status** | ✅ **本次交付** |

★ = 单一真相源层。本次交付的 70/80/90 已把链接锚点指向 30/40/50/60 的"家"路径，待这些层落盘即自动接通。

## 2. 代码资产 → 文档化进度

| 资产 | 实测总数 | 已被文档**触及**（flows/decisions/matrix 引用到 file:line） | 有专属**家篇**（30/40/50/60） |
|---|---|---|---|
| Business 模块 | **22** | ~14（Sales/ReSales/Payment/PaymentStation/Discount/Tax/Member/Point/EMoney/OpenCount/CloseCount/CashChanger/CashInOut/RJ/TranLogMaker） | 0（30_domain 建设中） |
| Device 模块 | **78** | 已点名族：CashChanger(Glory)/CAFISArch/PointInfinity/Printer(RJ)/Scanner/MSR | 0（50_devices 建设中） |
| 边缘 Controller | **11** | 经 ADR-002 / matrix 整体触及 | 0（60_services 建设中） |
| 存储过程 SP | **405**（+10_BI ~21） | 已锚定：`usp_InsertTransactionLog` · `usp_InsertTLogQueue` · `usp_GetMTransactionManagement` · `usp_DeleteMTransactionManagementAll` · `usp_SetBILineItems` · `usp_SaveBusinessCounter` · `usp_GetDiscountSubTotal` | 0（40_data 建设中） |
| 表 | **160** | 已锚定：`TransactionLog` · `MTransactionManagement` · `SettingMaster` · `ItemMaster` · `SalesDiscount` · `BusinessCounter` · `DiscountSubTotalMaster` | 0（40_data 建设中） |

> "触及" = 本次 70/80/90 里以 `file:line` 引用到；"家篇" = 该资产的单一真相源 reference 篇（属 30/40/50/60，尚未落盘）。二者差额即后续建设清单。

## 3. 本次交付明细（70/80/90）

- **70_flows（10）**：index · sale_end_to_end · return_void · payment_change · point_accrual_offline · emoney_charge · hold_recall · open_close_daily · price_change · master_sync_tlog。
- **80_decisions（6）**：index · adr-001-five-tuple-pk · adr-002-wcf-for-ipc · adr-003-offline-degradation · adr-004-tlog-xml-persist · investigations/subtotal_discount_defect。
- **90_traceability（4）**：matrix · coverage（本篇）· stpos-migration-hints · verification-status（既存，未覆盖）。

## 4. 可信度分布（本次交付 15 篇新文档）

| 级别 | 篇数 | 说明 |
|---|---|---|
| verified | 13 | 核心断言逐条回 最新发布 代码（含两处缺陷亲核） |
| 含 unverified 项 | — | 各篇末尾显式列出待复核点（如 ReSales 新单码、UI 层防呆行号、BR-CC 阻断态名） |
| 含 uncheckable 项 | — | 框架 DLL / 外部系统一律显式标注 |

## 关联

- 精度基线 → [../../90-verification](../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md)
- 逐篇可信度台账 → [verification-status](./verification-status.md)
