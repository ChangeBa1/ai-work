# 上游 SDD vs 本地 SDD 套件多维对比 — 2026-07-19

> **背景**：[分支综合盘点](./branch-triage-2026-07-19.md) §6 发现内网 aipos 正本上游团队（中川憲抄）也在 feature 分支铺设 spec-kit 式 SDD 装置。本报告对两套装置做多维度对比。
> **改订 v2（2026-07-19 当日）**：本地基座于当日完成升级 0.8.2.dev0 → **v0.13.0**（见 [`../speckit-upgrade/`](../speckit-upgrade/)），本报告已按升级后状态**全面重估**——基座版本关系反转（本地=工具链最新，上游落后约 6 个 minor）、本地 skill 数 16→17（新增 converge）、布局对齐方向由此明确。治理/流程实操维度（§3/§4）结论不受升级影响，维持原判。
> **取证来源**（对象已 fetch 至本地库，`git show` 直读，未创建 ref）：
> - **上游A**：`featureFixUnknownStatusTranForCreditCombined`（tip `d385e93d1`，2026-07-17）——クレジット決済併用案件，spec-kit 装置最全的上游分支
> - **上游B**：`001-role-based-access`（tip `e1ec487c3`，2026-04-22）——更早期的上游 SDD 试点（产物最全：8 件套）
> - **本地**：`trialpos-snapshots` @ `sdd/main`（`50831561c`，2026-07-18）
> **盘点人**：jinianxiang

---

## 0. TL;DR

| | 上游（中川氏） | 本地（sdd/main） |
|---|---|---|
| **基座** | spec-kit **0.7.2.dev0**（2026-04-28 导入，PowerShell 脚本，落后上游最新约 6 minor） | spec-kit **v0.13.0**（2026-07-19 固定 tag 升级＝**工具链最新**；初装 0.8.2.dev0，bash 脚本） |
| **spec 布局** | `.specify/features/NNN-名/`（0.7.x 时代布局，0.8 起已被上游工具弃用） | `specs/NNN-名/`（根目录布局＝**0.13 现行标准**） |
| **宪章** | ❌ **未填充的原始模板**（plan 中自认「Constitution Gates 不适用」，代之以临时质量门） | ✅ **v2.0.0 已批准**（日语·第一原理 F1〜F5 + 8 原则 + 言語規約） |
| **知识层** | ❌ 无 | ✅ 16 文件（架构原则/ADR 0001-0004/领域知识×4/测试战略/遗留规律） |
| **扩展钩子** | git 自动化（分支创建/auto-commit，**auto-commit 实际关闭**） | 知识溶接（context-preload 强制）+ 测试门（test-spec/test-results 强制） |
| **测试纪律** | ❌ 无 test-spec/test-results 制度（靠手动结合测试） | ✅ characterization + touch-only + Windows 验证门 |
| **人手门** | ❌ 无（spec 长期停留 Draft） | ✅ 5 道（approve-spec / test-spec 评审 / test-results 评审 / approve-adr / analyze CRITICAL=0） |
| **实绩** | 2 案件（001 试点 8 件套、002 实战 6 件套），**已随实装跑通全链** | 2 案件（001 样板 9 件套、002 9 件套），Windows 验证待完成 |
| **共识点** | SDD 装置不入 release 线（merge 时人工除外）；sequential 采番；日语成果物；行为保全意识 | 同左（结构性隔离于 `sdd/main`） |

**一句话**：上游是「**工具链原味 + 实战驱动**」（无治理层，但产物随代码高频迭代、已在真实案件全程落地）；本地是「**治理增强 + 流程完备**」（宪章/知识层/人手门/测试门齐备，且基座已是工具链最新版，但实战里程还浅）。两者互补性极强——且升级后本地在「基座新旧」维度上已无短板，向上游输出（治理层＋升级路径）的筹码更足。

---

## 1. 基座与版本

| 维度 | 上游A | 上游B | 本地 |
|---|---|---|---|
| spec-kit 版本 | 0.7.2.dev0（`init-options.json`） | 更早（无 init-options.json 留存，quickstart 日期 2026-03-26） | **v0.13.0**（2026-07-19 固定 tag 升级；初装 0.8.2.dev0） |
| 导入日 | 2026-04-28（workflow-registry 时间戳） | ≈2026-03 下旬 | 2026-07-15（基座更新 2026-07-19） |
| 脚本平台 | **PowerShell**（`script: ps`，`.specify/scripts/powershell/`；git 扩展含 bash+ps 双份） | 不明（仅存产物） | **bash**（`script: sh`，v0.13.0 版 5 本，含新增 `setup-tasks.sh`） |
| spec 产物位置 | `.specify/features/` | `.specify/features/` | `specs/`（仓库根＝0.13 现行标准） |
| 采番 | sequential（001、002） | sequential | sequential（001、002；采番键已随 0.13 更名 `feature_numbering`） |
| 基线台账 | ❌ 无 | ❌ 无 | ✅ `SPECKIT_BASELINE.md`（fork 台账 P3〜P6 + re-sync 条款） |

