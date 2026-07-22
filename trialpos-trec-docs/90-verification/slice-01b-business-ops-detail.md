# 切片 01B 精度核查报告
## 范围：01-confluence-cloud 的 01.業務知識 / 03.品質関連 / 04.運用関連 / 05.保守関連 / 09.その他 / 99.ST-POS関連

- 核查对象根：`.../07-strategic-knowledge-base/pj-trial-pos/01-confluence-cloud/`（注意：实际路径在 07 层下，非库根直挂；INDEX.md 位于此处，第461页镜像，同步日 2026-07-07）
- 真值代码库：`../trialpos-snapshots/pos-store-ver202606`（POS4U 门店端）+ `.../database`
- 口径：**仅以真实 .cs/.xml/.sql/.csproj（含 file:line）为正确性证据**；未使用代码库自带 `docs/`。凡本代码库找不到实装者标注「本代码库无对应实装」；業界知識/IT用語/流通用語等**内容性质上非代码**者标注「非代码可核（内容性质使然）」。

---

## 覆盖率与页数统计（本切片）

| 分类 | 页数 | 深读页数 | 代码级核查页数 |
| --- | --- | --- | --- |
| 01.業務知識（含 parent） | 1 | 1(stub) | - |
| └ 01.業界知識 | 85 | 3 抽样 | 3(部分,硬件/条码) |
| └ 02.TRIALの業務知識 | 17 | 14(其余为空stub) | 3 |
| 03.品質関連 | 66 | 15 | 6 |
| 04.運用関連 | 20 | 9 | 1 |
| 05.保守関連 | 9 | 5 | 1 |
| 09.その他 | 25 | 4 抽样 | 1 |
| 99.ST-POS関連 | 8 | 0(仅尺寸) | 0 |
| **合计** | **231** | **~51** | **~12** |

- **全部 231 页均已取尺寸并按 INDEX 归类**；**深读约 51 页**（其余多为 14 行 frontmatter-only 空 stub 或纯外链）；**代码级逐条核查约 12 页**（即真正「能落到 POS4U 代码」的页面，已全部覆盖）。
- 结构性事实：本切片大量页面为 **14 行空 stub**（仅有 frontmatter+标题）或 **纯 Google Docs/Drive 外链**（正文托管在外部，镜像内无实体内容）→ 这类无正文者归「非代码可核」。

---

## 一、01.業務知識

### 1.1 業界知識（85 页）— 🔵 非代码可核（内容性质使然）
业界通识：POS 定义/历史、条码（JAN/EAN/UPC/ITF/QR/GS1-128/CODE39/128、チェックデジット）、キャッシュレス決済、租税（消費税/軽減税率/インボイス/免税）、特殊商品、レジ帳票、ハードウェア。均为行业百科式内容，本质非本代码库逻辑。

| 核查点 | 判定 | 证据/说明 |
| --- | --- | --- |
| POSの基本知識（2977103895）POS/POSレジ/POS端末 定义 | 🔵 | 内容准确、无与代码矛盾；纯术语科普 |
| PLUとNON-PLU（2989948974） | 🔵 | 定义正确；示例取自 スマレジ/Airレジ 等**竞品**，非 POS4U 本体 |
| ハードウェア→POS機種/その他デバイス（~18页） | 🔵(部分可核) | 通用机型规格科普；但机型名与代码实装**对应**：CT5100→`Device/Device.CT5100`、CT6100→`Device.CT6100_ModeSelf`、GLORY 200/300→`Device.CashChangerGloryRADRT200/300`、TEC SS900/950→`Device.MSRTECSS900/950`、SS-900/950 自助机型有对应 MSR/Scanner 模块。机型清单与实装设备族一致 |
| 条码チェックデジット/26桁JAN 背景 | 🔵(线索) | 与 `Business.InputConverter` 的 26桁JAN 实装呼应（见 3.x） |

