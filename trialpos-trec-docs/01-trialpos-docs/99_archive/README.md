---
title: 封存档案 · 说明
layer: 99_archive
genre: meta
audience: [维护者]
code_baseline: latest
verification: uncheckable
owner: jinianxiang
updated: 2026-07-14
---

# 封存档案（99_archive）

> 本层封存**被本体系取代的历史材料**，**不作为权威内容**；任何引用须回代码复核。

## 内容来源

1. **旧 `01-trialpos-docs`（StackShift 代码分析文档体系）** — 本体系的前身：StackShift 自动分析（2026-04）+ 人工整理的 5 卷册 107 篇。其质的分析多准确（已被本体系吸收重写），但存在系统性定量造假、门面架构错误（SQLite）、链接断裂等（详见 [`../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md`](../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md)）。
   - **归档方式（已定 2026-07-14 · 删除 + 接名）**：解压 zip 与旧 `01-` 目录逐文件比对、确认备份忠实保存全部原始内容后，**旧 `01-` 目录已物理删除**，本重构体系（原 `00-trialpos-docs`）**改名接替 `01-` 目录名**成为权威版本。物理备份 zip 见 `z-archive/trialpos-trec-docs/01-trialpos-docs.zip`（276 条目 · 含全 5 卷册 + 6_archive）；如需查阅旧文档解压该 zip 即可。
   - 本体系各篇中"核查基线/素材参考"曾以活链接指向旧 `01-` 源文件，删除后已统一转为纯文本（保留文件名描述，指向该 zip 备份）。

2. **本次重构的迁移留档** — `migration-log.md`（待建）：记录旧 107 篇 → 本体系各层的去向、去重、ST-POS 剥离。

## 权威性

真实代码 > `90-verification` 核查 > **本体系（现 `01-`，已核实层）** > 线上镜像(10/11/12) > 旧 `01-` 代码分析文档（已删除·zip 备查）。
