---
title: ADR-004（代码反推）交易流水 XML 一体化落盘 + 队列转发
layer: 80_decisions
genre: adr
audience: [架构师, 重构开发, DBA]
code_baseline: latest
code_refs:
  - Application/Database/01_Tables/dbo.TransactionLog.Table.sql
  - Application/Source/POS4UBackground/Business/Background.Business.Transfer/Controller.cs
verification: verified
verified_by: ../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md
related:
  flows: [../70_flows/master_sync_tlog.md]
  data:  [../40_data/03_tran_tables.md, ../40_data/05_stored_procedures.md]
owner: jinianxiang
updated: 2026-07-14
---

# ADR-004（代码反推）交易流水 XML 一体化落盘 + 队列转发

## 背景

一笔交易的完整状态（头、明细、折扣、支付、会员、税…）是一棵富对象树（`TranDataSet` 强类型 DataSet）。它既要在店端可持久、可复原（呼出/退货读原单），又要**原样**上行给总部 ERP 审计/统计。

## 决策

**把整棵交易对象树序列化为 XML，作为单列整包落盘**（`TransactionData [xml]`），而非拆成大量规范化行；再由后台按队列**异步 FIFO 转发**出店。挂单（MTran）同理用 `MTransactionXml [xml]` 暂存整包。

## 证据（file:line）

- XML 列：`Application/Database/01_Tables/dbo.TransactionLog.Table.sql:24` `[TransactionData] [xml] NOT NULL`。
- 序列化：`TranDataSet.GetXml()`（销售落盘与挂单序列化共用同一链路，见 [subtotal 调查 §日志存储](./investigations/subtotal_discount_defect.md) 与 [hold_recall](../70_flows/hold_recall.md)）。
- 落盘 SP：`Application/Database/04_StoredProcedures/dbo.usp_InsertTransactionLog.StoredProcedure.sql`；转发队列 `dbo.usp_InsertTLogQueue.StoredProcedure.sql`。
- 异步转发：`POS4UBackground/Business/Background.Business.Transfer/Controller.cs`。

## 取舍

- **得**：写入简单（一次整包）、复原无损（`GetXml`/反序列化对称）、上行"原样"给下游、schema 演进对存储透明；SQL Server 原生 `[xml]` 类型可索引/查询。
- **付**：库内**不便做字段级聚合**（要 XML 解析或另建 BI 投影表，故另有 `usp_SetBILineItems` 等 BI 侧展开）；整包读写粒度粗。
- 这解释了系统为何**同时**有 `[xml]` 整包表**和** BI 展开表——两种诉求（复原/转发 vs. 统计）用两套结构分别满足。

## 现状 / 对新系统含义

- XML 落盘 + 队列转发 `verified`（DDL + SP + 转发控制器直证）。
- ST-POS 的流水模型（文档型 vs. XML 整包）差异线索 → [migration-hints](../90_traceability/stpos-migration-hints.md)（只外链）。