### 1.2 TRIALの業務知識（17 页）— 核心可核区
多数子页为空 stub（システム全体像/システム関連図/売価反映ロジック(仅图)/商品企画parent/グループセット企画/自動割引企画/TRIALポイント(外链)/免税オペ(外链) 等无正文）。有实质正文且可核者：

| 页面 | 判定 | 核查证据（file:line） |
| --- | --- | --- |
| **ポイント計算について**（2971566360, 105L） | ✅ 一致（强） | 基本ポイント公式「対象金額×通常倍率÷基準額(切捨)」= `Business.Point/PointLogic/CalcNormalPointLogic.cs:22-49`（`SettingMasterKeys.PointNormalRate`:30、`PointBaseAmount`:33，`RoundManager.Round(...RoundToFloor, point/pointBaseAmount)`:45）。优待倍率→`CalcRankPointLogic.cs`（"優待ポイントを計算します"、`PointMasterAccessor.GetPointRankRate`）。特定/メディア倍率→`CalcSpecificPointLogic.cs`/`CalcMediaPointLogic.cs`（同键存在:27-41）。个别电子券/RM 券「(採用売単価-内税額)×倍率÷基準額×数量」、`UnitPriceForPurchase`→`CalcRMPointLogic.cs`。チャージポイント（PointType/MinMoney/PointBase）→充值实装在 `Business.EMoney/EMoneyChargeTran.cs`（`ValueCardMaxChargeAmount`:1091 默认49000、`ValueCardCreditMaxChargeAmount`:1092 默认100000、`m.ValueDeposit(...)`:735）；充值企画点由 ChargePromotion 主数据驱动。**注**：文档单行公式省略了代码中的中间「丸め区分」(PointCalcRoundType) 步骤，属简化非错误 |
| **会員制仕組みについて**（2971893912, 47L） | ⚠️ 部分/含过时 | 会員制/プリペイドカード=业务描述，与 `Business.Member`、支付类型 `ValueCard=06`(PaymentTypes.cs:41) 一致；「200円で1P」为运营参数(非代码常量)。含**历史信息**（お買い物アプリ 2023-03 终了、2018-11 ポイント→プリペイド移行、ランクアップサービス 2018-10 终了）→ 运营史实，非当前代码 |
| **売価変更**（2971795769, 33L） | 🔵(后端流程) | 描述商談/マスタメンテ/夜間JOB(5:10)/店舗プリンター(6:00) — 属基幹/Azure 侧流程，POS4U 门店端代码无此实装（门店端仅接收マスタ同期结果） |
| **緊急売変**（2971697495, 25L） | 🔵(后端IF) | 提及 緊急売変API→Azure メンテファイル(4U000001.TXT / ItemMasterMaintenance)→夜間JOB→基幹(WBMN2047)。为 Azure/基幹 侧 IF；门店端代码不含此链路，本代码库无对应实装（属云侧/开发关连切片） |
| **M&M企画**（3182002324, 34L） | ⚠️ 部分 | 企画类型 M&M/セット 与代码 `Business.Discount`/商品企画 IF（WBMN6205/6206/6214/6222）呼应；正文以图为主，正文文字少 |

---

## 二、03.品質関連（66 页）

多数为**测试流程/方法论/内部规约**（🔵 非代码可核，内容性质为过程文档）：テストプロセス、テスト知識(ISTQB/機能テスト/正常系異常系)、自動化テスト(Pytest+Airtest+Allure、事前調査)、開発＆品質プロセス(Redmine/ブランチ/課題/実機検証ルール 302L/実機運用ルール 73L 等)。这些为团队 QA 过程规约，非 POS4U 逻辑，且不与代码矛盾。

**能落到代码的质量页（已逐条核查）：**

