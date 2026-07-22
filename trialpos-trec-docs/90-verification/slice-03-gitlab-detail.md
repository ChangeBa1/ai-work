# 切片 03：03-gitlab-wiki（AIPOS wiki＝POS4U 框架开发指南）精度核查报告

- 核查对象：`12-gitlab-wiki`（共 **158** 个 .md）
- 真值代码库：`../trialpos-snapshots/pos-store-ver202606`（门店端）、`.../pos-cloud/Source/POS4UBO`（BO）、`.../database`
- 核查原则：**仅以真实 .cs/.xml/.sql/.csproj/.sln 代码文件（含 file:line）为证据**；docs/ 未采信。
- 判定图例：✅一致 / ⚠️部分一致 / ❌偏差 / 🕰️过时 / 🔵无法核查

---

## 一、框架五要素（核心，逐条到代码）

### Command（2_3.-Command / 2_5.-Command）✅一致
| 声明 | 代码证据 | 判定 |
|---|---|---|
| Command 名字定义在 EventCode 里 | `Common/Common.Const/EventCodes.cs`（如 `Sales_ChangeDisplayWithMode` line1220） | ✅ |
| WinPOS/Command/ 下编写 Command 类 | `WinPOS/Command/` 含 12 个业务包：WinPOS.CommandSales / CommandPaymentService / CommandCashChanger… | ✅ |
| PluginWinPOS.xml 注册 Command | `POS4U/Settings/PluginWinPOS.xml` 有 `<Group Id="Command">`（grep 命中） | ✅ |
| StateWinPOS.xml 在状态下注册 Command | `POS4U/Settings/StateWinPOS.xml` 内 `<Command Id="Sales_Clear"/>` 等 | ✅ |
| Command 基类继承 | `WinPOS/Command/WinPOS.CommandSales/CommandSalesBase.cs` 等 *Base 类存在 | ✅ |

结论：Command 四步流程与代码结构**完全吻合**；命名前缀（Sales_/Common_/PaymentService_）与代码分包一致，印证协调者补充口径。

### Event（2_2.-Event / 2_4.-Event）✅一致（路径过时）
| 声明 | 代码证据 | 判定 |
|---|---|---|
| Event 定义在 `Bussiness/Common/EventCodes.cs` | 实际为 `Common/Common.Const/EventCodes.cs`（顶层 Common 项目，非 Business/Common，且缺 `.Const`） | 🕰️路径过时 |
| `Sales_ChangeDisplayWithMode = 411` | `Common/Common.Const/EventCodes.cs:1220` **完全一致** | ✅ |
| EventCode 与 Command 同名 | 印证：EventCodes.cs 名 = WinPOS/Command 类名 | ✅ |

### State（2_6.-State）✅一致（路径过时）
| 声明 | 代码证据 | 判定 |
|---|---|---|
| 状态定义在 `Bussiness/Common/Common.Const/State` | 实际 `Common/Common.Const/State/`（30+ *TranStates.cs） | 🕰️路径前缀过时 |
| SelfStates.cs 示例 | `Common/Common.Const/State/SelfStates.cs` 存在 | ✅ |
| 取引基类有 CurrentState / TranState / MainTranState 三属性 | 用法印证：`Business/Business.CashInOut/CashInOutTran.cs:279` `this.CurrentState = this.MainTranState;`（多处）；基类 `CommonTranBase : TranBase`（`Business/Business.BusinessCommon/CommonTranBase.cs:19`，TranBase 属框架核心程序集，本仓无源码） | ✅（属性由用法证实） |
| State 在 StateWinPOS.xml 控制 Command 可否 | 同上 StateWinPOS.xml | ✅ |

