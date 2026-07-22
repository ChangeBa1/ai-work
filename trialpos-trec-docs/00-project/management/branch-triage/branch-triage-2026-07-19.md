# POS4U（aipos 正本）分支综合盘点 — 2026-07-19

> **盘点对象**：内网 GitLab 正本 `https://74.226.74.29/git/trial.git`（本地克隆＝`trialpos-snapshots`）
> **数据源**：`git ls-remote --heads/--tags origin`（2026-07-19 实时）＋ 本地对象库（缺失的 181 支 tip 已按「fetch 专用」规约补拉对象，未创建任何 ref）
> **盘点人**：jinianxiang ｜ **全量明细**：[all-branches-2026-07-19.md](./all-branches-2026-07-19.md)

---

## 0. TL;DR

| 结论 | 要点 |
|---|---|
| **总量** | 远端 387 支分支 + 7 个 tag（tag 全部为 2019-2020 早期，之后弃用 tag 改用分支管版本） |
| **当前基线** | `release20260728_Local`＝**202607，已发布最新版**。本地克隆与远端完全一致（sha `a1a8beb8e`） |
| **开发中** | `release20260818_Local`＝**202608**，领先基线 42 提交（tip 2026-07-17，中川憲抄），基线是其祖先 → 主线延续正常 |
| **master 已废弃（实锤）** | 末次提交 2024-09-18，且其 tip **不是**当前基线的祖先——2024-09 之后的发布线从未回流 master，master 是死胡同侧线 |
| **未并入基线** | 182 支（47%）：其中 119 支超 12 个月无活动（清理候选）、38 支近 6 个月活跃（在途开发） |
| **重要发现** | 上游团队（中川憲抄）也在用 **spec-kit 式 SDD 装置**：feature 分支根目录带 `.claude/skills/speckit-*`＋`.specify/`＋`CLAUDE.md`，合入 release 时刻意除外；另有 SDD 编号风格分支 `001-role-based-access` |
| **本地克隆状态** | fetch refspec 已收窄为仅 master；本地分支＝基线镜像＋SDD 工作分支（`sdd/main`、`001-`、`002-`），与治理设计一致 |

---

## 1. 数据口径与限界

- **实时性**：远端清单为 2026-07-19 `ls-remote` 实时结果；「末次提交日」取各分支 tip 的 committer date。
- **对象补拉**：盘点开始时本地对象库缺 181 支分支的 tip（含 202608 开发分支）。已按仓库规约（origin＝fetch 专用）执行 `git fetch --no-write-fetch-head` 补拉，**只进对象库、未创建任何本地/远程跟踪 ref**，`.git` 由 455M 增至 469M（+14M）。
- **「并入基线」判定**：`git merge-base --is-ancestor <tip> release20260728_Local`。注意这只能识别 **merge 方式**的回流；以 **cherry-pick** 回流的分支会被判为「未并入」（见 §5 观察项）。
- **陈旧度分档**：以盘点日 2026-07-19 为基准，近 6 个月（≥2026-01-19）／6-12 个月／超 12 个月。

## 2. 总量与分类

**387 支**，按命名分 5 类，与基线（202607）的并入状态交叉如下：

| 类别 | 数量 | 已并入基线 | 未并入 | 说明 |
|---|---:|---:|---:|---|
| **主线定期发布** `release*_Local` | 60 | 52＋基线自身 | 7 | 全店发布主线，版本号＝名称中的 `YYYYMM` |
| **专用/案件 release** | 116 | 47 | 69 | 带用途后缀（`_FoodPark`/`_ChinaPay`/`_AeonTenant` 等）或无后缀旧式命名 |
| **feature** | 168 | 72 | 96 | 案件开发分支 |
| **fix / hotfix** | 39 | 32 | 7 | 缺陷修复 |
| **其他** | 4 | 1 | 3 | `master`（废弃）、`001-role-based-access`（SDD）、`testDownloadBlob`、`v1.4` |
| **合计** | **387** | **205** | **182** | |

