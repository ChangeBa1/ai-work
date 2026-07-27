---
title: TRI-POS / POS4U 知识库 × 实际代码 精度核查报告
scope: pj-trial-pos 下 01-confluence-cloud / 02-confluence-trec / 03-gitlab-wiki 三库
truth_baseline: ../trialpos-snapshots（POS4U 真实源码，基准版本 pos-store-ver202606）
date: 2026-07-14
author: jinianxiang
security: 🟡 敏感
method: 4 路并行交叉核查（仅以真实 .cs/.xml/.sql/.csproj/.sln 为证据，未采信任何二手文档，含代码库自带 docs/）
---

# TRI-POS / POS4U 知识库 × 实际代码 精度核查报告

> **姉妹报告**：本报告核查**线上镜像 10/11/12**（正文沿旧编号称 01/02/03）。从 POS4U 源码**源码分析直接生成的 `01-trialpos-docs`（5 卷册 107 页）**另见 [`reverse-docs-vs-code-audit-2026-07-14.md`](./reverse-docs-vs-code-audit-2026-07-14.md)——其画像不同（质的分析出众但门面架构 SQLite 造假、定量统计系统性捏造、链接全断）。二者合起来才是 `90-verification` 对全库的完整代码对照。**注意：本报告正文中的 01/02/03 = 现在的 10/11/12，与 `01-trialpos-docs` 无关。**

## 执行摘要

对 `pj-trial-pos` 三个知识库（01/02/03，合计约 **768 页/文件**）逐库对照 **POS4U 真实源码**（`trialpos-snapshots`，基准 `pos-store-ver202606`）做了严谨的精度核查。核查以**实际代码为唯一真值**，只有真实代码文件（含 file:line）才算证据；代码库自带的代码分析文档 `docs/` 亦被视为未经验证的二手材料，**未用作正确性证据**。

**总体结论：三库对 POS4U 的结构性描述可信度高，未发现"系统性造假"或大面积错误；问题集中在①量化口径错误 ②路径/命名随版本重构后过时 ③大量正文托管外链或空占位（信息缺失而非错误）。**

| 库 | 定位 | 与代码对应 | 精度评级 | 一句话 |
|---|---|---|---|---|
| **01-confluence-cloud**（461 页） | POS4U 現行系统全套知识（業務/開発/品質/運用/保守） | 同一系统 | **开发/技术 B+｜业务/运用 A−** | 结构层（事件/命令/枚举/接口/配置）高度一致，多处逐字吻合；扣分在 DB 计数口径、少量命名笔误、大量外链/空页 |
| **02-confluence-trec**（147 页） | POS開発树：ST-POS新系统设计(A) + POS4U架构级(B) + 通用规约(C) | B 类同一系统；A 类本库无实装 | **B 类 A−** | 架构级文档与代码高度一致（取引種別逐名吻合）；61% 是 ST-POS/JOBManager 新案件，本库无实装、技术栈完全不同，须防误读 |
| **03-gitlab-wiki**（158 文件） | POS4U 框架开发指南（AIPOS wiki） | 同一系统框架 | **B+** | 框架五要素与配置文件与代码结构级完全对齐；唯一硬偏差 NodeType 13，其余为路径前缀 `Bussiness→Common` 系统性过时 |

**必须修正的硬偏差（P0）共 6 类**（详见 §4）：DB 计数虚高、NodeType 13 名称错、2 处内部 API 命名错、テーブル一覧漏表、失效视图残留、核心内部 IF 页正文全空。

---

## 0. 核查前提：三库与代码的对应关系（重要）

经代码库身份确证：`trialpos-snapshots` 虽以 "stpos" 命名，其**实际内容是 POS4U（旧收银系统／現行 TRIAL 自社POS／通称 TRI-POS）的真实 C# 源码**——即 ST-POS 要置换的对象系统。据用户明确口径，**01/02/03 三库都作为"POS4U 的文档/知识库"来核查**。

