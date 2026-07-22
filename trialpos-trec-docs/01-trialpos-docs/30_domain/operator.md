---
title: 操作员·登录登出域（Business.Operator）
layer: 30_domain
module: Business.Operator
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/Business/Business.Operator/Operator.cs
  - Application/Source/Business/Business.Operator/SignInOutTranBase.cs
  - Application/Source/Business/Business.Operator/SignInTran.cs
  - Application/Source/Business/Business.Operator/SignOutTran.cs
  - Application/Source/Business/Business.Operator/ExtensionMethods/UserDataExtensionMethods.cs
  - Application/Source/Business/Business.Operator/Const/OperatorExtensionUserObjectIds.cs
verification: verified
related:
  data:  [../40_data/06_enums_constants.md]
  domain: [../30_domain/business_common.md, ../30_domain/open_close.md]
  devices: [../50_devices/index.md]
owner: jinianxiang
updated: 2026-07-14
---

# 操作员·登录登出域（Business.Operator）

> `verification: verified`——7 个源码文件（324 loc）全部逐条核实（最新发布）。`TranBase`/`UserData`/釣銭機设备内部属 `POS4U.Framework.dll` / Device，标 `uncheckable`。

## 1. 模块定位

管理收银员（オペレーター）身份对象与其**サインイン / サインアウト**（登录/登出）事务。承载两类操作员——**キャッシャー（Cashier）** 与 **チェッカー（Checker）**（双人作业），均以 `UserData` 扩展对象形式挂载。登录/登出事务在确定时**顺带读取釣銭機在高**（釣銭在高 `CalculatedCash`）。

- 命名空间：`ForYouApplications.POS4U.Business.Operator`
- ProjectReference（`Business.Operator.csproj` 实测）：`Business.BusinessCommon`、`Common.Const`、`Data.Accessor`、`Data.Container`、`Device.DeviceCommon`、`Device.DeviceDefine`。

## 2. 代码结构

7 个 `.cs`（含 `AssemblyInfo`）；核心 6 类，实测如下。

| 类型 | file:line | 说明 |
|---|---|---|
| `Operator` | [`Operator.cs:16`](Application/Source/Business/Business.Operator/Operator.cs) | `[Serializable]`（:15）操作员对象。属性 `Code`(:21)/`Name`(:26)/`RoleCode`(:31)/`StartWaitDateTime`(:36)/只读 `IsSignIn`(:42)。含 `SignIn(UserData,code)`(:56)、`SignOut(UserData)`(:85) 方法 |
| `SignInOutTranBase` | [`SignInOutTranBase.cs:13`](Application/Source/Business/Business.Operator/SignInOutTranBase.cs) | `abstract : CommonTranBase`，登录登出共通基类。属性 `CalculatedCash`(:18)、`CashChangerCashCount`(:23)；override `EndTran()`(:29) |
| `SignInTran` | [`SignInTran.cs:9`](Application/Source/Business/Business.Operator/SignInTran.cs) | `: SignInOutTranBase`。`TranLogType`→`TranLogTypes.SignIn`(:18)、`TranType`→`TranTypes.SignIn`(:29) |
| `SignOutTran` | [`SignOutTran.cs:9`](Application/Source/Business/Business.Operator/SignOutTran.cs) | `: SignInOutTranBase`。`TranLogType`→`TranLogTypes.SignOut`(:18)、`TranType`→`TranTypes.SignOut`(:29) |
| `UserDataExtensionMethods` | [`ExtensionMethods/UserDataExtensionMethods.cs:12`](Application/Source/Business/Business.Operator/ExtensionMethods/UserDataExtensionMethods.cs) | `static`。`GetCashier(this UserData)`(:19)、`GetChecker(this UserData)`(:37)——从 UserData 扩展对象取/建 `Operator`（不存在则 new 并 set） |
| `OperatorExtensionUserObjectIds` | [`Const/OperatorExtensionUserObjectIds.cs:12`](Application/Source/Business/Business.Operator/Const/OperatorExtensionUserObjectIds.cs) | `internal static`。`Cashier`(:17)、`Checker`(:22)，均 `ExtensionUserObjectId<Operator>` |

> `CommonTranBase` 是源码类（[`Business.BusinessCommon/CommonTranBase.cs:19`](Application/Source/Business/Business.BusinessCommon/CommonTranBase.cs) `abstract : TranBase, IDisposable`）；其上的 `TranBase` 在 `POS4U.Framework.dll`（无源码，`uncheckable`）。

## 3. 状态机

**无 Operator 专属状态文件**：`Common/Common.Const/State/` 下不存在 SignIn/SignOut/Operator 的 `*TranStates.cs`（实测仅有相关的 `TwoOperatorsStates.cs`）。`SignInTran`/`SignOutTran` 不显式设置 `CurrentState`，登录登出流程复用 `CommonTranBase`（→`TranBase`）的通用事务骨架（Start/Fix/End），骨架细节在 Framework DLL，`uncheckable`。

## 4. 业务规则

