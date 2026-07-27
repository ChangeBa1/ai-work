---
title: POS4U → ST-POS 迁移线索（只外链 · 不含 ST-POS 设计正文）
layer: 90_traceability
genre: meta
audience: [重构开发, 架构师]
code_baseline: latest
verification: verified
verified_by: ../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md
owner: jinianxiang
updated: 2026-07-14
---

# POS4U → ST-POS 迁移线索

> **本页只给"从哪儿看"的指针，不给"怎么做"的答案。** 每行左侧是 POS4U AS-IS 机制（带本体系 `file:line`），右侧只**外链**到 ST-POS 对应仓库/目录——**ST-POS 的设计正文一律在其自己的仓库里，本仓不复制、不展开**（红线：范围 = POS4U AS-IS，见 [conventions §7/§9](../00_portal/conventions.md)）。
>
> ⚠️ ST-POS 侧的实装状态、架构决定、正确性判定，以**各 ST-POS 仓库自身文档**为准；本页不对 ST-POS 做任何断言。

## ST-POS 仓库（外链目标）

| 仓库 | 角色 | 外链 |
|---|---|---|
| stpos-backend-kugelpos | POS 后端微服务（Python/FastAPI/MongoDB/Dapr） | [→](../../../stpos-backend-kugelpos/) |
| stpos-backend-mastertran | 主数据同步·变换（.NET8 Azure Functions） | [→](../../../stpos-backend-mastertran/) |
| stpos-device-kugelpos | 设备网关（.NET Framework 4.8） | [→](../../../stpos-device-kugelpos/) |
| stpos-frontend-app | 前端 UI（Avalonia/MVVM） | [→](../../../stpos-frontend-app/) |
| stpos-trec-docs | 团队内部设计文档 | [→](../../../stpos-trec-docs/) |

## 迁移线索表

| POS4U 机制（本体系 file:line / 文档） | 差异性质（栈级事实） | ST-POS 对应位置（只外链） |
|---|---|---|
| 店端 **SQL Server** 双库（`Data.Container/app.config`）· 五元组 PK（`TransactionLog.Table.sql:25-32`，[ADR-001](../80_decisions/adr-001-five-tuple-pk.md)） | 关系库 → 文档库；联合主键 → 租户/终端键 | [stpos-backend-kugelpos](../../../stpos-backend-kugelpos/)（MongoDB 侧） |
| **WCF net.tcp** 本机 IPC（`TranRemoteControllerLibrary.cs:20/132/145`，[ADR-002](../80_decisions/adr-002-wcf-for-ipc.md)） | 富客户端本机 IPC → 服务间 HTTP/消息 | [stpos-backend-kugelpos](../../../stpos-backend-kugelpos/)（Dapr/HTTP 侧） |
| **XML 一体化** TLog（`TransactionLog.TransactionData [xml]`，[ADR-004](../80_decisions/adr-004-tlog-xml-persist.md)） | XML 整包 → JSON 文档流水 | [stpos-backend-kugelpos](../../../stpos-backend-kugelpos/)（tranlog 侧） |
| **78 个 Device .csproj** 进程内驱动（经 TRAN4U） | 进程内外设 → 独立设备网关 | [stpos-device-kugelpos](../../../stpos-device-kugelpos/) |
| **WPF/WinForms** 前台（POS4U/TRAN4U/TwoOperatorsCH） | 富客户端 → 跨平台 UI | [stpos-frontend-app](../../../stpos-frontend-app/) |
| **MasterSync** 下行（`Download.cs:54`，[flows/master_sync](../70_flows/master_sync_tlog.md)） | 边缘拉取 → 上游变换+下发 | [stpos-backend-mastertran](../../../stpos-backend-mastertran/) · [stpos-backend-kugelpos](../../../stpos-backend-kugelpos/)（master-data 接收侧） |
| **挂单/呼出** 13 位 MTran ID + M10W31（`MTranObject.cs:23/659-668`，[flows/hold_recall](../70_flows/hold_recall.md)） | 店内共享库行锁 → 服务侧挂起/呼出 | [stpos-backend-kugelpos](../../../stpos-backend-kugelpos/)（cart suspend/recall 主题；**其设计正文在该仓，不在本仓**） |
| **离线降级**（`MemberObject.cs:591/679`，[ADR-003](../80_decisions/adr-003-offline-degradation.md)） | 富客户端离线记账 → 服务侧容灾策略 | [stpos-backend-kugelpos](../../../stpos-backend-kugelpos/) |
| **手动小计折扣缺陷**（`LineItemBase.cs:123`/`DiscountMaker.cs:34`，[investigations](../80_decisions/investigations/subtotal_discount_defect.md)） | AS-IS **反面教材**：新系统实现小计折扣时须让分摊贯通合计与落盘 | [stpos-backend-kugelpos](../../../stpos-backend-kugelpos/)（discount 侧） |

## 使用建议

1. 先在本体系读透 POS4U AS-IS（`file:line` 锚定）→ 再去对应 ST-POS 仓看目标实装。
2. 迁移决策**不写在这里**：跨端业务设计归 `stpos-trec-docs`，各子系统实装归各自仓库。本页只保证"从 POS4U 事实能一步跳到 ST-POS 现场"。

## 可信度

- verified：左侧全部 POS4U 机制的 `file:line` 已核（见各链接目标）。
- 右侧仅为**仓库级指针**；ST-POS 内容正确性不在本页判定范围（uncheckable from here）。
