# 切片 01A 核查报告：01-confluence-cloud「02.開発関連」技术页面

- 核查范围：`07-strategic-knowledge-base/pj-trial-pos/01-confluence-cloud/content/` 中 INDEX.md「02.開発関連」节全部页面（共 **222 页**，含空占位/纯图/枚举/取込仕様/课题别子页）。
- 真值来源：**仅**真实代码文件（.cs/.xml/.sql/.csproj），基准版本 `pos-store-ver202606`；代码库自带 `docs/` 不作为正确性证据。
- 判定图例：✅一致 / ⚠️部分一致 / ❌偏差 / 🕰️過時 / 🔵無法核查（外部链接/纯图/本库无对应实装）。
- 代码根：`../trialpos-snapshots/pos-store-ver202606`（下称 `$B`）。

---

## 关键架构发现（贯穿全切片）

1. **框架基类是外部编译 DLL，不在本仓库源码内。** `EventCode / TranBase / CommandBase / StateBase / Observer` 等框架基类通过引用 `..\..\ExternalModule\POS4U.Framework.dll`、`WinPOS.Framework.dll`、`LogicService.Framework.dll`、`Background.Framework.dll` 提供。
   - 证据：`$B/Common/Common.Const/Common.Const.csproj:43-49`（POS4U.Framework / POS4U.Framework.Library，HintPath `..\..\..\ExternalModule\*.dll`）；`$B/POS4U/POS4U.csproj:51,55,73,77`；`$B/POS4ULogicService/POS4ULogicService.csproj:54,58,69,73`；`$B/Azure/Azure.Logic/Azure.Logic.csproj:47,60`。
   - 影响：涉及"框架内部机制的抽象基类实现"的声明只能核到**引用与使用**层面，基类源码 = **本库无对应实装（在 ExternalModule）**。但框架的**用法**（Command 类、EventCode 常量、Observer、Tran、State-XML）全部在源码内，可核。
2. **MVC + Event→Command→Observer + State 机制在代码中真实存在且 XML 驱动**（见「開発ルール」「イベント管理_Xml管理」两节）。

---

## 一、02.共通仕様 → ★基礎仕様★

### 1. イベント管理 (2970550410, v55) — ✅一致（含少量命名漂移/計數過時）
逐条核对事件码表（wiki 456 行，正文注明"2026/04/07 436 個"）对照 `$B/Common/Common.Const/EventCodes.cs`（2248 行，`public static class EventCodes`，每项 `new EventCode(nameof(X), code)`）。

| 声明(wiki) | 代码证据 file:line | 判定 |
|---|---|---|
| 6=Sales_CancelSpecifiedLine, 10=Sales_ChangePrice, 27=Sales_EntryAmount, 31/32/33 小計系 | EventCodes.cs:14,20,25,31,37,43 | ✅ |
| 34~38 Common_PageUp/PageDown/ArrowUp/ArrowDown/Barcode | EventCodes.cs:48,53,58,63,69 | ✅ |
| 101~108 PriceLookup 系, 109~121 Common/Device 系 | EventCodes.cs:162-205,210-265 | ✅ |
| 301~344 SelfSales 系, 400~508 各業務 | EventCodes.cs:933-1094,1165-… | ✅ |
| 115 EMoneyCharge_**StartMoneyCharge** | 代码为 `EMoneyCharge_StartEMoneyCharge` (EventCodes.cs:240) | ⚠️ 命名漂移 |
| 159 EMoneyCharge_**StartMoneyInquiry** | 代码 `EMoneyCharge_StartEMoneyInquiry` (:393) | ⚠️ |
| 218 CashChanger＿**CasnChangerReexecute**(全角_+拼写) | 代码 `CashChanger_CashChangerReexecute` (:652) | ⚠️ wiki 笔误 |
| 272 Void_**Reason** | 代码 `Void_SetReason` (:923) | ⚠️ |
| 313 SelfSales_**paymentFixed**(小写) | 代码 `SelfSales_PaymentFixed` (:983) | ⚠️ 大小写 |
| (wiki 表中**缺** 158) | 代码有 `MainMenu_RebootConfirm=158` (:388) | 🕰️ wiki 漏项 |
| 正文"436 個"(2026/04/07) | 代码含 600+ 事件（含 570~612 QR/免税/レーンセルフ/ガソリン等） | 🕰️ 计数随版本增长，但大部分新事件 wiki 已收录 |

结论：事件码体系高度一致，是本切片最可信的一页；偏差均为拼写/大小写/个别漏项。

### 2. POS Type(Nodetype) (2970255585, v7) — ⚠️部分一致
对照 `$B/Common/Common.Const/NodeTypes.cs`（`new NodeType(nameof(X),"NN")`）。

