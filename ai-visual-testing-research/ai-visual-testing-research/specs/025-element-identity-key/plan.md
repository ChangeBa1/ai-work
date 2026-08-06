# Implementation Plan: 结构化元素身份主键（element-identity-key）

**Branch**: `025-element-identity-key` | **Date**: 2026-08-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/025-element-identity-key/spec.md`

## Summary

Feature 015 已具备页面指纹、元素模板与「高相似页面 + 邻域模板 → 跳过 Grounder」
整条通道，但元素检索主键是 Planner 自然语言 `target_label` 的 strip/lower，实测
`memory_hits.element_memory` 恒为 0。

本 feature **不重做记忆通道**，只把「是否同一控件」换成稳定的**结构化元素身份**：

1. **可见文本**经 research R4 深度归一化后精确相等（非空；无匹配 OCR → 不建可检索身份）；
2. **几何**为**被选 OCR bbox 中心**落入的固定网格单元（写/查同源；非 `target_region` 中心）；
3. **所属画面**仍用既有 `page_memories` + `fingerprint.py` 相似度；
4. 键格式 `eid-v1:g{G}|text|cell`（G 入前缀，改 G 旧键失配）；候选 ≥2 → 未命中；
5. 候选唯一后 **强制** `retrieval.match_element_template`（原则 III 准入条件 (c) 同构）；
6. 存量 **8 行** `element_memories` **整表作废**；**5 行** `page_memories` **保留**。

**复用硬约束**：`memory/fingerprint.py`、`memory/retrieval.py`（含
`match_element_template` / `find_best_page`）MUST 原样复用，MUST NOT 另起指纹或模板
匹配实现。改动集中在 `domain/memory.py`、`memory/identity.py`（新建纯函数）、
`memory/service.py`、`storage/database.py` + `repositories.py`、`config.py`；主循环
尽量零改动（见下文「主循环影响」）。

## Technical Context

**Language/Version**: Python 3.12（`vnc_agent/` uv 工程）

**Primary Dependencies**: 既有 — pydantic v2、opencv-python、numpy、SQLAlchemy 2 async
+ aiosqlite、unicodedata（stdlib）。**无新第三方依赖**（日文归一化用 stdlib NFKC +
确定性映射表，见 research.md）。

**Storage**: SQLite `element_memories` / `page_memories`（既有）。本 feature 为
`element_memories` 增加可检索身份列并作废旧自然语言主键行；`page_memories` 表结构与
5 行存量数据保留。迁移路径见「数据库变更与回滚」。

**Testing**: pytest + pytest-asyncio；扩展 `tests/unit/test_memory_*.py`；新增
`test_memory_identity.py`；e2e scenario 19 增加「换措辞仍命中」断言；离线 quickstart
用 artifacts 截图 + OCR fixture，不依赖真实 VNC。

**Target Platform**: 离线/CI + 既有 VNC 运行环境（Windows 被测端可选）

**Project Type**: 单进程模块化单体 Agent 库（Constitution 架构约束）

**Performance Goals**: 单次「身份解析 + 记忆查找 + 模板校验」p95 ≤ 50ms（SC-003），
计时样本 `SC003_MIN_SAMPLES=20`（不足 → `sc003_inconclusive`）；无新增模型调用。
正式验收由同一 `baseline/regression_suite_manifest.json` 上的度量脚本硬门禁
（tasks T034）：`hit_rate >= 0.30`（SC-001）；SC-002 三态（`hits≥20` 才判
`false_hit_rate <= 0.10`）；SC-003 三态（`n_latency≥20` 才判 `p95_ms <= 50`）；
MVP 单测命中>0 不得替代 T034。

**Constraints**:
- 复用 `fingerprint.py` / `retrieval.py`，禁止分叉。
- 不改 Planner/Grounder 协议；不新增模型调用。
- 不实现跨画面索引 / 画面版本管理（026）。
- 核心代码业务无关（Constitution VI）。
- 强制模板校验；多候选不消歧；整表作废旧元素行。

**Scale/Scope**: 8 行旧元素记忆、5 行页面记忆量级；身份网格默认 16×16（可配置）。

## Constitution Check

*GATE: Phase 0 前通过；Phase 1 设计后复检：通过。*

### 逐条对照 Core Principles

| 原则 | 结论 | 本 feature 如何满足 |
|------|------|---------------------|
| **I 确定性运行时控制** | ✔ | 身份解析、文本归一化、网格量化、OCR 等距字典序 tie-break、候选计数、模板阈值均为确定性纯函数/固定配置；不引入模型自主分支或无限重试；fail-open 不阻断主流程但 MUST 计 `identity_lookup_error`。 |
| **II 职责分离** | ✔ | 仅替换 Grounder 前置「目标是否同一」的检索键；Planner/Verifier/Executor 协议与职责不变。 |
| **III 键盘优先，视觉点击兜底** | ✔ | 不改优先级阶梯；记忆通道仍只在 `needs_grounding` 分支内。**不实现** III 新增的「已审批画面版本坐标索引直连」层级（属 026）。但本 feature **强制**在存储几何直点前走元素级模板校验，与 III 准入条件 **(c)** 同构（见下专节）。 |
| **IV 观察-执行-验证独立闭环** | ✔ | 记忆直点后独立验证照旧；`failed`/`uncertain` 计误命中并抑制本步复用（FR-008a）。 |
| **V 受控自进化** | ✔ | 仅更新允许的经验数据（页面/元素记忆）；不改断言/基线/模型；旧自然语言主键整表作废，避免噪声主键继续污染命中。 |
| **VI 业务无关核心** | ✔ | 归一化/身份/网格为通用脚本与几何规则；假名折叠表无 POS/收银业务词；用例中的日文标签仅出现在 fixture/YAML。 |

### 原则 III 准入条件 (c) 专节（元素级模板校验）

Constitution 1.3.0 原则 III 为「已审批画面版本坐标索引直连」规定准入条件 (c)：

> 点击前必须通过元素级模板校验（在记录坐标的邻域内重新确认该元素仍然存在）。

本 feature **不交付该索引层级**，但在 **015 元素记忆直点路径**上落实同一安全不变量：

1. 身份候选唯一（FR-003a）且页面 high 匹配后，**MUST** 调用既有
   `memory.retrieval.match_element_template`（邻域 = 历史 bbox ×
   `bbox_expand_ratio`，阈值 = `template_match_threshold`）；
2. 模板未达标 / 模板缺失 / 帧不可读 → **MUST NOT** 直点，仅可 medium 提示或回落
   Grounder；
3. **MUST NOT** 因连续成功、高置信或配置开关跳过模板（FR-007a / Clarification Q5）；
4. 审计 MUST 留下模板校验得分（及身份键），使「跳过 Grounder」可离线核对。

因此：**条件 (c) 的运行时证伪手段在本 feature 的记忆直点路径上强制成立**，并为 026
索引直连复用同一 `match_element_template` 闸门预留一致语义。

### Domain-Agnostic Core gate (Principle VI)

- [x] 核心模块不引入业务专用字段/关键词/分支
- [x] 业务语义仅出现在 testcase YAML / fixture / 离线 artifacts 样本说明
- [x] 通用身份能力至少用两个无关 GUI 场景验证（SC-006；plan：合成 TOTAL/MENU 场景 +
      真实日文 OCR fixture 场景）

### 工程与安全

- 无新模型调用；敏感区 mask 相交拒写（015 FR-005）保持。
- 索引直连可观测性字段（画面/版本 ID）属 026；本 feature 审计元素身份 + 页面 ID +
  模板分 + 跳过的 grounder 调用。

## Project Structure

### Documentation (this feature)

```text
specs/025-element-identity-key/
├── spec.md
├── plan.md              # 本文件
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── element-identity.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks（未在本阶段创建）
```

### Source Code（相对 `vnc_agent/`）

```text
src/vnc_agent/
├── config.py                 # MemoryConfig + identity_enabled / grid / schema 版本
├── domain/memory.py          # ElementMemory + identity 字段；Lookup 审计扩展（additive）
├── memory/
│   ├── fingerprint.py        # REUSE ONLY — 禁止分叉
│   ├── retrieval.py          # REUSE ONLY — match_element_template / find_best_page
│   ├── identity.py           # NEW：normalize_visible_text / geom_cell / resolve_*
│   └── service.py            # 写/查改走身份键；仍调用 fingerprint+retrieval
├── storage/
│   ├── database.py           # ElementMemoryRow + identity_key 列；迁移辅助
│   └── repositories.py       # find_elements_by_identity；作废旧行 API
├── runtime/
│   ├── agent_runtime.py      # 默认不改控制流；仅当审计字段需透出时 additive 映射
│   └── telemetry.py          # additive：identity_ambiguous / false_hit 计数（可选）
└── reporting/                # 仅当 audit 新字段需 JSON 透出时 additive

