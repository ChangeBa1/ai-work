---
title: 云端 BackOffice 接口与功能域（4 Controller · 双菜单各 93 action）
layer: 60_services
module: POS4UBackoffice
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/POS4UCloud/Source/POS4UBO/POS4UBackoffice/Controllers/BackOfficeMenuController.cs
  - Application/POS4UCloud/Source/POS4UBO/POS4UBackoffice/Controllers/CallCenterMenuController.cs
  - Application/POS4UCloud/Source/POS4UBO/POS4UBackoffice/Const/ControllersRoutePrefixes.cs
  - Application/POS4UCloud/Source/POS4UBO/POS4UBackoffice/Logics/
  - Application/POS4UCloud/Source/POS4UBO/Data/BOData.Accessor/
verification: verified
related:
  services:
    - ./index.md
    - ./auth_rbac.md
owner: jinianxiang
updated: 2026-07-14
---

# 云端 BackOffice 接口与功能域

> BackOffice 是服务端渲染的 MVC5 应用，「接口」即 Controller 的 action（GET 显示页面 / POST 提交或异步取数）。本文登记 4 个 Controller、路由常量、按功能域归类的 action，以及 action → `Logics` → `BOData.Accessor` → `usp_BO*` 的调用链。认证/权限见 [auth_rbac.md](./auth_rbac.md)。

---

## 1. Controller 与路由前缀

| Controller | RoutePrefix | 认证站点 | action 数 | 行 |
|---|---|---|---|---|
| `AccountController` | （无前缀，走默认路由） | `[AllowAnonymous]` | 5 | :18 |
| `BackOfficeMenuController` | `ControllersRoutePrefixes.BackOfficeMenu` | `[Authorize(Roles=nameof(BOSites.BackOffice))]` | 93 | :28 |
| `CallCenterMenuController` | `ControllersRoutePrefixes.CallCenterMenu` | `[Authorize(Roles=nameof(BOSites.CallCenter))]` | 93 | :28 |
| `ControllerBase` | —（`abstract : Controller`，公共基类） | — | — | :24 |

路由前缀常量 `Const/ControllersRoutePrefixes.cs`：`Account`(:11)、`BackOfficeMenu`(:14)、`CallCenterMenu`(:17)。

> `BackOfficeMenu` 与 `CallCenter​Menu` 两个 Controller 的 **93 个 action 完全同构**（仅前缀/站点/菜单主题不同，见 [auth_rbac.md §4](./auth_rbac.md)）。以下功能域以 `BackOfficeMenuController.cs` 行号为准，CallCenter 一一对应。

---

## 2. AccountController（5 action）

详见 [auth_rbac.md §2](./auth_rbac.md)：`Login()`(:26) / `Login(LoginModel)`(:39) / `Logout()`(:94) / `Error()`(:123) / `ErrorSessionTimeout()`(:141)。路由常量 `Const/AccountControllerActionsRoutes.cs`：`Login`(:11)/`Logout`(:14)/`Error`(:17)。

---

## 3. 业务菜单功能域（BackOfficeMenuController）

93 个 action 大体遵循「GET 显示页 + POST 检索/编辑」成对，主数据维护类另有 `Add`/`Edit`/`Delete`/`CsvUpload`。按功能域归类（行号为 `BackOfficeMenuController.cs`）：