| 声明 | 代码证据 | 判定 |
|---|---|---|
| 05 現金会計機 / 07 セミ登録機 / 08 セミ会計機 / 09 フルセルフ | NodeTypes.cs:43(CashPaymentStation),53(GoSemiSelfRegister),58(GoSemiSelfPaymentStation),63(GoFullSelf) | ✅ |
| 10 サービス, 11 ドラッグ, 12 オーダーキッチン | :68(LocalPOS),78(OTCDrugPOS),83(LocalOrderKitchen) | ✅ |
| **13 レーン** | 代码 13 = `TwoOperatorsPOS`("二人制レジ") NodeTypes.cs:88 | ⚠️ 名称不符 |
| 14 レーンセルフ / 15 レーンセルフPLUS会計機 / 50 チャージ機 | :93,98,73 | ✅ |
| CloudPOS 01~06(GoCart/GoSelf/OrderKitchen/GoCashRegister/Mobile) | :23,28,33,38,48 | ✅ |
| **16 ガソリンスタンド** | 代码 NodeTypes 无 16（GS 为 `featureGasolineStandPOS` 未导入分支） | 🕰️/本库无对应实装 |

### 3. 支払い種別 (2971598999, v49) — ✅一致（少量過時）
对照 `$B/Common/Common.Const/PaymentTypes.cs`（`new PaymentType(nameof(X),"NN")`）。

| PaymentCode(wiki) | 代码证据 PaymentTypes.cs | 判定 |
|---|---|---|
| 1 現金/2 クレジット/3 電子マネー/4 券類/5 ポイント/6 バリューカード/7 掛計 | :16,21,26,31,36,41,46 | ✅ |
| 8 ポイント支払機/9 バリューカード支払機/10 お試し引換券/11 現金(手入力)/12 クレジットLAN | :51,56,61,91,96 | ✅ |
| 20 デビット/21 デビットLAN/23 銀聯LAN/24 オフラインクレジット/31 ビール券バーコード | :66,71,76,101,81 | ✅ |
| 50 PayPay/51 楽天/52 d払い/53 アリペイ/54 Wechat | :106,111,116,121,126 | ✅ |
| **13 ダンゴ** | PaymentTypes 无 13（`featureDangoDelete`＝Dango削除，202606 已移除） | 🕰️ |
| 30 券類(バーコード) | 无对应 PaymentType（仅 31 BeerTicketBarCode） | ⚠️ |
| 併用機種 NodeType 08/09/10/14/15/50 | 与 NodeTypes.cs 全部对应 | ✅ |
| 取引别列表(Sales/SelfSales/OrderKitchen/Void/ReSales/Return/EMoneyCharge…) | 见下 Tran 类清单 | ✅ |
| PluginDevice.xml `Assembly="Device.CT6100_ModeSelf" Class="…CT6100ModeSelf"` | `$B/Device/Device.CT6100_ModeSelf/CT6100ModeSelf.cs`；`$B/Device/Device.CT5100/CT5100.cs`；`$B/POS4U/Settings/PluginDevice.xml`(Class="ForYouApplications.POS4U.Device.*" 模式一致) | ✅ |
| SettingMaster 键 CreditChargeMinimumAmount / CT6100ModeSelf*Timeout / IsCreditChargePoint / IsOfflineCreditDeviceCheck / IsCreditModeSelfPaymentShow | `$B/Common/Common.Const/SettingMasterKeys.cs:567,572,577,582,587,592,245,272,773` | ✅ |

Tran 类清单证据：`$B/Business/Business.Sales/{SalesTran,SelfSalesTran,OrderKitchenTran,ReturnTran}.cs`、`Business.ReSales/{ReSalesTran,VoidTran,EvidenceReceiptTran}.cs`、`Business.EMoney/{EMoneyChargeTran,EMoneyChargeVoidTran}.cs`、`Business.PaymentStation/PaymentStationTran.cs`。

### 4. 取引ログ種別 (2972057643, v5) — ✅一致（計數微過時）
对照 `$B/Common/Common.Const/TranLogTypes.cs`（`new TranLogType(nameof(X), code)`）。
- wiki 首项 101=NormalSales ↔ TranLogTypes.cs:27 `NormalSales,101` ✅。
- wiki 注"57 種類(2024/10/2)"；代码 `grep -c new TranLogType` = **58** 项 → 🕰️ 微增。
- 生成器实装：`$B/Business/Business.TranLogMaker/*TranLogMaker.cs` + `TranLogMakerBase.cs`；接口 `Business.BusinessCommon/ITranLogMaker.cs`。判定 ✅。

### 5. イベント管理_Xml管理 (3077111963, v11) — ✅一致（强证据）
| 声明 | 代码证据 | 判定 |
|---|---|---|
| XML 管理文件 MainMenuList.xml + 各 NodeType 变体(GoFullSelf/GoSemiSelf*/OrderKitchen/OTCDrug/PaymentStation/TwoOperatorsCA/CH/LaneSelf*) | `$B/POS4U/Settings/MainMenuList*.xml`(11 个)+`$B/POS4UTwoOperatorsCH/Settings/{MainMenuListLaneSelfCH,MainMenuListTwoOperatorsCH}.xml` | ✅ |
| SettingWinPOS.xml / SettingLogicService.xml / SettingWinPOSCH.xml | `$B/POS4U/Settings/SettingWinPOS.xml`；`$B/POS4ULogicService/Settings/SettingLogicService.xml`；`$B/POS4UTwoOperatorsCH/Settings/SettingWinPOSCH.xml` | ✅ |
| Barcode 处理键 BarcodeEventCodeCsv / UPCEEventCode 在 SettingWinPOS.xml | `$B/POS4U/Settings/SettingWinPOS.xml:11,13` | ✅ |
| MainMenuList.xml 位置1~8 = EventCode 114,206,184,411,174,161,169,149 | `$B/POS4U/Settings/MainMenuList.xml:15,25,35,44,54,63,73,82`(EventCode 完全对应) | ✅ |
| 事件四类使用场景（Source内/DB键盘/DB动态按钮/XML） | StateEventWinPOS.xml + MainMenuList.xml + SettingMaster 佐证 | ✅ |

