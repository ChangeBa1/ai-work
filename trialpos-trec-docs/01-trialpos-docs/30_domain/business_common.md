---
title: 业务公共基盘域（Business.BusinessCommon）
layer: 30_domain
module: Business.BusinessCommon
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/Business/Business.BusinessCommon/CommonTranBase.cs
  - Application/Source/Business/Business.BusinessCommon/ReportManager.cs
  - Application/Source/Business/Business.BusinessCommon/ExtensionMethods/UserDataExtensionMethods.cs
  - Application/Source/Business/Business.BusinessCommon/ExtensionMethods/TranBaseExtensionMethods.cs
verification: verified
related:
  framework: [../20_framework/index.md]
  data:  [../40_data/06_enums_constants.md]
  domain: [../30_domain/sales.md, ../30_domain/open_close.md, ../30_domain/rj.md]
owner: jinianxiang
updated: 2026-07-14
---

# 业务公共基盘域（Business.BusinessCommon）

> `verification: verified`——21 个源码文件（~1577 loc）逐 `file:line` 核实：`CommonTranBase` 全体、4 接口、9 共享类型、2 扩展方法类、4 常量类、`ReportManager`。**唯一 `uncheckable`**：祖先 `TranBase` 与 `RJManager`/`TranLogMaker`/`DeviceManager` 等 Framework 插件的内部实现（`POS4U.Framework.dll` 无源码）。

## 1. 模块定位

所有 `Business.*` 域模块的**公共地基**：提供业务事务共通基类 `CommonTranBase`（统一交易确定→取引日志→电子ジャーナル→レシート的骨架）、店铺/终端/节点/设备等运行时共享信息类型、三种 TranLog 生成器契约接口、报表契约与输出管理器、i18n 消息后缀转换、RJ 打印信息暂存。

它处于 domain 层依赖图的**最底层**：`.csproj` 仅引用 `Common.Const`、`Data.Accessor`、`Data.Container`、`Data.DataSetExtensions`、`Device.DeviceCommon`、`Device.DeviceDefine`，**无任何 `Business.*` 依赖**（实测 `Business.BusinessCommon/*.csproj`）。反向被 21 个具体 Tran 继承（见 §5）。

- 命名空间：`ForYouApplications.POS4U.Business.BusinessCommon`

## 2. 代码结构

### 2.1 事务共通基类 `CommonTranBase`（本域核心 · 317 loc）

[`CommonTranBase.cs:19`](Application/Source/Business/Business.BusinessCommon/CommonTranBase.cs) `[Serializable] public abstract class CommonTranBase : TranBase, IDisposable`（`[Serializable]` :18）。祖先 `TranBase` 在 `POS4U.Framework` DLL（无源码 → uncheckable）。

**属性**：`BusinessDate`(:29 get/private set)、`GenerateDateTime`(:35，注释「現在は売上取引のみ値を入れる」)、`FixedTranLog`(:40)、`IsMobile`(:45)、`IsVerifiedOneTimeBarcode`(:50，ワンタイムバーコード復号标志，注明「取引ログには残らない」)。

**方法**（骨架流程，已核实）：

| 方法 | file:line | 行为 |
|---|---|---|
| `Dispose`/`Dispose(bool)` | :55 / :64 | 标准 dispose 骨架，仅置 `_disposedValue` |
| `OnInit`（override） | :75 | `base.OnInit()` → `RefreshBusinessState()` → 消息后缀 `JA_JP`（当前/前值） |
| `RefreshBusinessState` | :86 | `BusinessStateAccessor.GetBusinessStateRow`；若营业日为空则取「现在时刻+1 日」（:95，注明支付机/充值机口径，LogicService 端返回现在时刻，属**客户固有仕様** TODO :92） |
| `FixTran` | :101 | 取引确定主路径：按 `TranType.Id` 取 `TranLogMaker` 插件 → `ConvertToTranDataSet` → `TransactionLogAccessor.InsertTransactionLog` → `RJManager` 插件 `GetRJPrintInfoPairs` → `EJournalAccessor.InsertEJournal` → `ReceiptPrintData.AddReceiptPrintInfo` |
| `FixSumTran` | :135 | 领收书合算确定，与 `FixTran` 唯一差别是走 `InsertTransactionLogSumEvidence`（:143） |
| `GetTransactionData` | :170 | 转 `IPTranLogMaker.ConvertToPTranDataSet` → `JsonConvert.SerializeObject`（异常吞掉返回空串，:180） |
| `CreateEjournalParameter`（private） | :192 | 组装 `InsertEJournalParameter`：从 `TranDataSet` 的 `TransactionHeader`/`SalesHeader`/`EMoneyCharge`/`TwoOperatorsHeader`/`Member` 行取值；`EJournalNo`/`EJournalSeqNo` 由 `BusinessCounter.NumberingCount`（:246-247）采番；含 24 行**积分处理结果区分**判定逻辑（:272-312，结果为 `PointProcResultTypes.PointNg`(:304)/`PointOk`(:309)/null） |

