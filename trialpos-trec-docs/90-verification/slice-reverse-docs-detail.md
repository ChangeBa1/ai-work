---
title: 01-trialpos-docs（源码分析文档）× 实际代码 逐 file:line 证据明细
scope: pj-trial-pos / 01-trialpos-docs 5 卷册 + 备份档案箱（107 页）
truth_baseline: ../trialpos-snapshots（POS4U 真实源码，基准版本 pos-store-ver202606）
parent_report: ./reverse-docs-vs-code-audit-2026-07-14.md
date: 2026-07-14
author: jinianxiang
security: 🟡 敏感
method: 5 路并行 subagent 实代码深潜（仅以真实 .cs/.xml/.sql/.config/.csproj/.sln 为证据，file:line 锚定；不采信被审文档自身、其它二次资料，含代码库自带 docs/）
---

# 01-trialpos-docs × 实代码 逐 file:line 证据明细

> 本文件是 [`reverse-docs-vs-code-audit-2026-07-14.md`](./reverse-docs-vs-code-audit-2026-07-14.md) 的证据附件，按 5 卷册逐条列出 `[声明 | 代码证据 file:line | 判定]`。所有相对路径以 `trialpos-snapshots/pos-store-ver202606/`（代码）或 `trialpos-snapshots/database/`（SQL）为起点。判定：✅一致 / ⚠️部分·过时·名称偏差 / ❌错误 / 🔵对象外·核查不能。

---

## 卷一 · 架构（1_architecture）

| 声明 | 代码证据 file:line | 判定 |
| :--- | :--- | :--- |
| 3 个解决方案 sln 路径 | store 侧 `pos-store/POS4U_V4.sln`、`POS4UBackground.sln` **断裂**（应 `pos-store-ver202606/`）；`pos-cloud/Source/POS4UBO_V4.sln` OK | ⚠️ 2/3 断链 |
| 168+ 个 C# 项目 | `find pos-store-ver202606 -name *.csproj`=**168** | ✅ |
| POS4U_V4.sln「60+ 子项目」 | sln 内引用 `.csproj`=**157** | ✅（成立但严重低估） |
| POS4U = WPF 前台 | `POS4U.csproj` `OutputType=WinExe`+`PresentationFramework`/`System.Xaml` | ✅ |
| TRAN4U = WinForms 守护进程 | `TRAN4U.csproj` `OutputType=WinExe`+`System.Windows.Forms` | ✅ |
| 全站 .NET Framework 4.0 / Win XP | store 全体 154×v4.0 + **14×v4.6.1** | ⚠️（前台成立，非全站） |
| 命令模式 100+ 命令类（继承 `CommandBase`） | `: CommandWinPOSBase`=**227 文件**；无 `class CommandBase` | ⚠️ 模式成立且被低估，但基类名为 `CommandWinPOSBase` |
| 启动时序 IsProcessAlreadyExist/UnhandledException/WinPOSController | `App.xaml.cs:45,58-60,211` | ✅ |
| overview step2：启动拉起 TwoOperatorsCH | `App.xaml.cs:87-105`（`if IsTwoOperatorsCashier`→`Process.Start(psi)`:104） | ✅（overview 正确） |
| **02** 端侧本地双 SQLite / Tran.db / Master.db | `sqlite`参照=**0**；`SqlConnection/SqlCommand`=137 文件 | ❌ P0 |
| **02** 边缘 SQL Server Express + IIS | IIS/Web API 部分 ✅（`Global.asax.cs:31`）；「WCF」标注 ❌（Web.config 无 serviceModel） | ⚠️ IIS 对 WCF 错 |
| **02** net.tcp WCF（POS4U↔TRAN4U） | `TranRemoteControllerLibrary.cs:20` `net.tcp://localhost:{0}/...` | ✅ |
| **03** `App.xaml.cs#L104 = Process.Start("TRAN4U.exe")` | `:96-105` 实为 TwoOperatorsChecker 条件启动；全码 `Process.Start.*TRAN4U`=0 | ❌ P1 |
| **03** net.tcp URI `.../TranRemoteControllerService`、端口 8012 | `WinPOSSettingValues.cs:27`(8012)；`TranRemoteControllerLibrary.cs:20`；`RemoteServiceController.cs:41` | ✅ |
| **03** Binding L126-148：Send/ReceiveTimeout=5min、Max*=int.MaxValue、SecurityMode.None | `TranRemoteControllerLibrary.cs:131`(0,5,0)/`:132`/`:134`/`:135`/`:145` | ✅ **行号区间精确一致** |
| **03** 接口 StartAll/StopAll/Start/Stop/IsRunning | `ITranRemoteControllerService.cs:19,25,34,43,55`（参数名实为 `tranPluginName`） | ✅（参数名轻微出入） |
| **04** MasterSync→Cloud_BO 直连 HTTP GET+Gzip 解压+覆盖 SQLite Master.db | `Download.cs:52-57` 实为向**边缘** LogicService POST `GetMasterDownloadFile` 存文件；无 sqlite/gzip/.db | ❌ 机制失真 |
| **04** MasterSync 每 5 分钟轮询增量特价 | console 无 interval 依据 | ❌ 未裏取り |
| **04** Transfer 调 WCF `WsPutTransaction` | `BackgroundServiceController.cs:117` `[Route("PutTransactionLog")]`（Web API） | ⚠️ 概念对，名+协议错 |
| **04** 云端 `sp_InsertTLog` | 实为 `dbo.usp_InsertTransactionLog`(+`usp_InsertTLogQueue`)；无 `sp_` 前缀 | ⚠️ 名错（全 `usp_`） |
| **04** 强幂等 `TransactionToken` via `Guid.NewGuid()` | Transfer 模块 `TransactionToken/Idempoten/Guid.NewGuid`=0 | ❌ 无代码依据 |