- **代码 = 唯一真值。** 本次核查只以真实 `.cs/.xml/.sql/.csproj/.sln` 文件为证据；`trialpos-snapshots/docs/`（代码库自带的 107 篇代码分析文档）本身也是未验证、可能片面的二手材料，**全程未作为正确性依据**。
- 三库内**确无代码实装**的内容（如 02 库的 ST-POS 新系统 TO-BE 设计），如实标注"**本代码库无对应实装**"，而非笼统当作"免核"。
- 業界知識/IT用語/流通用語等**内容性质上本就非代码**者，标注"**非代码可核（内容性质使然）**"。

---

## 1. 真值基准（代码事实，已亲自定夺）

| 事实 | 权威值（代码为准） | 说明 |
|---|---|---|
| 门店端版本 | ver202601 / 202605 / 202606（**基准=202606**） | 202605↔202606 顶层目录与 Business 模块**完全一致**，版本漂移仅在文件内容层 |
| 门店端解决方案 | `POS4U_V4.sln` / `POS4UBackground.sln` | |
| Business 模块 | **22 个** | Sales/ReSales/Payment/PaymentStation/CashChanger/CashInOut/OpenCount/CloseCount/Discount/EMoney/EntryNonCash/InputConverter/MainMenu/Member/Operator/Point/Report/RetailMedia/RJ/Tax/TranLogMaker/BusinessCommon |
| Device 模块 | **78 个 .csproj**（目录 80） | 找零机/支付终端CAFIS/CT5100·6100/MSR会员/打印机/人脸FaceMe/OrderKitchen/IncommQR 等 |
| **DB 表** | **约 160 张**（`dbo.*.Table.sql`；+`10_BI` 1 张） | ⚠️ 目录 `01_Tables` 裸文件 185 = 160 表 + 23 索引脚本 + 2 txt |
| **DB 存储过程** | **约 405 个**（`dbo.*.StoredProcedure.sql`；+`10_BI` 约 21） | ⚠️ 目录 `04_StoredProcedures` 裸文件 434 = 405 SP + 27 UDT表类型 + 2 txt |
| **DB 视图** | **约 24 个**（`dbo.*.View.sql`） | 目录 `03_Views` 27 文件 |
| 云端 BO | `pos-cloud/Source/POS4UBO/POS4UBackoffice`（ASP.NET **MVC 前端**） | BO API **后端**在门店端 `LogicService.ApiLogic/BackOffice/Management` |
| ⚠️ 框架基类 | **仅编译好的 `pos-cloud/ExternalModule/Framework/POS4U.Framework.dll`，无源码** | `EventCode/TranBase/CommandBase/State/Observer/IBarcodeConverter` 及编排器均在此 DLL；门店端只能核到"**使用层**"，基类定义层不可核（客观限制） |

> **口径修正**：知识库多处沿用的"185 表 / 434 存储过程"是 `ls | wc` 的目录裸文件数，**虚高**。真实规模应记为"**约 160 表 / 405 存储过程 / 24 视图（另 27 个用户定义表类型）**"。

---

## 2. 各库核查结果

### 2.1 01-confluence-cloud（461 页）

分两个切片核查，详见 [`slice-01a-dev-tech-detail.md`](./slice-01a-dev-tech-detail.md)、[`slice-01b-business-ops-detail.md`](./slice-01b-business-ops-detail.md)。

**切片 01A ·「02.開発関連」（技术密集，222 页，实查约 62 页）— 评级 B+**

全库最可信切片。结构层与代码高度一致，多处**逐字级吻合**：

