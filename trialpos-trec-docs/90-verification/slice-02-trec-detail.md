# 切片02 精度核查报告：02-confluence-trec（POS開発 / POSProduct）

- 镜像源：documents.trechina.cn pageId=18781665，共 **147 页**，基准 2026-07-12
- 代码真值库：`../trialpos-snapshots`
  - 门店端主锚点：`pos-store-ver202606`（POS4U_V4.sln / POS4UBackground.sln）
  - BO：`pos-cloud/Source/POS4UBO`（POS4UBackoffice.csproj）
  - DB：`database/01_Tables`（**185 张 .sql 建表**）、`04_StoredProcedures`（453 sp）
- 口径（已按协调者澄清校准）：**全部 147 页均视为 POS4U 相关文档**，凡可代码验证的声明一律到真实代码查证并给 file:line；仅真实代码文件算证据，代码库自带 `docs/` 不作证据。确无对应实装者标注「本代码库无对应实装」，并仍核对其对 POS4U 现状引用是否准确、内部是否自洽。

---

## 一、A/B/C 分类与页数占比

| 类别 | 定义 | 页数 | 占比 |
|---|---|---|---|
| **A** | ST-POS 新系统 / 独立改修案件的 TO-BE 设计 | **90** | 61.2% |
| **B** | POS4U 现行架构级文档（可对本代码库核查） | **49** | 33.3% |
| **C** | 通用流程 / 规约 / 工具 | **8** | 5.4% |
| 合计 | | 147 | 100% |

**A（90）拆分**：
- `301300102 ST-POSｼｽﾃﾑ要件定義&技術検証`：**51 页**（id 前缀 `33494*` + `33494303`）
- `504130153 Kompira pigeon…JOBManager改修`：**39 页**（id 前缀 `38*`）

**B（49）**：`18781665` 主页 + `Level1-1〜Level6-1` 全部（`18783*`/`18784*`/`18786*`/`18789*`/`27566931`），扣除 Level7-1 共通子树。

**C（8）**：`Level7-1 共通` 子树 = 18783356 共通 / 18783358 プロセス / 18783360 開発ルール / 18783362 チームルール / 18783364 自動化テスト / 18783366 ツール / 18783368 LogicServiceテスト(EPOSEventSender) / 18783370 操作ログ調査(RecordFileViewer)。

---

## 二、(A) 类核查结论（TO-BE / 外部案件，逐点查证）

**总判定：🔵 本代码库无对应实装**——A 类两个案件描述的系统/改修，代码均不在本 POS4U 门店库；且其技术栈与数据模型与 POS4U 现行 C# WinForms 体系不同。逐点证据：

### A-1. 301300102 ST-POS（新 Web 系统 TO-BE，51 页）
- **技术栈声明**：`3.2バックエンド処理方法`(33494219) 明确「フロント(VUE)とバックエンド(API)分離」「RESTful」；`06.前端技术选型`(33494303) 指向 GoogleDrive。
  - 代码查证：全仓 **`*.vue` 文件 = 0 个**；POS4U 门店端为 .NET Framework 4.0 WinForms（POS4U.csproj `OutputType=WinExe`, `TargetFrameworkVersion v4.0`）。→ 新前端未在本库。
- **DB 采番声明**：`5.2.DB採番方式`(33494228)「全てテーブルの主キーはDB自動インクリメントより発番」。
  - 与 POS4U 现状**不一致**：POS4U 走 SettingMaster/ManageNo 采番（CESettingTool「ManageNoを0に設定」）。→ 属新系统方案，非 POS4U 现状。
- **数据模型声明**：`【A1001】消費期限設定一覧`(33494246) 使用表 `app.tt_expiration_header` / `app.tt_expiration_detail` / `tm_dict`（snake_case + `app.` schema + YAPI `yapi.trechina.cn`）。
  - 代码查证：POS4U DB 无任何 `tt_expiration*` / `app.*` / `tm_dict`（`grep tt_expiration` 全仓=0）；POS4U 同域功能是 `dbo.BestBeforeDateMaster` / `dbo.BestBeforeMarkDownMaster`（PascalCase，18 个 cs 引用）。→ 两套 schema，ST-POS 是并行新建，非 POS4U 表。