## 卷五 · 追溯（5_traceability）

| 声明 | 代码证据 file:line | 判定 |
| :--- | :--- | :--- |
| 矩阵内全部店舗端 `file:///` 路径 | `pos-store/…` 7 条**全断裂**；同路径在 `pos-store-ver202606/` 全实在 | ❌ P0 断链 |
| 矩阵内 cloud/database 路径 | `BOAuthenticationAttribute.cs`、`PresetMenuButtonMasterLogic.cs`、`dbo.usp_BOUpdate…CloseCount.sql` OK | ✅ |
| README「23 C# / 14 API / 428 SP」 | 真值 SP=**405**；矩阵本体仅 8 .cs + 1 SP | ❌ 数值错且与矩阵不自洽 |
| 4 关键文件实体存在（SalesTran/SalesTranStates/MTranServiceController/MemberServiceController） | 均在 `pos-store-ver202606/…`；LogicService Controllers 共 11 个 | ✅（BR 编号为文档自造，无代码锚点，仅证"文件在"） |
| BR-STATE-001「17 个销售主状态」 | `SalesTranStates.cs`=**28** | ❌ |
| gap §2.1「实际 24 个状态」 vs Phase1/§5「30 个状态」 | 实测均非（=28），且二者互相矛盾 | ❌ 内部矛盾+错 |
| gap「SelfStates 32 状态」 | `SelfStates.cs`=**39** | ❌ |
| gap「87 设备模块命名空间」 | `Device/*.csproj`=**78** | ❌ |
| gap Scanner/Keyboard/`SelfStates.MemberScan:13` 全在 | `Device.Scanner*`、`Device.KeyboardScanner`、`SelfStates.cs:13` | ✅ |
| gap「代码实现覆盖率 100% / AST 精度 100%」 | AST 5 项存在为真，但与上列状态/设备错值冲突 | ⚠️ 自评过度乐观 |

---

## 卷二 · 核心业务规格（2_business_specs 主 6 篇）

### 01_sales.md
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| 销售状态「17 核心 + 3 阻塞」 | `Common/Common.Const/State/SalesTranStates.cs:13-149`=**28**（18 TranState+10 State）；全版本 27/28/28 | ❌ |
| 状态表 10 个状态名全部存在 | Neutral:13 EnteringItem:18 SelectEnteringItem:23 Paying:28 Fixed:33 Canceled:38 WaitingAgeConfirm:89 WaitingDrugConfirm:94 QRScanDialog:144 ValueCardOffline:119 | ✅ |
| BR-SALES-003 商品属性 `IsAgeLimitProhibition=true` | 全库（含 3 版本）无 `IsAgeLimitProhibition`；真实为交易级 `AgeConfirmType`(`SalesTran.cs:226`)+`IsAgeConfirmation`(:231)+5 种 `AgeConfirmTypes` | ❌ 捏造属性名 |
| BR-SALES-003 L40 客显副屏判断 | `SalesTran.cs:38-40` `if(GetSecondDisplay()==null) IsCustomerAgeConfirmation=true` | ✅ |
| BR-SALES-007 离线降级 `ValueCardOffline`+`OfflinePointCardNo`+`CanPointUpdateErrorContinue` | `SalesTran.cs:261/292/304`；状态`:119` | ✅机制/⚠️行号漂移 |
| BR-SALES-009 `ClearMember`→`TryEjectCard()` | `SalesTran.cs:819→838` | ✅机制/⚠️行号 |
| 链接前缀 `pos-store/Business/...` | 真实 `pos-store-ver202606/` | ❌ 断链 |

### 02_payment.md
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| `SortPaymens` 排序源码块 | `PaymentObject.cs:781-791` **逐字一致** | ✅ |
| 排序 4 维（不可溢收/不可找零/面额降序/现金最后） | `:785-787`（`PaymentTypes.Cash` 判定 :787） | ✅ |
| Glory `DispenseChange` 失败重试 **3 次**+退避键 | `PaymentObject.cs:528`(方法)、`:560`(retry=3)、`:569-573`(RetryCount/RetryTime) | ✅ |
| BR-PAY-003 刷卡成功 `CanCancel=false` | `PaymentCAFISArchLANBase.cs:311`（:393=true） | ✅ |
| 金种 现金=01；PayPay50/Alipay53/WeChat54；CreditLAN12/UnionPayLAN23，共 23 金种 | `PaymentTypes.cs:16,106,121,126,96,76` | ✅ |
| BR-PAY-008 信用卡退货强制原路逆转、断网禁现金垫付 | `VoidTran.cs:327/336/361/375/383` `ErrorNotFoundCAFISArchLAN` | ✅ |