- ✅ **事件码体系**：`イベント管理` 事件码表对照 `Common.Const/EventCodes.cs`（2248 行）逐条命中；`イベント管理_Xml管理` 中 MainMenuList.xml 位置 1–8 = EventCode 114/206/184/411/174/161/169/149，与 `POS4U/Settings/MainMenuList.xml:15–82` **精确对应**。
- ✅ **枚举族**：`PaymentTypes.cs`（現金01…PayPay50/Alipay53/WeChat54）、`NodeTypes.cs`、`TranLogTypes.cs`、`SettingMasterKeys.cs`(161 键)、`SettingDataType`(6 值+日文注释与 `EventGroupDetailSettingDataTypes.cs:14–47` 逐字一致)。
- ✅ **ダイナミックプライシング**：26 位拆分/校验位 M10W31/年份 4 分支推定/期限判定与 `Business.InputConverter/BarcodeConverter/BarcodeDynamicPricingConverter.cs` 深度吻合。
- ✅ **内部 API**：`DataService`(6/6)、`BackOfficeService`、`ServiceResultBase` 共通响应 7 字段全对（`ServiceResultBase.cs:18–42`）。
- ✅ **开发规则**：MVC + Event→Command→Observer + State-XML 机制、StyleCop + `POS4U.ruleset`、1 Class 1 File 均属实。

主要问题：DB 计数口径错（§4-P0-1）、`POS4ULogicのIF仕様`/`POS4ULogicService WebAPI` 及 `★ビジネスロジック★` 6 子页**正文全空**、2 处 API 命名错、テーブル一覧漏表、launcher 前提误解、若干枚举随版本漂移。

**切片 01B ·业务/运用/品质/保守/その他/ST-POS（231 页，代码级可核约 12 页）— 评级 A−**

凡能落到门店端代码的页面**零硬偏差**（✅6 / ⚠️5 / ❌0）：

- ✅ `ポイント計算について` 基本点数公式 = `Business.Point/CalcNormalPointLogic.cs:22–49`；各点数类型均有对应 `Calc*Logic`。
- ✅ `新店追加手順` 列的 **21 张主数据表 21/21 命中** `database/01_Tables`。
- ✅ `会員関連`(OTB→`CustomerIDInputTypes.cs:26`+`EventCodes.cs:1255`)、`レジランプチェック`(`Device.LaneLight/LaneLight.cs:154–174`)、`レシートチェック`/`領収書発行`(`TranLogTypes.cs`)、`法令遵守`(`Business.Tax` 内外税) 均对齐。
- ⚠️ `保留機能` 支付码表与 `PaymentTypes.cs` 逐码吻合，但 **13(ダンゴ)/30(券類バーコード)/41(テナント売掛) 三码代码无实装**。

本切片天然"代码可核比例低"：约 90% 为業界通識/QA 过程规约/外链托管/空 stub/ST-POS 别系统——属内容性质使然。

### 2.2 02-confluence-trec（147 页）— B 类评级 A−

详见 [`slice-02-trec-detail.md`](./slice-02-trec-detail.md)。三类构成：

| 类 | 内容 | 页数 | 占比 | 结论 |
|---|---|---|---|---|
| **A** | ST-POS 新系统要件定义(51) + JOBManager 改修案件(39) 的 TO-BE 设计 | 90 | 61% | 🔵 **本代码库无对应实装** |
| **B** | POS4U 架构级（Level1-1〜Level6-1、サブシステム、データ构造） | 49 | 33% | **A−**，与代码高度一致 |
| **C** | 通用流程/规约/工具 | 8 | 5% | 自洽（规约类） |

- ✅ **最强证据**：`Level4-1 業務ロジック` 的 **29 个取引種別与 `Common.Const/TranTypes.cs` 恰好 29 个、逐名精确吻合**。
- ✅ `SettingMaster` 列 CompanyCode/StoreCode/TerminalNo/Key/Value 与 `dbo.SettingMaster.Table.sql` 完全一致（该表被 154 个 cs 引用）；`配置ファイル` 抽 10 个全部存在于 `POS4U/Settings/`。
- ⚠️ **exe 命名简化**：`MasterSync.exe`/`VersionUp.exe` 实际是 `POS4U.Console.MasterSync`/`POS4U.Console.VersionUp`；Launcher/TimeSync/DBConnectTool 等为部署工具，不在门店库。
- 🔵 **A 类须警惕**：ST-POS 是 VUE+RESTful 新系统（全仓 `*.vue`=0）、DB 用 `app.tt_*`/snake_case/PK 自增，与 POS4U 的 `dbo.*`/PascalCase/采番机制**完全不同**；`JOBManager`/`Hinemos`/`Kompira` 代码引用均=0。这些 TO-BE 设计一旦被误读为"POS4U 现状"就会与实际矛盾。