### 取引 Tran（2_1.-取引 / 2_3.-取引 / 2_5.-Tran）✅一致（路径过时）
| 声明 | 代码证据 | 判定 |
|---|---|---|
| TranType 定义在 `Bussiness/Common/Common.Const/TranTypes.cs` | 实际 `Common/Common.Const/TranTypes.cs`（Sales/SelfSales/Return/EMoneyCharge…） | 🕰️路径前缀过时 |
| `EMoneyChargeTran.cs` 对应 TranTypes.EMoneyCharge | `Business/Business.EMoney/EMoneyChargeTran.cs` 存在 | ✅ |
| `posData.CreateTran<SelfSalesTran>` 创建 Tran | `WinPOS/Command/WinPOS.CommandReSales/ReSales_ChangeDisplay.cs:57` `posData.CreateTran<ReSalesTran>()`（泛型方法存在） | ✅（wiki 缺 `()` 小瑕） |

### POS（2_2.-POS）✅一致
纯概念（POS = 販売時点情報管理），无代码可反驳。✅

---

## 二、新建流程教程

| 页面 | 关键声明 | 代码证据 | 判定 |
|---|---|---|---|
| 3.-新建Tran | 复制 SalesTran.cs；TranTypes.cs 加 TranType；复制 SalesTranStates.cs | `Business/Business.Sales/SalesTran.cs`（`class SalesTran : CommonTranBase`）；`Common/Common.Const/TranTypes.cs`；`Common/Common.Const/State/SalesTranStates.cs` 均存在 | ✅ |
| 3_4.-新建Command | 继承 Command 基类；PluginWinPOS.xml 关联 | CommandSalesBase 等基类 + PluginWinPOS.xml `<Group Id="Command">` | ✅ |
| 3_5.-新建State | 在 `Business/Common/Common.Const/State` 下改 `SelfSales.cs`；StateWinPOSSales.xml 配置 | 路径前缀错(应 Common/…)；文件名错——实际是 `SelfStates.cs` 非 `SelfSales.cs`；`POS4U/Settings/StateWinPOSSales.xml` 存在✅ | ⚠️ |
| 3_7.-新建Devices | DeviceIds.cs 加 ID；PluginDevice.xml 注册；DeviceObserver.cs 里 `Factory.CreatePlugun(...DeviceManager).GetDevice(...)` | `Device/Device.DeviceDefine/Const/DeviceIds.cs`✅；`WinPOS/Observer/WinPOS.Observer/DeviceObserver.cs:928` `Factory.CreatePlugin(FrameworkPluginIds.DeviceManager).GetDevice(id)`✅（wiki 拼写 CreatePlugun 缺 i） | ✅ |
| 3_8.-新建Data | Data.Container 加 DataSet；选 POS4U_ConnectionString；usp_GetStoreInformationMaster；Data.Accessor 加 Accessor | `Data/Data.Container`✅；`POS4U_ConnectionString` 见 Data.Container 各 Designer.cs✅；`database/04_StoredProcedures/dbo.usp_GetStoreInformationMaster.StoredProcedure.sql`✅ | ✅ |
| 3_9.-Tran切换/State切换 | SelfSalesTran↔EMoneyChargeTran；`Bussiness/POS/Bussiness.EMoney/EMoneyChangeTran.cs` 的 ChangeState() | Tran 存在✅；ChangeState() 存在（`Business/Business.EMoney/EMoneyChargeVoidTran.cs:135` `public bool ChangeState(State)`）；但路径 `Bussiness/POS/Bussiness.EMoney` 错(应 Business/Business.EMoney)、文件名 `EMoneyChangeTran` 错(应 EMoneyChargeTran) | ⚠️ |
| 5.-新建按钮-Event-Command | 复制 `Sales_SelectItem.cs`；PluginWinPOS.xml 注册；StateWinPOSSales 配置 | `WinPOS/Command/WinPOS.CommandSales/Sales_SelectItem.cs`✅ | ✅ |
| 6.-新建一种支付方式-Device | Device.DeviceDefine 建接口；Device.* 前缀新项目；AssemblyKey.snk 署名；PluginDevice.xml + DeviceIds.cs 注册 | `Device/Device.DeviceDefine` 存在✅；各 Device 项目均带 AssemblyKey.snk✅；PluginDevice.xml/DeviceIds.cs✅（WXPay 为教学示例，未实装，属正常） | ✅ |

---

## 三、共通 UI