### 03_resales.md
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| `ReSalesTran`/`VoidTran`/`ReadReceiptObject` 三主类 | `Business.ReSales/{ReSalesTran.cs,VoidTran.cs,ReadReceiptObject.cs}` | ✅ |
| `TranTypes.Void`/`ReSales` | `TranTypes.cs:113,118` | ✅ |
| mermaid `SelectReason`/`VoidComfirm`（原文拼写） | `State/VoidTranStates.cs` | ✅ |
| §2.2 `CanChangeQuantity` 只减不加+`ErrorCannotAddQuantity` | `ReSalesTran.cs:450,463` | ✅ 行号精确 |
| BR-RESALES-002 会员+理由 08 冲突 `ErrorCannotReSalesDuetoReasonCode` | `ReSalesTran.cs:145-151` | ✅ 行号精确 |
| BR-RESALES-003 仅 1 件禁部分取消 `ErrorCannotReSalesDuetoItemCount` | `ReSalesTran.cs:137-143` | ✅ 行号精确 |
| §2.1 Void.EndTran 链（EndTran/LockInquiry/PointReturn/AddVoidPayments） | `VoidTran.cs:602/623/686/483`（文档引 L579-699 等，行号漂移） | ✅机制/⚠️行号 |

### 04_point_engine.md
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| `PointManager.Calc` 策略链（Target/Point/Return/Offline Logic） | `PointManager.cs:110/133,142,119,166` | ✅ |
| mermaid `TranTypes.Sales`/`Return` 分支 | `TranTypes.cs:13,23` | ✅ |
| §2.1 `CreateECouponList` 排除 `IsPointProhibition`、`IsExcludeNormalPoint` 互斥 | `PointManager.cs:225,237,254` | ✅ 行号精确 |
| §3.2 离线降级 `CalcPointOffline` | `PointManager.cs:156,166` | ✅ 行号精确 |
| `PointInfinityService.cs` 外部 Infinity 通信 | `Device/Device.PointInfinityService/PointInfinityService.cs`（Device 层） | ✅ |
| §3.2 `MemberOffline` 落 TLog + Transfer FIFO 补录 | 未在抽样中定位到具体代码 | ⚠️ 未核实 |

### 05_discount.md
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| `DiscountManager` 调 `DividedDiscountSubTotal` | `DiscountManager.cs:91` | ✅ 行号精确 |
| §2.1 `IsCalcDiscountLineItem` 仅限 `EnteringItem`/`Paying` | 实允许 **7 态**（`DiscountManager.cs:177-197`） | ⚠️ 过少陈述 |
| §2.1 `IsCalcDiscountSubTotal` 仅 `Paying` 且无付款 | `DiscountManager.cs:206,212` | ✅ |
| §3.1 分摊写入 `TotalDiscountSubTotalDivided`（文档 L57） | 实为 `DiscountCommonLogic.cs:517/535`（方法体 :496） | ⚠️ 机制真/行号错 |
| §3.1 残差加到最高单价行 | `DiscountCommonLogic.cs:548` `OrderByDescending(TargetUnitPrice)` | ✅ |
| §4 Mix&Match「SQL 主数据轮询 `T_MixMatchMaster`」 | 实为内存 `TranMasterDataSet.DiscountMixMatchMaster`（`SalesTranRepositoryExtensionMethods.cs:89-104`） | ⚠️ 名称+机制偏差 |

### 06_open_close_count.md
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| `CloseCountTran.StartConfirm` 拦截器链 | `CloseCountTran.cs:142` | ✅ 行号精确 |
| BR-CC-001 回收箱残留 `ErrorCloseCountRecoveryBox` | `CloseCountTran.cs:104,109` | ✅ |
| BR-CC-002 违算 `ErrorCloseCountUncertain` | `CloseCountTran.cs:122` | ✅ |
| BR-CC-003 暂挂单 `GetMTransactionUnoperatedDataTable` | `CloseCountTran.cs:174,180` | ✅机制/⚠️行号 |
| BR-CC-004 卡机 `DailyTotal()` | `CloseCountTran.cs:624,632` | ✅ |
| 日结 SP usp_BOUpdateBusinessStateForExecuteCloseCount / usp_BOInsertDailyPosSalesTotal… / usp_GetLastCloseBusinessDate | `database/04_StoredProcedures/` 三者均存在 | ✅ |
| §3.3 `OpenCountTran.cs` 调 usp_GetLastCloseBusinessDate、日期+1、切 `Opened`、校 100,000 备用金 | `OpenCountTran.cs`(179 行) 仅备用金清点（StartTran:91 读、:103 存 ChangeReserve、EndTran:125 比对）；**无 SP/AddDays/Opened/100000** | ❌ 功能归属错误 |
| §3.3 开店读备用金点检 | `OpenCountTran.cs:91` `ReadCashCounts()`、:97 求和 | ✅ |

---

## 卷二 · 专项分析报告（2_business_specs/reports 7 篇）