### 2.3 03-gitlab-wiki（158 文件）— 评级 B+

详见 [`slice-03-gitlab-detail.md`](./slice-03-gitlab-detail.md)。高优先页（框架五要素/11 个配置文件/Source·DB 结构/新建教程/共通UI/BO API/17 个流程图）**100% 覆盖**（✅27 / ⚠️8 / ❌1）。

- ✅ **框架五要素结构级完全对齐**：Command 四步流程、Event↔Command 同名约定、`StateWinPOS.xml` 的 TranType→State→Command 三层结构、`Sales_ChangeDisplayWithMode=411`(`EventCodes.cs:1220`)、`UIMapper`(MappingView:217/MappingDialog:230/_stateDialogMap:58)、`CreateTran<T>`、`DeviceObserver` 插件工厂调用均有 file:line 证据。
- ✅ **配置文件族**（AttendantPCSendState/MainMenuList/PluginDevice/PluginWinPOS/StateWinPOS）字段与结构逐项吻合。
- ✅ **BO 查询 API** 教程与门店端 `LogicService.ApiLogic/BackOffice/Management/ManagementManager.cs:97`（`ManagementType` 枚举字典派发 + `Get*Logic`）架构完全吻合（**定位更正**：后端在门店端而非 pos-cloud/POS4UBO）。
- ❌ **唯一硬偏差 NodeType 13**：wiki「レーンレジ」实为 `NodeTypes.cs:88 TwoOperatorsPOS`（二人制レジ），且缺 14/15=`LaneSelf`/`LaneSelfPlusPaymentStation`。
- 🕰️ **系统性过时**：全框架路径前缀反复写 `Bussiness/Common/Common.Const/…`，实际是顶层 `Common/Common.Const/…`、`Business/Business.EMoney/…`（结构重构遗留）；`Message.xml`/`MessageRJ.xml`/`Plugin.xml` 实际在 `POS4ULogicService/Settings/` 而非 `POS4U/Settings/`。

---

## 3. 亮点（与代码高度吻合，可放心引用）

1. **事件码 / 枚举族**（01A + 03）：EventCodes / PaymentTypes / NodeTypes / TranLogTypes / SettingDataType 与 `Common.Const/*.cs` 逐条乃至逐字命中——三库交叉印证，可信度最高。
2. **取引種別 29 项**（02-B）：`Level4-1` 与 `TranTypes.cs` 逐名精确吻合。
3. **XML 驱动的框架**（01A + 03）：MainMenuList.xml 按钮→EventCode→Command、StateWinPOS 三层结构、配置文件字段——结构级完全对齐。
4. **业务算法**（01B + 01A）：点数计算公式、ダイナミックプライシング 26 位条码算法、主数据表清单（21/21）。
5. **BO API 架构**（03）：ManagementManager 字典派发 + ManagementType + Get*Logic。

---

## 4. 跨库偏差清单（按优先级）

### 🔴 P0 · 硬偏差（须尽快修正）

