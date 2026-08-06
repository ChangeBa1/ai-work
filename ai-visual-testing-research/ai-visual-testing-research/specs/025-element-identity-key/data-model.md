# Data Model: 025-element-identity-key

**Date**: 2026-08-06 | **Spec**: [spec.md](./spec.md)

## Overview

在 015 的 `PageMemory` / `ElementMemory` 上扩展**元素身份**字段与检索键；页面指纹
模型不变。持久化仍为 SQLite payload + 关键索引列模式。

## Entities

### PageFingerprint / PageMemory（015，不变）

| 字段 | 类型 | 说明 |
|------|------|------|
| page_id | str | PK |
| fingerprint | PageFingerprint | pfp-v1 |
| resolution | (int,int) | |
| hit_count / last_seen_at / created_at | … | 统计 |

**存量**: 5 行 **保留**。

### NormalizedVisibleText（逻辑值对象）

- 经 `normalize_visible_text` 流水线的字符串。可检索身份要求该分量**非空**（选不出
  可见文本 OCR 时 MUST 不建立可检索身份，不得写入空文本键）。
- 不单独建表。

### GeomCell（逻辑值对象）

- `col: int`, `row: int`，`0 <= col,row < G`。
- 序列化：`"{col},{row}"`。
- 中心坐标 MUST 来自被选中 OCR 项的 bbox 中心（写/查同源）。

### ElementIdentity（逻辑值对象）

| 字段 | 类型 | 说明 |
|------|------|------|
| schema_version | str | 默认 `eid-v1` |
| grid_size | int | 默认 16；进入键前缀 |
| normalized_visible_text | str | FR-005a；可检索时非空 |
| geom_cell | str | `col,row` |
| identity_key | str | `f"{schema_version}:g{grid_size}|{text}|{cell}"`（例 `eid-v1:g16|小計|13,13`） |

相等：同 `page_id` 下 `identity_key` 字符串相等。

### ElementMemory（015 扩展）

| 字段 | 类型 | 变更 |
|------|------|------|
| element_id | str | 不变 PK |
| page_id | str | 不变 FK 逻辑 |
| target_label | str | **降级**：审计/线索；**非**唯一检索键 |
| **identity_key** | str | **新增**；可检索主键分量 |
| **normalized_visible_text** | str | **新增**；冗余便于审计 |
| **geom_cell** | str | **新增** |
| **identity_schema_version** | str | **新增** |
| template_path | str\|None | 不变 |
| bbox | (x1,y1,x2,y2) | 绝对像素；模板邻域用 |
| anchor_texts | list[str] | 不变 |
| success_count / failure_count / consecutive_success_count | int | 不变 |
| last_success_at / created_at | datetime | 不变 |

**校验**:

- `identity_enabled` 路径写入时 `identity_key` MUST 非空，且前缀 MUST 等于当前
  `{identity_schema_version}:g{identity_grid_size}`（例 `eid-v1:g16`）。
- 同 `(page_id, identity_key)` 逻辑唯一；repository 层确定性处理冲突。
- `identity_key == ""`、缺失、或前缀不匹配当前 `schema:gG` → **永不**进入命中候选
  （覆盖改 G / 改 schema 后的旧行；与 purge 条件一致）。

**存量**: 8 行 **整表作废**（见迁移）。

### IdentityResolutionResult（内存/审计）

| 字段 | 类型 | 说明 |
|------|------|------|
| status | enum | `unique` \| `ambiguous` \| `insufficient` \| `error` |
| candidates | list[ElementIdentity] | |
| identity | ElementIdentity\|None | 仅 unique |
| elapsed_ms | float | SC-003 |

`status=error` 对应 fail-open 吞掉的异常：MUST 递增 telemetry
`identity_lookup_error`，audit `resolution_status=error`，MUST NOT 与正常 miss 混计
（FR-013 / contracts §3）。

### MemoryLookupResult（015，additive）

保持 `level` / `matched_bbox` / `template_score` 语义；可选附加：

- `identity_key: str | None`
- `resolution_status: str | None`（如 `identity_ambiguous`）

直点授权条件不变：`level=="high" and matched_bbox is not None`。

### MemoryHitAudit（additive）

| 字段 | 类型 | 说明 |
|------|------|------|
| …既有 | | element_memory_id, page_memory_id, target_label, page_similarity, template_score, matched_bbox |
| identity_key | str \| None | 新增 |
| geom_cell | str \| None | 新增 |
| normalized_visible_text | str \| None | 新增 |

### LegacyElementMemoryRecord

迁移备份中的 015 行镜像；运行时不加载入命中路径。

## Relationships

```text
PageMemory 1 ── * ElementMemory
ElementMemory 1 ── 1 ElementIdentity（字段内嵌，非独立表）
ElementMemory 0..1 ── template 文件（template_path）
```

## State / Lifecycle

```text
[015 legacy row] --migrate--> deleted|archived (不可命中)
[new write] --> active (identity_key 非空) --> success/failure 计数更新
[lookup unique + template pass] --> direct click --> verify pass|fail|uncertain
[lookup ambiguous|template fail] --> miss (no direct click)
```

## SQLite 物理模型

### `page_memories`（不变）

既有列：`page_id`, `resolution_w/h`, `hit_count`, `last_seen_at`, `payload`。

### `element_memories`

| 列 | 类型 | 说明 |
|----|------|------|
| element_id | VARCHAR(64) PK | |
| page_id | VARCHAR(64) INDEX | |
| target_label | VARCHAR(512) INDEX | 保留；不再承担唯一命中 |
| **identity_key** | VARCHAR(640) INDEX | **新增**；格式 `eid-v1:g16|…|c,r`，640 足够（schema+gG+文本+cell） |
| success_count / failure_count | INT | |
| last_success_at | DATETIME | |
| payload | JSON | 完整 ElementMemory |

建议索引：`(page_id, identity_key)`。

### 迁移表（可选）`element_memories_legacy_015`

结构同迁移前 `element_memories`，仅用于回滚；或使用 JSONL 文件备份（plan §6）。

## Migration Procedures

见 [plan.md](./plan.md)「数据库变更与可回滚迁移」。摘要：

1. 备份 8 行元素 + 关联模板路径列表。
2. 加 `identity_key` 列。
3. `DELETE FROM element_memories`。
4. 保留 5 行 `page_memories`。

## Config 映射（非持久化实体）

`MemoryConfig.identity_enabled` / `identity_grid_size` / `identity_schema_version`  
见 plan。