> 本切片最突出的特征：**质的记述（算法/结构/契约/枚举值）高精度可裏取り，但定量统计系统性捏造**，且多处「未检出本地物理拉取」的免责注记为虚假（文件实际全部存在、可读取行数）。

### business_emoney_analysis.md
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| EMoneyChargeTran.cs=1,134 行 | 实测 1134 | ✅ |
| 类宣言 `: CommonTranBase, IPaymentTran, IMemberTran, IPaymentTranForCAFISArch…, …ForPaymentService` | `EMoneyChargeTran.cs:19` | ✅ |
| Start*/InputChargeAmount/MemberInquiry/AddPayment/EndTran 方法 | `:456,491,512,524,535,658,694,724` | ✅ |
| `ReasonType = "07"` | `EMoneyChargeVoidTran.cs:103`=`ReasonTypes.ReasonMinusTrade.Code`（非 "07"；`ReasonCode="07"` 是 :108 且正确） | ❌ |
| LocalReadTranDataSet 验 TranLogTypes.EMoneyCharge/TrainingEMoneyCharge | `:480,482,485` | ✅ |
| EndTran 呼 ValueDeposit（充值确定） | `EMoneyChargeTran.cs:735` | ✅ |
| 该文件「未检出本地物理拉取」 | 实文件存在（1134 行可读） | ❌ 免责虚假 |

### business_inputconverter_analysis.md
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| 14 种 barcode converter | `BarcodeConverter/*.cs`=14 | ✅ |
| Verhoeff / RadixConvert 嵌套 | `Utility/OneTimeBarcodeConvertUtility.cs:431,528` | ✅ |
| `_lifeTime=1` 硬编码 | `:29` | ✅ |
| ItemCode IsTarget/GetConvertedBarcode（PadLeft8/12/13, Substring5/1） | `BarcodeItemCodeConverter.cs:105-115,133-143` | ✅ |
| MemberScan Regex/Length==18/Substring(3,13) | `BarcodeMemberScanConverter.cs:37,41,103,111` | ✅ |
| DynamicPricing 26 桁：itemCode=Substring(0,13)、消费期限 (13,2)/(19,2) | `BarcodeDynamicPricingConverter.cs:62,90,157,158` | ✅ |
| NonPLUFood=食品公园结算，Length==24 | `BarcodeNonPLUFoodConverter.cs:10-13,34` | ✅ |
| 该文件「未检出本地物理拉取」 | 实文件存在（2 份拷贝 root + Utility/） | ❌ 免责虚假 |

### business_member_analysis.md
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| MemberObject.cs=2,175 行 | 实测 2174 | ⚠️ |
| IMemberTran = `MemberObject{get}` + `ChangeMember(Func<…>)` 两成员 | `Business.Member/IMemberTran.cs:16,23` | ✅ |
| PointCalcResult 积分 10 种 | 实测 **11** 种（+`RankPointAllRank[10]`）；11 字段位于 `PointCalcResult.cs:131-191` | ⚠️ |
| Inquiry/LockInquiry/Update/ValueDeposit/…/PointInfinity 方法 | `MemberObject.cs:251,442,531,566,653,843,1184`（文档行号一律 +8~14 漂移，存在均确认） | ⚠️ 行号 |
| MemberObject 等「未检出本地物理拉取」 | 实文件存在 | ❌ 免责虚假 |

### business_payment_analysis.md
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| PaymentObject 794/PaymentBase 204/PaymentCredit 435/PaymentCash 208/PaymentPoint 184 | 实测 793/203/434/207/183（一律 −1，实质一致） | ✅ |
| PaymentCredit `Modes{Sales=0,Void=1,EMoneyChargeVoid=2}`；Void 用 `CreditTransactionCodes.Void.Code` | `PaymentCredit.cs:33,38,43,225` | ✅ |
| PaymentObject AddPayment/…/DispenseChange | `:168,228,277,349,428,481,528` | ✅ |
| PaymentQRBase=138 行 | 实测 **364** 行 | ❌ |
| QR 各类 WeChat/Alipay/PayPay/RakutenPay/Docomo 53~56 行 | 实测 **全 23 行** | ❌ |
| PaymentDebit 220+/PaymentValueCard 208+ | 实测 596/474 | ❌ |
| 支付方式 25 种 | 实测具象子类 **26**（文档漏 `PaymentOfflineCredit`） | ⚠️ |
| 支付实现类 ~150,000 行 / 总计 ~153,454 行 | 实测 `Business.Payment` 全 38 文件 **8,375 行** | ❌ 约 18 倍夸大 |
| 各 Payment 实装「未检出本地物理拉取」 | `Payment/` 下全实在 | ❌ 免责虚假 |

### business_point_exception_analysis.md
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| try-catch 全模块仅 2 处 | grep=2 | ✅ |
| 位置1 CalcMemberECouponPointLogic try26-catch44 | `PointLogic/CalcMemberECouponPointLogic.cs:26,41,43` | ✅ |
| 位置2 SalesTranRepositoryExtensionMethods try111-catch180 | `ExtensionMethods/SalesTranRepositoryExtensionMethods.cs:111,177` | ✅ |
| throw 文/自定义异常类 = 0 | grep=0 / 0 | ✅ |
| PointManager.Calc TranType==Return 分支 + foreach Init/Calc | `PointManager.cs:102,107,119,142,144` | ✅ |
| C# 文件总数 20 | 实测 **19**（本文树列 18，自我矛盾） | ⚠️ |

