# Tasks: 结构化元素身份主键（element-identity-key）

**Input**: Design documents from `/specs/025-element-identity-key/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: 每个 User Story 均含至少一条**离线回归测试**任务。

**Organization**: 度量基线（禁止改业务代码）→ 纯函数/配置 → 数据模型与仓库（串行）→ **独立迁移** → US3→US1→US2→US4→US5→US6 → Polish（含 SC 硬门禁）。任务总数 **41**（T001–T040 + T018a）。

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: 可并行（不同文件、无未完成依赖）
- **[Story]**: 仅用户故事阶段标记 `[US1]`…`[US6]`
- 数据模型变更与依赖它的 service 改动 **MUST NOT** 标 `[P]` 并行

## Path Conventions

工作根：`vnc_agent/`（源码 `src/vnc_agent/`，测试 `tests/`）。规格产物：`specs/025-element-identity-key/`。

---

## Phase 1: 度量基线（Metric Baseline）— 禁止改业务代码

**Purpose**: 在任何身份主键代码改动前，用与 SC-001/002/003 **同一输入清单**固化基线。  
**Independent Test**: pre JSON 存在；`element_memory_hits==0` 且 `hit_rate==0`；manifest 固定且 pre/post 强制共用。

- [x] T001 编写 `vnc_agent/scripts/measure_element_memory_baseline.py` 与固定清单 `specs/025-element-identity-key/baseline/regression_suite_manifest.json`（run 报告路径和/或离线 fixture 查询项；**禁止**无 manifest 时静默换样本）。输出 JSON 至少含：`lookup_attempts`、`element_memory_hits`、`hit_rate`（hits/attempts，attempts=0→0）、`false_hits`、`false_hit_rate`（false_hits/hits，hits=0→null）、`lookup_latency_ms` 样本、`p50_ms`、`p95_ms`、`manifest_path`、时间戳
- [x] T002 运行 T001（`--manifest specs/025-element-identity-key/baseline/regression_suite_manifest.json`），存档 `specs/025-element-identity-key/baseline/element_memory_hits_pre_025.json`；**门禁**：`element_memory_hits == 0` 且 `hit_rate == 0`
- [x] T003 编写 `specs/025-element-identity-key/baseline/README.md`：manifest 含义；公式 `hit_rate`/`false_hit_rate`；正式门禁 **SC-001 hit_rate≥0.30**、**SC-002 三态**（`hits==0` 不适用；`0<hits<20` → `sc002_inconclusive` 非通过非失败；`hits≥20` → `false_hit_rate≤0.10`）、**SC-003 三态**（计时样本 `<20` → `sc003_inconclusive`；`≥20` → `p95_ms≤50`；`SC003_MIN_SAMPLES=20`）；pre/post 同 manifest；后测指向 T034

**Checkpoint**: 无业务源码 diff；manifest + pre JSON + README 可引用。

---

## Phase 2: Foundational — 纯函数与配置

**Purpose**: 身份纯函数 + 配置；**不改** `service.py` 热路径、**不改** DB 业务行。  
**⚠️ CRITICAL**: 完成前不得进入迁移或 User Story 实现。

- [x] T004 新建 `vnc_agent/src/vnc_agent/memory/identity.py`：`normalize_visible_text`（research R4 固定顺序）、`geom_cell_from_center`、`build_identity_key(*, schema_version, grid_size, normalized_visible_text, geom_cell)`，键格式 **`{schema_version}:g{G}|{text}|{cell}`**（例 `eid-v1:g16|小計|13,13`；`G` MUST 进前缀，改 G 旧键失配）
- [x] T005 [P] 在 `vnc_agent/tests/unit/test_memory_identity.py` 写入 research R4 金样：全半角、半角片假名、长音、空白、大小写、`小計`≠`小計解除`、`1金券`≠`金券`、**纯符号** `×`/`／`/`--`、`pre-paid`（ASCII `-` 不改长音）、空串；并隐式锁定 R4 流水线顺序（NFKC→浊点→长音→casefold→空白）
- [x] T006 [P] 在 `vnc_agent/tests/unit/test_memory_identity.py` 增加网格单测：以 **OCR bbox 中心**（非 target_region）为 `cx,cy`，1024×768 下 `小計` 类中心 → 预期 cell；边界夹紧；G=16 与 G=32 时 `build_identity_key` 前缀分别为 `:g16` / `:g32`；**等距 tie-break**：两 OCR 到 region 中心距离相同、文本/bbox 不同时，乱序 `ocr_items` 两次调用 `resolve_identity_for_write` 选出同一项且 `geom_cell`/`identity_key` 稳定
- [x] T007 在 `vnc_agent/src/vnc_agent/config.py` 的 `MemoryConfig` 增加 `identity_enabled`（默认 true）、`identity_grid_size`（16）、`identity_schema_version`（`eid-v1`）；同步项目既有 agent YAML 中 `memory` 段（若存在）；运行时当前前缀=`{schema}:g{G}`
- [x] T008 固化 `vnc_agent/tests/fixtures/memory/identity_ocr_samples.json`（research R5 正反例；仅 fixture，无核心业务词分支）

**Checkpoint**: `pytest tests/unit/test_memory_identity.py -q` 绿；R4 金样含纯符号；键含 `g{G}`；`fingerprint.py`/`retrieval.py` 零修改。

---

## Phase 3: 数据模型与仓库（串行 — 禁止与 service 并行）

**Purpose**: 持久化身份键 API；**尚未**改 `service.py` 命中语义。

- [x] T009 扩展 `vnc_agent/src/vnc_agent/domain/memory.py`：`ElementMemory` 增加 `identity_key`/`normalized_visible_text`/`geom_cell`/`identity_schema_version`；`MemoryLookupResult`/`MemoryHitAudit` additive 可选字段（data-model.md）；可检索键要求非空文本分量
- [x] T010 扩展 `vnc_agent/src/vnc_agent/storage/database.py`：`ElementMemoryRow.identity_key` 列（VARCHAR(640) 默认可空串）+ 索引；保持 `create_all` 兼容
- [x] T011 扩展 `vnc_agent/src/vnc_agent/storage/repositories.py`：`find_elements_by_identity`、`save_element` 同步列与 payload、`purge_legacy_element_memories()`——删除 `identity_key` 为空或**前缀不是当前** `{identity_schema_version}:g{identity_grid_size}` 的行（改 G / 改 schema 均覆盖）；**保留** `find_element(page_id, target_label)` 供关开关路径

**Checkpoint**: 仓库方法可单测；purge 按 `schema:gG` 前缀过滤；T009→T010→T011→（后续 T017）严格串行。

---

## Phase 4: 数据迁移（与功能代码分离）

**Purpose**: 整表作废 8 行旧 `element_memories`；保留 `page_memories`。  
**Independent Test**: 备份可还原；element 可命中集空；page 行保留。

- [x] T012 **迁移前备份** `vnc_agent/data/vnc_agent.db` → `vnc_agent/artifacts/memory/migrations/2026-08-06/vnc_agent.db.bak`（或带时间戳），校验非空
- [x] T013 导出 `element_memories` 全量 → `vnc_agent/artifacts/memory/migrations/2026-08-06/element_memories_legacy_015.jsonl`（回滚用；预期 8 行）
- [x] T014 实现并执行 `vnc_agent/scripts/migrate_element_identity_025.py`：确保 `identity_key` 列存在后 `DELETE` 全部旧 `element_memories`（015 自然语言主键行，无 `eid-v1:g*` 前缀）；模板移至 `artifacts/memory/templates/legacy_invalid/` 或删除；**不删** `page_memories`。后续新写入键形如 `eid-v1:g16|…`
- [x] T015 离线校验 `vnc_agent/tests/unit/test_memory_migration_025.py`：临时库跑迁移；assert element 可命中集空、page 保留、JSONL 行数匹配

**Checkpoint**: DB 已备份；旧 8 行不参与命中；5 行 page 仍在；新键格式与 purge 前缀约定已就绪。

---

## Phase 5: User Story 3 — 写入与查询统一身份主键 (P1) 🎯 MVP 内核

**Goal**: 写/查以 `identity_key` 为准，不再以 `strip/lower(target_label)` 为唯一主键；写查几何锚点同源。  
**Independent Test**: 写入后按身份查到同一条；写/查 `geom_cell` 逐字相等；查询不靠标签串 alone。

- [x] T016 [US3] 在 `vnc_agent/src/vnc_agent/memory/identity.py` 实现 `resolve_identity_for_write` 与 `resolve_identity_candidates_for_lookup`（contracts + research R3）：**写入**时 `target_region` 中心**仅**用于在 `ocr_items` 中选最近非动态 OCR，并可将 region 存为模板 bbox；中心距并列时 MUST 按 `(normalize_visible_text(text), (x1,y1,x2,y2))` 字典序取第一条（不依赖输入顺序）；**`geom_cell` MUST 取自被选 OCR 的 bbox 中心**（MUST NOT 用 region 中心）；选不出 OCR → 返回 `None`（跳过可检索写入）。**查询**时对各匹配 OCR 同样用其 bbox 中心算 `geom_cell`；`L` 空或无 OCR 匹配 → insufficient
- [x] T017 [US3] 改 `vnc_agent/src/vnc_agent/memory/service.py`：`record_success` 按身份 upsert（`None` 则跳过可检索写入，可仍 upsert 页面）；`lookup` 在 `identity_enabled=true` 时按身份检索；**强制** `match_element_template`（禁止跳过）；`identity_enabled=false` 走 015 标签路径；**复用** `fingerprint`/`retrieval` 不得分叉
- [x] T018 [US3] 离线回归：`vnc_agent/tests/unit/test_memory_store.py` 或 `test_memory_identity.py` — 写入后 `find_elements_by_identity` 命中；标签串不同但身份同则更新同一行；选不出 OCR 时不写入可检索行
- [x] T018a [US3] **锚点同源金样**（`vnc_agent/tests/unit/test_memory_identity.py`）：同一控件构造 `target_region` + 匹配 OCR（中心可故意偏离 region 中心跨格边界），分别调用 `resolve_identity_for_write` 与 `resolve_identity_candidates_for_lookup`，**断言两侧 `geom_cell` 字符串逐字符相等**（以及同源时 `identity_key` 一致）。**不得**仅断言「最终 lookup 命中」——锚点不一致时表现为未命中，与其他失败原因无法区分；本任务唯一目的是单独暴露「写/查几何锚点异源」失效模式

**Checkpoint**: US3 单测绿，含 T018a 写查 `geom_cell` 相等；无纯图标/空文本可检索写入。

---

## Phase 6: User Story 1 — 不同措辞下复用同一控件记忆 (P1)

**Goal**: 措辞变化仍解析到同一身份，模板通过后可直点授权。  
**Independent Test**: 写短标签 → lookup 长描述 → `level==high` 且 `matched_bbox` 非空。

- [x] T019 [US1] 在 `vnc_agent/src/vnc_agent/memory/identity.py` 完善 lookup 线索抽取，与 research R3 查询一致：`L=normalize(target_label)`；精确匹配 OCR → 以其 bbox 中心算 cell；若空且 L 较长则唯一最长整词 OCR 边界匹配；多 OCR → ambiguous；禁止子串模糊相等；覆盖 fixture `小計` / 长描述类样本
- [x] T020 [US1] 在 `vnc_agent/src/vnc_agent/memory/service.py` 的 `_lookup` 中确保：身份唯一 + 页面 high + 模板达标 → high/`matched_bbox`；模板失败不直点且审计可区分「身份命中模板未过」
- [x] T021 [US1] 离线回归：`vnc_agent/tests/unit/test_memory_identity.py::test_write_identity_lookup_with_paraphrased_label_hits`（`@pytest.mark.identity_paraphrase_hit`）

**Checkpoint**: `uv run pytest -m identity_paraphrase_hit -q` 绿（演示用，≠ SC-001 正式验收）。

---

## Phase 7: User Story 2 — 不同控件绝不误并 (P1)

**Goal**: 同文案不同网格 / 候选 ≥2 → 未命中。  
**Independent Test**: 双 cell 同文案不合并；模糊查询不点错。

- [x] T022 [US2] 在 `vnc_agent/src/vnc_agent/memory/service.py` / `identity.py` 落实 FR-003a：候选 ≥2 → 未命中 + `identity_ambiguous` 审计；禁止最近成功/序数消歧
- [x] T023 [US2] 离线回归：`vnc_agent/tests/unit/test_memory_identity.py` — `test_ambiguous_same_text_two_cells_no_hit` 与 `test_different_cells_not_merged_on_write`

**Checkpoint**: 防误并单测绿。

---

## Phase 8: User Story 4 — 存量记忆安全过渡 (P1)

**Goal**: 旧自然语言主键不可被新路径命中（迁移 + 代码双保险）。  
**Independent Test**: 注入空 `identity_key` 旧形态行 → lookup 不命中。

- [x] T024 [US4] 在 `vnc_agent/src/vnc_agent/memory/service.py` lookup 过滤：`identity_key` 为空、缺失、或**前缀不是当前** `{identity_schema_version}:g{identity_grid_size}` 的行（含改 G 后的旧键；与 purge 一致）
- [x] T025 [US4] 离线回归：`vnc_agent/tests/unit/test_memory_migration_025.py` 或 `test_memory_store.py` — 015 legacy 行与错误 `g{G}` 前缀行均不可 hit

**Checkpoint**: 新旧混用 / 改 G 后旧键无法直点。

---

## Phase 9: User Story 5 — 开关与回归安全 (P1)

**Goal**: `identity_enabled=false` 与 `memory.enabled=false` 行为安全（SC-004）。  
**Independent Test**: 关身份开关无新身份逻辑副作用；总开关关闭无记忆读写。

- [x] T026 [US5] 核实 `service.py` 双路径完整；`vnc_agent/src/vnc_agent/runtime/agent_runtime.py` **不改控制流**（仅当 audit 需透出时 additive 映射 ≤15 行；禁止 runtime 内嵌身份解析）
- [x] T027 [US5] 离线回归：扩展 `vnc_agent/tests/e2e/test_scenario_19_page_element_memory.py` 或单测 — `identity_enabled=false` 时不产生新身份 audit/解析日志路径（旧行已 purge 则命中可为 0，但**不得**走 eid 键逻辑）；`memory.enabled=false` 既有用例保持绿
- [x] T028 [US5] 跑 `vnc_agent/tests/unit/test_memory_retrieval.py` + `test_memory_fingerprint.py` 确认复用模块无回归

**Checkpoint**: 关闭开关无新身份主键行为泄漏。

---

## Phase 10: User Story 6 — 命中、误命中与开销可观测 (P2)

**Goal**: 为 SC-002/SC-003 提供可采集信号。  
**Independent Test**: 字段级可断言；批次门禁在 T034。

- [x] T029 [US6] 扩展 `vnc_agent/src/vnc_agent/runtime/telemetry.py`：additive `identity_ambiguous`、`element_memory_false_hit`、**`identity_lookup_error`**；lookup 路径记录 `memory_identity_lookup_ms`；`service.lookup`/`record_*` 异常 fail-open 时 MUST 递增 `identity_lookup_error` 并写 `resolution_status=error`（contracts §3/§6）
- [x] T030 [US6] 在 `vnc_agent/src/vnc_agent/memory/service.py` 与 runtime 回写路径：直点成功 audit 填 `identity_key`/模板分；直点后 verify `failed`|`uncertain` → `element_memory_false_hit`+1（FR-008a）；模板未通过未直点 **不计** false_hit；调用既有 `record_element_failure`
- [x] T031 [US6] 离线回归：`vnc_agent/tests/unit/test_memory_identity.py`（必要时 e2e）断言 hit/false_hit/ambiguous/**identity_lookup_error**/耗时≥0；注入异常时 error 计数 +1 且 **不**与正常 miss 混计；报告 additive 兼容；**不**在此宣称 SC-002/003 批次通过

**Checkpoint**: 度量信号可采集；字段单测绿。

---

## Phase 11: Polish & SC 硬门禁验收

**Purpose**: SC-001/002/003 硬门禁、SC-006、VI、quickstart、回滚文档。  
**Independent Test**: post JSON 相对同一 manifest 过三条阈值。

- [x] T032 [P] 新增 `vnc_agent/tests/contract/test_element_identity_cross_scenario.py`：两套无关 OCR/几何 fixture 各「写入→命中」一次（SC-006）
- [x] T033 [P] 更新 `vnc_agent/tests/e2e/test_scenario_19_page_element_memory.py`：身份开启下第二跑 grounder 跳过 + paraphrase 可选
- [x] T034 **SC-001/002/003 正式度量门禁**：同一 `baseline/regression_suite_manifest.json` 复跑 `vnc_agent/scripts/measure_element_memory_baseline.py` → `specs/025-element-identity-key/baseline/element_memory_hits_post_025.json`；用 `vnc_agent/scripts/assert_sc_metrics_025.py`（或脚本内 assert）判定：**(SC-001)** `hits>0` 且 `hit_rate>=0.30` 否则失败；**(SC-002 三态)** `hits==0` → 本条跳过；`0<hits<20` → `sc002_inconclusive`（非通过非失败）；`hits≥20` → `false_hit_rate<=0.10` 否则失败；**(SC-003 三态，与 Spec `SC003_MIN_SAMPLES=20` 一致)** 计时样本数 `n_latency`：`n_latency<20` → `sc003_inconclusive`（非通过非失败）；`n_latency≥20` → 要求 `p95_ms<=50` 否则失败。pre/post 对照写入 `baseline/README.md`。**MVP 单测命中>0 不得替代**
- [x] T035 执行 quickstart：`cd vnc_agent && uv run pytest -m identity_paraphrase_hit -q`，结果记入 `baseline/README.md`
- [x] T036 [P] Constitution VI：对 `vnc_agent/src/vnc_agent/memory/identity.py`、`service.py` grep 业务词（POS/收银/商品等）须无命中；日文仅 tests/fixtures
- [x] T037 确认 `vnc_agent/src/vnc_agent/memory/fingerprint.py` 与 `retrieval.py` 相对本 feature **无行为分叉**（diff 仅注释或未改）
- [x] T038 核对 `specs/025-element-identity-key/quickstart.md` 命令/测试名与「正式验收=T034」说明一致
- [x] T039 全量：`cd vnc_agent && uv run pytest tests/unit/test_memory_*.py tests/unit/test_memory_migration_025.py tests/contract/test_element_identity_cross_scenario.py tests/e2e/test_scenario_19_page_element_memory.py -q`
- [x] T040 回滚说明 `vnc_agent/artifacts/memory/migrations/2026-08-06/ROLLBACK.md`（`.bak`+JSONL 恢复 element；`identity_enabled=false`）

---

## Phase 12: Convergence

**Purpose**: Close remaining gaps between marked-complete T001–T040 and the live codebase (converge 2026-08-06). Offline unit/contract identity suite is green (20 passed); e2e + SC formal gate + FR-013 CounterEvent wiring are not.

- [x] T041 **CRITICAL** Align `vnc_agent/tests/e2e/test_scenario_19_page_element_memory.py` with identity write/query semantics per US1 / T033 / T039 (`partial`): under `identity_enabled=true`, run-1 currently writes identity from nearest OCR text `TOTAL` while planner/lookup clue is `OK` → run-2 never hits memory (2 failed: `test_second_run_hits_memory_with_zero_grounder_calls`, `test_memory_hit_failing_verification_bans_element`). Fix fixture/OCR/planner so write and lookup resolve the **same non-empty identity text** (e.g. OCR label on the target matches the planner `target.text` / lookup clue, or switch both sides to the same visible token); keep second-run **zero grounder calls** + `element_memory_hit` + ban-on-false-verify behavior. Re-run the two failing tests until green. Do **not** “fix” by setting `identity_enabled=false` for the happy path.
- [x] T042 Wire SC-001 post measure path per SC-001 / T034 (`partial`): extend `vnc_agent/scripts/measure_element_memory_baseline.py` so post runs can seed (or open) a real identity store—write identity for the manifest OCR fixture then count `element_memory_hits` when lookup resolves the same `identity_key` (hits must be able to be >0; pre-mode may stay hits=0). Produce `specs/025-element-identity-key/baseline/element_memory_hits_post_025.json`; run `vnc_agent/scripts/assert_sc_metrics_025.py --post …` and require SC-001 pass (`hits>0` and `hit_rate≥0.30`); SC-002/003 may remain three-state inconclusive if sample floors unmet. Update `baseline/README.md` with post results/commands. **Must not** claim SC-001 from unit-only paraphrase hit.
- [x] T043 Register and emit FR-013 CounterEvents per FR-013 / contracts §6 / T029–T030 (`missing`): in `vnc_agent/src/vnc_agent/runtime/telemetry.py` add `CounterKind` + `_REQUIRED_PAYLOAD_KEYS` for `identity_ambiguous`, `identity_lookup_error`, and `element_memory_false_hit` (and optional latency fields if needed). Emit real `CounterEvent`s (not only `log_event`) from `memory/service.py` fail-open / ambiguous paths and from `agent_runtime.py` when a memory direct click’s independent verify is `failed`|`uncertain` (FR-008a). Ensure unknown-kind validator no longer blocks these kinds.
- [x] T044 Populate success-hit audit identity fields per FR-013 / data-model `MemoryHitAudit` (`partial`): when constructing `MemoryHitAudit` in `vnc_agent/src/vnc_agent/runtime/agent_runtime.py` (memory direct-click branch ~L1684), set `identity_key` / `geom_cell` / `normalized_visible_text` from `memory_lookup` / `element` (additive; keep existing fields). Prefer mapping from `MemoryLookupResult` rather than re-resolving identity in runtime (T026: no embedded identity parse in runtime).
- [x] T045 Record lookup path latency per T029 / SC-003 (`partial`): on each `PageElementMemory.lookup` attempt, record elapsed ms (e.g. `memory_identity_lookup_ms` on result, stage measurement, or log field) so SC-003 / measure samples can use real lookup+template path cost, not only pure-function resolve time.
- [x] T046 Offline regression for FR-013 counters per T031 (`partial`): unit (or e2e) assertions that (1) injected exception on lookup increments `identity_lookup_error` (and does not mix with normal miss), (2) ambiguous path yields `identity_ambiguous`, (3) memory direct click + verify `failed`/`uncertain` yields `element_memory_false_hit` and does **not** count false_hit when template fails without direct click. Re-run scenario 19 ban test after T041/T043.
- [x] T047 [P] Register pytest mark `identity_paraphrase_hit` (or document in `pytest.ini` / `pyproject.toml`) per T021 / T035 (`partial`): eliminate `PytestUnknownMarkWarning` so `pytest -m identity_paraphrase_hit` is a first-class quickstart gate.

---

## Dependencies & Execution Order

```text
Phase 1 Baseline
    → Phase 2 Foundational
    → Phase 3 Data model/repo (T009→T010→T011 serial)
    → Phase 4 Migration (T012→T013→T014→T015)
    → Phase 5 US3 (write/lookup identity)
    → Phase 6 US1 / Phase 7 US2 / Phase 8 US4  (after US3)
    → Phase 9 US5
    → Phase 10 US6
    → Phase 11 Polish + T034 gates