| 功能域 | 代表 action（行号） | 对应 Logic |
|---|---|---|
| 仪表盘（首页） | `Index`(:36) + 异步取数 `GetReceiveMasterHistory`(:65)/`GetPosCollectionStatus`(:78)/`GetVMManagement`(:90)/`GetScheduleLog`(:102)/`GetUploadManagement`(:115)/`GetScheduleJob`(:128)/`GetStoreExpandSchedule`(:141) + `RegisterMessage`(:158)/`GetMessage`(:186) | `DashboardLogic` / `CommonLogic` |
| 主数据接收履历 | `ReceiveMasterHistory`(:212 / :266) | `ReceiveMasterHistoryLogic` |
| 店铺列表生成 | `CreateStoreList`(:331) | `CommonLogic` |
| 店铺环境确认 | `StoreTerminalCheck`(:346 / :367) | `StoreTerminalCheckLogic` |
| 集配信实绩送信 | `SendResultHistory`(:396 / :426) | `SendResultHistoryLogic` |
| POS 配信状况 | `PosDistributionStatusCheck`(:464 / :497) | `PosDistributionStatusCheckLogic` |
| POS 受信状况 | `PosCollectionStatusCheck`(:530 / :553) | `PosCollectionStatusCheckLogic` |
| Job 状况 | `JobStatusCheck`(:595 / :626) | `JobStatusCheckLogic` |
| 端末登录处理 | `TerminalSetting`(:667 / :680) | `TerminalSettingLogic` |
| 店铺复制 | `StoreCopy`(:712 / :732 `async`) + `StoreCopyGetSettingInfo`(:834) | `StoreCopyLogic` |
| 店铺端末编辑 | `TerminalMaintenance`(:849) + `StoreSearch`(:867)/`Add`(:892)/`Edit`(:953)/`Delete`(:1003) | `TerminalMaintenanceLogic` |
| 店铺设定编辑 | `SettingMaintenance`(:1040) + `Search`(:1058)/`Edit`(:1083) | `SettingMaintenanceLogic` |
| 收据消息编辑 | `ReceiptMessageMaintenance`(:1120 / :1140) + `Add`(:1166)/`Edit`(:1212)/`Delete`(:1259) | `ReceiptMessageMaintenanceLogic` |
| 支付媒体积分编辑 | `PaymentMasterMaintenance`(:1297) + `Search`(:1315)/`Edit`(:1340) | `PaymentMasterMaintenanceLogic` |
| 充值积分企划确认 | `ChargePointCalculateCheck`(:1377 / :1396) | `ChargePointCalculateCheckLogic` |
| POS 主数据批量配信 | `UploadManagementMaintenance`(:1425) + `Search`(:1444)/`SearchLatest`(:1472)/`Edit`(:1498)/`MakeFile`(:1547 `async`) | `UploadManagementMaintenanceLogic` |
| POS HW（能力）状况 | `PosTerminalCapacityStatusCheck`(:1611 / :1632) | `PosTerminalCapacityStatusCheckLogic` |
| 取引日志下载 | `TransactionLogDownload`(:1666 / :1686) + `Download`(:1720)/`Delete`(:1739) | `TransactionLogDownloadLogic`（→ Azure Blob） |
| 应用日志下载 | `AppLogDownload`(:1769) + `Search`(:1789)/`Download`(:1821)/`Delete`(:1838) | `AppLogDownloadLogic`（→ Azure Blob） |
| 功能菜单按钮主数据 | `FunctionMenuButtonMaster`(:1868 / :1886) + `Edit`(:1911)/`Add`(:1958)/`Delete`(:2013)/`CsvUpload`(:2055) | `FunctionMenuButtonMasterLogic` |
| 非条码其他商品主数据 | `NonBarcodeOtherItemMaster`(:2111 / :2129) + `Edit`(:2154)/`Add`(:2194)/`Delete`(:2242)/`CsvUpload`(:2282) | `NonBarcodeOtherItemMasterLogic` |
| 预设菜单按钮主数据 | `PresetMenuButtonMaster`(:2340) + `Search`(:2358)/`Edit`(:2383)/`Add`(:2430)/`Delete`(:2485)/`CsvUpload`(:2527) | `PresetMenuButtonMasterLogic` |
| 功能菜单主数据 | `FunctionMenuMaster`(:2585 / :2603) + `Edit`(:2628)/`Add`(:2670)/`Delete`(:2720)/`CsvUpload`(:2760) | `FunctionMenuMasterLogic` |
| 收银精算 | `ExecuteCloseCount`(:2818 / :2835) + `ExecuteCloseCountCloseCount`(:2861) | `ExecuteCloseCountLogic` |
| POS 模块配信编辑 | `UploadManagementForPosModule`(:2901 / :2929) + `Delete`(:2957)/`Add`(:2994) | `UploadManagementForPosModuleLogic`（→ Azure Blob） |
| 主数据配信文件下载 | `MasterMaintenanceFileDownload`(:3045 / :3066) + `Download`(:3100) | `MasterMaintenanceFileDownloadLogic` |

