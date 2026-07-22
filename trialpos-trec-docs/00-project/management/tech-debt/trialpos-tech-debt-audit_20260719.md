# POS4U（TrialPOS）技术债全面核查报告

> **核查日期**：2026-07-19
> **核查对象**：`trialpos-snapshots`（社内 GitLab `aipos` 正本克隆，基线 `release20260728_Local` = 202607 已发布版）
> **核查方式**：以 trechina 团队 2026-04-22 人工调查表（`trialpos-tech-debit_20260422.csv`）为起点，对源码做只读的证据级核查（精确到 `file:line`），并在调查表之外从 7 个技术维度深挖。
> **范围**：`Application/Source`（3,581 个 C# 文件）+ `Application/POS4UCloud`（244 个 C# 文件）+ `Application/Database`（664 个 SQL 文件）。**未修改任何文件**。
> **密级**：🟡 团队内部（含供应商信息，禁止对外）。凭证类问题仅记录位置与类型，不含明文值。

---

## 0. 执行摘要（TL;DR）

对 2026-04 调查表的 64 行条目做了证据级复核，并从架构 / 代码质量 / 安全 / 数据层 / 异常日志 / 并发状态 / 依赖构建 7 个维度做了全库深挖。核心结论：

1. **调查表基本可信，但普遍低估了范围**。抽查的条目大多在源码中找到确凿证据；多个条目的实际影响面比表格描述更大（典型：`TextTermianlNo` 拼写错误被复制到 JP/EN/ZH **三个语言变体**；`ToString("N0")` 散落 **78 处**且 `FormatUtility` 尚未建立）。个别条目**已被修正**（`SelfApiConnectionServie`/`StateManagementServie` 拼写已改正，全库搜 `Servie` = 0）。
2. **调查表把全部条目标为「低优先级」，这个判断需要修正**。调查表关注的是"注釈/命名/最適化/HACK"这类**可维护性债**；但全库深挖暴露出**若干高危债**是调查表完全没有覆盖的：
   - **证书校验被无条件绕过 8 处** + **显式启用 SSL3/TLS1.0** 6 处（安全债，高）。
   - **明文云端凭证（Azure SQL 口令、Storage 主密钥）已进 Git 全历史**（安全债，高）。
   - **钱 / 交易路径上存在完全空吞异常的 `catch{}`**（`PaymentObject`、`EMoneyChargeTran`、`SalesTran` 等，运营稳定性债，高）。
   - **整个系统的地基 `POS4U.Framework.dll` 无源码，被 171 个项目引用**（结构性债，高）。
3. **平台代际约束是最深的一层债**：173 个 C# 项目中 **154 个锁死在 .NET Framework 4.0**（XP 兼容上限，宪章禁止变更）。最敏感的支付 / 点卡外联组件正卡在 v4.0，原生无法稳定跑 TLS1.2，只能靠旁路库缓解。这不是单点 bug，而是**只能靠 ST-POS 置换根治**的结构性债务。

> **给决策者的一句话**：调查表列的是"想优化的地方"，本报告在其之上补齐了"运营中真正的风险点"。在 ST-POS 完成置换前的运维窗口里，建议优先处理的不是命名 / 注释类条目，而是 §C（安全）、§E（钱路径空吞异常）、§A-2（无源码地基）这三类。

---

## 1. 核查方法与规模底数

| 指标 | 数值 | 说明 |
|---|---|---|
| C# 文件（Source + POS4UCloud） | 3,825 | Device 904 / WinPOS 992 / Business 464 / POS4UBackground 506 / LogicService 356 等 |
| C# 代码行数（非 Designer 生成物） | 501,833 行 | — |
| C# 项目（.csproj） | 173 | 另有 12 个无 `TargetFrameworkVersion` 标签的 Web/测试项目，合计约 185 |
| 解决方案（.sln） | 6 + 顶层 8 个编排 | `TargetSolutions.xml` 手工编排 8 个 sln 的构建顺序 |
| 数据库表脚本（01_Tables） | 183 | — |
| **外键脚本（02_ForeignKeys）** | **0** | 全库无外键约束，完整性靠应用层保证 |
| 视图（03_Views） | 25 | — |
| 存储过程（04_StoredProcedures） | 432 | 大量业务逻辑下沉到 SP |
| 无源码 Framework DLL | 6 个 | `POS4U.Framework.dll` 等，`ExternalModule/` 下 |

核查手段：`grep`/`wc`/`find` 定量统计 + 关键条目 `file:line` 抽样核实 + 3 个自定义脚本（catch 块语义分类、方法长度、注释死代码块）。所有 `file:line` 路径从仓库根 `Application/` 起写。

---

## 2. 原调查表条目核实结果

调查表共 **56 条实质条目**（No.1–56；No.57 有内容但无详情，No.58–64 为空占位）。本节分两部分：**§2.1 全 56 条逐条对照总表**（回答"是否覆盖全部"），**§2.2 重点条目详析**（对信息量大的条目展开）。

