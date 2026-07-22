# branch-triage — 分支盘点

> 目的：POS4U（`trialpos-snapshots` / 内网 GitLab `aipos` 正本）的**分支盘点报告**——不定期全量盘点分支现状：发布分支↔版本对照、已发布/开发中判定、陈旧分支处置建议。命名同构于 `stpos-trec-docs` 的 `github-triage/`・`redmine-triage/`。
> 负责人：jinianxiang
> 最近更新：2026-07-19

## 目录索引

- [branch-triage-2026-07-19.md](branch-triage-2026-07-19.md) — **首次综合盘点**：远端 387 支全量台账（202607=基线 / 202608=开发中 / master 废弃实锤 / 未并入 182 支陈旧度分档 / 上游 SDD 装置发现）
- [all-branches-2026-07-19.md](all-branches-2026-07-19.md) — 同日全量快照表（387 支逐支：tip / 末次提交日 / 并入基线 / 作者）
- [sdd-suite-comparison-2026-07-19.md](sdd-suite-comparison-2026-07-19.md) — 上游 SDD vs 本地 SDD 套件多维对比（盘点 §6 发现的深挖：基座版本 / 治理 / 流程实操 / 冲突点 / 互鉴建议）

## 何时应放在这里

- 分支全量盘点快照（某时点 `aipos` 正本的分支清单 + 状态判定）
- 发布分支↔版本对照台账（`release<YYYYMMDD>_Local` → `YYYYMM`，最新＝版本号最大者）
- 陈旧/废弃分支的处置建议（如 `master` 已废弃类结论）

## 不属于这里

- 分支＝版本模型、SDD 分支策略等**持续有效的规则** → `trialpos-snapshots/CLAUDE.md`（及工作区根 `CLAUDE.md` 跨仓铁律 §6）
- 时间表、人员体制、路线图 → [`../`](../README.md)
- 协作规范、流程、术语 → [`../../guides/`](../../guides/)