> 关键发现（原稿缺）：`FixTran` 是「取引日志 + 电子ジャーナル + レシート」三写的统一入口，全部 Business Tran 通过它落地。营业日的「+1 日」是**支付机/充值机专属**口径且代码注为客户固有仕様待外置。

### 2.2 TranLog 生成器契约（3 接口，插件式）

| 接口 | file:line | 方法 |
|---|---|---|
| `ITranLogMaker` | [`ITranLogMaker.cs:12`](Application/Source/Business/Business.BusinessCommon/ITranLogMaker.cs) | `ConvertToTranDataSet(CommonTranBase) : TranDataSet`（:19） |
| `IMTranLogMaker` | [`IMTranLogMaker.cs:12`](Application/Source/Business/Business.BusinessCommon/IMTranLogMaker.cs) | `ConvertToMTranDataSet`(:19) + `ConvertToUnknownStatusTranDataSet`（未了取引，:26） |
| `IPTranLogMaker` | [`IPTranLogMaker.cs:12`](Application/Source/Business/Business.BusinessCommon/IPTranLogMaker.cs) | `ConvertToPTranDataSet`（JSON 形取引ログ，:19） |

三接口均以 `CommonTranBase` 为入参、`Data.Container.TranDataSet` 为出参，是 domain↔数据集的转换边界。实现体注册在 `BusinessCommonPluginGroupIds.TranLogMaker`（插件组，见 §2.5），按 `TranType.Id` 解析（`CommonTranBase.FixTran:104`）。

### 2.3 报表契约与输出管理器

- `IReport`（[`IReport.cs:9`](Application/Source/Business/Business.BusinessCommon/IReport.cs)）：`TranLogType`(:14) + `CreateReportDataSet(UserData, object) : ReportDataSet`(:22) + `CanExecute(UserData, object)`(:30)。
- `ReportManager`（[`ReportManager.cs:15`](Application/Source/Business/Business.BusinessCommon/ReportManager.cs)）：
  - `OutputReport`(:24/:37)：先查 `POSPrinter` 连接（未连接报 `ErrorDeviceNotConnect` 返回 false，:40-45）→ `Report` 插件 `CanExecute` → `CreateReportDataSet` → `RJManager.GetRJPrintInfoPairs` → `InsertEJournal` + `AddReceiptPrintInfo`。
  - `OutputEjournal`(:83)：**不查打印机**，仅出电子ジャーナル（无 receipt 追加，:97-104）。
  - `CreateEjournalParameter`(:116 private)：报表侧版本，`TransactionNo` 恒 0（:127），无积分判定（与 §2.1 的 tran 版本区分）。

### 2.4 共享运行时信息类型（`UserData` 扩展对象）