- 其余多为图片页 / GoogleDrive・Figma 链接页 / 变更履历页（アーキテクチャー 33494212 仅内嵌图；ERD/テーブルレイアウト/シーケンス 等）。**抽样 6 页详查，性质一致。**

### A-2. 504130153 Kompira pigeon / JOBManager 改修（后端作业调度案件，39 页）
- 内容：SMART ジョブ / SQL Server ジョブ / Hinemos / EAI ジョブ 的画面详细设计、API 仕様書、Kompira pigeon 导入。
  - 代码查证：`JOBManager` = 0 cs 引用；`Hinemos|Kompira|pigeon` = 0 引用。→ 属 AIPOS 后端/运维作业调度改修，本 POS4U 门店库无对应实装。
- `504130153_02_02.システム要件定義書`(38085261) 等多为内嵌构成图。

> A 类对 POS4U「现状引用」检查：未见对 POS4U 既有事实的错误断言（多为独立新建/后端案件，自洽）；唯 33494228「全 PK 自增」若被误读为 POS4U 现状会与实际采番机制矛盾，但其上下文是新系统方式设计，非描述 POS4U。

---

## 三、(B) 类逐页核查表（POS4U 架构级 → 代码 file:line）

图例：✅一致 / ⚠️部分一致 / ❌偏差 / 🕰️过时 / 🈳空/图链桩（无正文可逐条核查，但结构对应关系已查）