```

| 规则 | 说明 |
|------|------|
| 基线优先 | T001–T003 完成前禁止业务代码任务 |
| 模型↛service 并行 | T009→T010→T011→T017 禁止 `[P]` |
| US3 先于 US1/US2 | 写查主键是命中/消歧前提 |
| 排除范围 | **无任务**实现跨画面索引或画面版本管理（FR-012 / 026） |

### User Story 独立验收

| Story | 离线验证 |
|-------|----------|
| US3 | T018 写查同键；**T018a 写查 geom_cell 逐字相等** |
| US1 | T021 paraphrase hit |
| US2 | T023 ambiguous / 不合并 |
| US4 | T015 + T025 legacy 不可 hit |
| US5 | T027–T028 开关与复用模块 |
| US6 | T031 字段；**T034** 批次 SC-002/003 |

### Parallel Opportunities

| 可并行 | 不可并行 |
|--------|----------|
| T005 ∥ T006 ∥ T008（T004 之后） | T009 → T010 → T011 → T017 |
| T032 ∥ T033 ∥ T036 | T012 → T013 → T014 → T015 |
| | T001–T003 完成前的一切业务任务 |

### Parallel Example: Foundational tests

```bash
# After T004:
Task: "R4 golden tests in tests/unit/test_memory_identity.py"
Task: "Grid cell tests in tests/unit/test_memory_identity.py"
Task: "Fixture tests/fixtures/memory/identity_ocr_samples.json"
```

---

## Implementation Strategy

### MVP（演示）

1. Phase 1 基线  
2. Phase 2–4 基础 + 迁移  
3. Phase 5 US3 + Phase 6 US1  
4. **STOP（演示）**：T021 命中 >0 — **不等于** SC-001 正式验收  

### 增量

US2 → US4 → US5 → US6 → Polish + **T034 三门禁**

### SC 度量门禁速查

| SC | 门禁 | 任务 |
|----|------|------|
| SC-001 | 同 manifest：`hits>0` 且 `hit_rate≥0.30` | T001–T003 定义；**T034 assert** |
| SC-002 | 同 manifest：三态（`<20` inconclusive；`≥20` 则 `false_hit_rate≤0.10`） | T029–T031 信号；**T034 assert** |
| SC-003 | 同 manifest：三态（计时样本 `<20` inconclusive；`≥20` 则 `p95_ms≤50`） | T029 计时；**T034 assert** |
| SC-004 | 关开关一致 | T026–T028 |
| SC-005 | 无新协议/模型角色；复用无分叉 | T028, T033, T037 |
| SC-006 | ≥2 无关场景命中 | T032 |

### 任务数汇总

| 阶段 | ID | 数量 |
|------|-----|------|
| Phase 1 基线 | T001–T003 | 3 |
| Phase 2 基础 | T004–T008 | 5 |
| Phase 3 模型/仓库 | T009–T011 | 3 |
| Phase 4 迁移 | T012–T015 | 4 |
| US3 | T016–T018, **T018a** | **4** |
| US1 | T019–T021 | 3 |
| US2 | T022–T023 | 2 |
| US4 | T024–T025 | 2 |
| US5 | T026–T028 | 3 |
| US6 | T029–T031 | 3 |
| Polish | T032–T040 | 9 |
| **合计** | T001–T040 + **T018a** | **41** |

---

## Notes

- 复用硬约束：不得重写 `memory/fingerprint.py`、`memory/retrieval.match_element_template`。
- **T012 备份 DB** 为迁移门禁；无基线或未过 **T034** 不得宣称 SC-001/002/003 通过。
- 全部任务格式：`- [ ] Tnnn ...` + 路径；T018a 为锚点同源专用断言（规格修订 1e）。