| 类型 | file:line | 内容 |
|---|---|---|
| `StoreInfo` | [`StoreInfo.cs:13`](Application/Source/Business/Business.BusinessCommon/StoreInfo.cs) | `CompanyCode`/`StoreCode`/`StoreName`/`StoreType`/`ReferencedDatetime`（`[DataMember]`）；master 版本字段被 TODO #10663 注释掉（:39-48） |
| `TerminalInfo` | [`TerminalInfo.cs:13`](Application/Source/Business/Business.BusinessCommon/TerminalInfo.cs) | `TransactionNo`/`ReceiptNo`/`EJournalSeqNo`/`EJournalNo`/`ValueCardReqId`/`ReferencedDatetime`；`TransactionLogUnsentCount` 被 TODO #10663 注释掉（:45-50） |
| `NodeInfo` | [`NodeInfo.cs:13`](Application/Source/Business/Business.BusinessCommon/NodeInfo.cs) | `NodeType`/`ReferencedDatetime` |
| `DeviceInfo` | [`DeviceInfo.cs:16`](Application/Source/Business/Business.BusinessCommon/DeviceInfo.cs) | 设备错误/警告列表管理：`AddError`(:35)/`AddWarning`(:103) 均**按 DeviceId+MessageId+Message 去重**；`GetErrors`/`GetWarnings` 返 `ReadOnlyCollection`；`GetFirstError`/`ClearErrors`/`RemoveError`（警告对称） |
| `DeviceErrorInfo` / `DeviceWarningInfo` | [`:13`](Application/Source/Business/Business.BusinessCommon/DeviceErrorInfo.cs) / [`:13`](Application/Source/Business/Business.BusinessCommon/DeviceWarningInfo.cs) | `DeviceId` + `MessageInfo`，`internal` 构造（仅 `DeviceInfo` 可造） |
| `FixedTranLog` | [`FixedTranLog.cs:15`](Application/Source/Business/Business.BusinessCommon/FixedTranLog.cs) | `TranDataSet`(`internal set`) + `RJPrintInfoPairs` + `IsFixed`（= `TranDataSet != null`，:30） |
| `RJPrintInfoStore` | [`RJPrintInfoStore.cs:13`](Application/Source/Business/Business.BusinessCommon/RJPrintInfoStore.cs) | 打印数据暂存：`CanPrint`、`HasPrintInfos`、`SetPrintInfos`/`SetTempPrintInfos`(追加时保序，:52)/`GetPrintInfos`/`ClearPrintInfos` |

### 2.5 扩展方法与常量

**扩展方法（`static`）**：

- `UserDataExtensionMethods`（[`:14`](Application/Source/Business/Business.BusinessCommon/ExtensionMethods/UserDataExtensionMethods.cs)）：`GetDeviceInfo`/`GetStoreInfo`/`GetTerminalInfo`/`GetNodeInfo`（均**懒创建**并存入 `UserData` 扩展对象槽，:21-86）；`GetReprintInfo`(:93，含再印字可能枚数校验 `ReprintPermitCount`)；`SetSimplePauseTran`/`GetSimplePauseTran`（简易保留，注明**内存保管、LogicService 不可用**，:129-149）；`GetRJPrintInfoStore`(:156)。
- `TranBaseExtensionMethods`（[`:15`](Application/Source/Business/Business.BusinessCommon/ExtensionMethods/TranBaseExtensionMethods.cs)）：消息 i18n 后缀转换。`ConcurrentDictionary` 缓存已转换 `MessageId`（:20）；`ConvertMessageInfo`/`ConvertMessageId`/`Get|SetMessageSuffix`/`Get|SetBeforeMessageSuffix`；默认 `JA_JP`；**顾客固有消息不存在时回退共通消息**（:160-165）。

**常量类**：

| 常量 | file:line | 内容 |
|---|---|---|
| `BusinessCommonExtensionUserObjectIds`（internal） | [`:12`](Application/Source/Business/Business.BusinessCommon/Const/BusinessCommonExtensionUserObjectIds.cs) | 6 个 `ExtensionUserObjectId`：DeviceInfo/StoreInfo/TerminalInfo/NodeInfo/SimplePauseTran/RJPrintInfoStore |
| `BusinessCommonPluginGroupIds` | [`:12`](Application/Source/Business/Business.BusinessCommon/Const/BusinessCommonPluginGroupIds.cs) | `TranLogMaker : PluginGroupId<ITranLogMaker>` |
| `ReportPluginGroupIds` | [`:12`](Application/Source/Business/Business.BusinessCommon/Const/ReportPluginGroupIds.cs) | `Report : PluginGroupId<IReport>` |
| `ReportPluginIds` | [`:12`](Application/Source/Business/Business.BusinessCommon/Const/ReportPluginIds.cs) | `ReportManager : PluginId<ReportManager>` |

## 3. 状态机

本域**不定义**具体事务状态；`CommonTranBase` 仅提供 `CurrentState` 骨架（承 `TranBase`）由各子类在构造函数中初始化。状态节点集中在 `Common/Common.Const/State/`（前缀经 `StatePrefixes.cs` 注册）→ 详见各子域文档。