| 页面 | 声明 | 代码证据 | 判定 |
|---|---|---|---|
| 4_3.-UIMapper | UIMapper.cs 定义 TranType↔ViewId 字典；`MappingView(PosData)`；`MappingDialog()`；ViewIds.cs | `WinPOS/UI/WinPOS.UI.UIMapper/UIMapper.cs:217 MappingView(POSData)`、`:230 MappingDialog(POSData)`；`WinPOS/UI/WinPOS.UI.UICommon/Const/ViewIds.cs`✅ | ✅ |
| 4_4.-UIBaseForm | `WinPOS/UI/WinPOS.UI.UICommon/UIBaseForm.cs` 的 Update；ChangeView→UpdateDisplay→UpdateDialog | 实际 `UIBaseForm.xaml.cs`（code-behind），含 ChangeView✅ | ✅（.cs vs .xaml.cs 小瑕） |
| 4_5.-Timer | System.Timers.Timer 用法，WinPOS 中 Timer→Command | 通用 C# 知识；框架用法概念性描述 | ✅/🔵 |
| 4_2_1.-追加dialog | DialogIds.cs 加 id；UIMapper `_StateDialogMap` 加映射；PluginWinPOS.xml 配置 | `WinPOS/UI/WinPOS.UI.UICommon/Const/DialogIds.cs`✅；`UIMapper.cs:58 private readonly Dictionary<State,DialogId> _stateDialogMap`✅ | ✅（路径前缀 Business/ 小瑕） |

---

## 四、配置文件（POS4U/Settings，逐个到 XML）

总览 2_10.-常用配置文件：声明路径 `POS4U/Settings`，全部命中 ✅（`POS4U/Settings/` 下确有 30+ xml）。

| 页面 | 声明 | 代码证据 | 判定 |
|---|---|---|---|
| 2_10_1 AttendantPCSendState.xml | 字段 TranType/TranState/AttendantPcState(1,4,5,6)/HasTransaction(0,1)/EventID | `POS4U/Settings/AttendantPCSendState.xml` 注释与元素完全一致（另有 state=7 项，wiki 未列） | ✅ |
| 2_10_2 MainMenuList.xml | PageNumber/ButtonNumber/Description/ButtonType/EventCode/InputData/AddInfos | `MainMenuList.xml` 全字段一致（MenuButton 内） | ✅ |
| 2_10_3 Message.xml | 路径 `Pos4U/Settings/Message.xml`；调用 `WinPOS.UI.UIMapper/MessageDialogInfoCreator.cs` | 调用者存在✅；但 POS4U 侧为**多语言** `Message.{ja_JP,en_US,zh_CN}.xml`，纯 `Message.xml` 在 `POS4ULogicService/Settings/` | ⚠️路径/命名过时 |
| 2_10_4 Plugin.xml | 路径 `Pos4U/Settings/Plugin.xml`；配 Business 模块(RJLayout/TranLogMaker) | **POS4U/Settings 无 Plugin.xml**；实际 `POS4ULogicService/Settings/Plugin.xml`（含 `Id="TranLogMaker"``Id="RJLayout"`✅） | ⚠️路径过时 |
| 2_10_5 PluginDevice.xml | Group Id="Device" | `POS4U/Settings/PluginDevice.xml` 有 `Id="Device"` + CashChanger/CashDrawer… | ✅ |
| 2_10_6 PluginWinPOS.xml | 注册 Barcode/Dialog/Payment/Command/View/Observer | 命中 `Id="Command"``Id="BarcodeConverter"``Id="AttendantPCObserver"``Id="Cash"` 等 | ✅ |
| 2_10_7 StateWinPOS.xml | 外层 TranType→内层 State→Command | 根 `<State>`，含 `<Anytime>` 与 `<TranType Id="MainMenu">…` 嵌套 Command | ✅ |
| 2_10_8 MessageRJ.xml | 路径 `Pos4U/Settings/MessageRJ.xml`（レシート） | **POS4U/Settings 无**；实际仅 `POS4ULogicService/Settings/MessageRJ.xml` | ⚠️路径过时 |
| 2_10_9 SettingWinPOS.xml | 例 `CursorHide`、`ShowSelfSalesLineItemRowNumber` | `CursorHide` 命中✅；`ShowSelfSalesLineItemRowNumber` **未找到**（疑改名/删除） | ⚠️ |
| 2_10_10 SettingWinPOSDevice.xml | ローカルPOS device 设定 | `POS4U/Settings/SettingWinPOSDevice.xml` 存在（wiki 内容极简） | ✅ |
| 2_10_11 SettingWinPOSTerminal.xml | ローカルPOS 端末设定 | `POS4U/Settings/SettingWinPOSTerminal.xml` 存在（wiki 内容极简） | ✅ |

