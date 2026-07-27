# spec-kit 基座升级计划：0.8.2.dev0 → v0.13.x — 2026-07-19

> **背景**：本意是 2026-07-15 导入最新版 spec-kit，实际因本机 CLI 陈旧（2026-04-26 `uv tool install` 后未升级）装成了 0.8.2.dev0。上游现已到 **v0.13.0**（2026-07-17），且 0.12.x 期间几乎每日一发。本计划把基座**追到执行日的最新 release tag**。
> **对象仓库**：`trialpos-snapshots` @ `sdd/main`（SDD 装置：`.specify/` + `.claude/` + `CLAUDE.md`）
> **状态**：✅ **已执行**（2026-07-19，同日批准并执行；vLATEST＝v0.13.0。执行摘要见文末，经验教训已回填 [runbook](./upgrade-runbook.md) §5）
> **通用流程**：[upgrade-runbook.md](./upgrade-runbook.md)（本计划是 runbook 的首轮实例化）

---

## 0. TL;DR

| 项 | 结论 |
|---|---|
| 可行性 | ✅ **三个成败攸关点全部绿灯**（沙箱实测 v0.13.0）：①新版 10 本 skill **全部保留 `extensions.yml` 钩子机制**（本地知识溶接/测试门不破）；②`specs/` 根布局未变（无产物迁移）；③本地 7 本自定义 skill 与新版无命名冲突 |
| 工作量主体 | 9 本日语 fork 基础 skill 的**三方移植重译**：5 本实质改动（specify 118 / tasks 89 / clarify 84 / plan 81 / implement 75 行）、4 本近零改动（analyze 2 / constitution 4 / taskstoissues 8 / checklist 16 行）；另译新增 `speckit-converge`（279 行） |
| 零成本部分 | 本地 4 本 bash 脚本经 diff 验证**与 v0.8.1 vanilla 完全一致** → 直接用 v0.13 版本覆盖，另新增 `setup-tasks.sh` |
| 绝不触碰 | 宪章 v2.0.0、知识层 16 文件、7 本自定义 skill、9 本 POS4U 模板、extensions.yml、根 CLAUDE.md、specs/、SPECKIT_BASELINE.md |
| 升级通道 | ❗ v0.13 起 release **不再附模板 zip 资产**；CLI 选项 `--ai` 改为 `--integration`；新增 `specify self` 子命令（CLI 自身升级）。项目资产**不在仓库内跑 init**，走「沙箱生成 → 选择性同步」 |
| 预估耗时 | 半天～1 天（重译是主体；机械部分 <1h） |
| 风险等级 | 中低（全程 git 可回滚；不触代码本体；001/002 在途分支不受影响） |

---

## 1. 侦察结论（2026-07-19 实测证据）

沙箱方法：`uvx --from 'git+https://github.com/github/spec-kit.git@<tag>' specify init <sandbox> ...` 分别生成 v0.8.1 与 v0.13.0 vanilla 项目，与本地 `sdd/main` 三方对照。

### 1.1 版本与通道变化

| 事实 | 证据 |
|---|---|
| 上游最新 v0.13.0（2026-07-17），0.12.x 在 7 月高频迭代（几乎每日一发） | GitHub releases API |
| 本机 CLI＝2026-04-26 `uv tool install`（git main 快照 0.8.2.dev0，v0.8.1=04-24 发布后 2 天），源＝`git+https://github.com/github/spec-kit.git` **未固定 tag** | `~/.local/share/uv/tools/specify-cli/uv-receipt.toml`、`~/.local/bin/specify` 符号链接日期 |
| v0.13.0 release **assets 为空**（0.8 时代的 `spec-kit-template-claude-sh-*.zip` 分发方式已废止）；模板改为内置于 CLI 包（"initialization does not need network access"），并新增 PyPI 分发（0.12.16 起） | releases API assets 字段、`specify init --help`、CHANGELOG #3425 |
| CLI 接口变化：`--ai` → `--integration`；新增子命令 `self`（CLI 自升级/`--dry-run`）、`extension`、`preset`、`bundle`、`workflow`、`integration` | v0.13.0 `specify --help` / `init --help` |
| **v0.13 init 不再生成根 CLAUDE.md**（v0.8.1 会生成）；plan skill 中 agent-context 更新机制已移除 | 沙箱文件树对比、新版 plan SKILL grep 无 CLAUDE.md/update-agent-context 引用 |

