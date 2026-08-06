# Contract: Element Identity Memory (025)

**Consumers**: `PageElementMemory`（runtime / replay player 016）、单元测试、离线 quickstart  
**Non-goals**: Planner/Grounder HTTP 协议、跨画面索引、画面版本 API

## 1. Pure functions (`vnc_agent.memory.identity`)

### `normalize_visible_text(text: str) -> str`

- 确定性；规则见 [research.md](../research.md) R4。
- 无 I/O、无配置副作用（长音/假名规则内建；不读业务词表）。

### `geom_cell_from_center(cx: float, cy: float, width: int, height: int, grid_size: int) -> str`

- 返回 `"col,row"`；边界夹紧到 `[0, grid_size-1]`。
- `width/height <= 0` → 抛 `ValueError` 或返回调用方约定的 invalid（service fail-open）。

### `build_identity_key(*, schema_version: str, grid_size: int, normalized_visible_text: str, geom_cell: str) -> str`

- 格式：`{schema_version}:g{grid_size}|{normalized_visible_text}|{geom_cell}`。
- 例：`eid-v1:g16|小計|13,13`。`grid_size` MUST 进入键，改 G 后旧键失配。

### `resolve_identity_for_write(*, region, ocr_items, resolution, grid_size, schema_version) -> ElementIdentity | None`

- 按 research R3 写入规则；无法建立时返回 `None`（service 跳过可检索写入）。
- **锚点**：`region` 中心**仅**用于在 `ocr_items` 中选最近 OCR 项，并可将 `region`
  存为模板邻域 bbox；`geom_cell` MUST 取自**被选 OCR 项的 bbox 中心**，MUST NOT
  取自 `region` 中心。
- **OCR 选取（MUST）**：过滤后取中心距最小者；中心距并列时 MUST 按
  `(normalize_visible_text(text), (x1,y1,x2,y2))` 字典序取第一条，MUST NOT 依赖
  `ocr_items` 输入顺序。

### `resolve_identity_candidates_for_lookup(*, target_label: str, ocr_items, resolution, grid_size, schema_version) -> IdentityResolutionResult`

- `status=unique` 仅当恰好一个身份候选；`ambiguous` 当 ≥2；`insufficient` 当 0。
- 各候选的 `geom_cell` MUST 由匹配到的 OCR 项 bbox 中心计算（与写入侧同源）。

## 2. Reused pure functions（禁止再实现）

| 函数 | 模块 | 用途 |
|------|------|------|
| `build_page_fingerprint` | `memory.fingerprint` | 页面身份 |
| `page_similarity` / `classify_page_match` | `memory.fingerprint` | 分档 |
| `find_best_page` | `memory.retrieval` | 选页 |
| `match_element_template` | `memory.retrieval` | **强制**模板门禁（原则 III (c) 同构） |

## 3. `PageElementMemory` 外观契约

### `lookup(screen, target_label, *, exclude_element_ids=...) -> MemoryLookupResult | None`

**前置**: `memory.enabled` 且服务已构造。

**行为**:

1. `identity_enabled=false` → 015 语义：`normalize_target_label` + `find_element(page, label)` + 模板。
2. `identity_enabled=true` → 身份候选 → 唯一 → 页面 high 时强制模板 → 授权直点。

**直点授权**（对 runtime 稳定）:

```text
result is not None
and result.level == "high"
and result.matched_bbox is not None
and result.element is not None
```

**Fail-open**: 任意异常 MUST NOT 阻断主流程（返回 `None`），但 MUST 同时递增
`identity_lookup_error` 计数，并在 audit/日志中留下 `resolution_status=error`（或
等价字段），使异常与正常未命中（`insufficient`/`miss`）可区分。fail-open **不是**
「可以不记账」。

### `record_success(screen, target_label, target_region) -> None`

- 身份可建则按 `identity_key` upsert；否则不写可检索元素（可仍 upsert 页面）。
- mask 相交 → 不写元素（015）。

### `record_element_failure(element_id) -> None`

- 不变。

## 4. `MemoryRepository` 扩展

| 方法 | 契约 |
|------|------|
| `find_element(page_id, target_label)` | **保留**供 `identity_enabled=false`；文档标注 deprecated for hit path |
| `find_elements_by_identity(page_id, identity_key) -> list[ElementMemory]` | 新；0/1/N |
| `save_element` / `delete_element` / `list_elements` | 写入时同步 `identity_key` 列与 payload |
| `purge_legacy_element_memories() -> int` | 删除 `identity_key` 为空或**前缀不是当前** `{schema_version}:g{G}` 的行（含改 G / 改 schema 后的旧键）；返回删除数 |

## 5. 配置契约

```yaml
memory:
  enabled: true
  identity_enabled: true          # false => 015 标签路径
  identity_grid_size: 16          # 进入 identity_key 前缀 :g{G}；改 G 旧键失配
  identity_schema_version: "eid-v1"  # 与 g{G} 组成前缀 eid-v1:g16
  page_match_high: 0.88
  template_match_threshold: 0.85
  bbox_expand_ratio: 0.5
```

运行时「当前前缀」= `f"{identity_schema_version}:g{identity_grid_size}"`。命中与
purge 均以该前缀为准，二者 MUST 联动，不得只改 G 而依赖人工记得递增 schema。

## 6. 审计 / 计数（additive）

| 信号 | 何时 |
|------|------|
| `element_memory_hit` | 直点授权成功（模板通过） |
| `model_call_skipped` reason=`element_memory_hit` | 同上 |
| `identity_ambiguous` | 候选 ≥2（正常多候选未命中） |
| `identity_lookup_error` | 身份解析/查找路径抛异常被 fail-open 吞掉；MUST 与 `insufficient`/正常未命中可区分 |
| `element_memory_false_hit` | 直点后 verify `failed`\|`uncertain` |
| lookup 耗时字段 | 每次 lookup 尝试 |

## 7. 兼容性

- **不改变** GroundingRequest / Planner JSON schema。
- **不改变** 016 `MemoryLookupResult` 直点判定字段语义。
- 新增字段 MUST 为 optional/additive，旧报告解析不崩溃。