**末次活动年份分布**（tip 提交年）：2019=37 ／ 2020=37 ／ 2021=42 ／ 2022=44 ／ 2023=50 ／ 2024=44 ／ 2025=72 ／ 2026=61。分支从不删除、逐年累积——远端实质上把分支当作**永久版本档案**使用。

## 3. 版本主线台账（release`*_Local`）

主线共 60 支（2019-07 起）。**近 12 支**如下（全表见[快照](./all-branches-2026-07-19.md)）：

| 分支 | 版本 | tip 提交日 | 状态 |
|---|---|---|---|
| `release20260818_Local` | **202608** | 2026-07-17 | **开发中**（领先基线 42 提交，未并入） |
| `release20260728_Local` | **202607** | 2026-07-03 | **已发布最新版＝当前基线** ✅ |
| `release20260701_FixForScannerHang_Local` | 202607 系 | 2026-07-08 | 未并入基线（扫描枪挂死修正，晚于基线 tip → 疑似待入 202608 或 cherry-pick 回流） |
| `release20260630_AddLogForScannerHang_Local` | 202606 系 | 2026-06-30 | 未并入基线（同上，日志增补） |
| `release20260624_PointInfinitySimulatorFix_Local` | 202606 | 2026-06-24 | 已并入 |
| `release20260610_FixSendMTranDialog_Local` | 202606 | 2026-06-10 | 已并入 |
| `release20260609_StabilityFix_Local` | 202606 | 2026-06-12 | 已并入 |
| `release20260609_FixDeleteMTran_Local` | 202606 | 2026-06-09 | 已并入 |
| `release20260512_AutoDiscount_Local` | 202605 | 2026-05-26 | 已并入 |
| `release20260512_Local` | 202605 | 2026-04-28 | 已并入 |
| `release20260422_Local` | 202604 | 2026-04-14 | 已并入 |
| `release20260414_Local` | 202604 | 2026-04-08 | 已并入 |

**未并入基线的主线分支（7 支）观察**：

- `release20260818_Local`（202608 开发中）——正常，尚未发布。
- `release20260701_FixForScannerHang_Local` / `release20260630_AddLogForScannerHang_Local`——扫描枪挂死系列修正。基线 tip（2026-07-03 的 #8241 修正）正是同主题，推测该系列以 cherry-pick 或后续 merge 进 202608，需团队确认。
- `release20260422_LaneSelf_Local` / `release20260414_LaneSelf_Local`（tip 2026-04-03）——LaneSelf（レーンセルフ）店铺特化变体线，未回流全店主线。
- `release20260310_Local`（tip 2026-02-17）——**主线定期发布却未并入后续基线**，属異常项：内容或以 cherry-pick 回流、或该版有撤回，需团队确认。
- `release20250826_CESettingTool_Local`（tip 2026-04-23）——CE 设置工具专线，发布后仍有修正活动。

**命名异常（记录备查）**：`release2026041001_LaneSelf_Local`（10 位日期＝`YYYYMMDD`+2 位连番）；`release20190911_local`/`release20191015_local` 等早期小写 `_local`；`releaseFullTurn`、`releaseFC20240701` 无标准日期段。做名称→版本解析时需容错。

## 4. master 废弃状态（实锤）

- 末次提交：2024-09-18（p.shi，merge `release20240924_Local`）。
- 关键证据：master tip **不是** `release20260728_Local` 的祖先（merge-base 停在 2024-09-18 的 `c0c1592`，master 侧领先 77 提交）。即 **2024-09 之后发布主线不再从 master 分岔、也不再回流 master**，「分支＝版本、master 废弃」的团队口径与图谱完全吻合。
- 本地克隆的 fetch refspec 目前只跟踪 master（历史遗留的 clone 默认），实际治理意义已很低——参见 §8 建议。

