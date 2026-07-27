# spec-kit 基座升级 Runbook（可复用流程）

> 目的：`trialpos-snapshots` SDD 装置升级 spec-kit 基座的**标准作业流程**。每轮升级按本文执行，完毕后在 §5「历次实践记录」回填经验。
> 前提知识：本地装置=「vanilla 基座 + 日语 fork skill + POS4U 定制层」三明治结构，fork 台账见 `trialpos-snapshots/.specify/SPECKIT_BASELINE.md`（单一真相源）。
> 维护人：jinianxiang ｜ 制定：2026-07-19

---

## 0. 四条铁律（每轮升级不可违反）

1. **CLI 永远固定 release tag 安装**，绝不用浮动 main 快照（首轮 0.8.2.dev0 之坑即源于此）。
2. **绝不在 `trialpos-snapshots` 仓库内跑 `specify init --here`**——vanilla 模板会覆盖宪章等定制文件。资产更新一律走「沙箱生成 → 选择性同步」。
3. **保护清单文件全程只读**：`memory/constitution.md`、`extensions.yml`、根 `CLAUDE.md`、`.claude/knowledge/`、自定义 skill（context-preload/adr/approve-adr/approve-spec/feedback/test-spec/test-results）、POS4U 定制模板、`specs/`。升级只允许动 vanilla 资产与日语 fork skill。
4. **fork skill 用三方移植，不整篇重写**：`diff EN(旧tag) EN(新tag)` 得上游 hunks → 逐 hunk 移植进日语 fork 重译。每本完工即校验三类本地插入块在位（①extensions.yml 钩子描述 ②言語規約块 ③POS4U 补足块）。

## 1. 侦察（升级决策前）

```bash
# 1a. 上游最新 release tag（记为 vLATEST）
curl -s https://api.github.com/repos/github/spec-kit/releases/latest | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['tag_name'], d['published_at'])"

# 1b. 本机 CLI 现状（版本 + 安装来源是否固定 tag）
specify version
cat ~/.local/share/uv/tools/specify-cli/uv-receipt.toml

# 1c. 本地装置基线版本（应与台账一致）
cat <snapshots>/.specify/init-options.json
```

- 读 CHANGELOG（`raw.githubusercontent.com/github/spec-kit/main/CHANGELOG.md`）扫两个 tag 之间的条目，重点盯：**skills 机制、extensions/hooks、init 布局（specs 目录）、CLI 选项、分发方式**的变化。
- 沙箱生成两套 vanilla 并 diff 定级（见 §2）。跨度大或有布局级变化 → 先写升级计划文档（参照 [首轮计划](./upgrade-plan-2026-07-19-v0.8-to-v0.13.md) 的结构）；小版本跟进可直接按本 runbook 走。

## 2. 沙箱基线

```bash
cd <scratchpad>
# 旧基线（= 本地装置当前 vanilla 版本；注意旧版 CLI 用 --ai，0.13+ 用 --integration）
uvx --from "git+https://github.com/github/spec-kit.git@<旧tag>" specify init sandbox-old --ai claude --script sh --ignore-agent-tools --no-git
# 新基线
uvx --from "git+https://github.com/github/spec-kit.git@vLATEST" specify init sandbox-new --integration claude --script sh --ignore-agent-tools

# 变更面定级（示例：基础 skill 逐本 diff 行数）
for s in specify clarify plan tasks analyze implement checklist constitution taskstoissues; do
  echo "$s: $(diff sandbox-old/.claude/skills/speckit-$s/SKILL.md sandbox-new/.claude/skills/speckit-$s/SKILL.md | grep -c '^[<>]') 行"
done
```

**必查三个成败攸关点**（任何一个不成立 → 停下重新评估，不得硬升）：
- [ ] 新版 skill 是否仍读 `.specify/extensions.yml` 钩子（`grep -l extensions.yml sandbox-new/.claude/skills/*/SKILL.md`）
- [ ] `specs/` 布局是否未变（`grep SPECS_DIR sandbox-new/.specify/scripts/bash/create-new-feature.sh`）
- [ ] 新版是否新增了与本地自定义 skill **同名**的官方 skill（对照 SPECKIT_BASELINE 命名冲突预警条款）

## 3. 执行（阶段化提交）