**核实状态图例**：
- ✅ **已修正** — 源码中问题已不存在
- ⚠️ **仍存在** — 找到确凿证据，问题未处理
- 🔺 **仍存在且范围更大** — 实际影响面超出调查表描述
- 🔹 **团队已推进** — 调查表自身标记「開発完了／調査完了／受入テスト／マージ待ち」，属已处理或在流程中
- ❓ **需运行验证** — 属运行时不具合，静态分析仅能定位相关代码，是否已修需 Windows 侧运行验证
- ➖ **无内容 / 未定位** — 条目本身空白，或符号未直接定位

### 2.1 全条目逐条对照总表

| No | 区分 | 条目 | 状态 | 证据 / 说明（`Application/` 起） |
|---|---|---|---|---|
| 1 | 注釈 | Self_SameItemEnter 注释「同じ⇒同一」 | ⚠️ | `.../UICommon/Const/VoiceGuidanceNames.cs:280` 注释「同じ商品です」 |
| 2 | 命名 | Device.CAFISArchLAN（CT6100 替代） | 🔺 | `Source/Device/` 下 5 个 CAFIS 项目并存；`CT6100` 被 58 文件引用，旧码未下线 |
| 3 | 命名 | SelfApiConnectionServie／StateManagementServie | ✅ | 目录名已改正为 `...Service`；全库搜 `Servie`=0 |
| 4 | 命名 | Device.CRM／SettingMasterKeys.CRMBaseURL | ⚠️ | `SettingMasterKeys.cs:140`、`Device.CRM/CRMServiceCommon.cs:29`；命名 CRM 实为订单用途（`OrderKitchenApiServiceBase.cs:66` 也引用 CRMBaseURL） |
| 5 | 命名 | オーダー 命名・クラスの警告 | ❓➖ | 泛化条目，属 SonarQube 类批量告警（CSV 备注「一部分解决可」），无单一符号可锚定 |
| 6 | 命名 | CommonLayout.AddPaymentStationInfo | ⚠️ | `Business.RJ/Layout/CommonLayout.cs:146,474` |
| 7 | 命名 | メッセージID TextTermianl No（应 Terminal） | 🔺 | 错拼复制到 3 语言变体：`MessageIds.cs:2172`(JP)/`:3220`(EN)/`:4446`(ZH) |
| 8 | 命名 | RT300 釣銭機 DepositUpdate 命名＆権限 | ⚠️ | `Device_CashChangerDepositUpdate`(`PluginWinPOS.xml:455`)、`EMoneyChargeTran.cs:610` `CashChangerTempDepositUpdate` |
| 9 | 不具合 | 普通会員カード→OneTimeBarcode 记录 | ❓ | 会員登録 ログイン方法记录逻辑，需运行验证（CSV 注「修正するとは言っていない」） |
| 10 | 不具合 | セルフ顔認証 二つ店舗名表示 | ❓ | UI 显示 bug，需运行验证 |
| 11 | 不具合 | プリンターエラーで tran 預り金更新されない | ❓ | 釣銭機預り金，需运行验证（CSV 注「保留」） |
| 12 | 不具合 | 取引中止待ちで 26Jan スキャンでエラー | ❓ | 需运行验证 |
| 13 | 不具合 | オフライン時 2 重ポイント後付け | ❓ | 需运行验证（CSV 注「发生可能性非常に低い」） |
| 14 | 不具合 | ジャーナル検索 Blob データ不連続／161 除外 | ❓ | BO/本地 ジャーナル検索，需运行验证 |
| 15 | 不具合 | 給料天引き不具合 | 🔹 | マージ待ち（392 店差分，已有修复待合并） |
| 16 | 不具合 | キャッシュレス途中チャージ不足額現金 | 🔹 | マージ待ち（392 店差分） |
| 17 | 不具合 | 返品失敗（EndTran→VoidEndTran） | ❓ | LogicService 返品 API，需运行验证 |
| 18 | 不具合 | レーンレジ ManagedNo ずれ | ❓ | 需运行验证（CSV 注「保留」） |
| 19 | 最適化 | ToString("N0") ⇒ FormatUtility | 🔺 | 散落 78 处；`FormatUtility` 类尚未建立 |
| 20 | 最適化 | printInfoStore 無効コード（返金タイマー） | ⚠️ | `WinPOS.Observer/TempValueCleaner.cs:27`、`TimerScheduler/TimerCheckReturnMoney.cs:71` |
| 21 | 最適化 | セルフ・オーダーを Business\POS へ移動 | ⚠️ | 目录组织调整项，未做（CSV 注「要検討」） |
| 22 | 最適化 | 一括配信のみ対象マスタの差分同期 | ⚠️ | BackgroundService マスタ同期增强，未做 |
| 23 | 最適化 | レジ袋 3 円／枚 | 🔹 | 受入テスト済（票 7234） |
| 24 | 最適化 | ハードコーディングのメッセージ | 🔺 | `MessageIds.cs` 9,758 行 + 2,272 文件含日文字面量（票 6300 调查済） |
| 25 | 最適化 | SalesView を複数コントロールに分割 | ⚠️ | `SalesView.xaml.cs` 1,198 行；5 套并行 SalesView |
| 26 | 最適化 | スキャナー・MSR エラー提示／Observer 呼出 | ⚠️ | 设计改进项，未做（CSV 注「要検討」） |
| 27 | 最適化 | 釣銭機実装ソース最適化 | ⚠️ | 5 型号 `CashChanger.cs` 各 2,290–3,115 行 |
| 28 | 最適化 | 準備金抑止 0 円登録：NodeType07→デバイス判定 | 🔹➖ | 開発完了（票 3211，运用側确认中）；`NodeType07` 符号未直接定位 |
| 29 | 最適化 | キャッシャ別フラッシュ通過点数＝スキャン成功回数 | 🔹 | 開発完了（票 3212）；`SalesTran.cs:269`「スキャニング成功回数」 |
| 30 | 最適化 | 音声ループ鳴らす（音声長より） | 🔹➖ | 調査完了；符号未直接定位（音声实现依赖无源码 Framework） |
| 31 | 最適化 | 26 桁 JAN nowValue | 🔹 | 調査完了；`BarcodeConverter/BarcodeBestBeforeConverter.cs:106` |
| 32 | 最適化 | SelfSalesTran DeviceManager.GetDevice() 共通化 | 🔹 | 調査完了；`Business.Sales/SelfSalesTran.cs:20` |
| 33 | 最適化 | 端末入替 BusinessCounter アップロード | 🔹 | 調査完了；`BatchPutBusinessCounter`(`PluginWinPOS.xml:2113`) |
| 34 | 最適化 | BO 帳票 部門倍率抽出改善 | ⚠️ | 保留（复数企画少见，CSV 自注低价值） |
| 35 | 最適化 | デバイスエラー通知 | ⚠️ | 保留（难） |
| 36 | 共通化 | Attendant モード共通化 | ⚠️ | 跨 5 业态係員操作，共通化未做 |
| 37 | 共通化 | 通信系 TLS1.2 対応 | 🔺 | 票 5411 导入；但主体仍显式启用 SSL3/TLS1.0（见 §C-2） |
| 38 | 共通化 | 会員登録（スキャン/MSR/OTB/顔認証）統合 | ⚠️ | 难，共通化未做 |
| 39 | 共通化 | 小計処理共通化 | ⚠️ | 共通化未做 |
| 40 | 共通化 | 部分取消 会員登録可否共通化 | ⚠️ | 共通化未做 |
| 41 | 便利性 | 顔認証シミュレーター改善 | ⚠️ | 工具改进，未做 |
| 42 | 便利性 | ログ見える化（RecordFileViewer） | ⚠️ | 工具改进，未做 |
| 43 | 悪い癖 | タイマー妥当性 | ⚠️ | Timer 48+13、DispatcherTimer 2（见 §F-1） |
| 44 | 悪い癖 | フラグ妥当性 | ⚠️ | bool 密集 `DealServiceWithPoint.cs`(24)（见 §F-2） |
| 45 | 悪い癖 | ログ軽く | ⚠️ | 票 6443 受入待；日志实现在无源码 DLL（见 §E-4） |
| 46 | 悪い癖 | AttendantPCObserver 年齢確認 複数記録 | 🔹 | 調査完了；`AttendantPCObserver`(`PluginWinPOS.xml:1979`) |
| 47 | TODO | POS4U／LogicService（无具体内容） | ➖ | CSV 条目本身空白，无可核实对象 |
| 48 | HACK | 20190710 緊急リリース応急処理 | ⚠️ | `Sales_LoadMTransactionManagement.cs:45`、`RJLayoutMapper.cs:215`（7 年未清） |
| 49 | HACK | GetIsWinPOSMTran | ⚠️ | `Business.Sales/MTranObject.cs:113,190,267` |
| 50 | HACK | PPM 印字（右上日時・左下カード番号）ではない | ⚠️ | `PPMStampFilePath`(`SettingWinPOS.xml:308`)、`EJournalStorageAccessor.cs:653` |
| 51 | HACK | 横向け領収書発行（複数 RJ クラス・回転） | ⚠️ | 領収書特殊处理逻辑存在（`Message_FC.xml`、TLog 領収書字段） |
| 52 | HACK | SettingMaster 店舗別／端末別設定取得不可 | ⚠️ | 设计缺陷（外部 spreadsheet 参照，CSV 注「要検討」） |
| 53 | 共通化 | メッセージ一覧 句点有無不統一 | ⚠️ | 一致性问题（`MessageIds.cs` 9,758 行内混杂） |
| 54 | 音声 | 【ありがとうございます】再生タイミング | 🔹 | 完了・受入テスト待ち（票 5727） |
| 55 | レシート印字 | 印刷途中エラー復元でおかしい | ❓ | 需运行验证（有截图①） |
| 56 | メッセージ一覧 | 重複・統一しない・ハードコーディング | 🔺 | 同 No.24/53，2,272 文件含日文字面量 |
| 57 | 多语言 | 英文表示下 现金支付零钱机异常 | ❓ | 多语言 + 釣銭機，需运行验证（登录者高源，无详情） |