tests/
├── unit/test_memory_identity.py    # NEW：归一化表、网格、多候选、换措辞命中
├── unit/test_memory_store.py       # 更新：按身份 upsert / 旧行不可命中
├── unit/test_memory_retrieval.py   # 保持：仍测 match_element_template 契约
├── e2e/test_scenario_19_*.py       # 扩展：换措辞 + identity 开启
└── contract/test_element_identity_cross_scenario.py  # SC-006
```

**Structure Decision**: 单包 `vnc_agent` 内扩展；纯函数放 `memory/identity.py`，与
015 的 fingerprint/retrieval 分层一致；持久化变更仅 memory 表与 repository。

## 关键设计

### 1. 身份键（逻辑）

```text
identity_key = f"{schema_version}:g{G}|{normalized_visible_text}|{geom_cell}"
# 例：eid-v1:g16|小計|13,13
# 同 page_id 下 identity_key 唯一可检索
# geom_cell = f"{col},{row}"，col/row = floor(cx/w * G), floor(cy/h * G)，G 默认 16
# cx,cy MUST 来自被选中 OCR 项的 bbox 中心（与查询侧同源）
# 选不出可见文本 OCR → 不建立可检索身份（无空文本键）
```

`schema_version` 默认 `eid-v1`。键前缀 MUST 含 `g{G}`，故改 `identity_grid_size`
后旧键自动失配，且 `purge_legacy_element_memories` 的「非当前 schema 前缀」条件会
覆盖 G 变更，无需单独记忆「改 G 要手增 schema」。归一化规则语义变更时仍 MUST 递增
`schema_version`（如 `eid-v2`）。

### 2. 写入路径（`record_success`）

1. `build_page_fingerprint` + page upsert（**复用** fingerprint / 既有 `_upsert_page`）。
2. 以 `target_region` 中心**仅**在 `ocr_items` 中选最近非动态、归一化非空的 OCR 项；
   中心距并列时 MUST 按 `(normalize_visible_text(text), (x1,y1,x2,y2))` 字典序取第一条
   （research R3；不依赖输入顺序）。同时将 `target_region` 存为 `ElementMemory.bbox`
   供模板邻域。选不出 OCR → 跳过可检索写入。
3. 由**被选 OCR 的 bbox 中心**算 `geom_cell`（MUST NOT 用 `target_region` 中心）；
   `normalize_visible_text(OCR 文本)` → 组装 `identity_key`（含 `g{G}`）。
4. `repo.find_elements_by_identity(page_id, identity_key)`：0 → 新建；1 → 更新统计/
   模板；≥2 → 不合并，记日志并跳过可检索写入（数据损坏防护）。
5. `target_label` 仍保存**本轮线索原文归一化前/后审计串**，**不再**作为唯一索引。

### 3. 查询路径（`lookup`）

1. 指纹 + `find_best_page`（**复用**）；low/none → None。
2. 从 `(target_label, screen.ocr_items, resolution)` **解析候选身份集合**
   （research：线索→可见文本抽取 + 可选几何）。
3. 对每个候选 identity_key 查库，合并结果：
   - 0 条 → 未命中；
   - ≥2 条（跨候选或同键脏数据）→ `identity_ambiguous`，返回 None（或 medium 且
     element=None，**禁止**直点）；
   - 恰 1 条 → 进入模板。
4. `level==high` 时 **强制** `match_element_template`（**复用**）；成功才
   `matched_bbox` + high 直点授权。

公开方法签名保持：

```python
async def lookup(self, screen, target_label, *, exclude_element_ids=...) -> MemoryLookupResult | None
async def record_success(self, screen, target_label, target_region) -> None
```

以便 **runtime 主循环零改控制流**。

### 4. 开关

`MemoryConfig` 新增：

| 字段 | 默认 | 含义 |
|------|------|------|
| `identity_enabled` | `true` | `false` 时走旧 `normalize_target_label` + `find_element(page, label)` 路径（合入前语义）；与 `memory.enabled=false` 总开关兼容 |
| `identity_grid_size` | `16` | 归一化网格每轴格数 G |
| `identity_schema_version` | `"eid-v1"` | 与 `g{G}` 组成键前缀 `eid-v1:g16` |

### 5. 存量数据结论（实测库）

| 表 | 行数 | 处理 |
|----|------|------|
| `element_memories` | **8** | **整表作废**：迁移时 `DELETE` 全部行，并删除对应 `artifacts/memory/templates/*.png`（或移入 `templates/legacy_invalid/`）。旧 `target_label` 无法可靠反推 eid-v1 身份。 |
| `page_memories` | **5** | **保留**：页面指纹算法未变，仍服务页面匹配；不放行任何旧元素主键。 |

启用 `identity_enabled=true` 的首次启动/迁移脚本执行作废；之后仅新身份写入可命中。

### 6. 数据库变更与可回滚迁移

项目现用 `Base.metadata.create_all`（无 Alembic）。采用 **显式、可回滚** 步骤：

**Forward（v025）**

1. 备份：`COPY element_memories` → `element_memories_legacy_015`（同库新表或
   `artifacts/memory/migrations/2026-08-06-element_memories.jsonl` 导出 8 行 payload）。
2. `ALTER TABLE element_memories ADD COLUMN identity_key VARCHAR(640) DEFAULT ''`；
   创建索引 `(page_id, identity_key)`。
3. `DELETE FROM element_memories`（作废 8 行）；清理模板文件。
4. 代码只写入带非空 `identity_key` 且前缀匹配当前 `{schema_version}:g{G}` 的行；
   查找过滤 `identity_key == ''`、缺失字段或前缀不匹配（双保险）。

**Rollback**

1. 代码回退到 015 标签路径（或 `identity_enabled=false` + 旧二进制）。
2. `DELETE FROM element_memories`（清空可能已写入的新身份行）。
3. 从 `element_memories_legacy_015` / JSONL **原样插回** 8 行。
4. 可选：`identity_key` 列保留（可空，旧代码忽略）或 `DROP COLUMN`（SQLite 需表重建，
   脚本提供）。

**page_memories**：不修改 schema，不删 5 行。

### 7. 可观测性

- 成功直点：既有 `element_memory_hit` + `model_call_skipped(grounder)`；audit 增加
  `identity_key`、`geom_cell`、`normalized_visible_text`（additive）。
- 新计数（telemetry additive）：
  - `identity_ambiguous`（多候选未命中）
  - `element_memory_false_hit`（直点后 verify failed|uncertain）
  - **`identity_lookup_error`**（解析/查找异常被 fail-open 吞掉；MUST 与
    insufficient/miss 可区分；audit `resolution_status=error`）
- 耗时：`memory_identity_lookup_ms` 样本 → p50/p95，支撑 SC-003（`SC003_MIN_SAMPLES=20`）。

### 8. 验收度量门禁（与 Spec SC / tasks T034 一致）

同一 `baseline/regression_suite_manifest.json`：

| SC | 门禁 |
|----|------|
| SC-001 | `hits>0` 且 `hit_rate ≥ 0.30` |
| SC-002 | `hits==0` 跳过；`0<hits<20` → `sc002_inconclusive`；`hits≥20` → `false_hit_rate≤0.10` |
| SC-003 | `n_latency<20` → `sc003_inconclusive`；`n_latency≥20` → `p95_ms≤50` |
| SC-004 | `identity_enabled=false` / `memory.enabled=false` 行为任务（T026–T028） |
| SC-005 | 复用模块无分叉 + 命中路径跳过 grounder（T028/T033/T037） |
| SC-006 | 两无关 fixture 各 hit>0（T032） |

### 9. 主循环影响（`agent_runtime.py`）

**目标：不改控制流。**

| 触点 | 预期 |
|------|------|
| `PageElementMemory.lookup` / `record_success` 调用点 | 签名不变 → **无需改** |
| `MemoryHitAudit` 构造 | 若新增 additive 字段：仅多传 2～3 个可选 kwargs（默认空） |
| 直点 / 失败回写分支 | 条件仍是 `level=="high" and matched_bbox` → **不改** |

若实现阶段发现 audit 字段必须透出且构造处无法默认填充，允许 **≤15 行** additive 映射；
**禁止** 在主循环内重写身份解析逻辑。

**回滚主循环**：还原那一处 audit 字段赋值即可；记忆行为由 `identity_enabled=false`
或代码回退接管。

## Complexity Tracking

> 无 Constitution 违规需豁免。下列为有意的范围控制，非违规。

| 决策 | 原因 | 更简方案为何不用 |
|------|------|------------------|
| 新建 `memory/identity.py` | 与 fingerprint/retrieval 一样保持纯函数可单测 | 全塞进 service 会难测且膨胀 |
| 保留 `target_label` 列 | 审计/016 回放线索兼容 | 立刻删列迫使 runtime/replay 大改 |
| 整表删除 8 行元素 | 澄清 Q4；旧键不可靠 | 惰性迁移会误命中 |
| OCR 中心作 geom 锚点 | 查询侧仅有 OCR 几何 | region 中心写/OCR 查 → 第二代零命中 |
| G 编入键前缀 | 改 G 静默错命中 | 仅靠人工递增 schema |
| 无纯图标可检索键 | 查询侧不可达 | 污染 SC-001 分母 |

## Phase 0 / Phase 1 产出

| 文件 | 状态 |
|------|------|
| [research.md](./research.md) | 决策 + R4 归一化 + OCR 锚点/tie-break + 正反例 |
| [data-model.md](./data-model.md) | 实体、键格式 `eid-v1:g16|…`、校验 |
| [contracts/element-identity.md](./contracts/element-identity.md) | 纯函数/服务/purge/fail-open 计数 |
| [quickstart.md](./quickstart.md) | 离线 paraphrase + T034 正式门禁 |
| [tasks.md](./tasks.md) | 41 任务（含 T018a 锚点金样、T034 三态） |
| [checklists/memory-hit-correctness.md](./checklists/memory-hit-correctness.md) | 66/66 需求质量门禁通过 |

**Constitution Check（设计后复检）**: 仍通过；无新增违规。

## 下一步

设计已收敛；实现请按 [tasks.md](./tasks.md) 顺序：`/speckit-implement`  
（先 T001–T003 度量基线，再代码；正式验收过 T034）。
