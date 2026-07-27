---
title: 主菜单·非销售功能域（Business.MainMenu）
layer: 30_domain
module: Business.MainMenu
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/Business/Business.MainMenu/MainMenuTran.cs
  - Application/Source/Business/Business.MainMenu/MTranDeleteTran.cs
  - Application/Source/Business/Business.MainMenu/EJournalSearchTran.cs
  - Application/Source/Business/Business.MainMenu/DeviceSettingTran.cs
verification: verified
related:
  data:  [../40_data/06_enums_constants.md]
  domain: [../30_domain/rj.md, ../30_domain/business_common.md]
owner: jinianxiang
updated: 2026-07-14
---

# 主菜单·非销售功能域（Business.MainMenu）

> `verification: verified`——8 源码文件（~1295 loc）逐 `file:line` 核实：6 个 Tran 类全体、`MTranDeleteMode` 模型、TranLogType/TranType 绑定、边缘 `LogicServiceClient` 调用点、依赖清单。**`uncheckable`**：`TranBase`（Framework DLL）与 `LogicServiceClient`（设备插件，边缘 WebAPI 侧）内部实现。

## 1. 模块定位

收银主菜单及其下的**非销售辅助功能事务**：电源投入、设备设定、画面锁定、电子ジャーナル（EJournal）检索/再印字、购物车中间取引（MTran）删除。多为运维/操作类动作，**仅电源投入产生交易日志**，其余不入流水。

- 命名空间：`ForYouApplications.POS4U.Business.MainMenu`
- 依赖（实测 `.csproj`）：`Common.Const`、`Data.Accessor`、`Data.Container`、`Data.DataSetExtensions`、`Device.DeviceDefine`、`LogicService.ServiceAccessor`、`Business.BusinessCommon`、`Business.RJ`。

## 2. 代码结构

| 类 | file:line | 基类 | TranType | TranLogType | EndTran 行为 |
|---|---|---|---|---|---|
| `MainMenuTran` | [`MainMenuTran.cs:15`](Application/Source/Business/Business.MainMenu/MainMenuTran.cs) | `CommonTranBase` | `MainMenu`(:43) | `None`(:32) | `return false`（:51，不确定） |
| `PowerOnTran` | [`PowerOnTran.cs:10`](Application/Source/Business/Business.MainMenu/PowerOnTran.cs) | `CommonTranBase` | `PowerOn`(:30) | `PowerOn`(:19) | `FixTran()` → true（:38，**唯一落日志**） |
| `LockTran` | [`LockTran.cs:14`](Application/Source/Business/Business.MainMenu/LockTran.cs) | `CommonTranBase` | `Lock`(:42) | `None`(:31) | `return false`（:50） |
| `DeviceSettingTran` | [`DeviceSettingTran.cs:16`](Application/Source/Business/Business.MainMenu/DeviceSettingTran.cs) | `CommonTranBase` | `DeviceSetting`(:44) | `None`(:33) | `return false`（:64） |
| `MTranDeleteTran` | [`MTranDeleteTran.cs:15`](Application/Source/Business/Business.MainMenu/MTranDeleteTran.cs) | `CommonTranBase` | `MTranDelete`(:32) | `None`(:43) | `throw NotSupportedException`（:204） |
| `EJournalSearchTran` | [`EJournalSearchTran.cs:20`](Application/Source/Business/Business.MainMenu/EJournalSearchTran.cs) | `CommonTranBase` | `EJournalSearch`(:35) | `None`(:44) | `throw NotSupportedException`（:588） |
| `MTranDeleteMode` | [`MTranDelete/MTranDeleteMode.cs:6`](Application/Source/Business/Business.MainMenu/MTranDelete/MTranDeleteMode.cs) | —（DTO） | — | — | — |

> **原稿订正**：`MTranDeleteMode` 不是「删除模式枚举/常量」，而是**中间取引删除的行数据模型（DTO）**，且命名空间为 `ForYouApplications.POS4U.Device.DeviceDefine`（非 `Business.MainMenu`，:1）。字段：`MTransactionId`/`Status`/`Date`/`Time`/`TotalQuantity`/`TotalAmount`/`IsDelete`。

各功能类的详细行为：