## 5. 未并入基线的 182 支：陈旧度与在途开发

| 陈旧度 | 支数 | 处置倾向 |
|---|---:|---|
| 近 6 个月活跃（≥2026-01-19） | 38 | **在途开发/店铺特化线**，保留 |
| 6-12 个月 | 25 | 观察，随下次盘点复核 |
| 超 12 个月 | **119** | **清理候选**（归档/删除需正本侧团队决策） |

**近 6 个月活跃的 38 支**（在途开发全景，按末次提交日降序；完整列表见快照）：

| 主题簇 | 分支（末次提交日） |
|---|---|
| **202608 开发线** | `release20260818_Local`（07-17） |
| **クレジット併用（服务台/无人机）** | `featureFixUnknownStatusTranForCreditCombined`（07-17，**带 SDD 装置**）、`featureCreditCombinedPaymentForServiceCounter`（05-26） |
| **扫描枪挂死対策** | `release20260701_FixForScannerHang_Local`（07-08）、`release20260630_AddLogForScannerHang_Local`（06-30） |
| **免税（インバウンド/JTaxFree）** | `featureJTaxFreePosDataApi`（06-24）、`featureJTaxFreePosDataApi_mergedBO`（06-24）、`featureVerifyTaxFree`（06-09） |
| **薬機法フラグ（OTC 医薬品）** | `featureFixIsOTCDrugSalesFlagLogic_Prod/Pre`、`featureFixIsOTCDrugSaleFlagLogic_LS_Prod/Pre`（05-15〜19）、`release20260601_FixDrugFlagLogicLSPre`（05-26）、`release20260407_TLogDrugOperatorInfo`（03-27）、`release20260330_MstEmployeeDrugOperatorFlag`（03-27） |
| **BO（バックオフィス）改善** | `featureImproveBO`（05-11）、`featureBOChargePointView`（05-11）、`featureBOChargePointViewTest`（04-20） |
| **運用監視（OperationMonitoring）** | `featureImproveOperationMonitoringAndBO`（04-30）＋`_Bugfix`（04-27）、`featureImproveOperationMonitoring`（04-22）＋`_Verify`/`_MasterBulkRegister`（04-22）/`_ModuleBulkRegister`（04-21） |
| **LaneSelf（レーンセルフ）** | `release20260422_LaneSelf_Local`、`release20260414_LaneSelf_Local`（04-03）、`release20251125_AzureLaneSelf`（03-12） |
| **賞味期限値引** | `release20260601_BestBeforeMarkDownMaster`（06-01） |
| **Azure DB / ST-POS 关联** | `release20260302_AzureDbData`（02-25）、`featureAzureDbData`（02-11）、`featureSTPOSBackground`（03-10） |
| **FanCoupon** | `release20260209_FanCoupon`、`featureFanCoupon`（01-28） |
| **其他** | `001-role-based-access`（04-22，**SDD 编号风格**）、`featureTransportationICcard`（03-24）、`featureChargeFaceMeLogin`（03-02）、`release20250826_CESettingTool_Local`（04-23）、`release20260310_Local`（02-17） |

近期活跃分支的 tip 作者高度集中于**中川憲抄**（2026 年在途开发的绝对主力）。

## 6. 重要发现：上游也在铺 SDD 装置

`featureFixUnknownStatusTranForCreditCombined`（クレジット併用案件，2026-05〜07 活跃）根目录携带完整 spec-kit 装置：

- `.claude/skills/speckit-*`（specify/clarify/plan/tasks/analyze/implement/constitution/checklist/taskstoissues ＋ **git 扩展系** speckit-git-commit/feature/initialize/remote/validate）
- `.specify/extensions.yml` ＋ `.specify/extensions/git/`（含 bash/powershell 脚本的 git 工作流扩展）
- 根 `CLAUDE.md`

