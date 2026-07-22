---
title: 边缘 API 控制器清单（11 Controller · 70 action）
layer: 60_services
module: POS4ULogicService.Controllers
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/POS4ULogicService/Controllers/POSLogicWebServiceController.cs
  - Application/Source/POS4ULogicService/Controllers/BackOfficeServiceController.cs
  - Application/Source/POS4ULogicService/Controllers/DataServiceController.cs
  - Application/Source/POS4ULogicService/Controllers/ReportServiceController.cs
  - Application/Source/POS4ULogicService/Controllers/BackgroundServiceController.cs
  - Application/Source/POS4ULogicService/Controllers/CartMTranServiceController.cs
  - Application/Source/POS4ULogicService/Controllers/MTranServiceController.cs
  - Application/Source/POS4ULogicService/Controllers/MemberServiceController.cs
  - Application/Source/POS4ULogicService/Controllers/ReceiptServiceController.cs
  - Application/Source/POS4ULogicService/Controllers/ItemDetectionServiceController.cs
  - Application/Source/POS4ULogicService/Controllers/CheckHealthController.cs
verification: verified
related:
  services:
    - ./index.md
    - ./command_layer.md
    - ./conventions.md
owner: jinianxiang
updated: 2026-07-14
---

# 边缘 API 控制器清单（11 Controller · 70 action）

> 本文枚举 `Application/Source/POS4ULogicService/Controllers/` 下**全部 11 个 Controller** 及其公开 action。行号锚定 最新发布（`Controllers/` 目录内文件，下同）。路由为 **ASP.NET Web API 属性路由**（`WebApiConfig.cs:25` `MapHttpAttributeRoutes()`），实际 URL = `{RoutePrefix}/{Route}`。

---

## 0. 总表

| # | Controller | RoutePrefix | 基类 | action 数 | 职责 |
|---|---|---|---|---|---|
| 1 | POSLogicWebServiceController | `POSLogicWebService.svc` | `ApiController` | 14 | 取引操作（前台事件受理入口） |
| 2 | BackOfficeServiceController | `BackOfficeService.svc` | `ApiController` | 7 | 店内维护/管理（バックオフィス） |
| 3 | DataServiceController | `DataService.svc` | `ApiController` | 11 | 主数据/模块下发・上传 |
| 4 | ReportServiceController | `ReportService.svc` | `ApiControllerBase` | 8 | 报表・BI 速报 |
| 5 | BackgroundServiceController | `BackgroundService.svc` | `ApiControllerBase` | 11 | 后台任务入队・交易日志接收 |
| 6 | CartMTranServiceController | `CartMTranService.svc` | `ApiController` | 3 | 挂账（中断取引）· 购物车侧 |
| 7 | MTranServiceController | `MTranService.svc` | `ApiController` | 2 | 挂账（中断取引）· 终端侧 |
| 8 | MemberServiceController | `MemberService.svc` | `ApiController` | 3 | 会员信息・积分 |
| 9 | ReceiptServiceController | `ReceiptService.svc` | `ApiController` | 2 | 收据一览・明细 |
| 10 | ItemDetectionServiceController | `ItemDetectionService`（**无 `.svc`**） | `ApiController` | 7 | 商品识别（ItemDetection）· 称重 |
| 11 | CheckHealthController | `CheckHealth.svc` | `ApiController` | 2 | 死活监视 |

计：**70** 个公开 action。基类差异见 §12 与 [conventions.md](./conventions.md)。

> 基类两分：多数 Controller 直接继承 `ApiController` 并在每个 action 内手写「读体→脱敏→鉴权→计时→try/catch」；仅 `BackgroundServiceController`、`ReportServiceController` 继承自定义基类 `ApiControllerBase`（`ApiControllerBase.cs:21` 的 `ExecuteLogic<TParam,TResult>` 泛型封装）。

---

## 1. POSLogicWebServiceController（`POSLogicWebService.svc`）

取引操作。前台每个操作事件经此 Controller 进入命令引擎。文件：`POSLogicWebServiceController.cs`。