- **`MainMenuTran`**：主菜单入口，`IsOpend(POSData)` 依 `BusinessStateAccessor.GetBusinessStateRow` 的 `IsOpenCount` 判断是否已开设（:61-71）。
- **`PowerOnTran`**：唯一产生 `TranLogTypes.PowerOn` 日志的事务，`EndTran` 直接 `FixTran()`（走 [BusinessCommon 三写路径](../30_domain/business_common.md#21-事务共通基类-commontranbase本域核心--317-loc)）。
- **`DeviceSettingTran`**：设备接续/切断。`SettingDevices` 白名单 = `POSPrinter`/`CashChanger`/`CAFISArch`/`CAFISArchLAN`/`PaymentService`（:51-58）；`Connect`(:74)/`Disconnect`(:112) 经 `DeviceManager` 插件 `InitDevice`/`ReleaseDevice`；`ConnectCashDrawer`(:97) 额外接续钱箱（失败仅 Warn）。
- **`MTranDeleteTran`**：购物车中间取引删除。`Search(inputTerminalNo)`(:77) 经 `LogicServiceClient.SalesGetCartMTransactionList` 拉列表填入 `MTransactionList`（`Status` 由 `OperationState==0?"未処理":"異常"` 映射，:112）；`MTransactionSpecify`/`MTransactionSpecifyAll` 勾选；`Delete()`(:133) 收集 `IsDelete` 项 → `SalesDeleteCartMTransactionManagement` → 重新 `Search`。
- **`EJournalSearchTran`**（695 loc，本域最重）：EJournal 检索与再印字排版。`Search(...)`(:69) 做 7 项入力校验（日期 `yyyyMMdd`、时分范围等）后经 `LogicServiceClient` 检索，结果入 `EJournalModels`；`GetReprintReceiptData`(:240)/`GetReprintJournalData`(:485，带 `isDutyFreePrint` 免税印字参数) 重建再印字数据；含 receipt 页脚/中央寄せ/画线等排版 helper（`GetCenteringString`:606 等）。

## 3. 状态机

各事务专属 `TranState` 常量（`Common/Common.Const/State/`，前缀 `StatePrefixes`）：

| 事务 | 状态文件 | 状态节点（实测） |
|---|---|---|
| `MainMenuTran` | `MainMenuTranStates.cs` | `Neutral`(:17)、`WaitingForConfirmReboot`(:22) |
| `LockTran` | `LockTranStates.cs` | `Neutral`（构造置入，`LockTran:21`） |
| `DeviceSettingTran` | `DeviceSettingTranStates.cs` | `Neutral`（`DeviceSettingTran:23`） |
| `MTranDeleteTran` | `MTranDeleteTranStates.cs` | `Neutral`(:13)、`MTranDeleteConfirm`(:18) |
| `EJournalSearchTran` | `EJournalSearchTranStates.cs` | `Neutral`(:17) |

状态切换由各 Tran 的 `ChangeState(State)`（`LockTran:60`、`MTranDeleteTran:62`）驱动；具体迁移边由上层 Command/UI 触发，未在本域内枚举 → `uncheckable`（前端触发侧）。

## 4. 业务规则

- **BR-MAINMENU-001（仅电源投入落日志）**：6 个功能事务中唯 `PowerOnTran.EndTran` 调 `FixTran`；`MainMenu`/`Lock`/`DeviceSetting` 的 `EndTran` 返回 false，`MTranDelete`/`EJournalSearch` 的 `EndTran` 抛 `NotSupportedException`（表明不经确定路径）。
- **BR-MAINMENU-002（MTran 删除走边缘 LogicService）**：中间取引的查询/删除均委托 `LogicServiceClient`（云端购物车状态的真相源在边缘 WebAPI，`MTranDeleteTran.Search:94`/`Delete:152`）。
- **BR-MAINMENU-003（EJournal 训练模式横幅）**：再印字排版时若 `EJournalType == TranLogTypes.TrainingSales.Number` 则插入「トレーニング」横幅（`EJournalSearchTran:376`、:438）——是**再印字渲染**逻辑，非检索过滤。（原稿把此处描述为「检索时比较…以区分训练模式流水」，实为再印字侧渲染。）
- **BR-MAINMENU-004（EJournal 免税印字）**：`GetReprintJournalData` 的 `isDutyFreePrint` 控制是否输出免税明细（`GetPrintData:659`，按 `RJ_DutyFreeDetailMessage` 标记切分）。

## 5. 关键接口与契约

- 继承 `CommonTranBase`（→ [业务公共基盘域](../30_domain/business_common.md)）。
- `DeviceIds.LogicServiceClient` 设备插件：本域四事务（DeviceSetting 除外）经 `DeviceManager.GetDevice(DeviceIds.LogicServiceClient)` 获取，调用 `SalesGetCartMTransactionList`/`SalesDeleteCartMTransactionManagement`/`GetReprintReceiptData` 等（`LogicService.ServiceAccessor` 契约）。
- EJournal 再印字结果经 `Business.RJ` 排版打印 → 详见 [收据·日志域](../30_domain/rj.md)。

## 6. 数据依赖

`PowerOnTran` 经 `FixTran` 写 `TransactionLog`/`EJournal`（→ BusinessCommon）；`MainMenuTran.IsOpend`、`RefreshBusinessState` 读 `BusinessState`；EJournal 检索/再印字数据在**边缘 LogicService** 侧。TranLogType（PowerOn/None）与计数器 → [40_data/枚举与常量](../40_data/06_enums_constants.md)。

## 7. 设备依赖

`DeviceSettingTran` 直接编排 `POSPrinter`/`CashChanger`/`CAFISArch`/`CAFISArchLAN`/`PaymentService`/`CashDrawer`（`Device.DeviceDefine`）；全域经 `LogicServiceClient` 设备插件访问边缘逻辑 → 详见 [50_devices](../50_devices/index.md)。

## 8. 参与的端到端流程

日常运维（电源投入/设备设定/画面锁定）、EJournal 查询与再印字、购物车中间取引删除 → 详见 [70_flows](../70_flows/)。

## 9. 可信度与核查

- **verified（file:line）**：6 Tran 类 + `MTranDeleteMode` 模型的类/基类/TranType/TranLogType/EndTran 行为、`DeviceSettingTran` 设备白名单与接续逻辑、`MTranDeleteTran` 增删查、`EJournalSearchTran` 检索与再印字方法、状态常量，均实测于 最新发布（本次由 `unverified` 升级）。
- **uncheckable**：`TranBase`（Framework DLL）；`LogicServiceClient` 设备插件与边缘 WebAPI 服务端实现；UI/Command 触发的状态迁移边。

> 原稿订正：①`MTranDeleteMode` 是 DTO 模型（命名空间 `Device.DeviceDefine`），非枚举/常量；②`Data.DataSetExtensions` 依赖漏列；③训练模式比较位于再印字渲染而非检索过滤。

## 10. ST-POS 迁移提示

> ST-POS 的运维/日志功能分散于后端各服务与前端。对照仅供参考（外链）。