配置文件类整体一致度高；主要问题是 Message.xml / MessageRJ.xml / Plugin.xml 三者**真实路径在 POS4ULogicService/Settings**，wiki 误标为 POS4U/Settings（较旧版本可能确在 POS4U 下，属过时）。

---

## 五、框架概念 / 常量

### 1_9.-NodeType含义 🕰️过时（有硬偏差）
| wiki NodeType | wiki 名称 | 代码 `Common/Common.Const/NodeTypes.cs` | 判定 |
|---|---|---|---|
| 00–09 | 全端末…GOフルセルフ | AllTerminal…GoFullSelf 完全一致 | ✅ |
| 10 | GO対面レジ(サービス) | `LocalPOS "10"`（GetDescriptions:サービスカウンターレジ） | ⚠️名称不符 |
| 11 | 医薬品レジ | `OTCDrugPOS "11"`（ドラッグレジ） | ✅ |
| 12 | オーダーキッチン | `LocalOrderKitchen "12"`（オーダーキッチンセルフ） | ⚠️ |
| **13** | **レーンレジ** | **`TwoOperatorsPOS "13"`（二人制POS）** | ❌硬偏差 |
| 50 | チャージ機 | `EMoneyChargeStation "50"` | ✅ |
| （缺）| — | 代码另有 `LaneSelf "14"`、`LaneSelfPlusPaymentStation "15"`（レーンセルフ登録機/会計機） | 🕰️wiki 缺失 |

NodeType 页 00–09/11/50 准确，但 **13=レーンレジ 与代码 13=二人制POS 冲突**，且缺 14/15，为较旧版本快照。

### 1_11.-支付方式 ⚠️/🕰️
wiki 列 10 项业务级支付（現金/クレジット/売掛金/ポイント・商品券/金券/電子マネー/ビール券(手)/客注/修理/ポイント券）。代码 `Common/Common.Const/PaymentTypes.cs` 为技术枚举：Cash"01"/Credit"02"/ECash"03"/ExchangeTicket"04"/Point"05"/ValueCard"06"/AccountsReceivable"07"/…/PayPay"50" 等 20+ 项。二者**非 1:1**：wiki 的「客注/修理」在代码中非支付种别；代码新增 ValueCard/PayPay/QR/Debit/銀聯 等 wiki 未收。判定：业务级旧视图，与现枚举脱节。

### 1_13.-POSレジ種類 🔵
全为图片（POSレジ/ドロア付/レーンレジ/セルフ/セミセルフ/レジカート/ハイブリット）。概念与 NodeTypes 大类吻合，细节无法核查。

### 1_12.-RM商品API 🔵
外部 RetailMedia 服务 API 契约（dev-api2.retailmedia.jp 的 coupon/using、trycoupon/using、campaigns）。POS4U 侧集成点存在：`Business/Business.RetailMedia`、`Device/Device.RetailMediaService`；但具体 URL 未硬编码于这两处（应为环境/配置注入），故 API 契约本身无法在本仓核实。

### 1_1.-POS Application Framework / 4_4_1 🔵/✅
概念（.NET 插件式微内核框架 + 国际化）与代码事实相符（大量 Plugin*.xml 注册、Factory.CreatePlugin 插件工厂、Message 多语言）。图片部分不可核查。

---

## 六、Source 构成 / DB

