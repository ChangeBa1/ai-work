---
title: TrialPOS（POS4U）促销机制 · 分析报告
genre: analysis
audience: [POS4U 开发者, ST-POS 迁移设计者, Tech Lead, QA]
status: 已完成（全部 file:line 与种子数据对照 202607 源码亲核）
scope: POS4U（TRI-POS）现行促销/折扣引擎的 AS-IS 机制分析，供 ST-POS 内製化参照
code_baseline: trialpos-snapshots @ 202607（release20260728_Local）
module: Application/Source/Business/Business.Discount/
密级: 🟡 敏感（含未公开供应商资料，禁止对外）
source:
  - 01-trialpos-docs/30_domain/discount.md（source-anchored·verified）
  - 01-trialpos-docs/80_decisions/investigations/subtotal_discount_defect.md
  - POSSYS Confluence：値下げ種別 / 値下げ方法 / ０３：M&M / ダイナミックプライシング
  - trialpos-snapshots 源码亲核
owner: jinianxiang
created: 2026-07-16
updated: 2026-07-16
---

# TrialPOS（POS4U）促销机制分析报告

> **对象系统**：POS4U / TRI-POS（現行运用中的旧 POS，ST-POS 的置换对象）
> **代码基线**：`trialpos-snapshots` @ 202607（`release20260728_Local`）
> **锚定模块**：`Application/Source/Business/Business.Discount/`（39 个 `.cs`）
> **验证方式**：本报告全部 `file:line` 与种子数据已逐条对照真实源码复核（2026-07-16）

---

## 一、结论速览（TL;DR）

1. **一个引擎、两阶段、插件式**：POS4U 的促销不是散落的 if-else，而是一个由 `DiscountManager` 统一编排的引擎——先算**明细级折扣**、再算**小计级折扣**，加载哪些促销、按什么顺序算，完全由**主数据表 `DiscountTypeMaster` 驱动**动态装配。

2. **7 类促销有代码实现，但种子/实装存在三处错位**：代码里定义了 7 个折扣类型常量，种子 CSV 却含 10 个 code——其中 **code 3（自动小计）只有抽象基类无实现、code 4/8 有种子行却无对应类**。即"配置里能配、但引擎里根本装不上"。

3. **手动小计折扣是一条断链（两个真实 Bug）**：金额算对了却没回流到行总额（顾客白算）、落盘时必崩溃（NRE）。其中崩溃缺陷已在源码仓 SDD 分支 `001-fix-discount-maker-nre` 修复。

4. **"扫码即优惠"分两条独立路径**：一条是主数据驱动的 Mix&Match/单品自动值下げ（内存匹配），一条是 **Dynamic Pricing / 26 桁 JAN 条码**（从条码本身解析制造日期→反推年份→判鲜度与企画有效期）。

5. **案分（Apportionment）是精算核心**：小计折扣要公平摊回每个商品行，POS4U 用**向下取整 + 残差按单价降序逐项补足**，与 Mix&Match 的**四舍五入 + 可拆行**是两套完全不同的策略。

---

## 二、引擎架构：两阶段编排 + 插件式装配

核心类 `DiscountManager`（`DiscountManager.cs:19`，`sealed class : IDiscountManager`，423 行）。入口 `Calc(SalesTran)`（`:35`）执行**两阶段**：

```
Calc(tran)  [DiscountManager.cs:35]
│
├─① 明细阶段 (IsCalcDiscountLineItem)
│    ├─ ClearLineItemDetail            :49   清空上轮明细折扣
│    └─ loop DiscountLineItemLogics.Calc :65  逐个明细促销插件计算
│
└─② 小计阶段 (IsCalcDiscountSubTotal)
     ├─ GetDiscountSubTotalTarget      :74   确定小计折扣作用对象
     ├─ loop autoLogic.Calc(tran,tgt)  :82   自动小计折扣（注：无实现类）
     ├─ SortDiscountInfos              :88   把"手动小计折扣"排到最后
     └─ DividedDiscountSubTotal        :91   案分：小计折扣摊回各明细
```

