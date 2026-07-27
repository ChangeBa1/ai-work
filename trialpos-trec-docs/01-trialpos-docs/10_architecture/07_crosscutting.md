---
title: 横切关注点索引 · 採番 / 降级 / 事务 / 日志脱敏 / 多语言
layer: 10_architecture
audience: [架构师, 读码, 重构开发]
genre: explanation
code_baseline: latest
code_refs:
  - Application/Source/POS4ULogicService/POS4ULogicServiceLibrary.cs
  - Application/Source/Common/Common.Const/CounterCodes.cs
  - Application/Source/Data/Data.Container/TransactionLogTransferDataSet.Designer.cs
  - Application/Source/POS4U/Settings/Message.ja_JP.xml
verification: verified
verified_by: ../90_traceability/verification-status.md
related:
  arch: [./03_deployment.md, ./06_dataflow.md]
  framework: [../20_framework/04_base_classes.md]
owner: jinianxiang
updated: 2026-07-14
---

# 横切关注点索引

> 贯穿多域/多层的关注点在此**只做索引**（一句机制 + 关键 file:line + 去处），详情落在对应的域/服务/数据层，避免复制。

## 1. 日志脱敏 / 加密（AES · **非"256"字面量**）

- **主用途 = 请求体加密后写日志**（日志脱敏）：各 Controller 把原始请求体加密再 `Logger.Info`——`ReceiptServiceController.cs:56→60`、`MemberServiceController.cs:50→54`、`MTranServiceController.cs:54` 等。
- **实现**：`POS4ULogicService/POS4ULogicServiceLibrary.cs:29` `AesCryptoServiceProvider`；静态构造用 `RijndaelManaged`（`:38`）+ PBKDF2（`Rfc2898DeriveBytes`，`IterationCount=1013`，`:41`；salt=`EncryptionSaltKey`，`:39`）+ `CipherMode.CBC`（`:48`）+ `PaddingMode.PKCS7`（`:49`）。方法 `ContentEncrypt`（`:61`）/`ContentDecrypt`（`:91`）。
- ⚠️ **"AES-256" 需谨慎**：源码内**无 `256` 字面量**；密钥长度取 `RijndaelManaged.KeySize/8`（`:42`）= .NET 默认值（默认即 256bit，但该默认属**框架层**，源码读不到）→ **256 标 uncheckable**，本体系不将"256"写成实测。
- CAFIS 结果掩码脱敏：`Device_ReceiveCAFISArchResult.cs:175,191` `GetMaskedJson(...)`。
- 另一套 `SecurityUtility.AesDecrypt`（解密设备凭据，非日志）：`Device.ValueCard/ValueCard.cs:361`——`SecurityUtility` 无源码 → uncheckable。
- **家**：→ [60_services/edge-api](../60_services/edge-api/index.md)。

## 2. 採番 / Sequence

- **采番码表**：`Common/Common.Const/CounterCodes.cs` 定义 **14** 个 `CounterCode`：`TransactionNo`(:42) · `ReceiptNo`(:37) · `MTransactionNo`(:57) · `OpenCount`(:17) · `EJournalNo`(:22) · `CAFISArchSeqNo`(:62) · `CreditSequenceNumber`(:67) 等。
- **采番调用**：`BusinessCounter.NumberingCount(param, CounterCodes.X)`（`Business.BusinessCommon/CommonTranBase.cs:246-247`、`Business.Sales/MTranObject.cs:666`）——`BusinessCounter` 定义在 dll（uncheckable，见 [20_framework/04](../20_framework/04_base_classes.md)）。
- **持久化侧（可核）**：`Data/Data.Accessor/BusinessCounterAccessor.cs:29` 调 SP `dbo.usp_SaveBusinessCounter`；批处理回流 `WinPOS/Batch/WinPOS.Batch/BatchPutBusinessCounter.cs:16`。
- **五元组联合主键**（`CompanyCode/StoreCode/TerminalNo/ManagedNo/TransactionNo`）：`Data/Data.Container/TransactionLogTransferDataSet.Designer.cs:744` `FindByCompanyCodeStoreCodeTerminalNoManagedNoTransactionNo(string,string,int,int,long)`（`Rows.Find` 按主键）。
- **校验位 M10W31**：`CheckDigitManager.AddCheckDigit(CheckDigitTypes.CheckDigitM10W31, ...)`——用例 `MTranObject.cs:668`、`Business.InputConverter/BarcodeConverter/*.cs`；算法在 dll（uncheckable）。
- **家**：SP 字典 → [40_data/05](../40_data/05_stored_procedures.md)；PK → [40_data/03](../40_data/03_tran_tables.md)。

## 3. 离线降级

- 会员积分降级状态 `SalesTranStates.ValueCardOffline`（`:119`，被 `Business.Sales/SalesTran.cs`、`Business.Member/MemberObject.cs` 使用）；离线卡号 `OfflinePointCardNo`（`Business.ReSales/ReSalesTran.cs` 等）。
- **家**：三级降级漏斗 → [03_deployment §4](./03_deployment.md#4-三级降级漏斗)（含"触发阈值 unverified"说明，不在此重复）。

## 4. 多语言 i18n

- **3 种语言**：`POS4U/Settings/Message.en_US.xml` · `Message.ja_JP.xml` · `Message.zh_CN.xml`（无其它）。
- **结构**：`<Messages><Message Id="...">文本</Message></Messages>`；`&#xa;`=换行，`{0}`=占位符。消息 ID 经 `Common.Const/MessageIds.cs` 引用。
- **加载/culture 选择逻辑**：应用源码内**未找到**（`Data.Container/MessageDataSet.Designer.cs` 是 DB 表 typed-DataSet，与 xml 无关）→ 在 `POS4U.Framework`（uncheckable）。运行时切换见 `Common_ChangeCulture` 命令。
- **家**：弹窗内容构建 → [20_framework/03_ui_mapping §3](../20_framework/03_ui_mapping.md#3-uimapper-项目的其它映射器)。

## 5. 事务

- 主数据全量导入前 `TRUNCATE TABLE`（整表替换，`SyncMasterBase.cs:279`），增量为 upsert/delete（`DiffSyncMaster.cs`），均经 `System.Data.SqlClient`（本地 SQL Server 事务）。
- Master→Tran 搬运 `DBAccess.ExecuteTran`（`TransferTLog.cs` / `TransactionLogTransferAccessor.cs:140`）。
- **家**：数据流 → [06_dataflow](./06_dataflow.md)；表/SP → [40_data](../40_data/01_overview.md)。

## 6. 日志

- 统一 `Logger`（`ForYouApplications.POS4U.Framework.Library.Logger`，各进程 `Logger.Info/Warn/Fatal`）——定义在 `POS4U.Framework.Library`（uncheckable）；崩溃日志策略见 [04_runtime §4](./04_runtime_process.md#4-崩溃处理unhandledexception)。

## 7. 可信度与核查

- **verified**：加密实现（CBC/PKCS7/PBKDF2 1013 次）、14 采番码、五元组 PK finder、3 语言 Message、TRUNCATE 事务均带 file:line。
- **uncheckable**：AES **密钥长度 256**（框架默认，源码无字面量）；`BusinessCounter`/`CheckDigitM10W31`/`SecurityUtility`/`Logger`/i18n 加载逻辑——均在 dll。