| # | 库/页 | 偏差 | 代码真值 | 证据 |
|---|---|---|---|---|
| 1 | 全局（01A/02/03） | DB 规模"185 表/434 存储过程" | **约 160 表 / 405 SP / 24 视图** | `database/01_Tables *.Table.sql=160`；`04_StoredProcedures *.StoredProcedure.sql=405` |
| 2 | 03 `1_9.NodeType` | 13=「レーンレジ」；缺 14/15 | 13=`TwoOperatorsPOS`(二人制)；14/15=LaneSelf(登録/会計) | `NodeTypes.cs:88,93,98` |
| 3 | 01A `POSLogicWebService` | `PutBusinessCounterList` | 实为 `PutBusinessCounter` | `POSLogicWebServiceController.cs:563` |
| 4 | 01A `POS4UアプリのAPI仕様` | `DataService.svc/CheckModuleExist` | 实属 BackgroundService；DataService 相当为 `CheckExistUpdateModule` | `BackgroundServiceController.cs:171` / `DataServiceController.cs:54` |
| 5 | 01A `テーブル一覧`/`ビュー` | 漏列 `EnterpriseSystemInfoMaster`、`TerminalMaster`；残留失效视图 `T_D_PosSalesDetail`（源表已删） | 以 `database/*.sql` 为准 | `database/01_Tables/`、`03_Views/` |
| 6 | 01A `POS4ULogicのIF仕様`/`POS4ULogicService WebAPI`/`★ビジネスロジック★`×6 | 核心内部 IF/业务逻辑页**正文全空** | 主题在代码真实存在 | `WinPOS/Command/*`、`LogicService.CommandSales` |

### 🟡 P1 · 过时 / 命名（随版本重构遗留，宜统一订正）

| # | 库 | 问题 | 修正方向 |
|---|---|---|---|
| 7 | 03 全框架页 | 路径前缀 `Bussiness/Common/Common.Const`、`Bussiness/POS/…` | → `Common/Common.Const/…`、`Business/Business.EMoney/…` |
| 8 | 03 配置页 | `Message.xml`/`MessageRJ.xml`/`Plugin.xml` 标在 `POS4U/Settings` | 实际在 `POS4ULogicService/Settings`；POS4U 侧仅多语言 `Message.{ja_JP,en_US,zh_CN}.xml` |
| 9 | 01A/02 launcher | `VersionUp.exe`/`MasterSync.exe` 口语名；wiki 称 TimeSync/IMEChange/DataUpdate4Replace "有源" | 实名 `POS4U.Console.VersionUp/MasterSync.exe`；后三者本树无源码 |
| 10 | 01A launcher | "TRAN4U = ランチャー本体" | TRAN4U 是被 launcher 启动的**常驻插件宿主**；真正 launcher 本体不在本库 |
| 11 | 01A/01B/03 | 枚举随版本漂移：NodeType16 ガソリン、支払 13ダンゴ/30/41、TranLog 57→58、事件 436→600+ | 逐项标注"已废弃/未导入/新增"状态 |
| 12 | 03 新建教程 | 文件名笔误 `SelfSales.cs`(→`SelfStates.cs`)、`EMoneyChangeTran`(→`EMoneyChargeTran`)、`Factory.CreatePlugun`(→`CreatePlugin`)、示例键 `ShowSelfSalesLineItemRowNumber`(已不存在) | 按代码订正 |
| 13 | 01A コンバーター | 本地遍历第 10/11 位 QR↔NonPLUFood 互换；DynamicPricing 排除阈值"6 个 0"实为"7 个 0" | `PluginWinPOS.xml:94,98`；`BarcodeDynamicPricingConverter.cs:68` |

### 🔵 P2 · 结构性缺口（信息缺失，非错误）

| # | 现象 | 影响 |
|---|---|---|
| 14 | 大量运用/保守/その他页正文托管在 **Google Drive/Docs/Sheets 外链**，镜像未落地正文 | 外链失效即知识丢失；不可搜索、不可离线核查 |
| 15 | 大量**空标题桩**（14 行 frontmatter-only）：02 库 Level6-1 全部子页(CRM/ISM/売上フラッシュ/現金管理/緊急売変)、DBConnectTool/Sleep/ツール 等 | 目录看似完整、实则无内容 |
| 16 | 01A 仅详述 4/11 个 Controller；`MemberService/ItemDetection/ReportService` 整只未记载 | API 面"正确但不完整" |
| 17 | 02 `POS4Uテーブル一覧`、01 `設定マスタキー`/`Table-Layout` 仅外链，未落地实际清单 | 无法逐项核查 |
| 18 | 78–80 个 Device 模块中仅少数被结构化文档覆盖 | 设备侧知识稀薄 |