**装配机制（主数据驱动）** —— `UpdateCompanyDiscountLogic`（`:264`）：

- 读 `DiscountMasterAccessor.GetDiscountTypeMasterRows(...)`，`.OrderBy(Priority).ThenBy(DiscountTypeCode)`（`:280`）。**Priority 数值越小越先算**。
- 按 `CompanyCode` 缓存装配结果。
- CSV 行的 `DiscountTypeCode` 必须与某个插件的 `DiscountType.Code` 匹配才会被实例化（`:291-300`）——**这就是 code 4/8 有种子行却不生效的根因**。
- 具体插件类注册在 `POS4ULogicService/Settings/Plugin.xml`。

> **设计要点**：促销的"启用/顺序/排他"是**配置层（主数据）的事**，不是改代码。这让门店/企业可以差异化配置促销组合，但也带来了"配置得上、代码装不上"的隐性错位风险（见第六节）。

---

## 三、七种促销类型全景

代码实测 `DiscountTypes.cs` 定义 7 个常量，`LineItem/` 6 类 + `SubTotal/` 2 类逻辑：

| Code | DiscountType 常量 | 中文/日文名 | 层级 | 实现类 | 实装状态 |
|:---:|---|---|:---:|---|:---:|
| `1` | ManualDiscountLineItem | マニュアルアイテム値引き（手动单品） | 明细 | `DiscountManualLineItemLogic` | ✅ |
| `2` | ManualDiscountSubTotal | マニュアル小計値引き（手动小计） | 小计 | `DiscountManualSubTotalLogic` | ⚠️ 有 Bug（断链） |
| `5` | DiscountMixMatch | ミックスマッチ（混合搭配） | 明细 | `DiscountMixMatchLogic` | ✅ 仅 Price/Set |
| `6` | DiscountGroupSet | グループセット（组套） | 明细 | `DiscountGroupSetLogic` | ✅ |
| `9` | DiscountMarkDown | マークダウン（降价标） | 明细 | `DiscountMarkDownLogic` | ✅ |
| `10` | DiscountAutoItem | 単品自動値下げ（单品自动） | 明细 | `DiscountAutoLineItemLogic` | ✅ |
| `11` | DiscountFanCoupon | ファン化促進クーポン（粉丝券） | 明细 | `DiscountFanCouponLogic` | ✅ 202607 起入种子 |

> 🔎 **源码彩蛋（复制粘贴 Bug）**：`DiscountTypes.cs:31` 中 `DiscountGroupSet` 的 name 参数误写成 `nameof(ManualDiscountSubTotal)`——即 code=6 的类型名字符串实际是 `"ManualDiscountSubTotal"`。Code 值（`"6"`）正确，但凡是靠 name 字符串做判断/落盘/日志的地方都可能踩坑。本次亲核新发现。

**业务侧对照（Confluence `値下げ種別` v3）**：业务文档列的 7 种与代码常量**完全一致**（1/2/5/6/9/10/11），是本库中少见的业务↔代码高度对齐模块。

---

## 四、优先级与排他机制：`DiscountTypeMaster`

表 `dbo.DiscountTypeMaster`（列：`CompanyCode`/`StoreCode`/`DiscountTypeCode`(PK)/`Description`/`Priority`/`IsSubTotalDiscountTarget`/`ExcludeTargets`）。

**种子数据实测 20 行 = 2 社（CompanyCode 1/2）× 10 种**（已 UTF-16 转码逐值核对，两社内容完全相同，下表列 CompanyCode=1）：

| Code | Description（CSV 原文） | Priority | ExcludeTargets | 说明 |
|:---:|---|:---:|:---:|---|
| `8` | マニュアル１数量値下げ | 0 | `1,4,8` | ⚠️ **有种子行，无实现类** |
| `2` | マニュアル小計値引き | 0 | `3` | 小计·手动（有 Bug） |
| `1` | マニュアルアイテム値引き | 1 | `1,4,8,9` | 手动单品 |
| `9` | マークダウン値引 | 1 | `9` | 降价标 |
| `11` | ファン推進クーポン値下げ | 1 | `11` | 粉丝券（202607 新增） |
| `3` | 自動小計値引き | 1 | `2,3` | ⚠️ **仅抽象基类，未实装** |
| `4` | 商品階層値引き | 2 | `1,4,8` | ⚠️ **有种子行，无实现类** |
| `5` | ミックスマッチ値引き | 2 | `5,6` | 混合搭配 |
| `6` | グループセット値引き | 2 | `5,6` | 组套 |
| `10` | 単品自動値下げ | 3 | `10` | 单品自动 |