> 异步 action（`async Task<ActionResult>`）：`StoreCopy`(:732)、`UploadManagementMaintenance` 的 `MakeFile`(:1547)。路由常量在 `Const/BackOfficeMenuControllerActionsRoutes.cs`（**73** 个 `public const string`，`: MenuControllerActionsRoutesBase`）与 `CallCenterMenuControllerActionsRoutes.cs`（同 73 个、逐名一致）；基类 `MenuControllerActionsRoutesBase.cs:11` 定义共通 `Index`。

---

## 4. 调用链：action → Logics → Accessor → `usp_BO*`

Controller 只做入口，业务落在 `Logics/`（29 个静态类），DB 访问在 `BOData.Accessor/`（25 个 Accessor，`SqlCommand` 调存储过程）。代表连线：

| 入口 action | Logic | Accessor → SP |
|---|---|---|
| 登录 `AccountController.Login`(:47) | `AuthenticationLogic.Login`(:29) | `AuthAccessor.Login`(:23) → `usp_BOLogin` |
| 仪表盘消息登录 `RegisterMessage` | `DashboardLogic` | `DashboardAccessor.cs:320` → `usp_BOInsertMessageManagement` |
| 主数据接收履历 `ReceiveMasterHistory`(:266) | `ReceiveMasterHistoryLogic.cs:67` | `ReceiveMasterHistoryAccessor`（`DataAccessTypes.Tran`）→ `usp_BOGetReceiveMasterHistory` |
| 功能菜单主数据 `FunctionMenuMaster.*` | `FunctionMenuMasterLogic.cs:13` | `FunctionMenuMasterAccessor.cs:91/:147/:195` → `usp_BOUpdate/Insert/DeleteFunctionMenuMaster` |

`usp_BO*` 的命名订正与数据库归属见 [index.md §4](./index.md)（前缀无下划线；SP 跑 Master/Tran 库，物理位置 uncheckable）。

---

## 5. Azure Storage 直连（日志/配信）

部分功能由 `Logics` 直接经 `Azure.Logic` 读写 Blob：

- `UploadManagementForPosModuleLogic.cs:28` `StorageLibrary.GetInstance(Account.Default)`
- `TransactionLogDownloadLogic.cs:137` `StorageLibrary.GetInstance(Account.TransactionLog)`
- `AppLogDownloadLogic.cs:65` `StorageLibrary.GetInstance(Account.Default)`

Blob/Queue 封装见 `Azure/Azure.Logic/Accessor/StorageLibraryBase.cs`（Blob :196/:300、Queue :494/:506）。

---

## 6. Models（视图模型 / DTO）

`POS4UBackoffice/Models/`（实测 **74** 个 `.cs`）。主要基类/代表：

| 类 | 行 | 角色 |
|---|---|---|
| `LoginModel` | :11 | 登录输入（CompanyCode/UserCode/Password，均 `[Required]`） |
| `DashboardPageModel` | :9 | 首页仪表盘页面模型 |
| `BORoleModel` | :6 | 角色 DTO |
| `BOAbilityModel` | :6 | 权限（ability）DTO |
| `MaintenancePageModelBase` | :11 | `abstract` 维护页面模型基类 |
| `MasterModelForCsvUploadBase` | :14 | `abstract` CSV 上传主数据基类（含 `StoreCode`） |

其余按功能成组：`*PageModel`（页面模型）、`*Model`（行/DTO）、`*DBModel`（DB 投影）。

---

## 7. 可信度与核查

`verification: verified`：Controller 数、双菜单各 93 action、代表 action 行号、`ActionsRoutes` 各 73 常量、`Logics` 29、`Models` 74 均实测 `pos-cloud`（BackOffice）核对。§3 未逐一展开全部 93 action（同构且重复），按功能域给代表行号；§4 调用链给代表连线。`usp_BO*` SP 内部实现属数据库层，不在此断言。