| 页面 | 判定 | 核查证据（file:line） |
| --- | --- | --- |
| **保留機能**（3237183489, 支付类型码表） | ⚠️ 大部一致，3项无实装 | `Common/Common.Const/PaymentTypes.cs`：現金Cash=01(:16)、クレジットCredit=02(:21)、電子マネーECash=03(:26)、券類ExchangeTicket=04(:31)、ポイントPoint=05(:36)、バリューカードValueCard=06(:41)、掛計AccountsReceivable=07(:46)、Point/ValueCardPaymentStation=08/09、お試し引換券TrialCoupon=10(:61)、現金手入力CashInput=11(:91)、クレジットLAN=12(:96)、デビットDebit=20(:66)、デビットLAN=21(:71)、銀聯LAN UnionPayLAN=23(:76)、OfflineCredit=24、ビール券BeerTicketBarCode=31(:81)、PayPay=50(:106)、楽天RakutenPay=51(:111)、d払いDocomo=52(:116)、アリペイAlipay=53(:121)、ウィーチャットWeChatPay=54(:126) — **全部逐码吻合**。文档中「ダンゴ=13」「券類(バーコード)=30」「テナント売掛=41」**在 PaymentTypes.cs 中无对应**→本代码库无对应实装（可能已废弃或它处定义） |
| **会員関連**（3236659297） | ✅ 一致 | スキャン方式：会員/MSR/OTB。OTB(OneTimeBarcode)→`CustomerIDInputTypes.cs:26`(值="3")、`EventCodes.cs:1255` Member_MemberOneTimeBarcodeScan=418、`Business.Member/MemberObject.cs`、`InputConverter/OneTimeBarcodeConvertUtility.cs`。会员状态(無効/退会/停止/切替/ランク/オフライン)与 Member 模块一致 |
| **レジランプチェック**（3015049263） | ✅ 一致 | `Device/Device.LaneLight/LaneLight.cs:154-174` 有 青点灯/黄点灯/赤点灯/赤点滅 分支，与文档 SS900 列（青点灯=正常、黄=ニアエンプティ、赤/赤点滅=异常）语义一致 |
| **レシートチェック**（3010625581, 42种帳票） | ✅ 一致 | `Common/Common.Const/TranLogTypes.cs`：通常領収書発行(:85)、練習モード領収書(:90)、釣銭機補充(:180)/補充ドロア(:185)/両替(:200)、中間取引保存レポート(:240)、精算レポート(:245)、売上フラッシュレポート(:250)、簡易精算レポート(:305)、CAFISArchLAN 銀聯各种(:285-361)。清单帳票在代码枚举中可对应 |
| **領収書発行のチェック**（3011281013） | ✅ 一致 | 「トレーニングの売上レシート不可发行」= 代码区分 通常領収書発行 vs 練習モード領収書発行(TranLogTypes.cs:85/90)；发行规则(当日/1ヶ月/已发行)符合 Report/領収書 逻辑 |
| **バージョンアップ・マスター同期のチェック**（3086418503, 141L） | ⚠️ 部分可核 | `SettingWinPOS.xml` 存在(`POS4U/Settings/SettingWinPOS.xml`)、`ModuleVersion` 键存在(`POS4U/App.config`)；路径 `C:\POS4UGO\Work\...` 为运行时目录，代码库中未见硬编码该绝对路径字符串→路径细节本代码库无法直接核实（属运行环境约定） |
| **デバイスのチェック**（2971533357） | 🔵(通用) | レジ/プリンター/スキャナー/カードリーダー/ドロア/NW/電源 通用检查表；对应设备族在 `Device.*` 存在，但内容为通用测试清单 |
| **法令遵守・税制対応**（2971533377） | ✅(概念) | 消費税10%/8% 与 `Business.Tax` 内外税实装一致（税区分/軽減税率有实装）；法令遵守条目为通用 |

---

## 三、04.運用関連（20 页）