**要点**：
- 上游比本地早约 **3 个半月**开始用 spec-kit（3 月试点 → 4 月底正式装置化），是**先行者**。
- **版本关系已反转（v2 重估）**：初版对比时两边都不新（上游 0.7.2 / 本地 0.8.2，本地 0.8.2.dev0 的成因是本机浮动 CLI 未升级——`SPECKIT_BASELINE.md` 误记已订正）。本地于 2026-07-19 按 [runbook](../speckit-upgrade/upgrade-runbook.md) 升级至 **v0.13.0（工具链最新）**，现在**只有上游落后**（约 6 个 minor；0.7.x≈2026-04 → 0.13.0＝2026-07-17，上游工具约 3 个月内高速演化出的差距）。
- **布局对齐方向由此明确**：上游A/B 的 `.specify/features/` 是 0.7.x 时代布局，spec-kit 0.8 起已改回根 `specs/` 且 0.13 延续——即**上游用的是被工具弃用的旧布局**。将来产物互通/回流时，迁移方应是上游（`.specify/features/` → `specs/`），本地无需动。
- 上游若升级 0.7→0.13，将面对与本地同量级的移植面（钩子块重构、`feature_numbering` 更名、setup-tasks 脚本等）——但上游 skill 是英文原版零改动，**无重译成本**，比本地这轮容易得多；本地首轮 runbook 的「固定 tag + 沙箱三方 diff + 保护清单」方法可直接供其复用。
- 上游选 PowerShell（Windows 开发机前提）、本地选 bash（Mac/AI 前提）——同一工具链在两种平台前提下各自成立，佐证基座本身平台中立。

## 2. 装置构成

| 构件 | 上游A（14 skills） | 本地（**17 skills**·v2 更新） |
|---|---|---|
| 基础链 skill | 9 本: specify / clarify / plan / tasks / analyze / implement / checklist / constitution / taskstoissues（**英文原版**，github-spec-kit 0.7.2 原样） | **10 本**（**全面日语化 fork**，v0.13.0 水准，含言語規約块 + POS4U 补足块）: 同 9 本 + **converge**（0.13 新设——对照 spec/plan/tasks 盘点代码现状、残作业追记 tasks；上游 0.7.2 尚无此 skill） |
| git 扩展 skill（5） | ✅ speckit-git-commit / feature / initialize / remote / validate + `.specify/extensions/git/`（脚本+配置） | ❌ 未装（有意不采用，git 操作走人工规约） |
| 治理/质量 skill（7） | ❌ 无 | ✅ context-preload / adr / approve-adr / approve-spec / feedback / test-spec / test-results |
| 模板 | **6 本标准**（spec/plan/tasks/checklist/constitution/agent-file） | **13 本 POS4U 化**（标准 4 重写 + research/data-model/contracts/quickstart/test-spec/test-results/spec-nfr/spec-cross-cutting 新设；0.13 升级时审阅 vanilla 模板 diff＝纯排版差分，维持不变） |
| `.claude/knowledge/` | ❌ 无 | ✅ 16 文件 |
| 宪章 | 模板未填充 | v2.0.0（2026-07-16 批准、07-18 修订） |
| 根 CLAUDE.md | **自动生成的 agent context**（update-agent-context 脚本产物，近乎空壳） | **手写开发规则**（最重要ルール/工作流/语言规约/分支规约） |
| extensions.yml 钩子 | git 扩展：全阶段 before/after auto-commit（optional，且 git-config 里 **default: false＝实际未启用**）+ before_specify 建分支 | pos4u-sdd：before_specify/plan/implement/analyze **强制** context-preload；after_plan 强制 test-spec；after_implement 强制 test-results |

**要点**：
- 上游的扩展点用在 **git 工序自动化**（但 auto-commit 配置为关闭，实际提交全手动）；本地的扩展点用在**知识注入与测试门禁**。两边都没 fork 核心链——扩展机制的两种正交用法。
- 上游 skill 是英文原版零改动 → 升级零成本；本地是日语 fork → 升级需重译。该负债已在 P6 首轮升级中**实际兑付一次**（0.8→0.13 三方移植重译约 2 小时，方法固化为 [runbook](../speckit-upgrade/upgrade-runbook.md)），证明成本可控、不构成拒绝追随上游的理由。

## 3. 治理维度