**排他判定** —— `DiscountCommonLogic.IsExcludeDiscount`（明细 `:25` / 小计 `:570`）：
> 若某明细已挂了**更高优先级**的折扣，且那个折扣的 code ∈ 当前折扣的 `ExcludeTargets`，则**当前折扣不再应用**到该明细。

例：code 1（手动单品，Exclude=`1,4,8,9`）一旦生效，同行的 code 9（降价标）就会被排除；而 code 5/6（M&M/组套）互斥（彼此 Exclude=`5,6`），同一商品不能同时吃两种搭配促销。

---

## 五、折扣"方法"与 Mix&Match 三型

**折扣方法（`DiscountMethods.cs`，即"怎么减"）**——每种促销落地时选一种减法：

| Code | 方法 | 含义 |
|:---:|---|---|
| `01` | AmountOff | 值引き（直接减固定金额） |
| `02` | PercentOff | 割引（按百分比打折） |
| `03` | NewPrice | 值引後の価格指定（直接指定折后价） |

**Mix&Match 种别（`DiscountMixMatchTypes.cs`）**——注意**只实装 2 种**：

| Code | 类型 | 实装 | 说明 |
|:---:|---|:---:|---|
| `0` | Amount（值引指定） | ❌ **无分支** | `OnCalc:48` 未分派 |
| `1` | Price（价格指定） | ✅ | `CalcMixMatchTypePrice:147` |
| `3` | Set（组套販売） | ✅ | `CalcMixMatchTypeSet:264` |

> ⚠️ 业务文档 `値下げ方法` 把 M&M 种别列为 `1=Amount / 2=Price / 3=Set`，但**代码常量实为 `0=Amount / 1=Price / 3=Set`（无 "2"）**，且 Amount 无实现。业务文档此处编号与命名与代码不一致，以代码为准。

**Mix&Match 计算细节（`DiscountMixMatchLogic.cs`）**：

- **Price 型**：商品按 `MMTargetUnitPrice` 降序（`:160`）、阶梯按 `DiscountSetCount` 降序（`:164`）贪心配对；当 `targetTotalAmt <= DiscountSetPrice`（越促销越贵）不成立时 `break`（`:191`）；`IsSplitPrice` 溢出时按 `Round(DiscountSetPrice / DiscountSetCount)` 均摊（`:210`）。
- **Set 型**：`while(hasData)` 多套循环（`:281`），按 `SetQuantity` 逐组配额。
- **尾数拆行**：凑不满整组时用 `CopyUtility.DeepCopy` 把一行深拷贝拆成两个明细行（`ApplyDiscountMixMatchInfo:406`）。

**M&M 多档位（TLog `03:M&M` 文件）**：落盘结构支持 **Level 1/2/3** 三档（如"买 2 件享 A 价、买 4 件享 B 价"），每档记录对象点数/金额/成立回数/值引额。字段 20=スプリットプライス、21=値引計上。

---

## 六、代码 vs 种子：实装状态矩阵（关键风险）

这是本模块**最重要的隐性风险**——配置层（种子/主数据）与代码层不对齐：

| Code | 种子 CSV | 代码类 | 结论 |
|:---:|:---:|:---:|---|
| 1,2,5,6,9,10 | ✅ | ✅ | 正常 |
| `11`（FanCoupon） | ✅（202607 新增） | ✅ | **此前"有类无行"，202607 已对齐** |
| `3`（自動小計） | ✅ | ❌ 仅 `abstract` 基类 | **配得上，装不出** —— `DiscountAutoSubTotalLogicBase.cs:14` 无 concrete 派生 |
| `4`（商品階層） | ✅ | ❌ 无 `DiscountType` 类 | **有种子行，引擎不装配** |
| `8`（マニュアル１数量） | ✅ | ❌ 无 `DiscountType` 类 | **有种子行，引擎不装配** |