| 页面(id) | 声明 | 代码证据 (file:line / 路径) | 判定 |
|---|---|---|---|
| **Level4-1 業務ロジック**(18783342) | 29 个取引種別：Sales/SelfSales/OrderKitchen/PaymentStation/Void/ReSales/Return/EMoneyCharge/OpenCount/CloseCount… | `pos-store-ver202606/Common/Common.Const/TranTypes.cs`：**恰好 29 个** `new TranType(nameof(..))`，名称逐一吻合（含 EMoneyChargeVoid/Employee/SelfSales, CashChangerRecover/Replenish/ExchangeMoney, EntryCalculatedCash, MTranDelete, EntryNonCash, EvidenceReceipt 等） | ✅（最强一致） |
| **SettingMaster**(18783350) | 键表列 企業/店舗/端末/Key/Value；~100+ 设定键(AccessCode/CRMBaseURL/IsFaceMe/ManjyuApiClientId/DiscountRoundType/PointBaseAmount/Dango* 等) | `database/01_Tables/dbo.SettingMaster.Table.sql`：`[CompanyCode][StoreCode][TerminalNo][Key][Value]` 列完全一致；键在代码大量使用：IsFaceMe=17 cs, PointBaseAmount=16, DiscountRoundType=7, ManjyuApiClientId=5, CRMBaseURL=4；`SettingMaster` 被 **154 个 cs** 引用 | ✅ |
| **配置ファイル**(18783352) | 34 个本地 POS XML（Message*.xml/StateWinPOS*.xml/MainMenuList*.xml/Plugin*.xml/Setting*.xml/Schedule*.xml/AttendantPCSendState.xml 等） | 抽 10 个全部存在于 `pos-store-ver202606/POS4U/Settings/`（Message.xml/StateWinPOS.xml/MainMenuList.xml/Plugin.xml/PluginDevice.xml/SettingWinPOS.xml/AttendantPCSendState.xml/ControllerWinPOS.xml/ScheduleCloseCount.xml/SettingTerminal.xml 各=1）；MainMenuList 变体齐全 | ✅ |
| **POS4U.exe**(18783326) | POS 画面/機能主程序；58 项功能 | `POS4U/POS4U.csproj`：`OutputType=WinExe`,`AssemblyName=POS4U`；Launcher 第9步「POS4U_V4起動」对应 `POS4U_V4.sln` | ✅ |
| **TRAN4U.exe**(18783322) | 后台：Azure 传输トランlog/ジャーナル、集計、マスタ差分同期 | `TRAN4U/TRAN4U.csproj`：`OutputType=WinExe`,`AssemblyName=TRAN4U`；后台传输/同步职责与 POS4UBackground 各服务一致 | ✅ |
| **Launcher.exe**(18783308) | 依序启动 9 个程序 | Launcher 自身**不在门店库**（部署启动器）；但链路引用的 TRAN4U/POS4U/MasterSync/VersionUp 存在 | ⚠️（编排真实，Launcher 本体外置） |
| **MasterSync.exe**(18783318) | 起动时マスタ一括/差分同期（Azure↔POS DB） | 实装为 `POS4UBackground/POS4U.Console.MasterSync/`（`AssemblyName=POS4U.Console.MasterSync`）；MasterSync=227 cs 引用 | ⚠️（程序名简化：实际非「MasterSync.exe」而是 POS4U.Console.MasterSync.exe） |
| **VersionUp.exe**(18783314) | POS 版本升级流程 | 实装为 `POS4UBackground/POS4U.Console.VersionUp/`（`AssemblyName=POS4U.Console.VersionUp`）；页内引用 `MasterDownload.exe`→代码 MasterDownload=33 cs 引用（自洽） | ⚠️（程序名简化） |
| **TimeSynchronization.exe**(18783310) | 取 Azure 当前时间(GetCurrentDateTime) | GetCurrentDateTime=4 cs 引用（概念存在）；exe 本体不在门店库 | ⚠️/🔵 |
| **CESettingTool.exe**(18783328) | 端末用途/情报设定，DB 初期化 | CESetting=1 cs 引用；工具本体不在门店库（部署配置工具） | ⚠️/🔵 |
| DBConnectTool.exe(18783312)/DataUpdate4Replace.exe(18783316)/IMEChange.exe(18783320)/Sleep.exe(18783324) | 仅标题（空桩） | 均为部署/启动小工具，不在 POS4U_V4.sln | 🔵 无对应实装 |
| **Level3-3 LogicService**(27566931) | 标题桩 | LogicService 结构真实存在：`POS4ULogicService.csproj` + `LogicService.ApiLogic/ApiConverter/CommandSales/CommandCommon/Common/ServiceAccessor` 6 个工程 | ✅（结构） |
| **POS4Uテーブル一覧**(18783348) | 仅 GoogleDrive 链接，无表清单正文 | DB 实际 `01_Tables` = **185 张**（dbo.PascalCase）；文档未罗列，无法逐表比对 | ⚠️（桩/外链；表数已旁证185） |
| **Level3-2 キッチン**(18783340,+基本/詳細18784729/18784731) | 厨房子系统设计 | `Device.OrderKitchenApiService(.Simulator).csproj` + `WinPOS.UI.OrderKitchenView.csproj`；Kitchen=166 cs 引用 | ✅（结构/设计对应） |
| **アテンダント監視**(18783336,+18789494/18789497) | 值守监视 | Attendant=212 cs 引用；`POS4U/Settings/AttendantPCSendState.xml`、WAV_CALL_ATTENDANT | ✅（结构） |
| **SC代替**(18783338,+18786196/18786229) | 状态管理代替 | `Device.StateManagementService(.Simulator).csproj`（映射合理） | ⚠️（命名间接） |
| **POS運用監視ツール**(18783332,+18786122)/**BO帳票**(18783334) | 监视/帐票 | POS4UBO(POS4UBackoffice) 存在；帐票在 Business.Report | ⚠️（设计文档,细节未逐条） |
| システム構成(18783288)/Level1-1(18783297)/AIPOS全体像(18783299)/Level2-1(18783301)/Level2-2(18783304)/Level5-1(18783344)/データ構造(18783346)/Level6-1(18783354)/POS開発主页(18781665) | 图片/链接/标题桩 | 无正文文本可逐条核查；所指系统在代码可见（结构不矛盾） | 🈳 |
| **Level6-1 子**：CRM(18789342)/ISM(18789344)/売上フラッシュ(18789331)/現金管理(18789333)/緊急売変(18789338)/GO実績帳票/26JAN/キャッシャ別フラッシュ | 全为空标题桩 | 对应能力在代码存在：`Device.CRM.csproj`、`Business.RetailMedia`、`Business.CashInOut/CloseCount`（现金管理域）等 | 🈳（正文为空，无法核查文本） |

**旁证（模块数量锚点）**：
- Business 模块 = **22 个**（`find Business/Business.*.csproj`）——与协调者锚点「Business(22模块)」**精确吻合**：BusinessCommon/Sales/ReSales/Payment/PaymentStation/CashChanger/CashInOut/OpenCount/CloseCount/Discount/EMoney/EntryNonCash/InputConverter/MainMenu/Member/Operator/Point/Report/RetailMedia/RJ/Tax/TranLogMaker。
- Device 模块 = **78 个** csproj（锚点「Device(80+)」近似，略少）。
- DB Tables = **185**（锚点吻合）；SP = 453（锚点「434」略多，含 10_BI 子目录差异）。

---

## 四、(C) 类核查结论（通用流程/规约/工具，8 页）

- プロセス(18783358)/開発ルール(18783360)/チームルール(18783362)：draw.io/GoogleDrive 链接 + Redmine 进度规约 + C#开发规约链接（`POS4U開発ルール`）。规约类，非代码可核查，内部自洽。→ ✅（作为规约）。
- 自動化テスト(18783364)：UI/API/性能测试工具选型调研（Airtest/Appium/Selenium/pytest 等）。调研文档。→ ✅（调研）。
- ツール(18783366)：空标题桩。
- **LogicServiceテスト(EPOSEventSender)**(18783368) / **操作ログ調査(RecordFileViewer)**(18783370)：空标题桩；且 `EPOSEventSender`=0、`RecordFileViewer`=0 门店库引用。→ 🔵 辅助测试/日志工具，本代码库无对应实装。

---

## 五、精度评分与覆盖率

### 精度评级
- **(B) 类精度：高（约 A- / ~90%）**。凡有实质正文的 B 页（Level4-1 取引種別、SettingMaster、配置ファイル、POS4U/TRAN4U/MasterSync/VersionUp、LogicService 结构、Level3-2 子系统）与代码高度一致，Level4-1 的 29 取引種別 与 `TranTypes.cs` **逐名精确吻合**为最强证据。
  - 扣分项：① exe 程序名简化（MasterSync.exe/VersionUp.exe ↔ 实际 POS4U.Console.*）——⚠️非❌；② 大量 B 页为图片/外链/空标题桩（信息缺失而非错误）；③ POS4Uテーブル一覧 仅外链、未落地表清单。
- **(A) 类**：作为 POS4U 门店库核查=🔵 无对应实装（VUE+API 新系统 / JOBManager 后端案件），且其数据模型(app.tt_*/snake_case/PK自增)与 POS4U(dbo.*/PascalCase/采番) 明确不同——**须警惕误当作 POS4U 现状**。
- **(C) 类**：规约/调研类，自洽；两个工具页为空且工具不在门店库。