| action | HTTP | 路由 | 方法行 | 职责 |
|---|---|---|---|---|
| AcceptEvent | POST | `AcceptEvent/{companyCode}/{storeCode}/{terminalNo}` | :49 | 事件受理主入口；版本不符时 `RedirectAcceptEvent`（:53-58） |
| AcceptEventOld | POST | `AcceptEventOld/{c}/{s}/{t}` | :74 | 事件受理（旧模块用） |
| AcceptEventNew | POST | `AcceptEventNew/{c}/{s}/{t}` | :89 | 事件受理（新模块用） |
| GetTransactionResponseInfo | POST | `GetTransactionResponseInfo/{c}/{s}` | :103 | 取得已发生交易的响应信息一览 |
| AddItemMaster | POST | `AddItemMaster/{c}/{s}` | :159 | 商品マスタ緊急メンテナンス（追加） |
| ChangePriceItemMaster | POST | `ChangePriceItemMaster/{c}/{s}` | :207 | 商品マスタ緊急メンテナンス（价格变更） |
| PutCashChangerStatus | POST | `PutCashChangerStatus/{c}/{s}/{t}` | :256 | 登录釣銭機（找零机）状态 |
| PutTerminalCapacity | POST | `PutTerminalCapacity/{c}/{s}/{t}` | :305 | 登录端末能力 |
| GetOneTimeBarcode | POST | `GetOneTimeBarcode/{c}` | :352 | 取得一次性条码 |
| VerifyOneTimeBarcode | POST | `VerifyOneTimeBarcode/{c}` | :408 | 校验一次性条码 |
| GetCurrentDateTime | POST | `GetCurrentDateTime/{c}/{s}/{t}` | :466 | 取得当前日时 |
| GetTransactionLog | POST | `GetTransactionLog/{c}/{s}/{t}` | :515 | 取得交易日志 |
| PutBusinessCounter | POST | `PutBusinessCounter/{c}/{s}/{t}` | :564 | 登录营业计数器 |
| GetBusinessCounterList | POST | `GetBusinessCounterList/{c}/{s}/{t}` | :613 | 取得营业计数器一览 |

- 事件分发落点：`:677` `LogicServiceController.Instance.AcceptEvent(new object[]{companyCode, storeCode, terminalNo, content})`（引擎在 Framework.dll，见 [command_layer.md](./command_layer.md)）。
- URI 模板常量：`:25` `"{0}/POSLogicWebService.svc/{1}/{2}/{3}/{4}?Timestamp={5}"`。

---

## 2. BackOfficeServiceController（`BackOfficeService.svc`）

店内维护/管理。文件：`BackOfficeServiceController.cs`。

| action | HTTP | 路由 | 方法行 | 职责 |
|---|---|---|---|---|
| CommitMaintenanceData | POST | `CommitMaintenanceData` | :42 | 提交维护数据 |
| GetItemImageFile | **GET** | `GetItemImageFile/{companyCode}/{storeCode}/{fileName}` | :94 | 取得商品图片文件（返回 `HttpResponseMessage`） |
| CheckExistMaintenanceData | POST | `CheckExistMaintenanceData` | :153 | 检查维护数据是否存在 |
| GetManagementInitialData | POST | `GetManagementInitialData/{c}/{s}/{t}` | :209 | 取得管理初始数据 |
| GetManagementData | POST | `GetManagementData/{c}/{s}/{t}` | :276 | 取得管理数据 |
| GetReprintReceiptData | POST | `GetReprintReceiptData/{c}/{s}/{t}` | :343 | 取得补打收据数据 |
| CheckLoginUserPermission | （无动词特性） | `CheckLoginUserPermission` | :407 | 登录用户权限检查。⚠️ `[HttpPost]` 已被注释（:405），仅保留 `[Route]`（:406） |

> `GetManagementData`、`GetReprintReceiptData`、`CheckLoginUserPermission` 三个 action 任务清单未列，此处据源码补全。

---

## 3. DataServiceController（`DataService.svc`）

主数据与模块的下发/上传。文件：`DataServiceController.cs`。

| action | HTTP | 路由 | 方法行 | 职责 |
|---|---|---|---|---|
| CheckExistUpdateModule | POST | `CheckExistUpdateModule/{c}/{s}` | :55 | 检查是否存在更新模块 |
| NotifyModuleUpload | POST | `NotifyModuleUpload/{c}/{s}/{t}` | :114 | 通知模块上传 |
| GetMasterDownloadFile | POST | `GetMasterDownloadFile/{c}` | :172 | 取得主数据下载文件（返回 `HttpResponseMessage` 文件流） |
| GetMasterDownloadInfo | POST | `GetMasterDownloadInfo/{c}/{s}/{t}` | :254 | 取得主数据下载信息 |
| GetMasterDownloadInfo2 | POST | `GetMasterDownloadInfo2/{c}/{s}/{t}` | :311 | 取得主数据下载信息（v2） |
| NotifyMasterDownloadCompleted | POST | `NotifyMasterDownloadCompleted/{c}/{s}/{t}` | :368 | 通知主数据下载完成 |
| GetMasterUpdateInfo | POST | `GetMasterUpdateInfo/{c}/{s}/{t}` | :424 | 取得主数据更新信息 |
| GetMasterUpdateInfo2 | POST | `GetMasterUpdateInfo2/{c}/{s}/{t}` | :481 | 取得主数据更新信息（v2） |
| NotifyMasterUpdateCompleted | POST | `NotifyMasterUpdateCompleted/{c}/{s}/{t}` | :538 | 通知主数据更新完成 |
| UploadFile | POST | `UploadFile/{c}` | :592 | 上传文件 |
| DownloadFile | POST | `DownloadFile/{c}` | :659 | 下载文件（返回 `HttpResponseMessage` 文件流） |