### business_rj_analysis.md
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| SalesLayout.cs=2,484 行 | 实测 2487 | ✅ |
| SalesLayout 6 方法（AddLineItems/AddPayments/…/AddSalesReceiptBarcode） | `Layout/SalesLayout.cs:49,578,1271,1843,1956,555` | ✅ |
| RJLayoutMapper 541/RJLayoutSales 414 | 实测 543/418 | ✅ |
| RJLayoutEMoneyCharge=414 行 | 实测 **549** 行 | ❌ |
| Layout/* 递归 52 个 | 实测 52 | ✅ |
| 总计 101/102 文件 ~40,741 行 | 实测全 98 文件 **18,711 行** | ❌ 约 2.2 倍夸大 |
| TranLogTypes.EMoneyCharge/EMoneyChargeVoid/NormalSales 引用 | `TranLogTypes.cs:142(801),147(816),27(101)` | ✅ |
| `RJDeviceType` R/J/RJ | 使用处确认，enum 定义本体在 Business.RJ 外（Framework） | ⚠️ 核查不能 |

### business_sales_analysis.md
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| SalesTran.cs=2,127 行 | 实测 **2263** 行 | ⚠️ |
| SelfSalesTran 1340/ReturnTran 150/OrderKitchenTran 641/LineItemBase 479 | 实测 1360/149/640/478 | ✅ |
| RestoreTranObject 857 行 | 实测 **1116** 行 | ❌ |
| LineItemPLU 5,119 行 | 实测 `LineItem/LineItemPLU.cs` **135** 行 | ❌ |
| LineItemNonPLU 6,405 行 | 实测 **170** 行 | ❌ |
| LineItemPLUBook 14,083 行 | 实测 **371** 行（约 38 倍夸大） | ❌ |
| LineItemPLUMagazine 7,171 行 | 实测 **204** 行 | ❌ |
| LineItem 系列 ~51,000 行 | 实测合计 **2,583** 行 | ❌ |
| 总计 ~33 文件 ~178,000 行 | 实测 `Business.Sales` 全 52 文件 **11,318 行** | ❌ 约 16 倍夸大 |
| IPointManager/IDiscountManager/ITaxManager | `Business.Sales/{Point/IPointManager.cs,Discount/IDiscountManager.cs,Tax/ITaxManager.cs}` | ✅ |

---

## 卷三 · 技术与数据规格（3_technical_specs）

### 数据库（database）
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| 门店本地「双 SQLite」离线优先架构 | `sqlite`参照=0；`Data/Data.Container/app.config:7-16` = `Data Source=(local)\SQLEXPRESS;Initial Catalog=POS4U_Trial_Master/Tran`；`POS4ULogicService/Web.Release.config:13`=`Initial Catalog=MyReleaseDB` | ❌ 引擎为 SQL Server |
| Master/Tran 双库分工 | app.config 确有 `POS4U_Trial_Master` 与 `POS4U_Trial_Tran` 两库 | ✅（双库属实，但非 SQLite 文件，是 SQL Server DB） |
| 五元组分布式联合主键 | `dbo.TransactionLog.Table.sql` / `dbo.TransactionManagement.Table.sql` PK CLUSTERED=CompanyCode/StoreCode/TerminalNo/ManagedNo/TransactionNo | ✅ |
| SettingMaster 四元组 PK | `dbo.SettingMaster.Table.sql:18-23` | ✅ |
| ItemMaster 三元组 PK；`[UnitPrice][money]`、`[PointRate][numeric](3,1)` | `dbo.ItemMaster.Table.sql:13-15,23,38,49-53`（index.md:60 把字段腐化为 `numeric (3,1 内部关联引用已搬迁)`） | ✅（字段值对，文档腐化） |
| TransactionLog 用 `[TransactionData][xml]` 一体化落盘 | `dbo.TransactionLog.Table.sql:24` | ✅（schema 属实，动机叙述错误引擎） |
| SP「約300」/「428ファイル」 | 真值 SP=**405**；表 160；视图 24；04 裸文件 434（含 udt/ufn/txt）；01 裸文件 185（含 zz_IDX_*） | ❌ 计数失准（既低估又口径混乱） |
| SQLite WAL/synchronous=NORMAL/temp_store=MEMORY 调优（index §4） | 无任何 SQLite/PRAGMA 引用 | ❌ 整节虚构 |
| （§2 粘贴 DDL）`PRIMARY KEY CLUSTERED`/`[money]`/`[xml]`/`NONCLUSTERED`/`WITH(PAD_INDEX…)` | 均为 SQL Server 专属语法，SQLite 不支持 | ⚠️ 自证矛盾（真实 DDL 之上叠加 SQLite 臆造） |
| MasterSync ControllerBulk/ControllerDiff/Transfer | `POS4UBackground/Business/Background.Business.MasterSyncPos/{ControllerBulk.cs,ControllerDiff.cs}`、`.../Transfer/Transfer.cs` | ✅（引擎存在，下发目标"覆盖 SQLite Master DB"错误） |
| NodeType 枚举（00…11 OTCDrugPOS…50 EMoneyChargeStation） | `Common/Common.Const/NodeTypes.cs`；`MTranObject.cs:739` 用 `NodeTypes.GoSemiSelfRegister.Code` | ✅ |

### 设备（devices）
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| Device `.csproj` 总数 | `find Device -name *.csproj`=**78** | ✅ |
| Glory RAD/RT-300 + ECS7 | `Device/Device.CashChangerGloryRADRT300/RADRT300Define.cs`、`Device.CashChangerECS7/`（另 RADRT200/RAD262/VT280 等） | ✅ |
| 前台→TRAN4U net.tcp、Send/ReceiveTimeout=5 分钟 | `WinPOS.Batch/TranRemoteControllerLibrary.cs:131-132`、`TRAN4U/RemoteController/RemoteServiceController.cs:104-105`=`new TimeSpan(0,5,0)` | ✅（绑定为编程式，非 .config） |
| Stera CT-6100/Saturn1000L CAFIS、TCP JSON、SendSync/SendASync | `Device/Device.CAFISArchLAN/Device/CAFISArchSaturn1000L.cs`、`CAFISArchLANBase.cs:48,81` | ✅（文档仅覆盖 LAN 一支，CAFIS 家族含 CT5100/CT6100_ModeSelf 等更大） |
| 打印 `ModifyPrintDataByCapabilityESC` 能力剔除 | `Device/Device.POSPrinterLibrary/PrintDataLibrary.cs:56` | ✅ |
| 「从 SQLite SettingMaster 读 CutPercent」(03:98)/「本地事务 SQLite 核验」(02:107) | 同 P0，引擎为 SQL Server | ❌ SQLite 误植 |

### 接口（apis）
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| POS4ULogicService 11 控制器 | `POS4ULogicService/Controllers/*Controller.cs`=**11**（含 `CartMTranServiceController` 与 `MTranServiceController` 并存，文档只提后者） | ✅ |
| AccessCode 校验 `IsValidAccessCode` | `POS4ULogicServiceLibrary.cs:187` | ✅ |
| 日志脱敏 AES-256 `ContentEncrypt` | `POS4ULogicServiceLibrary.cs:29,45-49,61`=`AesCryptoServiceProvider`+CBC/PKCS7+PBKDF2(`Rfc2898DeriveBytes`,Iteration=1013)（密钥源自硬编码口令+salt，文档未提示安全债） | ✅ |
| `PutBusinessCounter`→`usp_SaveBusinessCounter` 落盘至 `T_BusinessCounter` | `dbo.usp_SaveBusinessCounter.StoredProcedure.sql:25`=`MERGE INTO BusinessCounter`（表名无 `T_` 前缀；`T_` 仅用于视图如 `T_D_PosSales`） | ❌ 表名错误 |
| 「断网离线收银（SQLite）」(store_logic:78) | 同 P0 | ❌ SQLite 误植 |
| BO 超时用 HTTP 418 I'm a teapot | `pos-cloud/.../BOAuthenticationAttribute.cs:53-56` `HttpStatusCodeResult(418)`+HACK 注释 | ✅ 精确命中 |
| POS4UBO=云端 ASP.NET MVC5 多租户后台 | `pos-cloud/Source/POS4UBO/POS4UBackoffice/{Controllers,Views,Logics,Models}` | ✅ |
| POS4UBO 承担「Web API 2 后端」 | BO 业务 SP `usp_BO*` 实际在**门店端 tran DB**，由店端 `BackOfficeServiceController.cs` 驱动 | ⚠️ 部分混淆（云端主体是 MVC 管理前端） |

---

## 卷四 · Trial 专项深度评估（4_trial_specs）

> 本卷分析**实质精度异常高**——算法级、行号级，连 SQL 原文与 CSV 种子数据都对，甚至分析发现 2 个真实 Bug。扣分集中在系统性路径断裂、少量数值/编码硬错误、receipt 符号造假。

### hold_recall（3 篇）
| 篇 | 声明 | 代码证据 file:line | 判定 |
|---|---|---|---|
| business_spec | CanSave 五条（Fixed 存在/零元例外/支付排他/找零排他/上限） | `MTranObject.cs:577,584-585,595-600,604,613/631` | ✅ |
| business_spec | 13 位 ID="13"+终端+ServiceType+流水+M10W31 CD | `MTranObject.cs:23,662,666,668`(`CheckDigitM10W31`) | ✅（算法体在 Framework.dll，仅调用可证） |
| business_spec | 呼出跳过自动折扣、SubTotal 重算；ROWLOCK/UPDLOCK SP | `RestoreTranObject.cs:677-683,833`；`usp_GetMTransactionManagement.sql:34,40-41,50` | ✅ |
| business_spec | 「PauseTypes.cs 定义 **5 种**保留」 | 实为 **9 种**（1-9）`PauseTypes.cs:11-51`（漏 FullSelf/TwoSelf 系列） | ❌ 漏计 |
| evaluation_904 | 旧系统列：强制重算/13 位 ID/物理 DELETE/ROWLOCK | 同上+`usp_DeleteMTransactionManagementAll.sql`、`BatchDeleteMTransaction.cs` | ✅（POS4U 列） |
| consistency_904 | 「904 分支 spec vs code 100% 对齐」 | 全篇=ST-POS kugelpos(Python) `904-cart-suspend-recall`；POS4U 全库**无 904 交易码** | 🔵 对象外·前提误置（引用 kugelpos 行号亦陈旧） |

### price_change（3 篇）
| 篇 | 声明 | 代码证据 file:line | 判定 |
|---|---|---|---|
| v1 | 四重阀门（格式/取消/手动折扣互斥/变价禁止） | `LineItemBase.cs:248,256,261-263,268-270`（`ChangePrice` :237） | ✅ |
| v1 | 采用售价优先级 Overrided>Special>Unit | `LineItemPLUBase.cs:68-79` | ✅ |
| v1 | §5.2 `HeadquartersTransferPriceChangeLogDataFile` 售价变更审计链 | grep 全库无此类名 | ❌ 疑似虚构 |
| v2 | 对话框 6 位限/首 0 过滤/`_isModifyFlag`/双事件级联 | `PriceChangeDialog.xaml.cs:48,88,130,145-149,174-177` | ✅ |
| v2 | §5-6 Avalonia/Python 落地方案 | — | 🔵 对象外（ST-POS 建议） |

### mixmatch / promotion（4 篇）
| 篇 | 声明 | 代码证据 file:line | 判定 |
|---|---|---|---|
| mixmatch_spec | Amount"0"/Price"1"/Set"3"，仅 1 和 3 实装 | `DiscountMixMatchTypes.cs:16-26`；`DiscountMixMatchLogic.cs:68,72` | ✅ |
| mixmatch_spec | DiscountDivided：RoundAwayFromZero+adjust±1+DeepCopy 拆行；小计 RoundToFloor | `DiscountCommonLogic.cs:448,457/461,474-475` | ✅ |
| mixmatch_spec | 排序 `OrderByDescending(MMTargetUnitPrice).ThenBy(IndexOf)`；损失防止 | `DiscountMixMatchLogic.cs:160-161,191,325` | ✅ |
| mixmatch_spec | TLog 111/112 + MM/GS 双轨 | `TranLogConverterMMLogic.cs:111,129,133,52,76` | ✅ |
| promotion | 两阶段·Priority 升序·排他表（8/1/9/4/5/6/10 + 小计 2/3） | `DiscountManager.cs`；`DiscountTypeMaster.csv`（**逐格命中**） | ✅ |
| promotion | DiscountAutoSubTotal 仅抽象基类·C# 未实装·SP 存在 | `DiscountAutoSubTotalLogicBase.cs`（base only）；`usp_GetDiscountSubTotal.sql` | ✅ |
| promotion | §3.2.2 MM 字段名 MixMatchCode/Count/Amount/TypeCode | 实码用 DiscountMixMatchCode/DiscountSetCount/DiscountSetPrice/MixMatchType（与本卷 mixmatch 篇自相矛盾） | ⚠️ 字段名不符 |
| test_scenarios v1/v2 | "A 系统事实"（OnCalc 无 Amount/Fixed 过滤/Void Sign=-1） | 上述 + `TranLogConverterBase.cs:93-95` | ✅（A 系统）；B 系统期待值=对象外 |

### receipt（1 篇）
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| 三段式/RJLayoutMapper 路由/R·J·RJ 通道/BMP 券/Right90/NoPrintLogo·NoCutReceipt | `RJLayoutMapper.cs:34,173,242`；`RJLayoutMemberECouponMessage.cs:16-32`；`RJLayoutMemberECouponImage.cs:53-54` | ✅ |
| Journal=23/Receipt=22 字节截断 | `SalesLayout.cs:23,28`（const 23/22） | ✅ 精确 |
| 印字符号 ☆(点禁)/●(eCoupon)/軽(轻减税) | 实为 `ﾋ`(MessageRJ.xml:88)/`★`(:93)/`*`(:362)；R/外/非 正确 | ❌ 符号造假 |
| 返回 `List<>`/证明书前 3 张 NoCut/加赠标签"クーポン"/SalesLayout 2484 行 | 实为 `[]`/仅 2/3 张 NoCut/"商品単品P"(:94)/实测 2487 行 | ⚠️ 四处小误 |

### return（5 篇）
| 篇 | 声明 | 代码证据 file:line | 判定 |
|---|---|---|---|
| 01 | ReSalesTran 内含 VoidTran；Void=121/新单=101 | `ReSalesTran.cs`（组合）；`TranLogTypes.cs:67,27` | ✅ |
| 02 | 时效 1 月/跨店/IsVoided/数量不可增/理由码"08"互斥 | `ReadReceiptObject.cs:235,260,141`；`ReSalesTran.cs:139-149` | ✅ |
| 02 | Credit/CreditLAN 部分退货**不支持** | `ReSalesLibrary.cs:62-65` 仅移除 Debit/DebitLAN/UnionPay/PayPay，**未移除 Credit** | ⚠️ 存疑（Credit 实留在允许集） |
| 03 | LockInquiry+try/finally UnLockUpdate；CalPreReSalesPoint 公式 | `VoidTran.cs:623,711,717`；`ReSalesTran.cs:80,106` | ✅ |
| 04 | excludeTables/Sign=-1/明细"301"区分/IsCanceled 过滤 | `VoidTranLogMaker.cs:32-43`；`TranLogConverterBase.cs:93-95` | ✅ 实质 |
| 04 | Sign 代码注释 `//121(Return) //125(EMoneyVoid) //122(Void)` | 应 105/816/121，且源码 `TranLogConverterBase.cs:93-95` **本就无此注释** | ❌ 注释数值全错 |
| 05 | IsEvidenceReceiptIssued 二重发行拦截；IsReSales 合并打印 | `EvidenceReceiptTran.cs:251-254`；VoidTran/ReSalesTran EndTran | ✅ |

### cancel_specified（1 篇）
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| WinPOS `unitPriceNormal!=0`→同 Barcode 全 Fixed 一键 Cancel；否则单行 | `Sales_CancelSpecifiedLineByItem.cs:99-114` | ✅ |
| 自助/LogicService qty==1→Cancel；qty>1→ChangeQuantity−1 | `SelfSales_CancelSpecifiedLineByItem.cs` | ✅ |
| LineItemBase.Cancel 乒乓翻转（+非 LogicService VerifyLimit） | `LineItemBase.cs:394-408` | ✅ 逐行命中 |
| 收据 R 通道 `if(!row.IsCanceled)`(L314)/日记账 J 印 `RJ_CanceledItem`(L146) | `SalesLayout.cs:314,146,148`；`RJMessageIds.cs:77` | ✅ 行号精确 |

### open_close（1 篇）
| 声明 | 代码证据 file:line | 判定 |
|---|---|---|
| OpenCountTran 找零机重连/ReadCashCounts/CashChangerAmountNonConfirm/AmountDiffer | `OpenCountTran.cs`（全 token 命中） | ✅ |
| 闭设 4 阻断（UnOperatedMTran/SummaryError/RecoveryBox/Uncertain） | `CloseCountTran.cs`（4 token 全命中） | ✅ |
| CloseCount 状态「20+个」 | `CloseCountTranStates.cs`=**28**；Open=5 | ✅ |
| 开设写「301」/闭设写「302」日志 | 实为 OpenCount=**201**/CloseCount=**202**（`TranLogTypes.cs:97,102`；301/302 是 SelfSales :122,127） | ❌ 数值错 |
| 4 批处理（Report/SummaryComplete/PutBusinessCounter/CyclicClear） | `WinPOS.Batch/Batch*.cs` 均存在 | ✅ |