绝大多数为 **14 行空 stub 或纯 Google Drive/Docs 外链**（クレジット運用/商品登録/通過点数UP/釣り銭機トラブル/会計機/取引中止保留/販売制限商品/現金管理/返品運用/自社Pos設置マニュアル/展開状況 等正文托管在外部）→ 🔵 非代码可核（内容在镜像外）。

| 页面 | 判定 | 说明 |
| --- | --- | --- |
| 全店展開状況/クレジット運用/商品登録/通過点数UP/釣り銭機トラブル/端末各种 | 🔵 | 均为外部 Drive/Sheets 链接，镜像内无正文 |
| 釣り銭機トラブル/現金管理（业务）| 🔵(呼应) | 概念与 `Business.CashChanger`/`Business.CashInOut`/`Device.CashChanger*` 呼应，但页面无正文可逐条核 |

---

## 四、05.保守関連（9 页）

| 页面 | 判定 | 核查证据 |
| --- | --- | --- |
| **新店追加手順（運用監視ツール）**（3025928239, 46L） | ✅ 一致（强） | 页列 21 张复制主数据表，**全部**在 `database/01_Tables` 存在：AreaMaster / CashChangerCheckMaster / CashDenominationMaster / DiscountAutoItemMaster / EmployeeRoleMaster / FunctionMenuMaster / FunctionMenuButtonMaster / MDHierarchyLevelMaster / OperationLimitMaster / PaymentMaster / PaymentTicketBarCodeMaster / PaymentTicketMaster / SettingMaster / PointRankMaster / ReasonMaster / ReceiptMessageMaster / NonBarcodeOtherItemMaster / PresetMenuMaster / PresetMenuButtonMaster / NonBarcodeOtherItemCategoryMaster / ItemImageMaster（21/21 命中） |
| **スキャナー初期設定**（2987688023, 29L） | 🔵(设备配置) | UPC/EAN/CD/2度読み防止/書籍JAN2段 等扫描器硬件参数；属设备侧固件配置，非 POS4U 代码；与 `Device.*Scanner` 存在呼应 |
| **端末初期設定**（2975596551, 56L） | 🔵(外链) | 各机型(クレジット端末/釣銭機/SS900/SS950/HS-580/M8750/Posiflex)配置手顺，正文为 Google Slides 外链；机型均有 `Device.*` 对应实装 |
| **インシデント調査**（4124672014, 32L） | 🔵(工具) | 操作ログ確認Tool(RecordFileViewer)；与 イベント管理(Event定义) 关联，工具本体在外部 Drive |
| 改装/閉店/初期設定(parent) | stub | 空 stub |

---

## 五、09.その他（25 页）— 🔵 为主

| 页面 | 判定 | 说明 |
| --- | --- | --- |
| C#について/.NET TLS1.1-1.2/.NET版本对应表 | 🔵(相关) | .NET 通识；代码库 `TargetFrameworkVersion=v4.0`（POS4U.csproj 确认）→ 版本表内容与本代码库实际使用的 .NET Framework 相关且无矛盾 |
| IT用語/オブジェクト指向/コネクタ形状/クレジット決済(ChatGPT)/UML/デザインパターン(Observer/State)/命名指南/要件定義/非機能要件 | 🔵 | 通用技术学习资料。注：Observer/State 模式确与代码库「オブザバー体系」「取引State」实装呼应，但页面本身为通用教程 |
| **ソース改善ポイントまとめ**（3155788106） | 🔵(外链) | 唯一潜在代码相关页，但正文=Google Sheets 外链，镜像内无实体内容，无法逐条核 |
| **流通用語&業務用語→商品マスタ関連**（2977071135, 182L） | ⚠️ 部分可核 | TRIAL 专有 JAN 前缀约定(22JAN免税/24JAN割引券/25JAN生鮮NON-PLU不定貫/28JAN原材料/491雑誌/192・978・979書籍) 与条码转换实装呼应：`Business.InputConverter/BarcodeConverter/` 有 BarcodeNonPLUFoodConverter(生鮮,Substring(0,13):119)、BarcodeDynamicPricingConverter、BarcodeBestBeforeConverter、BarcodeMarkDownConverter；26桁JAN→`Utility/BestBeforeBarcodeConvertUtility.cs:14「26桁JANのFlg定義」`+消費期限チェック(:93)。**具体数字前缀多由主数据/设定驱动而非硬编码**，故判 ⚠️（业务约定层可核、转换器实装存在；数字前缀未逐一硬编码核实）。カット商品24种処分/月次半期部門変更=纯业务运营知识 🔵 |