| 页面 | 声明 | 代码证据 | 判定 |
|---|---|---|---|
| 2_2.-Source目录结构 | Azure/Business/Common/Data/Device/LogicService/POS4UBackground/WinPOS(Batch/Command/Common/Library/Observer/UI)/POS4U/TRAN4U/POS4ULogicService | 顶层目录逐一命中；WinPOS 子目录 Batch/Command/Common/Library/Observer/UI 全部存在 | ✅ |
| 3_3_1.-Source构成概要 | 同上（重复页） | 同上 | ✅ |
| 2_2_1.-DB構成概要 | 3 库：POS4U_Trial / POS4U_Trial_Master / POS4U_Trial_Tran；常用表 TransactionLog、EJournal | 三库名均命中 `POS4U/Settings/SettingWinPOS.xml` 等；`database/` 有 185 表/434存储过程结构 | ✅ |
| 2_7.-Business | 按业务分类 | `Business/` 下 22 个 Business.* 模块 | ✅ |
| 2_8.-Devices | 即插即用，PluginDevice.xml 配置 | `Device/` 78 目录 + PluginDevice.xml | ✅ |
| 2_9.-Data | Data.Accessor（连库/存储过程）+ Data.Container（表数据集） | `Data/Data.Accessor`、`Data/Data.Container` | ✅ |

---

## 七、BO（POS4ULS_BO）—— 重要定位更正

| 页面 | 声明 | 代码证据 | 判定 |
|---|---|---|---|
| 1.-访问BO | 登录 URL/企業コード/店舗コード/画面 | 运行期 Web UI（POS4ULS_BO），无代码可核 | 🔵 |
| 3.-新建一个查询API | 改 `GetManagementDataParam.cs`→加 `ManagementManager` 一项→`管理種別`加类别→建 `GetXxxLogic` 实现 `GetManagementData`→建实体 | **均命中，但不在 pos-cloud/POS4UBO，而在门店端 LogicService**：`LogicService/LogicService.ServiceAccessor/DataContract/BackOffice/Param/GetManagementDataParam.cs`；`LogicService/LogicService.ApiLogic/BackOffice/Management/ManagementManager.cs:97 GetManagementData(...)` 用 `_dicManagementLogic[(int)ManagementType.X]=new XLogic()` 字典派发；`ManagementType` 枚举 `.../Management/Enum/ManagementType.cs:12`；Logic 类如 `GetSettingDataListLogic.cs`/`SearchEJournalLogic.cs` | ✅（架构完全吻合，位置更正） |
| 4.-新建一个插入API | `ManagementManager` 加项→管理種別加类→建 `PutGoodsDataLogic` 实现 `PutManagementData`→`ItemMasterAccessor.cs` 插入 | Manager/ManagementType/`ItemMasterAccessor.cs`(`Data/Data.Accessor/`) 均在✅；但 **`PutManagementData` / `Put*Logic` 方法名未找到**（插入侧疑改名或走别的 Manager） | ⚠️ |
| 2.-添加新功能——商品登录 | BO 商品登录画面教程 | 同上 BO 体系；未逐类核（POS4UBackoffice 为 ASP.NET MVC，Controllers/Views/Models/Logics） | 🔵/⚠️ |

**定位更正**：任务书假设 BO 查询/插入 API 对应 `pos-cloud/POS4UBO`，实测 `pos-cloud/Source/POS4UBO/POS4UBackoffice` 是 ASP.NET MVC **前端**（无这些类）；BO API **后端**在门店端 `LogicService.ApiLogic/BackOffice/Management`，且查询 API 教程与其架构**高度一致**。

---

## 八、画面流程图 1_1 / 1_1_1 ~ 1_1_17

页面主体为截图（各画面状态），像素级流程 🔵；但所引业务/状态均能对应真实模块（存在性 ✅）：