> **实际是否激活**，最终还取决于 `Plugin.xml` 注册 + 企业主数据下发。种子有行 ≠ 生效。ST-POS 迁移时若照搬种子表而不核对代码实现，会把 3 个"幽灵促销类型"一起搬过去。

---

## 七、案分（Apportionment）算法：小计折扣如何摊回明细

小计折扣是"对整单减 X 元"，但税额、积分、退货都按**行**结算，所以必须把这 X 元公平摊回每个商品行。

**`DividedDiscountSubTotal`（`DiscountCommonLogic.cs:496`）**：
1. **第一轮**：按 `TargetUnitPrice / targetAmount * discountAmount`，以 **`RoundToFloor`（向下取整）** 分摊（`:515`）——保证不会摊多。
2. **补残差**：剩下的 `restAmount` 按 `SortDividedDetails`（**单价降序 → KeyNo 升序**，`:548`）逐项以 `minDivided * Quantity` 补足，直到 `restAmount == 0`（`:522-538`）。
3. 结果写入 `LineItemDiscountData.TotalDiscountSubTotalDivided`。

> ⚠️ **订正基线**：旧业务文档称"残差全部加在价格最高的那一行"——**实为按单价降序逐项补足**（不是堆到单行）。

**两套案分策略对照**（设计上刻意不同）：

| | 小计折扣案分 | Mix&Match 案分（`DiscountDivided:438`） |
|---|---|---|
| 取整 | `RoundToFloor`（向下） | `RoundAwayFromZero`（四舍五入，`:448`） |
| 残差 | 按单价降序逐项补足 | 可拆行 |

---

## 八、触发时机与状态门控

促销**不是随时都算**，受交易状态机门控：

- **明细折扣白名单（7 态）** —— `IsCalcDiscountLineItem`（`:177`）：仅在 `CurrentState ∈ {Neutral, EnteringItem, SelectEnteringItem, Paying, ItemReference, EnteringBarCode, WaitingClearMemberCofirm}` 时计算。
- **小计折扣（仅 1 态）** —— `IsCalcDiscountSubTotal`（`:204`）：仅 `Paying` 时计算。
- **付款后锁定**：两者一旦 `PaymentObject.HasPayments == true`（`:190`/`:212`），**立即冻结不再重算**——防止找零倒挂、账务浮动。

> ⚠️ **订正基线**：旧文档 `05_discount.md` 只列 2 态、另一份报告列 4 态；**实测明细折扣白名单为 7 态**。

---

## 九、"扫码即优惠"的另一条路：Dynamic Pricing / 26 桁 JAN

与主数据驱动的 M&M 平行，POS4U 有一套**基于条码的鲜度折扣**（生鲜临期打折典型场景）：

- **条码两类**：①13 位内普通 JAN；②**26 位条码** = 13 位商品码 + 6 位制造月日時 + 6 位赏味月日時 + 1 位 C/D（Mod10 权重 3-1 校验）。
- **年份反推**：26 位条码不含年份，须结合扫描时点的"当前月"推定制造年/赏味年（4 种月份大小关系分支）。
- **鲜度门槛**：算出赏味期限后与当前比较，`当前 > 赏味期限` → 判"期限切れ"错误，拒绝折扣。
- **企画表 `DynamicPricingMaster`**：`CompanyCode`+`StoreCode`+`ItemCode`(26)+制造日 From/To + 值引开始/终了日時 + `DiscountType`（00 值引/01 割引/02 价格指定）+ `DiscountValue`。
- **判定**：普通码只比商品码+企画有效期；26 位码额外校验鲜度 + 制造日区间。满足才应用，否则原价。

---

## 十、已知缺陷：手动小计折扣的断链（两个真实 Bug）

> 这是分析 POS4U 时**从源码挖出的两个真实 Bug**（非纸面推测），使 `ManualDiscountSubTotal`（code 2）功能**有骨架无闭环**。