### 6. イベント管理_DB管理 (3077144710, v?) — ⚠️部分一致（DB 侧，见 DB 集群）
声明事件与 DB（键盘按键/动态按钮/SettingMaster）绑定；SettingMaster 机制经 SettingMasterKeys.cs(161 键) 证实。具体表 KeyLayout/FunctionButton 交由 DB 集群核查。

### 7. 其余 ★基礎仕様★ 枚举/小页（Settingファイル一覧/カウンターコード/機種とButtonLayoutCode/限界値/集計/店舗タイプ/ポイントの種類 等）
- Settingファイル一覧：上述 `$B/POS4U/Settings/*.xml`、`SettingWinPOSTerminal.xml`、`SettingWinPOSDevice.xml`、`PluginWinPOS.xml`、`PluginDevice.xml`、`PluginCAFISArchLAN.xml` 均存在 → ✅。
- カウンターコード ↔ `$B/Common/Common.Const/CounterCodes.cs`（存在）→ ✅（结构存在，未逐值核）。
- 集計/限界値/店舗タイプ/機種とButtonLayoutCode：多为业务数值/映射表，部分对应 SettingMaster/Report 逻辑 → ⚠️/🔵（未逐条核）。

---

## 二、02.共通仕様 → その他 / 業務系 / デバイス系（枚举页集群）

以下 wiki 枚举页均在 `$B/Common/Common.Const/` 有**同名常量类**（`public static` 项计数见括号），结构一致 ✅（值级抽样，未逐条穷举）：