### 分析发现的 2 个真实 Bug（经复核属实）
| 断言 | 代码证据 file:line | 判定 |
|---|---|---|
| subtotal_discount：`DiscountMaker.cs:34` 会 NRE | `:34` `discountRow.TransactionNo = tranDs.SalesDiscount.FirstOrDefault().TransactionNo` 首迭代 SalesDiscount 空表→`FirstOrDefault()`=null→**确 NRE** | ✅ 缺陷属实 |
| subtotal_discount：`LineItemBase.LineTotal`(:123) 漏减小计折扣分摊额 | `:123` 仅减 `DiscountTotal`，未减 SubTotal 折扣分摊 | ✅ 缺陷属实 |

---

## 卷六 · 备份档案箱（6_archive）— 非核查重点

`6_archive/` 为前期分析的**封存历史层**，非本次核查重点，仅作性质标注：

- `stackshift/`：StackShift 分析诊断工具的自动产物，`.stackshift-analysis/summary.json` 记 `analyzed_at: 2026-04-05` — 即整套代码分析文档的最早生成时点。卷二报告中「行数捏造 / 未检出物理拉取免责」等特征，与自动分析工具在无法读全文件时的估算/幻觉行为一致，可追溯至此层。
- `original_analysis/`（11 篇）、`old_fine_grained_drafts/`（25 篇模块草稿）、`original_background_business/`、`reports/`：均为被 5 卷册取代的原始扁平草稿，README 明示「100% 完整保留」作字典库备查。**不作为权威内容核查**；若被引用，一律回代码复核。
- `walkthrough.md`（完工报告）自述：分析针对旧目录布局 `database`/`pos-store`/`pos-cloud` 生成，宣称「311 个超级链接 0 死链」，且 DB 逻辑写作「SQL Server / SQLite」两论并存 — 与正卷 SUMMARY/README 的「双 SQLite」定论、以及现今 `pos-store→pos-store-ver202606` 版本化后链接全断，互为印证。

---

> 每条判定均以 `trialpos-snapshots` 真实代码（`pos-store-ver202606/` 及 `database/`）为准，file:line 锚定，未采信任何二次文档（含被审文档自身与代码库自带 `docs/`）。5 卷册的评级与跨卷偏差综合见 [`reverse-docs-vs-code-audit-2026-07-14.md`](./reverse-docs-vs-code-audit-2026-07-14.md)。