---

## 4. ReportServiceController（`ReportService.svc`）

报表与 BI 速报。文件：`ReportServiceController.cs`。基类 `ApiControllerBase`（部分 action 用 `ExecuteLogic`，如 :260/:357）。

| action | HTTP | 路由 | 方法行 | 职责 |
|---|---|---|---|---|
| GetRMReportData | POST | `GetRMReportData/{c}/{s}` | :55 | 取得 RM 报表数据（`HttpResponseMessage`） |
| GetTransactionRMResult | POST | `GetTransactionRMResult/{c}/{s}` | :130 | 取得交易 RM 结果 |
| GetBISalesFlashCsvFile | POST | `GetBISalesFlashCsvFile`（`nameof`） | :185 | 取得 BI 销售速报 CSV 文件（`HttpResponseMessage`） |
| GetBISalesFlash | POST | `GetBISalesFlash`（`nameof`） | :258 | 取得 BI 销售速报 |
| GetBISalesFlashTimeZoneDetailCsvFile | POST | `GetBISalesFlashTimeZoneDetailCsvFile`（`nameof`） | :282 | 取得 BI 销售速报·时段明细 CSV |
| GetBISalesFlashTimeZoneDetail | POST | `GetBISalesFlashTimeZoneDetail`（`nameof`） | :355 | 取得 BI 销售速报·时段明细 |
| GetMobileUsageData | POST | `GetMobileUsageData/{c}/{s}` | :381 | 取得移动利用数据（`HttpResponseMessage`） |
| GetFaceMeUsageData | POST | `GetFaceMeUsageData/{c}/{s}` | :456 | 取得 FaceMe 利用数据（`HttpResponseMessage`） |

---

## 5. BackgroundServiceController（`BackgroundService.svc`）

后台任务入队与交易/电子日志接收，是 [后台批处理](../background/index.md) 与边缘服务的对接点。文件：`BackgroundServiceController.cs`。基类 `ApiControllerBase`，**全部 action 经 `ExecuteLogic` 表达式体实现**（=> 单行）。

| action | HTTP | 路由 | 方法行 | 职责 |
|---|---|---|---|---|
| EnqueueBOStoreCopySchedule | POST | `EnqueueBOStoreCopySchedule`（`nameof`） | :46 | 入队「BO 店铺复制」计划 |
| EnqueueBOMakeDailyMasterDownloadFileSchedule | POST | `EnqueueBOMakeDailyMasterDownloadFileSchedule`（`nameof`） | :69 | 入队「BO 生成每日主数据下载文件」计划 |
| GetLastTransactionLog | POST | `GetLastTransactionLog` | :98 | 取得最后交易日志 |
| GetLastEJournal | POST | `GetLastEJournal` | :108 | 取得最后电子日志（EJournal） |
| PutTransactionLog | POST | `PutTransactionLog` | :118 | 登录交易日志 |
| PutTransactionLogList | POST | `PutTransactionLogList` | :128 | 批量登录交易日志 |
| PutEJournal | POST | `PutEJournal` | :138 | 登录电子日志 |
| SetOnPremisesManagement | POST | `SetOnPremisesManagement` | :152 | 设置本地（on-premises）管理 |
| GetNewModulenfo | POST | `GetNewModulenfo` | :162 | 取得新模块信息（方法名原样保留拼写 `Modulenfo`） |
| CheckModuleExist | POST | `CheckModuleExist` | :172 | 检查模块是否存在 |
| UpdateModuleManagement | POST | `UpdateModuleManagement` | :182 | 更新模块管理 |

> 另有一个 `EnqueueSchedule` 被整体注释（:28-29），不计入活跃 action。

---

## 6. CartMTranServiceController（`CartMTranService.svc`）

挂账（中断取引）· 购物车侧。文件：`CartMTranServiceController.cs`。

| action | HTTP | 路由 | 方法行 | 职责 |
|---|---|---|---|---|
| GetMTransaction | POST | `GetMTransaction/{c}/{s}/{t}` | :35 | 取得中断取引 |
| GetMTransactionList | POST | `GetMTransactionList/{c}/{s}/{t}` | :118 | 取得中断取引一览 |
| DeleteMTransactions | POST | `DeleteMTransactions/{c}/{s}/{t}` | :201 | 删除中断取引（复数） |

---

## 7. MTranServiceController（`MTranService.svc`）

挂账（中断取引）· 终端侧，按 `mTransactionId` 定位。文件：`MTranServiceController.cs`。