### 1.2 兼容性三绿灯（升级成立的前提）

1. **extensions.yml 钩子机制保留**：v0.13.0 全部 10 本 skill 均含「Check for extension hooks」段，读取 `hooks.before_*/after_*`——本地 mandatory 钩子（context-preload×4、test-spec、test-results）机制在新版下继续成立。
2. **`specs/` 布局未变**：v0.13.0 `create-new-feature.sh` 中 `SPECS_DIR="$REPO_ROOT/specs"`——本地 `specs/NNN-名` 无需迁移（上游内网团队 0.7.2 的 `.specify/features/` 反而是旧布局）。
3. **无命名冲突**：新版基础 skill 集＝旧 9 本 + `speckit-converge`（新）；与本地自定义 7 本（context-preload/adr/approve-adr/approve-spec/feedback/test-spec/test-results）无重名。SPECKIT_BASELINE 预警过的「上游出同名官方 skill」风险本轮未发生。

### 1.3 变更面量化（v0.8.1 → v0.13.0 vanilla diff）

| 构件 | 变更规模 | 本地状态 → 处置 |
|---|---|---|
| skill: specify / tasks / clarify / plan / implement | 118 / 89 / 84 / 81 / 75 行 | 日语 fork → **三方移植重译**（主工作量） |
| skill: checklist / taskstoissues / constitution / analyze | 16 / 8 / 4 / 2 行 | 日语 fork → 小 hunk 移植 |
| skill: **converge（新增）** | 279 行（全新） | 全文日译 + POS4U 适配评估（§3-C） |
| 模板: plan / spec / tasks / checklist / constitution | 25 / 13 / 9 / 6 / 0 行 | 本地已 POS4U 全重写 → **仅审阅结构性变化择优吸收**，不整体替换 |
| 脚本: common / create-new-feature / setup-plan / check-prerequisites | 425 / 182 / 60 / 29 行 | 本地=纯 vanilla（diff 实证零改动）→ **直接覆盖** |
| 脚本: **setup-tasks.sh（新增）** | 91 行 | 直接引入 |
| 其他新增: `memory/.constitution-template.json`、manifests/init-options/integration.json 更新 | 小 | 直接引入/更新（**绝不覆盖 memory/constitution.md**） |

## 2. 目标与非目标

**目标**：
1. CLI 固定安装到执行日最新 release tag（不再用浮动 main 快照——0.8.2.dev0 的教训）。
2. 项目资产（vanilla 部分）同步到同一 tag；日语 fork 部分完成三方移植重译；新增构件（converge、setup-tasks.sh）引入并日语化。
3. 定制面 100% 保全（钩子、宪章、知识层、自定义 skill/模板、CLAUDE.md、specs/）。
4. SPECKIT_BASELINE 台账新增 P6 条目；runbook 回填实践经验。

**非目标**：
- 不采用 0.9〜0.13 新增的 extension/preset/bundle 生态（POS4U 场景暂无需求，降低升级面）；
- 不改动 001/002 已产出的 specs 产物（模板升级只影响未来 spec）；
- 不动代码本体（`Application/`），不涉及 Windows 侧。

## 3. 执行计划（6 阶段）

> 每阶段一个 commit（Conventional Commits，scope=sdd）。全程在 `sdd/main` 直接提交（沿用 P3〜P5 惯例）。执行日先重查上游最新 tag（0.12.x 节奏很快，可能已 >0.13.0），下文以 `vLATEST` 指代。

### Phase 0 — 前置检查（5 分钟）
- `git status` 干净、当前在 `sdd/main`；`git log -1` 记录起点 sha。
- 查上游最新 release tag（`gh api repos/github/spec-kit/releases/latest` 或 releases 页），确定 `vLATEST` 并记入执行日志。

### Phase 1 — CLI 升级（固定 tag）（10 分钟）
```bash
uv tool install --force --from "git+https://github.com/github/spec-kit.git@vLATEST" specify-cli
specify version   # 确认版本号 = vLATEST
```
- 以后升级 CLI 可用新版内置 `specify self`（本轮先建立固定 tag 基线）。