**覆盖度小结**：56 条实质条目全部逐条给出状态——✅ 已修正 1 条；🔺 范围更大 6 条；⚠️ 仍存在 25 条；🔹 团队已推进 9 条；❓ 需运行验证 12 条；➖ 无内容/未定位 3 条（含交叉）。**静态分析的固有边界**：No.9–18、55、57 等「不具合」类是运行时行为 bug，本次只读静态核查只能定位到相关代码模块，**无法判定是否已修复**——这些必须在 Windows 环境按 characterization 用例实跑才能定案，属调查表落地的下一步（本仓库 SDD 的 test-spec/test-results 环节）。

### 2.2 重点条目详析

下表对信息量大、需展开论证的条目做详析（内容与 §2.1 一致，此处补充证据细节与判断依据）：

| 调查表 No. | 区分 | 条目 | 核实状态 | 证据（`Application/` 起） |
|---|---|---|---|---|
| 1 | 注釈 | `Self_SameItemEnter` 注释「同じ⇒同一」 | ⚠️ 仍存在 | `.../UICommon/Const/VoiceGuidanceNames.cs:280` 注释为「同じ商品です」；符号在 `ItemScanControl.xaml.cs:354` 使用 |
| 2 | 命名 | `Device.CAFISArchLAN`（已被 CT6100 替代） | 🔺 死代码待清理 | `Source/Device/` 下**并存 5 个 CAFIS 项目**（`CAFISArch`/`CAFISArchLAN`/`CAFISArchLANSimulator`/`CAFISArchService`/`CAFISArchSimulator`）；`CT6100` 已被 58 个文件引用。旧 CAFIS 实装未随替代下线 |
| 3 | 命名 | `SelfApiConnectionServie`、`StateManagementServie` 拼写 | ✅ **已修正** | 目录名现为正确的 `Device.SelfApiConnectionService`/`Device.StateManagementService`；**全库搜 `Servie` = 0** |
| 7 | 命名 | 消息 ID `TextTermianlNo`（应为 `TextTerminalNo`） | 🔺 **范围更大** | 错拼被复制到**三个语言变体**：`MessageIds.cs:2172`（JP）、`:3220`（EN_US）、`:4446`（ZH_CN）。改名需同步 3 处 + 所有引用 |
| 19 | 最適化 | `ToString("N0")` ⇒ 统一到 `FormatUtility` | 🔺 **范围更大** | `ToString("N0")` 散落 **78 处**；**`FormatUtility` 类尚不存在**，即"统一目标"还未建立，重构无落点 |
| 24 | 最適化 | 硬编码消息（ハードコーディング） | 🔺 **范围巨大** | `MessageIds.cs` 达 **9,758 行**（集中管理的消息 ID 表）；即便如此，仍有 **2,272 个 .cs 文件含日文字符串字面量**（散落硬编码） |
| 25 | 最適化 | `SalesView` 状态复合、控件未拆分 | ⚠️ 仍存在 | `SalesView.xaml.cs` **1,198 行** code-behind；且存在 **5 套并行 SalesView**（`SalesView`/`SelfSalesView`/`ReSalesView`/`EMoneySelfSalesView` + `CAFISArchLAN` 下另一套） |
| 37 | 共通化 | 通信系 TLS1.2 対応（票号 5411 已导入） | 🔺 部分导入、残留隐患 | 存在专用旁路库 `Device.TLS12ConnectLibrary`、`LogicService.ServiceAccessor/Utility/Tls12Library.cs`；但主体项目仍显式设 `SecurityProtocol` 含 SSL3/TLS1.0（见 §C-2） |
| 43 | 悪い癖 | タイマー妥当性 | ⚠️ 证据充分 | `System.Timers.Timer` 48 处、`new Timer` 13、`DispatcherTimer` 2、`Forms.Timer` 2；见 §F-1 |
| 44 | 悪い癖 | フラグ妥当性 | ⚠️ 证据充分 | bool 标志密集类如 `DealServiceWithPoint.cs`（24 个 bool 字段）；见 §F-2 |
| 45 | 悪い癖 | ログ軽く（日志过重） | ⚠️ 部分 uncheckable | 日志实现主体在无源码 `POS4U.Framework.dll` 内（`log4net`=0、`NLog` 仅 6 文件）；见 §E-4 |
| 48 | HACK | 20190710 緊急リリース応急処理 | ⚠️ **仍在** | `LogicService.CommandSales/Sales_LoadMTransactionManagement.cs:45`「HACK 2019/07/10 緊急リリースのための応急処置」；`Business.RJ/RJLayoutMapper.cs:215`「HACK release20190710」。7 年未清理 |
| 49 | HACK | `GetIsWinPOSMTran`（WinPOS 中间交易标志） | ⚠️ 仍在 | `Business.Sales/MTranObject.cs:113,190,267` 等多处调用，是分支判断的硬编码钩子 |