| action | HTTP | 路由 | 方法行 | 职责 |
|---|---|---|---|---|
| GetMTransaction | POST | `GetMTransaction/{c}/{s}/{mTransactionId}` | :41 | 取得中断取引 |
| DeleteMTransaction | POST | `DeleteMTransaction/{c}/{s}/{mTransactionId}` | :123 | 删除中断取引（单数） |

---

## 8. MemberServiceController（`MemberService.svc`）

会员信息与积分。文件：`MemberServiceController.cs`。逻辑委托 `GetMemberInfoLogic`（构造于 :33）。

| action | HTTP | 路由 | 方法行 | 职责 |
|---|---|---|---|---|
| GetMemberInfo | POST | `GetMemberInfo` | :42 | 取得会员信息 |
| PointPlus | POST | `PointPlus` | :96 | 积分加算（内部 `PointPlusMinus(false)`，:117） |
| PointMinus | POST | `PointMinus` | :107 | 积分减算（内部 `PointPlusMinus(true)`，:117） |

---

## 9. ReceiptServiceController（`ReceiptService.svc`）

收据。文件：`ReceiptServiceController.cs`。action 参数 `timestamp` 来自 query。

| action | HTTP | 路由 | 方法行 | 职责 |
|---|---|---|---|---|
| GetReceiptList | POST | `GetReceiptList` | :48 | 取得收据一览 |
| GetReceiptData | POST | `GetReceiptData` | :104 | 取得收据数据 |

---

## 10. ItemDetectionServiceController（`ItemDetectionService`）

商品识别（ItemDetection）与称重。文件：`ItemDetectionServiceController.cs`。**RoutePrefix 无 `.svc` 后缀**（:15），路由均用 `[Route(nameof(...))]`。该 Controller 自带私有 `ExecuteLogic<TParam,TResult>(func, parameter)`（:120，鉴权在其中 :139），逻辑委托 `ItemDetectionLogic`。

| action | HTTP | 路由 | 方法行 | 职责 |
|---|---|---|---|---|
| RequestUploadItemDetectionServicesAppLog | POST | `RequestUploadItemDetectionServicesAppLog` | :25 | 请求上传商品识别服务应用日志 |
| UploadItemDetectionServicesAppLog | POST | `UploadItemDetectionServicesAppLog` | :33 | 上传商品识别服务应用日志（返回 `void`） |
| GetItemsWeight | POST | `GetItemsWeight` | :69 | 取得商品重量 |
| SetItemsWeight | POST | `SetItemsWeight` | :79 | 设置商品重量 |
| GetBulkOfCaseSalesWeight | POST | `GetBulkOfCaseSalesWeight` | :89 | 取得整箱销售批量重量 |
| SetBulkOfCaseSalesWeight | POST | `SetBulkOfCaseSalesWeight` | :99 | 设置整箱销售批量重量 |
| DeleteBulkOfCaseSalesWeight | POST | `DeleteBulkOfCaseSalesWeight` | :109 | 删除整箱销售批量重量 |

---

## 11. CheckHealthController（`CheckHealth.svc`）

死活监视。文件：`CheckHealthController.cs`（全文仅 38 行）。

| action | HTTP | 路由 | 方法行 | 职责 |
|---|---|---|---|---|
| CheckHealthApiGateway | **GET** | `CheckHealthApiGateway` | :19 | Azure API Gateway 探针用；恒返回 `IsSuccess = true`（:21） |
| CheckHealth | **GET** | `CheckHealth` | :30 | 外部死活监视用；经 `CheckHealthAccessor.CheckHealth()` 实际探测（:34） |

---

## 12. 共性与差异

- **HTTP 动词**：除 `GetItemImageFile`（GET）、`CheckHealth*`（GET）外，其余 action 均为 `[HttpPost]`；`CheckLoginUserPermission` 的 `[HttpPost]` 被注释（见 §2）。
- **返回文件流**的 action 用 `HttpResponseMessage`：`GetItemImageFile`、`DataService.Get/DownloadFile`、`Report` 的多个 CSV/报表 action。
- **鉴权**：几乎所有业务 action 在入口调用 `POS4ULogicServiceLibrary.IsValidAccessCode(...)`；`BackOfficeService` 的部分 action 改用 `VerifyUrl(...)`（仅校验端末番号）。统一模式与错误码详见 [conventions.md](./conventions.md)。
- **逻辑委托**：Controller 仅做「受理+鉴权+计时」，业务转交 `LogicService.ApiLogic` 的 `*Logic` 类或命令引擎，详见 [command_layer.md](./command_layer.md)。

---

## 13. 可信度与核查

`verification: verified`：11 个 Controller 与 70 个 action 的 RoutePrefix / Route / HTTP 动词 / 方法行号 / 返回类型均逐条实测核对（最新发布）。action 职责说明取自各方法的日文 `<summary>` 注释直译，无源码依据处未擅自补写。`ItemDetection` 对接的外部识别系统细节不在本层源码内，仅按方法命名/注释描述。