### Phase 2 — 沙箱基线生成（10 分钟）
- scratchpad 中生成两套 vanilla：`uvx ...@v0.8.1 specify init sandbox-old --ai claude --script sh`（旧语法）与 `uvx ...@vLATEST specify init sandbox-new --integration claude --script sh --ignore-agent-tools`（新语法）。
- **禁止在 `trialpos-snapshots` 仓库内跑 `specify init --here`**——会用 vanilla 模板覆盖 `memory/constitution.md`（v2.0.0）等定制文件。

### Phase 3 — 分类同步（核心，半天）

按文件分类矩阵逐类处理：

**A. 直接覆盖（本地=vanilla 零改动，diff 已实证）**：
`scripts/bash/` 4 本 → 换 vLATEST 版；新增 `setup-tasks.sh`、`memory/.constitution-template.json`；`workflows/`、`integrations/*.manifest.json`、`integration.json`、`init-options.json` 换新（init-options 如实记录本轮参数与版本）。
→ commit ①: `chore(sdd): spec-kit 基盤 vanilla 資産を vLATEST へ更新 [speckit-upgrade]`

**B. 三方移植重译（9 本日语 fork skill）**：
每本执行：`diff EN(v0.8.1) EN(vLATEST)` 得上游 hunks → 逐 hunk 移植进日语 fork 并重译 → 保全三类本地插入块（①extensions.yml 钩子扩展描述 ②言語規約块 ③POS4U 补足块）。
顺序：先做 4 本近零改动（analyze/constitution/taskstoissues/checklist，热身+验证方法），再做 5 本大改动（plan → tasks → implement → clarify → specify）。
→ commit ②: `feat(sdd): 基盤 skill 9本を vLATEST へ三方移植・再翻訳 [speckit-upgrade]`

**C. 新增 converge skill**：
全文日译（279 行）+ 插入言語規約块 + POS4U 适配评估（converge=「对照 spec/plan/tasks 盘点代码现状、把未完成工作追加进 tasks」——与本地 characterization 流程兼容，定位为**任意工序**，同 checklist）。CLAUDE.md 基盤チェーン一句带过（任意）。
→ commit ③: `feat(sdd): speckit-converge を導入・日本語化（任意工程として位置付け）[speckit-upgrade]`

**D. 模板审阅（择优吸收，不整体替换）**：
对照 vanilla 模板 diff（plan 25 行为最大），判断是否有值得移植进 POS4U 模板的结构性改进；有则小步吸收，无则记录「已审阅、不采用」。
→ commit ④（如有实改）: `feat(sdd): テンプレートへ上流 vLATEST の構造改善を選択的に反映 [speckit-upgrade]`

**E. 保护清单（全程只读校验）**：
`memory/constitution.md`、`SPECKIT_BASELINE.md`（本阶段只在 Phase 4 更新）、`extensions.yml`、根 `CLAUDE.md`、`.claude/knowledge/`（16 文件）、自定义 skill 7 本、POS4U 模板 9 本、`specs/`。Phase 5 用 `git diff --stat` 确认这些路径零意外变更。

### Phase 4 — 台账与文档同步（30 分钟）
- `SPECKIT_BASELINE.md`：基盤节版本改为 vLATEST（固定 tag+安装命令）；新增「✅ P6（执行日）— 基座升级 0.8.2.dev0 → vLATEST」台账条目（含 converge 定位、模板吸收结论、重译范围）；「アップグレード戦略」补记「以后升级按 trec-docs runbook 执行」。
- `CLAUDE.md`（snapshots 根）：基盤チェーン补 converge（任意）；如 CLI 用法变化影响描述则同步。
- trec-docs：本文件状态改「✅ 已执行」；[runbook](./upgrade-runbook.md) 回填实践经验；`branch-triage/sdd-suite-comparison-2026-07-19.md` §1 注记补「本地已升至 vLATEST」。
→ commit ⑤: `docs(sdd): SPECKIT_BASELINE P6 台帳＋CLAUDE.md を基盤 vLATEST に同期 [speckit-upgrade]`

### Phase 5 — 验证（人手门）（1 小时）
1. **结构校验**（机械）：16+1 本 skill 全部存在且 frontmatter 合法；9 本 fork skill 中三类本地插入块逐本 grep 在位；`extensions.yml` 六个 mandatory 钩子引用的 skill 均存在；保护清单路径 `git diff` 零变更。
2. **语义校验**（人工）：抽读 specify/plan/implement 三本重译 skill，确认日语质量与逻辑等价。
3. **冒烟测试**：在丢弃分支上跑一次 `/speckit-specify` 微型输入，验证 before_specify 钩子（context-preload）触发、`specs/003-*` 采番正确、产物为日语 → 验证后删除该分支与产物。
4. **最终人手门**：用户审阅全部 diff 后批准；不满足则按 §5 回滚。