| 维度 | 上游 | 本地 |
|---|---|---|
| 宪章 | **未制定**。002 plan.md 明言：「プロジェクト固有の Constitution は未設定（テンプレートのまま）のため、Constitution Gates は適用しない」，代之以 3 条临时 GATE | v2.0.0：第一原理 F1〜F5、8 原则（含 .NET 版本禁改、Framework.dll uncheckable、离线缩退等）、言語規約、人手门表、提交规约 |
| analyze 的宪章校验 | 空转（无宪章可校验） | 实质校验（CRITICAL=0 才可 PR）+ 语言整合性检查 |
| ADR | ❌ 无制度。架构判断散落在 spec Clarifications 里 | ✅ 二速 ADR（灰色地带继续/明确违反停下）+ 已有 0001〜0004 + approve-adr 反哺 principles |
| 知识注入 | ❌ 每次靠人（或 agent context 空壳） | ✅ context-preload 强制钩子，宪章/原则/ADR/领域知识自动进上下文 |
| 人手门 | ❌ spec Status 长期 Draft，无审批记账 | ✅ Draft→レビュー待ち→承認済み 生命周期 + approved-specs/index.md 记账 |
| 可追溯 | 提交风格 `【機能追加】【バグ修正・仕様更新】`＋FR 编号在 spec 内引用；无 [spec:] 提交标签 | Conventional Commits + `[spec:NNN-名]` 标签；tasks↔TC↔FR 链条 |
| 定制自我记录 | ❌ 无台账 | ✅ SPECKIT_BASELINE.md（P3/P4/P5 台账 + re-sync 条款） |

**值得注意的镜像巧合**：上游没有宪章，但其临时 GATE 1〜3 全部是「**既存フローが無変更であること**」——与本地宪章 III（characterization、行为保全）**精神完全一致**。两个团队从同一个遗留系统的现实里独立推导出了同一条纪律：**先保全现行行为**。这是将来合流最坚实的公共地基。

## 4. 流程实操对比（从提交史观察）

| 观察点 | 上游（002 案件，2026-04-28〜07-17） | 本地（001/002，2026-07-16〜18） |
|---|---|---|
| spec↔代码同步 | **同一提交里代码+spec/tasks 一起改**（`【バグ修正・仕様更新】`），高频迭代 3 个月，Clarifications 累积 7 个 session | 1 任务=1 提交 + `[spec:]` 标签，同步门（tasks 完成时 spec 同步更新）由 disciplines 约束 |
| Clarifications 用法 | **超出原设计**：后期 session 实为**调试日志/缺陷分析记录**（含堆栈级根因、修复方案、FR 增补），信息密度极高但 spec 与 debug log 边界模糊 | 按 clarify 原设计使用（决策问答）；缺陷分析归 research/analysis 产物 |
| tasks 执行 | ✅ checkbox 全程勾选，含「※…変更不要」的**确认型任务注记**（characterization 意识） | ✅ 同样 checkbox + characterization 任务先行（test-spec 派生） |
| 深度产物 | 001 试点做了 research/data-model/contracts/quickstart（8 件套）；002 实战收敛为 6 件套（无 quickstart/contracts） | 规模门（S/M/L）决定派生哪些深度产物，001/002 均 9 件套（多 analysis/spec_review/test-spec/test-results） |
| 测试 | 「手動結合テスト（既存テスト手順に準拠）」——无独立测试产物 | test-spec（NUnit characterization）→ Windows 执行 → test-results TC-ID 1:1 回填 |

**解读**：上游把 spec-kit 用成了「**实装伴走的活文档**」——工具链轻、纪律靠个人素养（中川氏一人高水平驱动），产物质量高但**不可复制**（换个人就没有门禁兜底）。本地把 spec-kit 用成了「**制度化流水线**」——纪律外化为钩子和门禁，可复制可移交，但尚缺上游那种数月实战的锤炼。

## 5. 命名空间与冲突点（回流前必须解决）

| 冲突点 | 上游 | 本地 | 风险 |
|---|---|---|---|
| 采番 | `001-role-based-access`、`002-credit-combined-payment`（`.specify/features/` + 分支名） | `001-fix-discount-maker-nre`、`002-fix-linetotal-subtotal-divided`（`specs/` + 分支名） | **001/002 双方已各自占用**。git 层面因名称不同暂不冲突，但同一编号指向不同案件，合流后追溯会混乱 |
| spec 布局 | `.specify/features/`（0.7.x 布局，工具 0.8 起已弃用） | `specs/`（0.13 现行标准） | 产物互通需迁移，**迁移方＝上游**（v2 重估：对齐方向已无悬念，本地不动） |
| skill 同名 | 14 本 `speckit-*`（英文原版 0.7.2） | **17 本** `speckit-*`（日语 fork，v0.13.0 水准），其中 9 本与上游**同名不同文**（converge/治理系 7 本为本地独有） | 若两套装置进同一分支，**同名 skill 直接互相覆盖**——绝不可简单合并目录 |
| CLAUDE.md | 自动生成 agent context | 手写开发规则 | 同路径根文件，合并即冲突（上游 merge 时「CLAUDE.md除外」已经在规避这一点） |
| 宪章文件 | 模板未填 | v2.0.0 | 同路径 `.specify/memory/constitution.md`，直接覆盖会摧毁一方 |