- **BR-OPERATOR-001（登录校验）**：`SignIn` 先判 `code` 空→`MessageIds.ErrorInputNeed`；否则把 `code` 左补零至 `SettingValues.EmployeeCodeLength` 长度，查 `EmployeeMasterAccessor.GetEmployeeMasterRow`；查无→`MessageIds.ErrorInputIllegal`。`Operator.cs:56-71`。
- **BR-OPERATOR-002（登录赋值）**：命中后写入 `Code`/`RoleCode`/`Name`（来自 EmployeeMaster 行），`StartWaitDateTime = DateTimeUtility.GetUserTimeNow()`。`Operator.cs:73-76`。`IsSignIn` 以 `Code` 非空判定（`Operator.cs:42-48`）。
- **BR-OPERATOR-003（登出清空）**：`SignOut` 将 `Code`/`Name`/`RoleCode`/`StartWaitDateTime` 全部置 null。`Operator.cs:85-91`。
- **BR-OPERATOR-004（登录/登出携带釣銭在高）**：`SignInOutTranBase.EndTran()` 经 `DeviceManager` 插件取 `DeviceIds.CashChanger`；设备存在且 `IsEnable` 时 `ReadCashCounts()`，`CalculatedCash = Σ(CashCount.Denomination×Count) + Σ(OverCount.Denomination×Count)`，并留存 `CashChangerCashCount`，最后 `FixTran()`。`SignInOutTranBase.cs:29-53`。
- **BR-OPERATOR-005（双操作员：Cashier / Checker）**：同一 `UserData` 上并存两个 `Operator` 扩展对象——`Cashier` 与 `Checker`，通过 `GetCashier()`/`GetChecker()` 惰性获取。`UserDataExtensionMethods.cs:19-48`、`OperatorExtensionUserObjectIds.cs:17-22`。

> 合规/权限背景：`RoleCode`（`Operator.cs:31`）承载操作员角色，供权限判定使用；本模块只**读取**角色码，不含权限校验逻辑（权限判定在其他模块/框架，本模块未见）。

## 5. 关键接口与契约

- `Operator`：`[Serializable]`（`Operator.cs:15`）——可随 UserData / 事务序列化跨进程携带。
- `SignInOutTranBase.EndTran()`（`:29`）：登录登出共通的确定钩子，产出 `CalculatedCash` / `CashChangerCashCount`。
- 事务种别：`TranTypes.SignIn` / `TranTypes.SignOut`；日志种别：`TranLogTypes.SignIn`(=205) / `TranLogTypes.SignOut`(=206)（[`Common.Const/TranLogTypes.cs:112,117`](Application/Source/Common/Common.Const/TranLogTypes.cs)）。

## 6. 数据依赖

- 従業員主数据：`EmployeeMasterAccessor.GetEmployeeMasterRow`（[`Data/Data.Accessor/EmployeeMasterAccessor.cs:24`](Application/Source/Data/Data.Accessor/EmployeeMasterAccessor.cs)），返 `EmployeeDataSet.EmployeeMasterRow`（Code/RoleCode/Name）。
- 设定值：`SettingValues.EmployeeCodeLength`（[`Common.Const/SettingValues.cs:63`](Application/Source/Common/Common.Const/SettingValues.cs)）。
- TranLogType（SignIn=205 / SignOut=206）→ [40_data/枚举与常量](../40_data/06_enums_constants.md)。表结构（従業員マスタ）→ 40_data（不复制字典）。

## 7. 设备依赖

**釣銭機（CashChanger）**：登录/登出确定时读取在高——`Device.DeviceDefine.CashChanger`（`ICashChanger` / `CashCountDataSet`），经 `Factory.CreatePlugin(FrameworkPluginIds.DeviceManager).GetDevice(DeviceIds.CashChanger)` 获取。→ 详见 [50_devices](../50_devices/index.md)。设备内部实现 `uncheckable`。

> 原稿曾推测"依赖刷卡/键盘登录设备"——**未见源码依据**；实测唯一设备依赖为釣銭機（读在高），登录本身仅键入従業員コード（无专用登录设备）。

## 8. 参与的端到端流程

- 营业开始前收银员登录、精算/关店前登出（登出确定时记录釣銭在高）→ 详见 [开闭店精算域](../30_domain/open_close.md)、[70_flows](../70_flows/)。

## 9. 可信度与核查

- **verified**：`Operator` 实体全字段/方法、`SignInOutTranBase.EndTran` 釣銭在高逻辑、SignIn/SignOut 两 Tran 的 TranType/TranLogType（含 205/206 数值）、Cashier/Checker 双扩展对象、EmployeeMaster/SettingValues 依赖，均逐条实测于 最新发布。
- **uncheckable**：`TranBase`、`UserData`、`ExtensionUserObjectId<T>` 内部实现（Framework DLL）；釣銭機设备内部实现（Device）。
- 订正：原稿"可能依赖刷卡/键盘登录设备"删除，改为釣銭在高读取；补入 Cashier/Checker 双操作员机制、SignIn 校验规则、TranType 绑定与 205/206 数值。

## 10. ST-POS 迁移提示

> ST-POS 后端操作员/登录在 `account` 等服务独立实现，且无釣銭機在高耦合。对照仅供参考（外链）。