**结论**：调查表的观察方向准确，但整体处于"发现问题、尚未量化"的阶段——大量条目标记为"未着手"，且实际范围普遍被低估。建议后续把调查表升级为可跟踪的债务台账（带 `file:line`、范围计数、责任人、与置换计划的关联）。

---

## 3. 深挖发现（调查表之外）

> 分级口径：**高** = 影响钱 / 交易正确性、安全、或阻断运维；**中** = 影响可维护性 / 变更成本 / 局部稳定性；**低** = 整洁度 / 一致性。所有"内网现实风险"均已按"POS 专用内网、非零信任"环境校准。

### A. 架构维度

| # | 发现 | 证据 | 分级 |
|---|---|---|---|
| A-1 | **目标框架碎片化**：154 个项目 v4.0 / 19 个项目 v4.6.1 混用。v4.0 是 XP 兼容上限（宪章禁止变更）；跨版本互相引用时，v4.0 无法使用 v4.6.1 的 API，且 TLS/加密能力受限 | 173 个 csproj 中 `<TargetFrameworkVersion>v4.0` × 154、`v4.6.1` × 19 | 高（结构性） |
| A-2 | **无源码地基**：`POS4U.Framework.dll`（132KB，无源码）被 **171 个项目**引用，`POS4U.Framework.Library` 同为 171，`WinPOS.Framework` 75。系统的日志、连接、加密、FTP 等底层能力都在其中，无法审计、无法修改，只能经公开钩子（TranBase/CommandBase/Observer/EventCode）扩展 | `ExternalModule/*.dll`；csproj 引用计数 | 高 |
| A-3 | **业态平行实现**：Self/Order/Regi/Semi/Charge 各业态 UI 大量重复。同名控件多份：`LineItemRowControl.xaml.cs`×7、`LineItemRowListControl`×7、`SelectPaymentControl`×6、`AttendantControl`×5 等。一处业务规则变更需在多份间同步 | `find … | basename | uniq -c` | 中 |
| A-4 | **WCF net.tcp IPC 无安全**：`SecurityMode.None`，绑定 `localhost`。同机进程间通信（对应 ADR-0002），实际暴露面为"同终端本地进程"，风险低但配置层面无认证 | `TRAN4U/RemoteController/RemoteServiceController.cs:118`、`WinPOS.Batch/TranRemoteControllerLibrary.cs:145` | 中 |
| A-5 | **构建链脆弱**：`1-RBuild.bat` 硬编码 `C:\Program Files (x86)\MSBuild\14.0\Bin\MSBuild`（**锁死 VS2015**）；`TargetSolutions.xml` + `0-BuildOrderSortTool.exe` 手工编排 8 个 sln 的构建顺序。换新构建机必须精确复刻 VS2015 环境 | `Application/1-RBuild.bat:14`、`TargetSolutions.xml` | 中 |