| 流程页 | 对应代码 | 存在 |
|---|---|---|
| 1_1 画面（主画面 チャージ/釣銭機回収/補充/在庫レポート/開設/会計機/精算/休止/売上/両替/セルフ） | 各对应 MainMenuList.xml EventCode + Business 模块 | ✅ |
| 1_1_1 セルフレジ | WinPOS.UI.SelfSalesView + Business.Sales(SelfSalesTran) | ✅ |
| 1_1_2 チャージ機 | Business.EMoney + WinPOS.UI.EMoneyView | ✅ |
| 1_1_3 売上 | Business.Sales | ✅ |
| 1_1_4 釣銭機回収 | Business.CashChanger(CashChangerRecoverTranVer2) | ✅ |
| 1_1_5 休止 | TranType Lock (StateWinPOS TranType Id="Lock") | ✅ |
| 1_1_6/1_1_7 在高/現金外在高 | Business.Report / Business.CashChanger | ✅ |
| 1_1_8 ジャーナル検索 | TranType EJournalSearch + SearchEJournalLogic.cs | ✅ |
| 1_1_9 オーダーキッチン | WinPOS.UI.OrderKitchenView + Device.OrderKitchenApiService | ✅ |
| 1_1_10 精算レポート | Business.CloseCount + TranType CloseCount | ✅ |
| 1_1_11 売上フラッシュ | Business.Report | ✅（模块存在） |
| 1_1_12 登録機モード | NodeType GoSemiSelfRegister"07" | ✅ |
| 1_1_13 会計機モード | Business.PaymentStation + WinPOS.UI.PaymentStationView | ✅ |
| 1_1_14/1_1_15 返品 | Business.ReSales + TranType Return/ReSales | ✅ |
| 1_1_16/1_1_17 領収証/合算領収証 | WinPOS.UI.EvidenceReceiptView + TranType EvidenceReceipt | ✅ |

---

## 九、未逐条代码核查页（诚实说明）

以下约 90 页多为**通用 C# 教程**或**运维手顺**，非 POS4U 框架实装，未做 file:line 核查（性质属 🔵/通用知识）：
- C# 基础：2_1_1~2_1_7（委托/事件/泛型/LINQ/Lambda/接口/继承）、1_5.-CSharp知识点、2_1.-C
- 环境/运维：0_1.-环境搭建、1.-POS4U开发环境搭建、6.-登录机会计机搭建、7.-检证update.xml、8/9.-DB環境構築SQL、5.-代码Merge、5.-検証環境教育用、6/7.-ツールSQL、1.-创建Project 系列(3_1_x)、2.-新建XAML画面、3.-启动项目加载XAML、4.-AttendntPC
- 开发/测试总结：9_1~9_9（scanner禁止/画面等待/トレーニング/釣銭機/MSR/ワンバーコード/模拟按键/OCX/注意事项）、1_1.-基幹売上データ検証、1.-売上データ検証、10_x
- 概念/图片页：1_2.-POS CLOUD Framework、1_3/1_4.-系统架构图、1_6.-常用术语、1_7.-常用注册文件、1_10.-バーコード、1_14.-POS4U知識、test.md

其中 9_x 开发总结页多涉及真实机能（釣銭機/MSR/ワンバーコード/scanner），如需可二轮抽查对应 Device/Business 实装。

---

## 十、精度评分与统计

- **实查页数（含存在性核查的流程页）：约 66 / 158**（≈42%）；其中**任务书列明的高优先页（框架五要素、全部 11 个配置文件、Source/DB 结构、NodeType/支付/レジ種類、8 个新建教程、4 个共通UI、BO 查询/插入 API、17 个流程图）已 100% 覆盖**。
- 分类计数（针对已核查页/主题，共约 40 个判定单元）：
  - ✅一致：**27**（Command/State/Tran/POS/新建Tran/Command/Devices/Data/按钮/支付Device、UIMapper/UIBaseForm/追加dialog、8 项配置文件、Source目录/DB構成/Business/Devices/Data、BO查询API、流程图模块群）
  - ⚠️部分一致：**8**（Event 与 State/Tran 的路径前缀过时；新建State 文件名错；Tran切换路径/名错；Message/MessageRJ/Plugin 路径过时；SettingWinPOS 例键缺失；支付方式旧视图；BO插入API 方法名缺失）
  - ❌偏差：**1**（NodeType 13=レーンレジ 与代码 13=二人制POS 冲突）
  - 🕰️过时：NodeType 缺 14/15、支付方式旧枚举（并入上）
  - 🔵无法核查：**4**（RM商品API、レジ種類、访问BO、C#/运维/图片大类）