**缺陷 1（金额错）：`LineTotal` 漏减小计折扣分摊额**
`LineItemBase.cs:119-123`：
```csharp
return (this.UnitPriceForPurchase * this.Quantity) - this.DiscountTotal;
// 减了明细折扣，却漏减小计折扣分摊额 TotalDiscountSubTotalDivided
```
案分算得对、税额/积分都排除对了，但分摊结果**没回流到行总额** → `TotalAmount = Σ LineTotal` 少减 → **顾客实付、画面合计、小票合计全都没享受这个折扣**。（而 `SalesTran.DiscountTotal` 本身是对的，只是应付额没用它。）

**缺陷 2（崩溃）：落盘 NRE**
`DiscountMaker.cs:33-34`：
```csharp
SalesDiscountRow discountRow = discountTable.NewSalesDiscountRow(); // 新行，未加入表
discountRow.TransactionNo = tranDs.SalesDiscount.FirstOrDefault().TransactionNo; // ★ 空表!→ null.属性 → NRE
```
第一条折扣就必触发（此时表恒空），收银台崩溃，TLog 无法持久化。

> ✅ **时点更新**：源码仓当前停在分支 `001-fix-discount-maker-nre`，提交 `0c2434de4 fix(discount): DiscountMaker.AddDiscountInfo 首条折扣 NRE（dogfood #001）`——**缺陷 2（NRE）已在 SDD dogfood 分支修复**；缺陷 1（LineTotal）据现有记录尚未见对应修复。

**触发条件**：在 `Paying` 状态注册手动小计折扣后做交易确定。**改价与手动折扣互斥**（price_change 闸门③）是同源背景。

---

## 十一、对 ST-POS 内製化的迁移含义

1. **断链是首要教训**：小计折扣"UI/注册/分摊算得对，但没接到合计与落盘"——ST-POS 实现小计折扣时，务必让分摊额**贯通 `LineTotal` → 应付 → 票据 → TLog** 全链，并给折扣行正确的 `TransactionNo` 来源。
2. **别照搬种子表**：code 3/4/8 是"幽灵类型"，迁移时须按代码实装状态过滤，否则把死配置一并搬入。
3. **两套案分取整策略要显式保留语义**：floor+降序补残 vs 四舍五入+拆行，是刻意设计，不能统一。
4. **鲜度折扣（26 桁 JAN）是生鲜刚需**：年份反推逻辑与 Mod10 校验须完整迁移。
5. ST-POS（KugelPOS）折扣编排走 **ADR-0006 统一折扣编排架构**，为独立实现（非本模块移植），对照仅供参考。

---

## 十二、可信度与来源

| 结论 | 可信度 | 依据 |
|---|:---:|---|
| 两阶段编排 / 7 态门控 / 优先级排序 / 20 行种子 / 案分算法 / M&M 仅 Price&Set | ✅ **verified** | 本报告已逐条对照 202607 源码 `file:line` 亲核 |
| 两个真实 Bug（LineTotal / NRE） | ✅ **verified** | 源码两处 `file:line` 亲核成立 |
| NRE 已在 `001-fix-discount-maker-nre` 修复 | ✅ **verified** | 源码仓 git log |
| `DiscountGroupSet` name 复制粘贴 Bug | ✅ **本次新发现** | `DiscountTypes.cs:31` 亲核 |
| Dynamic Pricing 年份反推规则 | 🟡 业务文档 | POSSYS Confluence（未逐行核 C# 实现） |
| `Factory`/`PluginGroupId`/`CompanyDiscountLogic` 内部语义 | ⚪ **uncheckable** | 依赖 `POS4U.Framework.dll`（无源码） |

**主要来源**：
- `01-trialpos-docs/30_domain/discount.md`（source-anchored·verified）
- `01-trialpos-docs/80_decisions/investigations/subtotal_discount_defect.md`
- POSSYS Confluence：`値下げ種別` / `値下げ方法` / `０３：M&M` / `ダイナミックプライシング`
- 源码仓 `trialpos-snapshots` @ 202607（亲核）