| 阶段 | 内容 | commit 约定 |
|---|---|---|
| P-0 | `git status` 干净、记录起点 sha、确认在 `sdd/main` | — |
| P-1 | CLI 固定 tag 安装：`uv tool install --force --from "git+https://github.com/github/spec-kit.git@vLATEST" specify-cli` → `specify version` 验证 | — |
| P-2 | **A 类·直接覆盖**：vanilla 零改动资产（scripts/workflows/manifests/init-options 等，覆盖前用 diff 实证本地=旧 vanilla）+ 新增 vanilla 文件 | `chore(sdd): ... vanilla 資産を vLATEST へ更新` |
| P-3 | **B 类·三方移植重译**：日语 fork skill，先小改动热身、后大改动；逐本校验三类插入块 | `feat(sdd): 基盤 skill を vLATEST へ三方移植・再翻訳` |
| P-4 | **C 类·新增构件**：新 skill/脚本全文日译 + POS4U 适配定位（默认「任意工序」，试用后再升格） | `feat(sdd): <新構件> を導入・日本語化` |
| P-5 | **D 类·模板审阅**：vanilla 模板 diff 择优吸收进 POS4U 模板（不整体替换）；不采用也要记录 | `feat(sdd): テンプレートへ構造改善を選択的に反映` |
| P-6 | 台账/文档同步：SPECKIT_BASELINE 新增台账条目 + CLAUDE.md + trec-docs 本目录回填 | `docs(sdd): SPECKIT_BASELINE 台帳を vLATEST に同期` |

## 4. 验证与收尾（人手门）

1. **结构校验**：skill 全量存在、frontmatter 合法；fork skill 三类插入块 100% 在位；extensions.yml 引用的 skill 全部存在；保护清单路径 `git diff` 零变更。
2. **语义抽读**：抽 2〜3 本大改动 skill 人工读，确认日语质量 + 与上游逻辑等价。
3. **冒烟测试**：丢弃分支上跑 `/speckit-specify` 微型输入 → 验证钩子触发、采番、日语产物 → 删分支。
4. **回填本文件 §5** + 升级计划文档标记「已执行」。
5. 用户审阅 diff → 批准（不合格按 git 回滚：整体 revert / 单文件 checkout 回退）。

## 5. 历次实践记录（每轮回填）

| # | 日期 | from → to | 耗时 | 结果 | 踩坑/经验（详见当轮计划文档） |
|---|---|---|---|---|---|
| 1 | 2026-07-19（计划+执行同日） | 0.8.2.dev0 → v0.13.0 | 约 2h | ✅ 完成（snapshots 5 commits，验收全过） | 见下方「首轮已知教训」+「首轮执行期教训」 |

**首轮已知教训（侦察阶段即确认）**：
- 0.8.2.dev0 之坑：`uv tool install` 未固定 tag + 长期未升级 → CLI 是 4 月末 main 快照，7 月 init 时以为是最新版。→ 铁律 1。
- v0.13 起 release 不再附模板 zip 资产（模板内置于 CLI 包、新增 PyPI 分发）——依赖下载 zip 的旧升级思路作废。
- CLI 选项 `--ai` → `--integration`（0.13 报错 `No such option: --ai`）；新增 `specify self` 子命令可用于以后 CLI 自升级。
- v0.13 init 不再生成根 CLAUDE.md、plan skill 的 agent-context 更新机制被移除——本地手写 CLAUDE.md 的覆盖风险反而消除。
- 上游 0.12.x 几乎每日一发：计划里版本号一律参数化为 vLATEST，执行日重查。

**首轮执行期教训（2026-07-19 回填）**：
- **批量脚本插入有坑**：用脚本向多个 skill 批量插入文本时，嵌套缩进（4/7/8 空格混存）导致 4 个文件尾部被意外复制。教训：批量文本手术前先 `git status` 确认可随时 `checkout` 回退；脚本内对每处替换 `assert count==1`；改完立刻用「行数增量 = 预期增量」核对每个文件。
- **上游 vanilla 本身可能有 bug**：v0.13.0 的 specify skill 存在重复步骤编号（两个 6.）。三方移植时按上游**意图**修正后移植，并在台账记录。
- **frontmatter 校验别依赖 python-yaml**（本机无该模块）：用纯文本检查（首行 `---`、闭合 `---`、`name:` 存在）即可。
- **冒烟测试注意采番来源**：`create-new-feature.sh` 扫描**当前分支**的 `specs/`。本仓库产物在 feature 分支上，`sdd/main` 的 specs/ 为空 → 冒烟会给出 001。这是既有行为非回归；实际开新 feature 时人工指定下一号。冒烟产物（specs 目录 + `.specify/feature.json`）记得清理。
- **模板 diff 可能全是排版**：0.8→0.13 的 5 本 vanilla 模板 diff 全为 trailing-space/空行调整，无结构改进——「审阅后不采用」也是合法结论，记录即可。

## 6. 关联文档

- 首轮升级计划（含文件分类矩阵与量化 diff 数据）：[upgrade-plan-2026-07-19-v0.8-to-v0.13.md](./upgrade-plan-2026-07-19-v0.8-to-v0.13.md)
- fork 台账（定制内容单一真相源，日语）：`trialpos-snapshots/.specify/SPECKIT_BASELINE.md`
- 上游 vs 本地装置对比：[../branch-triage/sdd-suite-comparison-2026-07-19.md](../branch-triage/sdd-suite-comparison-2026-07-19.md)