- **切片精度评级：B+（高，框架与配置文件核心一致度很高）**。框架五要素与配置文件与 202606 代码**结构级完全对齐**；偏差集中在**路径命名**（wiki 一律用旧前缀 `Bussiness/Common/…`，实际为顶层 `Common/Common.Const/…`）与**少数常量/文件位置的版本漂移**。

---

## 十一、重大偏差 / 过时清单（优先修正）

1. ❌ **NodeType 13**：wiki「レーンレジ」← 代码 `NodeTypes.cs` 13=`TwoOperatorsPOS`(二人制POS)；且 wiki 缺 14/15=`LaneSelf`/`LaneSelfPlusPaymentStation`(レーンセルフ登録機/会計機)。
2. 🕰️ **Message.xml / MessageRJ.xml / Plugin.xml 路径**：wiki 标 `POS4U/Settings/`，实际 POS4U 侧为多语言 `Message.{locale}.xml`，纯 `Message.xml`/`MessageRJ.xml`/`Plugin.xml` 均在 `POS4ULogicService/Settings/`。
3. 🕰️ **全框架路径前缀过时**：Event/State/Tran/新建教程反复写 `Bussiness/Common/Common.Const/…` 或 `Bussiness/POS/…`，实际是顶层 **`Common/Common.Const/…`**、`Business/Business.EMoney/…`。属结构重构后遗留。
4. ⚠️ **BO API 位置误标**：查询/插入 API 后端不在 pos-cloud/POS4UBO，而在门店端 `LogicService.ApiLogic/BackOffice/Management`（查询 API 架构吻合；插入 API 方法名 `PutManagementData`/`PutGoodsDataLogic` 在 202606 未找到，疑改名）。
5. ⚠️ **支付方式页**为业务级旧视图，与 `PaymentTypes.cs` 现枚举脱节（缺 ValueCard/PayPay/QR/Debit/銀聯；多出「客注/修理」非支付种别）。
6. ⚠️ **新建State 文件名错**：wiki「SelfSales.cs」实际为 `SelfStates.cs`；「EMoneyChangeTran」实际 `EMoneyChargeTran`；「Factory.CreatePlugun」实际 `Factory.CreatePlugin`（拼写）。
7. ⚠️ **SettingWinPOS.xml** 示例键 `ShowSelfSalesLineItemRowNumber` 在 202606 未找到（`CursorHide` 仍在）。

## 亮点（高一致，可放心引用）
- 配置文件族（AttendantPCSendState/MainMenuList/PluginDevice/PluginWinPOS/StateWinPOS）字段与结构**逐项吻合**。
- Command 四步流程、Event↔Command 同名约定、StateWinPOS 的 TranType→State→Command 三层结构与代码分包（CommandSales/CommandPaymentService…）**完全一致**。
- `Sales_ChangeDisplayWithMode=411` 等 EventCode 值精确到行。
- Source 目录、22 个 Business 模块、Data.Accessor/Container、UIMapper(MappingView/MappingDialog/_stateDialogMap)、CreateTran<T> 泛型、DeviceObserver 插件工厂调用 —— 均有 file:line 证据。

## 最该补强处
1. 修正 NodeType 表（13 及补 14/15）——唯一硬偏差，影响端末类型判断。
2. 全局把框架路径前缀 `Bussiness/Common/Common.Const` → `Common/Common.Const`；`Bussiness/POS/Bussiness.EMoney` → `Business/Business.EMoney`。
3. 更正 Message/MessageRJ/Plugin.xml 真实路径（POS4ULogicService/Settings）与 POS4U 侧多语言命名。
4. BO 章节标注后端在 LogicService.ApiLogic/BackOffice，并复核插入 API 方法名。
