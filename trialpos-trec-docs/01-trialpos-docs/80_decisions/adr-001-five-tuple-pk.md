---
title: ADR-001（代码反推）交易表五元组联合主键 · 按可变性分层
layer: 80_decisions
genre: adr
audience: [架构师, 重构开发, DBA]
code_baseline: latest
code_refs:
  - Application/Database/01_Tables/dbo.TransactionLog.Table.sql
  - Application/Database/01_Tables/dbo.SettingMaster.Table.sql
  - Application/Database/01_Tables/dbo.ItemMaster.Table.sql
verification: verified
verified_by: ../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md
related:
  flows: [../70_flows/hold_recall.md, ../70_flows/master_sync_tlog.md]
  data:  [../40_data/03_tran_tables.md]
owner: jinianxiang
updated: 2026-07-14
---

# ADR-001（代码反推）交易表五元组联合主键

## 背景

POS4U 是**店舗边缘**系统：多台终端在同一店内并发交易，且必须在与总部/云断网时照常营业。主键设计要同时满足"跨终端不撞号"与"离线可独立采番"。

## 决策

**按数据可变性/归属范围分层设计联合主键**，交易数据用**五元组**，向下逐级递减：

| 表 | 主键元组 | 归属范围 |
|---|---|---|
| `TransactionLog`（交易流水） | **5**：CompanyCode / StoreCode / TerminalNo / ManagedNo / TransactionNo | 每终端一条采番序列 |
| `SettingMaster`（设定） | **4**：CompanyCode / StoreCode / TerminalNo / Key | 每终端 |
| `ItemMaster`（商品主档） | **3**：CompanyCode / StoreCode / ItemCode | 每店共享 |

## 证据（file:line）

- 五元组：`Application/Database/01_Tables/dbo.TransactionLog.Table.sql:25-32`
  ```sql
  CONSTRAINT [PK_TransactionLog] PRIMARY KEY CLUSTERED
  ( [CompanyCode] ASC, [StoreCode] ASC, [TerminalNo] ASC, [ManagedNo] ASC, [TransactionNo] ASC )
  ```
- 四元组：`Application/Database/01_Tables/dbo.SettingMaster.Table.sql`（PK = CompanyCode/StoreCode/TerminalNo/Key）
- 三元组：`Application/Database/01_Tables/dbo.ItemMaster.Table.sql`（PK = CompanyCode/StoreCode/ItemCode）
- 采番配合：`MTranObject.cs:666` `BusinessCounter.NumberingCount(…, CounterCodes.MTransactionNo)`（分布式序列号）

## 取舍

- **得**：`TerminalNo` 进主键 → 每终端**本地独立采番** `TransactionNo`，无需中心协调即可跨终端不撞号，天然支撑离线营业与后续 TLog 汇聚。主档只 3 元组 → 全店共享一份、同步成本低。
- **付**：交易查询/外键必须携全 5 列；跨终端聚合（如店级日结）需在这 5 列上做集计，索引与 join 复杂度高。
- 这是"按可变性选粒度"的一致设计：越易变/越私有的数据键越长（交易 > 设定 > 主档）。

## 现状 / 对新系统含义

- POS4U 现行如上，DDL 直证，`verified`。
- ST-POS 差异线索（分布式采番/租户隔离键的取舍）→ [migration-hints](../90_traceability/stpos-migration-hints.md)（只外链，不在此展开 ST-POS 设计）。