---

## 5. 覆盖率与局限（诚实说明）

- **全部约 768 页均已按目录归类**；**深度详读 + 代码交叉验证约 216 页**（01A≈62、01B≈51、02≈37、03≈66），其中**结构/框架/DB/接口/配置/枚举类页面已尽数覆盖**。
- 未逐页展开者：01A 的基幹 IF 电文规格子页（WBRT/WBMN 系约 60+）、课题别页、外部系统 API 页；01B 的業界知識 85 页与 QA 过程规约；02 的 A 类 90 页（TO-BE 无实装，抽样 6 页代表）；03 的通用 C#/运维/图片页约 90 个。这些属外链/纯图/通用知识/别系统，非"应核而未核"。
- **客观不可核层**：框架基类与编排器在缺失的 `*.Framework.dll` 内（门店端只能核到使用层）；纯图片页、外链页、运行时绝对路径（`C:\POS4UGO\...`）无法在源码内验证。
- 逐 file:line 证据表见 `90-verification/` 下 4 份切片明细。

---

## 6. 体系现状诊断与改进计划

### 6.1 现状诊断

**三库定位与重叠**：

```
                 POS4U 现行系统
   ┌───────────────┼───────────────┐
01-confluence-cloud  02-confluence-trec  03-gitlab-wiki
（現行全套知识/権威）  （设计过程/含新系统） （框架开发指南）
   │                   │                   │
   └── 開発関連 ⇄ 框架五要素/配置 ⇄ 新建教程 （三库在"框架/配置"层高度重叠、但口径与版本不一）
```

- **重叠区**：框架五要素、配置文件、枚举、Source 结构在 01A / 02-B / 03 三处各有一份，**互相印证但版本与命名不统一**（如路径前缀 01A 用 `Common.Const`、03 用 `Bussiness/Common`）。→ 无"单一真相源"。
- **缺口区**：内部 WebAPI 完整清单、设备族、业务逻辑细节（★ビジネスロジック★ 空页）、退货/促销/日结等深链路——三库都薄或空。恰恰这些在 `trialpos-snapshots/docs/`（代码库自带代码分析文档：架构/业务规格/DB字典/设备/接口/Trial 专项/追溯矩阵）里有较系统的覆盖，但 **docs/ 未经代码验证、也未与三库打通**。
- **系统归属混淆**：02 库 61% 是 ST-POS 新系统/JOBManager 案件，与 POS4U 门店库并置于同一树，无顶层"系统归属"标识，易误读。
- **留存风险**：大量正文托管 Google Drive/Docs 外链，镜像内是空壳。

### 6.2 内容补充清单（结合代码体系，指出"应补什么"）

| 领域 | 代码现状 | 文档现状 | 建议补充 |
|---|---|---|---|
| 内部 WebAPI | 11 个 Controller（`POS4ULogicService/Controllers/`） | 仅详述 4 个 | 补 `MemberService/ItemDetectionService/ReportService` 及各 Controller 全 action；填 `POS4ULogicのIF仕様`/`WebAPI` 两页空正文 |
| DB 数据字典 | 约 160 表/405 SP/24 视图，`SettingMaster`(154 引用) 等核心表 | テーブル一覧仅外链、计数虚高 | 落地真实表/视图/SP 清单，更正计数口径，补 `EnterpriseSystemInfoMaster`/`TerminalMaster`、删失效 `T_D_PosSalesDetail` |
| 设备族 | 78 个 Device 模块（找零机/CAFIS/CT/MSR/打印机/FaceMe/OrderKitchen 等） | 仅少数机型有结构化描述 | 建"Device 模块 × 型号 × 状态(实装/Simulator)"总表 |
| 业务逻辑 | 22 个 Business 模块、State/Command/Observer 链 | ★ビジネスロジック★ 6 子页全空 | 按模块补 Tran/State/Command/Observer 处理链（可参考 docs/2_business_specs 但须回代码复核） |
| 框架五要素 | 分布于 `Common.Const`、`WinPOS/*`、`*.Framework.dll` | 三库口径/路径不一 | 统一为一份"框架权威说明"，注明基类在 `POS4U.Framework.dll`（仅使用层可见） |
| 启动/部署链路 | TRAN4U(常驻宿主)/POS4U/POS4U.Console.*；launcher 本体外置 | launcher 前提有误、exe 名不符 | 画一张"launcher→9 程序（含真实 AssemblyName、常驻/批处理）"权威图 |
| 系统边界 | POS4U 门店端 ⇄ Azure/基幹 ⇄ ST-POS(新) | 售价变更/緊急売変/ST-POS 边界模糊 | 每页标注"门店端 / Azure / 基幹 / ST-POS新系统"归属 |