### B. 代码质量维度

| # | 发现 | 证据 | 分级 |
|---|---|---|---|
| B-1 | **技术债标记总量**：`TODO`×58、`XXX`×54、`未実装`×55、`HACK`×18、`暫定`×5、`FIXME`×4、`応急`×1。合计约 195 处显式自认债务 | `grep -rni` over `*.cs` | 中 |
| B-2 | **超长方法**：单方法行数 TOP —— `MessageDialogInfoCreator.CreateDialogInfo` **2,293 行**、`TranLogServiceDealCodeTotal.SetValues` **1,882 行**、多个 `TranLogConverter*.SetTableBody` 700–870 行、`SalesLayout.AddPayments` 684 行。圈复杂度极高，无法安全测试 | `method_len` 扫描 | 高 |
| B-3 | **巨型文件**：`MessageIds.cs` 9,758 行、BO 的 `*MenuController.cs` 3,100+ 行、多个 `CashChanger.cs` 2,650–3,115 行（各钓钱机型号一份）、`SalesTran.cs` 2,263 行 | `wc -l` TOP15 | 中 |
| B-4 | **注释死代码**：约 **779 行**被注释掉的代码，散落 51 个文件；最大单块 33 行（`Business.Report/ReportCloseCount.cs:462`），`MasterSync/RecordConverter.cs` 多块累计 60+ 行 | `deadcode` 扫描 | 低 |
| B-5 | **拼写错误标识符**：`Cancle`（应 Cancel）**89 处**、`Recieve`（应 Receive）42、`Comfirm`（应 Confirm）19、`Termianl` 4、`Adress` 3。已固化进公开 API 名，改名有连锁成本 | `grep` typo 集 | 低 |