## 6. 互鉴机会

**本地可向上游借鉴**：
1. **实战锤炼的产物形态**——002 spec 的 Clarifications 密度展示了「spec 伴随实装持续吸收决策」的真实样貌；本地 disciplines 可吸收其「代码+spec 同提交」的同步粒度（现行同步门是任务级，上游是提交级）。
2. **git 扩展**——分支创建/校验脚本（bash+ps 双平台）可评估引入，替代手工建分支；auto-commit 建议保持关闭（与本地 1 任务=1 提交规约冲突）。
3. ~~0.7.x `.specify/features/` 布局的取舍经验~~（v2 重估后失效：0.13 确认现行布局＝根 `specs/`，上游布局系工具弃用产物，对齐方向已定，无需「从容选择」）。

**上游可从本地受益（若有交流机会）**：
1. **宪章 + 知识层**——上游 plan 里的临时 GATE 证明他们需要治理层，本地 v2.0.0 宪章（尤其 .NET 版本禁改、Framework.dll uncheckable、离线缩退等硬约束）+ ADR 0001-0004 可直接填上这个洞。
2. **测试门**——上游靠手动结合测试，本地 test-spec/test-results + characterization 制度是现成的升级路径。
3. **人手门与审批记账**——spec 长期 Draft 的状态管理空白。
4. **基座升级路径（v2 新增）**——本地已实证 0.8→0.13 的升级方法（固定 tag 安装、沙箱双基线三方 diff、保护清单、禁 `init --here`），[runbook](../speckit-upgrade/upgrade-runbook.md) 可直接供上游复用；上游 skill 无重译负担，升级成本比本地首轮更低，还可顺带完成 `.specify/features/` → `specs/` 布局迁移与 converge 引入。

## 7. 建议

1. **短期（现状即可）**：两套装置**各自演化、互不合并**。本地采番继续 sequential；因双方 001/002 已重号，**本地下一个案件从 003 起且名称避开上游已用名**即可（git 无冲突）。
2. **回流前置条件**（任一 SDD 产物回流正本前）：与中川氏对齐①采番命名空间（如本地加前缀/段位）②spec 布局——方向已定：**统一到根 `specs/`（0.13 现行标准），迁移方为上游**③skill 目录归属（两套 fork 不可同分支共存）。
3. **主动交流窗口**：上游 4〜7 月已独立验证了 spec-kit 在 POS4U 上可行，且自认缺宪章——这是向上游输出本地治理层（宪章/知识层/测试门）的好时机；v2 起还可**顺带交付基座升级方案**（建议上游直接 0.7→0.13：runbook 现成、其英文原版 skill 无重译负担、可一并完成布局迁移）。
4. **下次盘点跟踪**：观察上游是否在更多 feature 分支铺装置（当前仅 2 支）、是否开始填宪章、是否升级基座/迁移布局、`.specify` 是否进入 202608 之后的 release 线（截至本次盘点均被除外，纪律保持良好）。

---

## 附：证据锚点

| 证据 | 位置 |
|---|---|
| 上游A 装置全树 | `d385e93d1:.specify/`、`d385e93d1:.claude/skills/` |
| 上游A 版本/初始化参数 | `d385e93d1:.specify/init-options.json`（0.7.2.dev0 / ps / sequential）、`workflow-registry.json`（installed_at 2026-04-28） |
| 上游A 宪章未填充 | `d385e93d1:.specify/memory/constitution.md`（`[PROJECT_NAME] Constitution` 原始占位） |
| 上游A plan 自认无宪章 | `d385e93d1:.specify/features/002-credit-combined-payment/plan.md` §Constitution Check |
| 上游A git 扩展配置 | `d385e93d1:.specify/extensions/git/`（extension.yml v1.0.0 / git-config.yml auto_commit default: false） |
| 上游B 产物 8 件套 | `e1ec487c3:.specify/features/001-role-based-access/` |
| SDD 除外合流证据 | `b0a59a391` / `d707de1b6`（release20260818_Local 上的 merge，注记「(.claude/.specify/CLAUDE.md除外)」） |
| 本地装置 | `sdd/main`：`.specify/SPECKIT_BASELINE.md`（v0.13.0 / P3-P6 台账）、`.specify/memory/constitution.md`（v2.0.0）、`.claude/knowledge/`（16 文件）；升级证据＝commit `8f72fe0f`〜`3a686ed2` 及 [`../speckit-upgrade/`](../speckit-upgrade/) |