---

## 六、99.ST-POS関連（8 页）— 🔵 全部（别系统）

STPOS-Backend / KugelPOS 环境构建（WSL2/Ubuntu 安装、Docker 安装、Kugel-STPOS 运行环境、Linux 篇构建手顺、中国国内网络环境构建）。**属新系统 ST-POS（非 POS4U 本代码库）** 的搭建指南 → 超出本 POS4U 代码库；内容为环境操作手顺，未与本代码库冲突（本就无交集）。

---

## 七、分类统计（按已判定页面，以「有实质内容或代码相关」为主计）

| 判定 | 说明 | 代表页 |
| --- | --- | --- |
| ✅ 一致 | 6 | ポイント計算(基本公式)、会員関連(OTB)、レジランプ、レシートチェック、領収書発行、新店追加手順 |
| ⚠️ 部分一致 | 5 | 保留機能(3码无实装)、会員制(含史料)、M&M企画、バージョンアップ(路径)、商品マスタ関連(JAN前缀) |
| ❌ 偏差 | 0 | 未发现与代码直接矛盾的实质性错误 |
| 🕰️ 过时 | (并入⚠️) | 会員制页含 2018/2023 已终了服务的历史描述 |
| 🔵 非代码可核 / 无对应实装 | 绝大多数 | 業界知識85 + 品质流程~50 + 运用外链~18 + その他通识~23 + STPOS 8 + 各 stub |

**代码级可核页（约12页）判定：✅6 / ⚠️5 / ❌0。** 未出现「文档说 A、代码是 B」型硬偏差；⚠️ 多为「文档更全/含历史或后端流程，门店端代码只覆盖其中一部分」。

---

## 八、精度评分与结论

- **切片精度评级：高（A-）**。凡能落到 POS4U 门店端代码的页面，内容与真实 .cs/.sql 高度吻合（支付类型码、点数公式、帳票种别、设备灯态、主数据表、OTB/26桁JAN 实装均对齐），**零硬偏差**。
- 本切片天然「代码可核比例低」：约 90% 页面为业界通识 / QA 过程规约 / 外链托管 / 空 stub / 别系统(ST-POS)，属内容性质使然的非代码可核，而非本代码库缺失。
- **最重要发现**：
  1. `保留機能` 表中 支付码 13(ダンゴ)/30(券類バーコード)/41(テナント売掛) 在当前 `PaymentTypes.cs` 无实装——需确认是废弃码还是它处(如 PaymentMaster 数据)定义；文档可能领先/落后于现行代码。
  2. 大量运用/保守页正文托管于 Google Drive/Docs 外链，镜像**未落地正文**——知识库可搜索性与长期留存有风险。
  3. `会員制仕組み` 混入 2018/2023 已终止服务的历史信息，易被误读为现行规则，建议标注「史料」。

- **最该补强处**：
  1. 把纯外链页（クレジット運用/商品登録/通過点数UP/端末初期設定/ソース改善ポイント 等）的关键正文/表格落地进镜像，避免外链失效即知识丢失；
  2. 校正 `保留機能` 支付码表与 `PaymentTypes.cs` 的差异（补注废弃/新增）；
  3. `売価変更/緊急売変` 明确标注「基幹/Azure 侧流程」，与门店端 POS4U 代码职责边界区分（当前易让读者以为门店端有该实装）。