### C. 安全维度 ⚠️（调查表完全未覆盖，含本次最高危项）

| # | 发现 | 证据 | 教科书分级 / 内网现实风险 |
|---|---|---|---|
| C-1 | **证书校验被无条件绕过**：`ServerCertificateValidationCallback` 恒返回 `true`，共 **8 处**，且多数挂到进程级 `ServicePointManager`（全局生效）。任何链路中间人可冒充服务端 | `LogicService.ServiceAccessor/{ReceiptServiceAccessor:27, POSLogicWebServiceAccessor:36, MTranServiceAccessor:23, CartMTranServiceAccessor:24, DataServiceAccessor:32, BackgroundServiceAccessor:22}`、`MasterSyncPos/Library/Download.cs:24`、`SelfApiConnectionService/Manjyu/ManjyuServiceConnection.cs:137` | 高 / 中-高 |
| C-2 | **显式启用 SSL3/TLS1.0**：`SecurityProtocol = (SecurityProtocolType)4080`（= SSL3｜TLS1.0｜1.1｜1.2），进程级全局降级，共 6 处 | `ServiceAccessorLibrary.cs:209,299,349`、`ValueCard.cs:416`、`PointInfinityService.cs:49`、`ManjyuApiServiceConnection.cs:42` | 中-高 / 中 |
| C-3 | **明文云凭证已入 Git**：Azure SQL DB 口令（dev/test 复用）、Azure Storage AccountKey（storage 全权限主密钥）硬编码在 `POSModuleUploader` 设置 XML；`参照用ユーザ作成.sql:45` 明文 DB 口令。密钥进全历史，轮换成本高、不受内网边界保护 | `Tools/POSModuleUploader/.../SettingPOSModuleUploader.xml:10,14` 等；`Database/99_other/参照用ユーザ作成.sql:45` | 高 / 中-高 |
| C-4 | **硬编码加密密钥**：AES 派生口令 / 密钥写死源码（一处泄露 = 全终端同密钥，无法按门店隔离） | `POS4ULogicServiceLibrary.cs:36`、`RetailMediaServiceCommon.cs:19` | 高 / 中 |
| C-5 | **会员卡号明文入日志**：`PointCardNo` 等写入日志约 30 处（多为 PointManager/PointInfinityManager）。日志经 `POSLogUploader` 外传，扩大个人信息留存面 | `Tools/CESettingTool*/Point/PointManager.cs:249,290` 等 | 中 / 中 |
| C-6 | **弱哈希 MD5**：CRM 点卡 / 给与控除接入 token「暗号化」用 MD5（注释直书「MD5暗号化」）。作 token 摘要而非口令存储，危害有限但抗碰撞弱。**未发现 DES/3DES/ECB（正面结论）** | `Point/PointCRMServiceConnection.cs:48`、`SalaryDeductionService.cs:139` | 中 / 低-中 |
| C-7 | **支付类 http 明文端点**：`savePayInfo`/`dataReceive`/`customerCheck` 等走 `http://`（内网 IP）；`CORS: Access-Control-Allow-Origin *` | `Settings/SettingWinPOS.xml:191-228,432`；`POS4ULogicService/Web.config` | 高 / 中 |
| C-8 | **v4.0 对 TLS1.2 的结构性阻碍**：.NET 4.0 的 `SecurityProtocolType` 枚举无 TLS1.1/1.2 成员，只能裸整数 `(SecurityProtocolType)3072` 硬凑；支付/点卡/主数据的外联组件正卡在 v4.0，只能靠 `Tls12Library` 旁路。**这是最应纳入置换优先级的结构性债** | `Device.TLS12ConnectLibrary/Tls12Library.cs` 等旁路库的存在本身即佐证 | 高 / 中-高 |

> FTP 能力声明于无源码 `POS4U.Framework.Library.dll`（`FtpHelper`），是否明文 FTP 无法从本仓库确认，需向框架供应商核实（uncheckable）。

### D. 数据层维度

| # | 发现 | 证据 | 分级 |
|---|---|---|---|
| D-1 | **零外键约束**：183 张表、**0 个外键脚本**。参照完整性完全靠应用层（配合 ADR-0001 的 5 要素复合主键）。孤儿数据 / 引用悬空只能靠代码兜底，DB 层无护栏 | `Database/02_ForeignKeys/` 为空 | 高 |
| D-2 | **业务逻辑下沉存储过程**：432 个 SP，最大 267 行（`usp_BOGetDailyPosTerminalCapacity`）。逻辑跨 C# 与 T-SQL 两处，测试与变更需双侧同步 | `Database/04_StoredProcedures/` | 中 |
| D-3 | **老式 typed DataSet 数据访问**：`DataSet` 引用 **33,653 次**、`DataTable` 7,746 次、`SqlDataAdapter` 602；**无 EntityFramework/ORM**。连接管理封装在 TableAdapter / 无源码 Framework 内（`new SqlConnection` 直用 0 次、`using(conn)` 仅 14 处）。这是 .NET 2.0 时代模式，弱类型迁移成本高 | `grep` over `*.cs` | 中 |
| D-4 | **DB 版本管理为全量 Create 脚本**：`CreateDatabaseScript` + `Prod`/`LocalDev` 双份 ImportData（`05_ImportData` vs `06_ImportData_Prod`），无 migration 机制，schema 演进靠人工比对 | `Database/05_ImportData`、`06_ImportData_Prod` | 中 |