### 6.3 改进计划（分阶段）

**阶段 0 · 硬偏差修正（本周，低成本高收益）**
- 修 §4 全部 6 项 P0：DB 计数口径、NodeType 13(+14/15)、2 处 API 命名、テーブル/ビュー 增删、填两页空 IF 正文（至少列 action 清单）。

**阶段 1 · 口径与命名统一（1–2 周）**
- 全局订正框架路径前缀 `Bussiness/…`→`Common/Common.Const`、`Business/Business.*`；订正 Message/MessageRJ/Plugin 真实路径；统一 exe 实名；修正 launcher/TRAN4U 前提；订正 P1 各笔误。
- 为每份文档 frontmatter 增加 **`code_baseline: pos-store-ver202606`** 与 **`code_refs:`（关联的代码文件路径）**，把文档锚定到代码。

**阶段 2 · 内容补全与外链落地（3–4 周）**
- 把 Google Drive/Docs/Sheets 外链页的关键正文/表格**落地进镜像**（优先 クレジット運用/商品登録/端末初期設定/ソース改善ポイント/テーブル一覧/設定マスタキー）。
- 按 §6.2 清单补 Controller / Device 总表 / 业务逻辑链 / 空标题桩。

**阶段 3 · 结构治理与 docs/ 打通（1–2 月）**
- 建 `pj-trial-pos` 顶层**交叉索引**：一个能力/主题 → 三库对应页 + 代码路径 + `trialpos-snapshots/docs/` 对应文档，标注"单一真相源"。
- 把代码库自带 `docs/`（107 篇）作为**候选素材**并入知识库，但**逐条回代码复核**后才升级为"已验证"；未复核者标 `unverified`。
- 02 库 A 类顶部显式声明系统归属（ST-POS 新系统 / JOBManager 后端案件 ≠ POS4U 门店库）。

**阶段 4 · 维护机制（长期）**
- 以本报告为**精度基线**；每次差分同步（见各库 `_sync/`）后，对结构/枚举/配置类页面跑一次轻量回归核查，检测漂移。
- 明确 owner 与复核周期；将"文档 ⇄ 代码"一致性纳入版本发布检查项。

---

## 附录 · 证据明细索引

| 切片 | 明细文件 | 覆盖 |
|---|---|---|
| 01A 开发/技术 | [`slice-01a-dev-tech-detail.md`](./slice-01a-dev-tech-detail.md) | 02.開発関連 222 页，约 95 判定点 |
| 01B 业务/运用 | [`slice-01b-business-ops-detail.md`](./slice-01b-business-ops-detail.md) | 業務/品質/運用/保守/その他/ST-POS 231 页 |
| 02 trec | [`slice-02-trec-detail.md`](./slice-02-trec-detail.md) | 147 页 A/B/C 分类 + B 类逐页表 |
| 03 gitlab | [`slice-03-gitlab-detail.md`](./slice-03-gitlab-detail.md) | 框架五要素/配置/新建教程/BO/流程图 |

> 每份明细含 `[声明 | 代码证据 file:line | 判定]` 三列证据表。所有判定均以 `trialpos-snapshots` 真实代码为准，未采信任何二手文档。