### 覆盖率（诚实申报）
- 全部 **147/147** 页已按结构完成 A/B/C 分类。
- **详读正文并做代码交叉验证：约 37 页**（B 类实质页几乎全查 + C 类 7 页 + A 类抽样 6 页）。
- B 类实质正文页基本全查；B 类中的空桩/图链页（约 20+ 页）已确认「无正文可逐条核查」，并旁证其所指系统在代码存在。
- A 类 90 页：详查 6 页代表页（涵盖两案件的技术栈/DB/API 关键声明），其余按同性质归纳；未逐页展开（TO-BE 无实装，性价比低）。

### 最该补强处
1. **exe 命名对齐**：Level3-1/Launcher 用「MasterSync.exe/VersionUp.exe」的口语名，代码实际是 `POS4U.Console.MasterSync/VersionUp`。建议在 wiki 标注真实 AssemblyName，避免检索断链。
2. **POS4Uテーブル一覧 落地**：目前仅 GoogleDrive 外链；DB 已有 185 张 dbo 表，建议镜像实际表清单（至少代表表名）以便核查。
3. **大量空标题桩补正文**：Level6-1 全部子页(CRM/ISM/売上フラッシュ/現金管理/緊急売変等)、DBConnectTool/DataUpdate4Replace/IMEChange/Sleep、ツール、两个工具页均为空——建议补最小说明或标注「设计见外部」。
4. **A 类须显式标注系统归属**：301300102(VUE+API 新系统)、504130153(Hinemos/Kompira 后端作业)与 POS4U 门店 C# 库是不同工程，建议在 wiki 顶部声明，避免把「PK 自增/app.tt_* schema」误读为 POS4U 现状。
5. Device 模块数 78 与锚点「80+」有出入，非文档错误，属锚点近似——记录备查。