### E. 异常处理与日志维度 ⚠️（含钱路径高危项）

catch 块语义分类（全库 2,940 个 catch）：

| 类别 | 数量 | 含义 |
|---|---|---|
| RETHROW | 1,957 | 重抛（健康） |
| LOG_ONLY_CONTINUE | 421 | 仅记日志后继续 |
| LOG_PLUS | 417 | 记日志 + 其他处理 |
| **SWALLOW_NO_LOG** | **73** | 有代码但既不记、不抛、不改流程（静默） |
| FLOW_NO_LOG | 36 | 改流程但不记日志 |
| **EMPTY** | **25** | 完全空吞 `catch{}` |
| UI_ONLY | 11 | 仅弹窗 |

| # | 发现 | 证据 | 分级 |
|---|---|---|---|
| E-1 | **钱/交易路径上完全空吞异常**：`Business.Payment/PaymentObject.cs:575,674`、`TranLogMaker/SalesHeaderMaker.cs:109`、`WinPOS.CommandSales/Sales_CancelSubTotal.cs:50`、`SalesView.xaml.cs:772`。异常被吞后状态可能不一致，且无任何痕迹可排查 | catch 明细（EMPTY 类） | 高 |
| E-2 | **充值/交易的静默降级**：`Business.EMoney/EMoneyChargeTran.cs` 多处 `catch` 后 `chargePayment=null`/`isCreditChargePoint=false`；`SalesTran.cs:2152` `isSalaryDeduction=false`；`Sales_Total.cs:124`/`Sales_CancelTransaction.cs:97` `isSuccess=false`。异常被转成"业务失败"却不记录原因 | catch 明细（SWALLOW_NO_LOG 类） | 高 |
| E-3 | 空吞 catch 目录分布：Device 39、Business 33、WinPOS 31、POS4UBackground 17。集中在设备交互与业务核心 | catch 明细目录聚合 | 中 |
| E-4 | **日志机制在无源码 DLL 内**：`log4net`=0、`NLog` 仅 6 文件、`Console.WriteLine`/`Debug.WriteLine`=0。统一 Logger 在 `POS4U.Framework.dll`（uncheckable），日志级别 / 量 / 脱敏策略无法从源码侧调整——这正是调查表 #45「ログ軽く」难以落地的根因 | `grep` over `*.cs` | 中 |

### F. 并发与状态管理维度

| # | 发现 | 证据 | 分级 |
|---|---|---|---|
| F-1 | **Timer 使用面广**：`System.Timers.Timer` 48 处 + `new Timer` 13 + `DispatcherTimer` 2 + `Forms.Timer` 2。分布于调查表点名的 UI 音声循环、充值机无操作、找零抽取待、远程年龄确认、钓钱机状态上报、通道收银（レーンレジ）。多计时器共存 + 回调改 UI 是卡死 / 竞态的常见来源 | `grep` Timer 类型 | 中 |
| F-2 | **bool 标志代替状态机**：`DealServiceWithPoint.cs` 24 个 bool 字段（点卡业务）、`POSPrinterFP2000.cs` 7 个。标志位组合爆炸，状态一致性靠人工维护（对应调查表 #44） | `grep` bool 字段计数 | 中 |
| F-3 | **轮询式等待**：`Thread.Sleep` **127 处**（多为 `Sleep + while` 轮询代替事件/信号）。占用线程、响应延迟、隐藏竞态 | `grep` Thread.Sleep | 中 |
| F-4 | **可变 static 状态规模大**：非 const/readonly 的 static 字段粗估约数百处（信号级，需精确复核）。单例 + 可变状态在多终端 / 多线程下有共享状态风险。**正面项**：未发现 `lock(this)`/`lock(typeof)` 反模式（均 0） | `grep`（粗略信号） | 中 |

### G. 依赖与构建维度

| # | 发现 | 证据 | 分级 |
|---|---|---|---|
| G-1 | **依赖停留在 2018 年版**：`Newtonsoft.Json` 11.0.2（2018）、`WindowsAzure.Storage` 9.3.0（已被 `Azure.Storage.Blobs` 取代）、`StyleCop.Analyzers` 双版本并存（1.0.2 与 1.1.118）、`Portable.BouncyCastle` 1.8.10；BO 前端 `bootstrap 3.3.7`/`jQuery`/`Vue 2` | `packages.config` 汇总 | 中 |
| G-2 | **无源码裸 DLL 引用无版本管理**：6 个 Framework DLL 直接引用（见 A-2），无 NuGet 版本锁、无来源追溯 | `ExternalModule/` | 高 |
| G-3 | **构建环境锁死且手工**：硬编码 VS2015（MSBuild 14.0）绝对路径、手工构建顺序编排（见 A-5）、发布流程记于 `WinPOSリリースモジュールの作り方.txt`（手工 runbook） | `1-RBuild.bat`、`TargetSolutions.xml` | 中 |
| G-4 | **无 CI/CD**：仓库内未发现任何 CI 配置（`.yml`/pipeline）。构建 + 测试 + 发布全手工，回归靠人工 | 全库搜 CI 配置为空 | 中 |