| wiki 页 | 代码文件 | 判定 |
|---|---|---|
| データアクセス種別 | DataAccessTypes.cs | ✅ |
| 理由タイプ / 理由コード | ReasonTypes.cs / ReasonCodeTypes.cs | ✅ |
| 係員モード | AttendantModes.cs | ✅ |
| 価格種別 | PriceTypes.cs | ✅ |
| 保留種別 | PauseTypes.cs | ✅ |
| 値下げ方法 / 値下げ種別 | DiscountMethods.cs / DiscountTypes.cs | ✅ |
| 会員 / 顧客ID入力タイプ / 顧客年齢確認タイプ | MemberTypes.cs / CustomerIDInputTypes.cs / AgeConfirmTypes.cs | ✅ |
| レシートメッセージ種別 | ReceiptMessageTypes.cs | ✅ |
| ポイント処理結果区分 / 税区分 | PointProcResultTypes.cs / (TaxGroup 见 Business.Tax) | ✅/⚠️ |
| アテンダントPC状態 / 顔認証デバイス状態 | AttendantPCTypes.cs / FaceMeDeviceStatusTypes.cs | ✅ |
| デバイスId | DeviceId（见 Device.DeviceDefine） | ⚠️ |
| 釣銭機状態 | CashChangerErrorStates.cs 等 | ✅ |
| CT6100(クレジット) | Device.CT6100_ModeSelf/Const/* | ✅ |
| オブザーバー / タイマー | `$B/WinPOS/Observer/WinPOS.Observer/`(EventObserver/DeviceObserver/PrintObserver/AttendantPCObserver/TimerScheduler.cs 等) | ✅ |
| コンバーター系(5 页) | 见「バーコードコンバーター集群」 | 见集群 |

Observer 体系代码证据：`$B/WinPOS/Observer/WinPOS.Observer/{EventObserver,DeviceObserver,PrintObserver,AttendantPCObserver,FaceMeDeviceObserver,LDSPObserver,SelfFraudDetectionObserver,TimerScheduler}.cs`。

---

## 三、02.共通仕様 → ★ビジネスロジック★（占位页）
`★ビジネスロジック★`(3011903558)、`UI`(3011969080)、`イベント・コマンド体系`(3011936320)、`オブザバー体系`(3011903600)、`デバイス`(3011870781)、`取引の処理ロジック`(3011969068) 正文**全部为空**（仅标题，version=1）→ 🔵 无正文可核（占位）。
- 但其主题在代码中真实存在：Command 体系 = `$B/WinPOS/Command/WinPOS.Command*`(12 模块，每事件一 .cs，`CommandSalesBase.cs`/`CommandActiveTranSalesBase.cs` 基类) + `$B/LogicService/LogicService.Command{Common,Sales}`（服务端命令）。

---

## 四、04.Source管理

### Source管理一覧 (2970550543, v10) — ⚠️部分一致（组织表，本库覆盖其中一部分）
31 个工程条目；能落到本代码库的：

| No/Project | 代码证据 | 判定 |
|---|---|---|
| 1 POS4U (exe,C#) | `$B/POS4U/POS4U.csproj` | ✅ |
| 2 POS4UTwoOpeatorsCH | `$B/POS4UTwoOperatorsCH/POS4UTwoOperatorsCH.csproj`(wiki 拼写 TwoOpeators) | ✅⚠️ |
| 3 POS4ULogicService (webservice) | `$B/POS4ULogicService/POS4ULogicService.csproj` | ✅ |
| 4 POS4ULS_BO (web,BO帳票) | `$B/POS4ULogicService/POS4ULS_BO/` | ✅ |
| 5 TRAN4U | `$B/TRAN4U/TRAN4U.csproj` | ✅ |
| 6 POS4UBackground (基幹IF) | `$B/POS4UBackground/` | ✅ |
| 7 POS4UCloud (運用監視) | `pos-cloud/Source/POS4UBO`（命名 BO） | ⚠️ 命名差 |
| 9 VersionUP / 10 MasterSync (独立 exe) | 代码为子工程 `$B/POS4UBackground/POS4U.Console.VersionUp/` 与 `POS4U.Console.MasterSync/` | ⚠️ 归属差异 |
| 8 CESettingTool/11 IMEChange/12 TimeSynchronization/13 RecorderViewer/30 BarcodeNonItemUpdate | 本库无对应源码目录 | 🔵 本库无对应实装 |
| 14-29,31 (Vue/Java/Node/kotlin/batch, GitLab/其他仓) | 本库无 | 🔵 |

### POSアプリブランチ管理 (2970681594, v19) / リリースノート / 現行版バージョン管理 — 🔵/⚠️
纯 Git 分支/发布管理表；仅能佐证分支名与代码特性对应（如 `featureDangoDelete`↔202606 无 Dango 支付、`featureGasolineStandPOS`↔无 NodeType16、`release20240927_NEXMART01GO`↔事件表 QR 决济）。判定 🔵（流程页，无代码实体）＋交叉佐证已在上文标注。

---

## 五、07.ログ管理

### 07.ログ管理 (2971894009, v3) — ⚠️部分一致
- POS 侧日志文件命名（POS4U-YYYYMMDDHHMM.log/.error、TRAN4U-…、Launcher-、TimeSynchronization-、VersionUp-、MasterSyncBulk-、DBConnectTool-）：代码中出现 `"POS4U"`/`"TRAN4U"`/`"VersionUp"`/`"MasterSyncBulk"` 等日志前缀字面量（`grep` 命中于 TRAN4U、POS4UBackground/Business/…/MasterSyncBulk.cs 等）→ ⚠️ 大部分前缀可佐证；完整命名格式未逐一比对。
- 其余"操作ログ/認証ログ/…"为通用 IT 概念解说 → 🔵 非代码可核。

### ログレベル (2971730517, v4) — ⚠️部分一致
- 声明 5 级(Debug/Info/Warn/Error/Fatal) 映射 sourceSwitch(Verbose/Information/Warning/Error/Critical)——即 .NET TraceSource/SourceLevels 体系。代码确用 `sourceSwitch/SourceLevels/TraceSource`（命中 `$B/Device/Device.CashChangerRAD262/CashChanger.cs`、`Device.CashChangerLADYf/CashChangerLADYf.cs`、`$B/POS4UBackground/Business/Background.Business.BackgroundCommon/Utility/BackgroundCommonUtility.cs` 等）→ ⚠️ 机制成立；五级名称到 sourceSwitch 的逐一映射未取到集中定义（框架 DLL 内）。

---

## 六、09.開発ルール

### 開発ルール (2993258724, v5) — ✅一致
| 声明 | 代码证据 | 判定 |
|---|---|---|
| MVC：Model=BusinessObject / View=UI(含レシート) / Controller 中介 Event→Command→Observer | `$B/Business/*`(22 业务模块) + `$B/WinPOS/UI/*` + `$B/WinPOS/Command/*` + Observer；StateEventWinPOS.xml 佐证 Event/Command 链 | ✅ |
| 框架规则：UI/Device/Observer 才能触发事件；Command 引継可 | `$B/POS4U/Settings/StateEventWinPOS.xml`：`<TranType><State Id><Command Before=".." After=".."/>` 即命令拦截/引継机制 | ✅ |
| 1 Class 1 File | 每事件一命令 .cs（WinPOS.CommandSales 目录逐一对应）| ✅ |
| StyleCop.Analyzers + POS4U.ruleset | `$B/POS4U.ruleset`(存在，RuleSet Name="POS4U の規則")；`StyleCop.Analyzers` 见 `$B/POS4U/POS4U.csproj`、`POS4ULogicService.csproj`、`Azure.Logic.csproj` | ✅ |

### マージ作業ルール (3522166807) — 🔵 流程页（无代码实体）。

---

## 十、10.基幹システム連携仕様
### 10.基幹システム連携仕様 (4296966201) / 売上実績連携仕様 (4298178581, v1) — 🔵無法核查
正文仅 Google Sheets 外链（全トランデータ項目定義），无页内可核内容。基幹 IF 具体电文(WBRT/WBMN 系)见「03.インタフェース仕様」子页（多为固定长电文规格，部分可对 Business.TranLogMaker / POS4UBackground 取込逻辑核查，属其它集群/子页）。

---
## 七、06.データベース（子代理核查，真值＝database/*.sql）

### 计数口径 — ❌偏差（重大）
知识库全局说明"185 表 / 434 存储过程"= 目录 `ls|wc` 裸文件数（含 .txt 辅助文件、索引脚本、表类型、函数）。真实：
| 对象 | 知识库称 | 真实 | 证据 |
|---|---|---|---|
| Tables | 185 | **160**（+`10_BI` BISalesHeaders=161） | `database/01_Tables/` 中 `dbo.*.Table.sql`=160，`zz_IDX_*/zz_NonClustered*`=23（索引脚本非表），另 2 个 .txt |
| Stored Proc | 434 | **~407** SP | `database/04_StoredProcedures/` `dbo.usp_*.sql`=407；另 udt_*(表类型)=18、UDF=1、.txt=2；`10_BI/04_StoredProcedures/` 另有 21 未计 |
| Views | (27) | **25** | `database/03_Views/` 25 个 .sql |

### 页面
| 页面 | 判定 | 要点/证据 |
|---|---|---|
| 06.データベース(2971500805) | 🔵 | 空占位页（仅标题） |
| テーブル一覧(2972024892, v79) | ⚠️部分一致 | 22 抽样表全命中(ItemMaster/SettingMaster/TransactionLog…)；**漏列代码中存在的 `EnterpriseSystemInfoMaster`、`TerminalMaster`(与已列 TerminalManagement 是两张表)** ❌；19 个 `BILineItems_*` 月分区表为运行时动态建(`10_BI/04_StoredProcedures/dbo.usp_CreateTableBILineItems.sql`)非静态缺失 ⚠️；No.60 DailyPosSalesDetail 删除线正确 ✅ |
| Table-Layout(3006201926) | 🔵 | 仅 Google Sheets 外链 |
| ビュー(3070428047) | ⚠️部分一致 | 代码 25 视图全部在 wiki 有登记 ✅；**No.13 `T_D_PosSalesDetail` 代码不存在（源表 DailyPosSalesDetail 已删）** 🕰️ |
| ER図(2971664617) | 🔵 | 纯图片页，正文空 |
| 設定マスタキー(2971631844) | 🔵 | 仅 Google Sheets 外链（旁证：`database/01_Tables/dbo.SettingMaster.Table.sql:11-16` Key/Value/PK 结构成立 ✅） |
| SettingDataType(2971697419) | ✅一致（逐字） | 6 值 1-6 及日文说明与 `$B/WinPOS/Common/WinPOS.Common/Const/EventGroupDetailSettingDataTypes.cs:14,20,27,33,40,47` 完全吻合；字段 `dbo.EventGroupDetailMaster.Table.sql:18 [SettingDataType] smallint` |
| バージョンアップ配置(3125870648) | 🔵 | 仅 Google Sheets 外链 |

## 八、03.インタフェース仕様（子代理核查，真值＝POS4ULogicService/Controllers 等）

**架构前提**：wiki 的 `〜.svc/方法` 是 WCF 风记法，实体为 **ASP.NET Web API 属性路由**（`$B/POS4ULogicService/App_Start/WebApiConfig.cs:25` `MapHttpAttributeRoutes()`；各 Controller `[RoutePrefix("X.svc")]`+`[Route]`）；客户端 `$B/LogicService/LogicService.ServiceAccessor/*Accessor.cs` 同名 `nameof` 调用。

| 页面 | 判定 | 证据/要点 |
|---|---|---|
| BackgroundService(3027206146) | ⚠️部分一致 | GetLastTransactionLog/GetLastEJournal/PutTransactionLogList/PutEJournal 全对(`BackgroundServiceController.cs:97,107,127,137`)；**URL 的 /企业/店铺/端末 路径描述错误**（该路由无 path 段，参数在 body，`BackgroundServiceAccessor.cs:14`） |
| BackOfficeService(3026714678) | ✅一致 | GetManagementInitialData/GetManagementData/GetReprintReceiptData 连 path 形式全对(`BackOfficeServiceController.cs:208,275,342`) |
| DataService(3030646787) | ✅一致 | 6/6 全对(`DataServiceController.cs:54,113,310,171,367,480`) |
| POSLogicWebService(3012624472) | ⚠️/❌ | GetCurrentDateTime/GetBusinessCounterList/PutTerminalCapacity/PutCashChangerStatus 对(:465,612,304,255)；**`PutBusinessCounterList` 不存在，实为 `PutBusinessCounter`(:563)** ❌ |
| POS4UアプリのAPI仕様(2970517707) | ✅一致(POS逻辑段) | No.14-41 POS逻辑/Azure 段实测 **一致 25 / 偏差 2**：❌ No.19 `DataService.svc/CheckModuleExist`（实为 BackgroundService 的 `CheckModuleExist:171`；DataService 相当为 `CheckExistUpdateModule:54`）；其余 MTranService/ReceiptService/CartMTranService/CheckHealth 等全命中。No.2-13,42-92 为外部服务→🔵 |
| AzureとのAPI仕様(3011970010) | ✅一致 | 共通响应 7 字段 IsSuccess/ErrorCode/ErrorMessage/ErrorCodeDetail/WarningCode/WarningMessage/WarningCodeDetail 与 `ServiceResultBase.cs:18-42` 全对 |
| POS4ULogicのIF仕様(2970353925) / POS4ULogicService WebAPI(2970255657) | 🔵/🕰️ | **两页正文皆空**（应为 IF 核心却未整备） |
| CRM/Incomm/ISM/Manju/PA/RM/Telpo/VD/アテンダントSV/キッチンSV/ポイントGW 等 API | 🔵 | 外部系统 API，本代码库无对应服务端实装（客户端 Device.* 侧部分可见，未逐核） |

**API 面完整性**：`Controllers/` 共 **11 个 Controller**，wiki 仅详述 4 个且各只覆盖约半数 action；`MemberServiceController/ItemDetectionServiceController/ReportServiceController` 整只未记载 → wiki "正确但不完整"（下限）。
**Azure 连接**：`.svc` 服务本身托管于 Azure（本番 `trialmercuryv2/trialvenusv2.posaas.net`）；另 `$B/Azure/Azure.Logic` 用旧 SDK `Microsoft.WindowsAzure.Storage` 连 3 个存储账户(Default/EJournal/TransactionLog，`StorageLibrary.cs:64,71,78`)；连接串外置于 SettingLogicService*.xml → 实值 🔵。

## 九、08.ランチャー（子代理核查）

**重大前提修正**：**TRAN4U ≠ ランチャー本体**。TRAN4U 是"被 launcher 启动的常驻插件宿主"（`$B/TRAN4U/Program.cs:26` 向 Launcher 通知自身启动；`TRAN4UController.cs` 全无 `Process.Start`，靠 `PluginTRAN4U.xml` 载入 TranLogService/Transfer/MasterSyncPosDiff 插件 + WCF net.tcp 远程 Start/Stop）。**真正的 launcher 本体（按 config 顺序 Process.Start 9 个程序）在本代码库及整个 stpos 仓库中均不存在**。

| 页面/项 | 判定 | 证据 |
|---|---|---|
| 概要(3022356549) | 🔵/⚠️ | launcher 本体不在库；目的（最新 DB/版本/时刻）由 VersionUp/MasterSync 工具佐证，TimeSync 不在 |
| 項目リスト #1 TimeSynchronization.exe(称有源) | 🔵/🕰️ | 全树无此工程（wiki 称"ソースあり"但本树不在） |
| #2 DBConnectTool.exe / #8 Sleep.exe | 🔵 | 本库无 |
| #3 VersionUp.exe | ⚠️部分一致 | 实在但实 exe 名 `POS4U.Console.VersionUp.exe`(`$B/POS4UBackground/POS4U.Console.VersionUp/`，`Program.cs:36`；`BackgroundSettingValues.cs:51`) |
| #4 DataUpdate4Replace.exe(称有源) | 🔵/🕰️ | 无工程，仅消息常量 `MessageIds.cs:7650` |
| #5 MasterSync.exe | ⚠️部分一致 | 实 exe 名 `POS4U.Console.MasterSync.exe`(`$B/POS4UBackground/POS4U.Console.MasterSync/`，`Program.cs:31`；`BackgroundSettingValues.cs:56`) |
| #6 IMEChange.exe(称有源) | 🔵/🕰️ | 本树无 |
| #7 TRAN4U.exe | ✅一致 | `$B/TRAN4U/TRAN4U.csproj`(AssemblyName=TRAN4U, WinExe)，常驻→WaitForExit=FALSE 相符 |
| #9 POS4U.exe | ✅一致 | `$B/POS4U/POS4U.csproj`(AssemblyName=POS4U, WinExe)，`App.xaml.cs:39` 向 launcher 通知 |
| WaitForExit 列(仅 TRAN4U/POS4U=FALSE) | ✅逻辑相符 | 常驻 WinExe vs 批处理 Exe 之别一致；ErrorMode 值本体不在→🔵 |

代码中另有 wiki 未列的运行期子进程：`POS4UTwoOperatorsCH.exe`(二人制，`POS4U/App.xaml.cs:90-105`)、Administrator 服务按云通知 on-demand 启 VersionUp/MasterSync(`AdministratorService.cs:162-206`)。

## 十一、02.共通仕様 → バーコードコンバーター体系 / コンバーター（子代理核查）

真值＝`$B/Business/Business.InputConverter/BarcodeConverter/` + `$B/POS4U/Settings/*.xml`。**框架编排器 + `IBarcodeConverter`/`IEventConverter` 接口 + `BarcodeConvertMaster/SubMaster` 表访问逻辑在外部 `POS4U.Framework.dll`（本 worktree 缺失）→ 该层 🔵。** 扩展类 = 12 个类直接实现 `IBarcodeConverter` + 2 个继承 `BarcodeItemListConverter`（非抽象基类，是"接口+一处继承"）。

| 页面 | 判定 | 要点/证据 |
|---|---|---|
| 01.処理概要(3011903583) | ✅/⚠️/🔵 | 14 扩展类 ✅(`.../BarcodeConverter/` 13 .cs)；云端遍历 7 项顺序与 `PluginLogicService.xml:32-60` 逐条一致 ✅；**本地遍历第 10/11 位互换**（wiki QR→NonPLUFood；`PluginWinPOS.xml:94,98` NonPLUFood→QR）⚠️；框架表转换分支 🔵 |
| 02.基础条码转换体系(3011936380) | 🔵 | BarcodeConvertMaster/SubMaster 字段与示例数据均由框架二进制+运行时 DB 数据驱动，本库无 DDL/访问源码（仅注释 `EventCodes.cs:179`、`BarcodeItemCodeConverter.cs:91`） |
| 03.条码转换拓展类(3011903651) | ✅一致（逐类） | 14 类 IsTarget 条件逐条命中：MemberScan 18位含大写(`BarcodeMemberScanConverter.cs:33-46`)、BestBefore 26位非978/979(`.cs:45-48`)、MarkDown 20位(`.cs:31`)、CartTerminalNoScan 12/13位"0000000"→553(`.cs:30,53`)、NonPLUFood 24位(`.cs:34`)、LogicService 13位29/20/13开头(`.cs:34`)、ItemWithQuantity 无条件(`.cs:31`) 等；**DynamicPricing 阈值笔误**：wiki"000000(6个0)" vs 代码 `StartsWith("0000000")`7个0(`BarcodeDynamicPricingConverter.cs:68`) ⚠️ |
| 04.TRIAL独自バーコード各種(4254302263) | ✅/🔵 | 카ート/OneTime18/値下げ20/FoodPark24/26桁JAN/DP26 全部命中代码；係員/会員/中間取引/レシート(2-4,7)属 BarcodeConvertMaster 表驱动→🔵 |
| ダイナミックプライシング(4258004997) | ✅一致（深度） | 26位拆分(13商品+6製造+6賞味+CD)`BarcodeDynamicPricingConverter.cs:90,157,158`；CD=CheckDigitM10W31(`.cs:122`)；年份推定4分支(`.cs:171-202`)；期限切れ判定(`.cs:204-217`)；DynamicPricingMaster 访问(`.cs:223,230-234`) 全部吻合 |
| コンバーター(3002499219)+5子页 | ✅/⚠️ | イベントコンバーター：由 `StateEventWinPOS.xml:92,94`(TranType Lock: Common_SignInOut→Lock_SignIn) 逐字命中 ✅；メッセージコンバーター后缀 Customer/EN_US/JA_JP/KO_KR/ZH_CN=`MessageSuffixes.cs:16,21,26,31,36` ✅+`LogicService.ApiConverter/MessageConverter.cs`；音声=`WinPOS.UI.UICommon/VoiceConverter.cs:11,20`(NodeVoiceType) ✅；取引情報モデルコンバーター 3 处均在(Attendant 本地 22 个吻合；Azure 两处各 24 个，多出 StoreInfo/TerminalInfoModelConverter) ⚠️；バーコードコンバーター表少列 QR/NonPLUFood ⚠️ |

---

# 切片精度评分与分类统计

## 覆盖率
- 切片总页数：**222 页**（INDEX「02.開発関連」全节）。
- **实质核查（含并行集群）：约 62 页**（框架/枚举/DB/接口/ランチャー/コンバーター/日志/开发规则等全部结构性页面 + 其正文可核内容）。
- 覆盖判断：结构/框架/DB/接口/ランチャー/コンバーター类页面**已全部覆盖**；剩余约 160 页为 03.インタフェース仕様 下的**基幹IF电文规格子页(WBRT/WBMN 系约 60+)**、99.課題別各课题页、及外部API页——这些多为"外部系统电文/课题设计"，本代码库无服务端实装或仅 Google Sheets 外链，属抽样/🔵范畴，未逐页展开。

## 分类计数（已核查点，约 95 个判定点）
- ✅一致：约 **55**（事件码、PaymentTypes、NodeTypes、TranLogTypes、SettingMasterKeys、XML事件管理、DataService/BackOffice API、ServiceResultBase、コンバーター类、SettingDataType、开发规则、TRAN4U/POS4U exe 等）
- ⚠️部分一致：约 **20**（命名漂移、遍历顺序、URL路径描述、VersionUp/MasterSync exe名、模型转换器清单、DynamicPricing阈值等）
- ❌偏差：约 **6**（DB计数185/434、テーブル一覧漏2表、PutBusinessCounterList、CheckModuleExist服务取错）
- 🕰️過時：约 **6**（Nodetype16ガソリン、支払13ダンゴ、TranLog57→58、ビューT_D_PosSalesDetail、事件计数、TimeSync/DataUpdate4Replace/IMEChange称有源实无）
- 🔵無法核查：约 **8 类**（空占位页6个、Google Sheets外链页4个、纯图ER図、框架DLL内基类/编排器、launcher本体、外部系统API、BarcodeConvertMaster数据侧）

## 切片总体精度评级：**B+（良好偏上，"准确但不完整/口径偏差"）**
最可核的结构层（事件/命令/状态/观察者/转换器/枚举/内部API/XML配置）与代码**高度一致**，是全库最可信切片之一；扣分集中在：①量化口径错误（DB 185/434）②少量命名/路由笔误 ③大量空占位与外链页（同步机制未抓正文）④框架基类与 launcher 本体不在本代码库（客观不可核）。

---

# 重大偏差清单（Top 10，按重要性）

1. **❌ DB 计数严重虚高**：知识库"185 表 / 434 存储过程"是目录裸文件计数；真实约 **160 表 / 407 SP / 25 视图**（含混入的 .txt、23 索引脚本、18 表类型、1 函数）。应更正口径。
2. **❌ POS4ULogicのIF仕様 与 POS4ULogicService WebAPI 两页正文全空**——恰是内部 WebAPI 的核心 IF 规格却未整备（🕰️/未整备）。同为空占位的还有 ★ビジネスロジック★ 全部 6 个子页（UI/イベント・コマンド体系/オブザバー体系/デバイス/取引の処理ロジック）。
3. **⚠️ 前提性误解：TRAN4U ≠ ランチャー本体**。TRAN4U 是被 launcher 启动的常驻插件宿主（WCF 远程控制），真正 launcher 本体（顺序 Process.Start 9 程序）不在本代码库。
4. **❌ API 命名两处错**：`PutBusinessCounterList`（实为 `PutBusinessCounter`，`POSLogicWebServiceController.cs:563`）；`DataService.svc/CheckModuleExist`（实属 BackgroundService，DataService 相当为 `CheckExistUpdateModule`）。
5. **❌ テーブル一覧漏列** 代码中实存的 `EnterpriseSystemInfoMaster`、`TerminalMaster`（后者≠已列的 TerminalManagement）；**ビュー**残留失效条目 `T_D_PosSalesDetail`（源表已删）🕰️。
6. **🕰️ 若干枚举随版本漂移但 wiki 未跟进**：Nodetype 16 ガソリン（未导入分支，代码无）、支払コード 13 ダンゴ（featureDangoDelete 已移除）、TranLog 57→58、事件计数 436→600+。
7. **⚠️ ランチャー exe 名不符**：wiki `VersionUp.exe`/`MasterSync.exe` vs 实 `POS4U.Console.VersionUp.exe`/`POS4U.Console.MasterSync.exe`（`BackgroundSettingValues.cs:51,56`）；wiki 称有源的 TimeSynchronization/DataUpdate4Replace/IMEChange 在本树不存在。
8. **⚠️ バーコード遍历顺序/阈值笔误**：本地第10/11位 QR↔NonPLUFood 互换（`PluginWinPOS.xml:94,98`）；DynamicPricing 排除阈值"6个0"实为"7个0"（`BarcodeDynamicPricingConverter.cs:68`）。
9. **⚠️ 事件码命名漂移**：EMoneyCharge_Start**E**MoneyCharge/Inquiry、Void_**Set**Reason、CashChanger_CashChangerReexecute（wiki 全角_+拼写 Casn）、SelfSales_**P**aymentFixed 等——均属 wiki 笔误，代码为准。
10. **🔵 框架基类不在本库（客观限制）**：EventCode/TranBase/Command/State/Observer/IBarcodeConverter 及编排器在 `ExternalModule/*.Framework.dll`（本 worktree 缺失，姊妹 worktree `pos-cloud/ExternalModule/Framework/` 有）。故"框架内部机制"声明仅能核到引用与用法层。

# 亮点（文档与代码高度吻合处）
- **イベント管理 / イベント管理_Xml管理**：事件码、MainMenuList.xml 按钮→EventCode→Command 映射（位置1-8=114/206/184/411/174/161/169/149，`MainMenuList.xml:15-82`）、SettingWinPOS.xml 键 —— 逐条命中，是全切片最强证据。
- **SettingDataType**：6 值+日文注释与 `EventGroupDetailSettingDataTypes.cs` 逐字一致。
- **ダイナミックプライシング**：26位拆分/校验位算法/年份4分支推定/期限判定与 `BarcodeDynamicPricingConverter.cs` 深度吻合。
- **PaymentTypes / NodeTypes / TranLogTypes / DataService API / ServiceResultBase / コンバーター类**：结构与命名高一致。

# 最该补强处
1. 更正 DB 计数口径（改为"约 160 表/407 SP/25 视图"，或明确注明为目录文件数）；补 `EnterpriseSystemInfoMaster`/`TerminalMaster`，删失效视图 `T_D_PosSalesDetail`。
2. 补齐两页空的内部 IF 核心规格（POS4ULogicのIF仕様 / POS4ULogicService WebAPI）及 ★ビジネスロジック★ 6 子页；至少补 MemberService/ItemDetectionService/ReportService 三个未记载 Controller。
3. 修正 launcher 前提（区分 launcher 本体 vs TRAN4U/POS4U 子进程），统一 exe 实名。
4. 订正 API 命名两处（PutBusinessCounter / CheckExistUpdateModule）与 BackgroundService URL 描述。
5. 修 バーコード遍历顺序与 DynamicPricing 阈值笔误；清理随版本过时的枚举项（ダンゴ/ガソリン等标注状态）。