## 4. 业务规则

- **BR-BIZCOMMON-001（交易确定三写）**：`FixTran`(:101) 必然产生 `TransactionLog` + `EJournal` + `ReceiptPrintInfo` 三者；`FixSumTran`(:135) 仅在合算领收书场景改用 `InsertTransactionLogSumEvidence`(:143)。
- **BR-BIZCOMMON-002（营业日 +1 日口径）**：营业日为空时，支付机/充值机取「现在+1 日」（`RefreshBusinessState:95`）；LogicService 端由 `BusinessStateAccessor` 恒返现在时刻。代码注为**客户固有仕様**、待外置到配置（:90-93）。
- **BR-BIZCOMMON-003（积分处理结果区分）**：`CreateEjournalParameter` 依据交易种别/会员/离线积分卡号/后付标志等多分支决定 `PointProcResultType`（NormalSales/Return/Void/EMoneyCharge(Void) 之外一律 null；离线卡号或含 `02BITMAPPOS.bmp` 时 null）（:272-312）。
- **BR-BIZCOMMON-004（设备消息去重）**：`DeviceInfo.AddError/AddWarning` 相同 DeviceId+MessageId+文本不重复入队（:39-52 / :107-116）。

## 5. 关键接口与契约

`CommonTranBase`（承 Framework `TranBase`）是 domain 层编译期锚点，实测被 **21 个具体 Tran 继承**（跨 `Business/` grep `: CommonTranBase`）：
`SalesTran`、`VoidTran`、`OpenCountTran`、`CloseCountTran`、`CashInOutTran`、`SignInOutTranBase`、`EntryNonCashTran`、`EntryCalculatedCashTran`、`CashChangerExchangeMoneyTran`/`RecoverTran`/`RecoverTranVer2`/`ReplenishTran`、`EMoneyChargeTran`/`EMoneyChargeVoidTran`、`PaymentStationTran`、`MainMenuTran`/`PowerOnTran`/`LockTran`/`DeviceSettingTran`/`MTranDeleteTran`/`EJournalSearchTran`。

对外契约：`I{Tran|MTran|PTran}LogMaker`（数据集转换插件）、`IReport`（报表插件）、`ReportManager`（输出编排）→ 详见 [20_framework 基类与插件](../20_framework/index.md)。

## 6. 数据依赖

`FixTran`/`CreateEjournalParameter` 写 `TransactionLog`、`EJournal` 并采番 `BusinessCounter`（`CounterCodes.EJournalNo`/`EJournalSeqNo`）；读 `BusinessState`。字段字典与计数器 → [40_data/枚举与常量](../40_data/06_enums_constants.md)（不复制）。

## 7. 设备依赖

`DeviceInfo`/`DeviceErrorInfo`/`DeviceWarningInfo` 封装设备错误/警告；`ReportManager` 通过 `DeviceManager` 插件访问 `POSPrinter`。依赖 `Device.DeviceCommon`/`Device.DeviceDefine` → 详见 [50_devices](../50_devices/index.md)。

## 8. 参与的端到端流程

作为地基隐式参与所有交易流程（提供 `CommonTranBase.FixTran` 确定路径与运行时上下文）→ 详见 [销售端到端流程](../70_flows/sale_end_to_end.md)。

## 9. 可信度与核查

- **verified（file:line）**：全部 21 源码文件的类/接口/方法/属性/依赖，实测于 最新发布；21 个子类继承经跨模块 grep 核实；`FixTran`/`FixSumTran`/`CreateEjournalParameter`/`RefreshBusinessState` 骨架流转已逐行核实（本次由 `unverified` 升级）。
- **uncheckable**：`TranBase`（`POS4U.Framework.dll`）及 `Factory.CreatePlugin` 解析出的 `TranLogMaker`/`RJManager`/`DeviceManager` 等插件实现体内部行为——见 [真值基线 §2](../00_portal/conventions.md)。

> 原稿订正：`Data.DataSetExtensions` 依赖此前漏列；`FixTran`/`CreateEjournalParameter` 等骨架此前标 `unverified`，本次全部回代码核实。

## 10. ST-POS 迁移提示

> ST-POS 无对应的单体事务基类；后端以微服务 + 领域模型组织，取引日志/电子ジャーナル拆分到独立服务。对照仅供参考（外链）。