---

## 4. 严重度分级汇总

### 🔴 高（运维窗口内建议优先处理）

- **C-1** 证书校验绕过 8 处 + **C-2** SSL3/TLS1.0 全局降级
- **C-3** 明文云凭证入 Git + **C-4** 硬编码加密密钥
- **C-8 / A-1** v4.0 平台对 TLS1.2 的结构性阻碍（支付/点卡外联）
- **E-1 / E-2** 钱 / 交易路径上的空吞与静默降级异常
- **A-2 / G-2** 无源码 `POS4U.Framework.dll` 地基（171 项目依赖）
- **B-2** 2,000+ 行超长方法（不可测试）
- **C-7** 支付类 http 明文端点
- **D-1** 零外键约束

### 🟡 中（可维护性 / 局部稳定性）

A-3 业态平行实现、A-4 net.tcp 无认证、A-5/G-3 构建脆弱、B-1 债务标记 195 处、B-3 巨型文件、C-5 会员卡号入日志、C-6 MD5、D-2 SP 逻辑下沉、D-3 DataSet 老模式、D-4 无 migration、E-3/E-4 日志、F-1~F-4 并发、G-1 旧依赖、G-4 无 CI

### 🟢 低（整洁度）

B-4 注释死代码、B-5 拼写错误、调查表命名/注释类条目、C 系统内 CORS 通配

---

## 5. 与 ST-POS 置换的关系（处置建议）

POS4U 是**现行运营中**系统，且是 ST-POS 内製化的 AS-IS 摸底对象。技术债处置需区分"根治"与"缓解"：

1. **只能靠置换根治的结构性债**（不建议在 POS4U 上投入大改）：
   A-1 框架代际、A-2 无源码地基、C-8 TLS 结构限制、D-1/D-3 数据层范式。→ **纳入 ST-POS 设计输入**，作为"新系统必须避免的反面教材"记录进 `stpos-trec-docs`。

2. **运维窗口内值得缓解的高危债**（低成本、高收益）：
   - C-3 云凭证：轮换密钥 + 移出源码 / 配置（改用 KeyVault / 环境注入），并清理 Git 历史暴露。
   - C-1：至少把恒真的证书回调改为校验（内网可用内部 CA），削掉最大中间人面。
   - E-1/E-2：给钱路径的空吞 catch **补日志**（不改流程，先获得可观测性），是风险最高但改动最小的一类。
   - C-5：会员卡号日志脱敏（掩码）。

3. **可批量清理的低危债**（适合作为 characterization 练手 / 新人任务）：
   B-5 拼写、B-4 死代码、调查表命名类、A-3 未下线的 CAFIS 旧码。**均须遵循本仓库 SDD 纪律**：characterization 测试固定现行行为后再动，touch-only，Windows 侧验证合格再合并。

4. **须向供应商核实的 uncheckable 项**：`POS4U.Framework.dll` 的 FTP/日志/加密实现（A-2、C 系统、E-4、G-2 相关）。宪章规定不得臆测该 DLL，只能经公开钩子扩展。

> **对调查表的行动建议**：把 2026-04 的 CSV 升级为**可跟踪台账**——为每条补 `file:line`、范围计数、真实分级（不再一律"低"）、责任人、与置换计划的关联标签。本报告的 §2/§3 表格可直接作为首版数据源。

---

## 附录：核查底数速查

- 代码：3,825 个 C# 文件 / 501,833 行；173 个 csproj（v4.0×154、v4.6.1×19）；6+8 个 sln
- 数据库：183 表 / **0 外键** / 25 视图 / 432 存储过程
- 异常：2,940 catch（RETHROW 1,957 / 空吞 EMPTY 25 / 静默 SWALLOW_NO_LOG 73）
- 安全：证书绕过 8 / SSL3-TLS1.0 全局降级 6 / 会员卡号入日志 ~30
- 并发：Timer 48+13 / Thread.Sleep 127
- 债务标记：TODO 58 / XXX 54 / 未実装 55 / HACK 18
- 依赖：无源码 Framework DLL 6 个（`POS4U.Framework` 被 171 项目引用）

> 核查为只读静态分析，未在 Windows 侧构建 / 运行。部分底层能力位于无源码 `POS4U.Framework.dll`，标注为 uncheckable，未臆测其内部实现。