合入 `release20260818_Local` 时提交注记明确写「**(.claude/.specify/CLAUDE.md除外)**」——即上游团队同样遵循「**SDD 装置不进 release 线**」的原则，与本克隆「SDD 只在 `sdd/main`、release 镜像保持干净」的治理设计不谋而合。

另有 `001-role-based-access`（2026-04-22，中川憲抄）采用 spec-kit 的 `NNN-名` 分支命名，根目录带 `.specify/`＋`CLAUDE.md`。

**影响**：
1. 本地 SDD 采番（`specs/001-`、`002-`…）与上游 `001-role-based-access` 处于**同一编号命名空间**，将来若把 SDD 分支推回正本可能撞名——回流前需与上游对齐采番规则（如命名空间前缀）。
2. 上游 SDD 装置（含 git 扩展）与本克隆装置（日语化＋POS4U 定制）为**两套独立演化的 fork**，存在合流/互鉴机会，建议与中川氏交流。

→ 深挖对比见 [sdd-suite-comparison-2026-07-19.md](./sdd-suite-comparison-2026-07-19.md)（基座版本/治理/流程实操/冲突点/互鉴建议）。

## 7. Tags（7 个，全部早期）

`Release2019022801`〜`Release2019052201_Local`（2019 年 5 个）、`20200107_MarukyuBase`（2020）、共 7 个；本地与远端一致。2020 年后**未再打 tag**——版本标识完全转移到 `release<YYYYMMDD>_Local` 分支命名，佐证「分支＝版本」模型。

## 8. 本地克隆（trialpos-snapshots）状态

| 项 | 状态 | 评注 |
|---|---|---|
| 本地分支 | `sdd/main`（HEAD）、`001-fix-discount-maker-nre`、`002-fix-linetotal-subtotal-divided`、`release20260728_Local`、`master` | 与「SDD 在 `sdd/main`、release 镜像干净」设计一致；`release20260728_Local`/`master` 与远端逐 sha 一致 ✅ |
| fetch refspec | 仅 `+refs/heads/master:refs/remotes/origin/master` | **收窄产物**。master 已废弃，此 refspec 跟踪的恰是最没价值的分支；切换基线版本时需显式 `git fetch origin <branch>` |
| push | 已禁用（push URL＝占位符）✅ | 符合治理 |
| 对象覆盖 | 盘点前缺 181 支 tip（含 202608）；已补拉 tip 对象（+14M，无 ref） | `CLAUDE.md` 中「全履歴/全ブランチ含む」的表述与实际不符，建议修正表述或按需扩 refspec |
| tags / stash | 7 个早期 tag（与远端一致）；无 stash；工作区干净 | ✅ |

## 9. 处置建议

1. **正本侧（需团队决策，本克隆不动手）**：119 支超 12 个月未动且未并入基线的分支为清理/归档候选；但鉴于上游把分支当版本档案用，**默认保留、仅建档不删**亦可接受——本报告先做台账。
2. **`release20260310_Local` 未并入基线**属主线異常项，建议向团队确认该版的回流方式（cherry-pick？撤回？）。
3. **fetch refspec**：建议改为跟踪基线与开发中主线（如 `release20260728_Local`、`release20260818_Local`），master 可不再跟踪；或保持现状但在 `CLAUDE.md` 修正「全ブランチ含む」表述。
4. **SDD 采番冲突预防**：与上游（中川氏）对齐 `NNN-名` 编号空间后再考虑任何回流；短期内本地采番继续 sequential 即可（远端仅占用 `001-role-based-access`，本地 `001-` 已用不同名称，git 层面不冲突）。
5. **下次盘点**：建议 202608 发布（`release20260818_Local` 定版）后复核一次，重点看：202608 是否成为新基线、扫描枪挂死系列是否收敛、38 支在途分支的消长。

---

*生成方式：`git ls-remote` + `merge-base --is-ancestor` 逐支判定；明细数据与生成脚本口径见 §1。*