## 4. 风险与对策

| 风险 | 等级 | 对策 |
|---|---|---|
| 重译引入语义漂移（skill 行为与上游逻辑不等价） | 中 | 三方 diff 逐 hunk 移植（不整篇重写）；4 本小改动先行验证方法；Phase 5 人工抽读 |
| 本地插入块（钩子/言語規約/POS4U 补足）在移植中丢失 | 中 | 每本 skill 完工即 grep 校验三类块；Phase 5 全量复查 |
| 上游版本日更，执行日 vLATEST ≠ 0.13.0 | 低 | 计划按 `vLATEST` 参数化；runbook 固化「执行日先查 tag」步骤 |
| `init --here` 误跑覆盖宪章 | 低 | 明令禁止（§3 Phase 2）；宪章在保护清单 + git 兜底 |
| converge 与本地流程冲突 | 低 | 定位为任意工序，不进 mandatory 链；试用后再决定升格 |
| 001/002 在途分支受影响 | 极低 | 升级只动 sdd/main 的流程文件；feature 分支未触及 `.claude/.specify`；后续 merge 无冲突面 |

## 5. 回滚方案

- 资产回滚：`git revert <P6 各 commit>`（或 `git reset --hard <起点 sha>` 若未推送——本仓库本就禁 push，安全）。
- CLI 回滚：`uv tool install --force --from "git+https://github.com/github/spec-kit.git@v0.8.1" specify-cli`（CLI 版本仅影响 init/采番脚本，日常 SDD 工作流不依赖 CLI 在位）。
- 部分回滚：任一 skill 重译不合格，单文件 `git checkout <起点 sha> -- <path>` 回退，其余保留。

## 6. 验收标准

- [ ] `specify version` = vLATEST（固定 tag 安装，uv-receipt 记录含 `@vLATEST`）
- [ ] vanilla 资产（脚本/workflows/manifests）与 vLATEST 沙箱逐 byte 一致
- [ ] 9 本 fork skill 完成移植重译，三类本地插入块 100% 在位
- [ ] converge 已日语化并定位为任意工序
- [ ] 保护清单 8 类路径零意外变更（git diff 实证）
- [ ] 冒烟测试通过（钩子触发/采番/日语产物）
- [ ] SPECKIT_BASELINE P6 条目 + CLAUDE.md + runbook 回填完成
- [ ] 用户最终批准（人手门）

---

*侦察数据生成于 2026-07-19（沙箱 diff 实测）；执行时若 vLATEST > 0.13.0，需按 runbook 步骤 2 重跑侦察 diff 更新工作量估计。*

---

## 执行摘要（2026-07-19 回填）

- **实际 vLATEST**：v0.13.0（执行日与侦察日同日，无需重跑侦察）。
- **snapshots 侧 5 个 commit**（`sdd/main`，起点 `50831561c`）：`e33ed51df` 台账误记订正 → `8f72fe0f1` vanilla 资产同步 → `a587eb218` 9 本 skill 三方移植重译 → `c06e2345d` converge 导入 → `3a686ed25` 台账 P6 记帐。
- **验收清单**：CLI=0.13.0 固定 tag ✅｜vanilla 资产 byte 一致（12 文件逐一 cmp）✅｜9 本 fork skill 移植完成、三类插入块 100% 在位（言語規約 16/16、POS4U 补足 4/4、共通钩子句 2×9）✅｜converge 日语化＋任意工序定位 ✅｜保护清单零意外变更 ✅｜脚本 bash -n 全过＋create-new-feature 冒烟通过（产物即清理）✅｜台账 P6＋CLAUDE.md 同步 ✅。
- **计划外发现**：①模板 diff 全为体裁差分 → 商定「不采用」，无 commit ④（模板）；②上游 specify 存在重复步骤编号 bug → 修正后移植；③`create-new-feature.sh` 采番扫描当前分支 `specs/`（既有行为）——在 `sdd/main` 上开新 feature 时需人工指定下一号（下一个为 003）。
- **实际耗时**：约 2 小时（重译主体；侦察已在计划阶段完成）。
