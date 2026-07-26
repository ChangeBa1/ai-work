# Tasks: 页面记忆与元素记忆（page-element-memory）

**Input**: spec.md / plan.md（本目录）
**Prerequisites**: main 已含 feature 008~014；`uv sync --extra dev`；baseline 测试绿

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup / Foundational

- [x] T001 config：`src/vnc_agent/config.py` 新增 `MemoryConfig`（enabled=true、
      page_match_high/medium/low=0.88/0.72/0.55、template_match_threshold=0.85、
      bbox_expand_ratio=0.5、max_elements_per_page=64、
      template_refresh_min_consecutive_successes=3、storage_dir=None，带范围校验：
      high>medium>low）；`AgentConfig` 增 `memory` 字段（FR-009）
- [x] T002 config：`config/agent.yaml` 新增 `memory` 段（FR-009）
- [x] T003 domain：`src/vnc_agent/domain/memory.py`（NEW）——PageFingerprint /
      PageMemory / ElementMemory / MemoryLookupResult / MemoryHitAudit（FR-003）；
      `domain/run.py` ActionIteration + `memory_hit: MemoryHitAudit | None`
- [x] T004 storage：`storage/database.py` + PageMemoryRow / ElementMemoryRow；
      `storage/repositories.py` + MemoryRepository（list_pages / get_page /
      save_page / list_elements / find_element / save_element / delete_element /
      count_elements，照既有模式）（FR-003）

## Phase 2: US1 指纹与写入 (P1)

- [x] T005 [US1] `memory/fingerprint.py`（NEW）：compute_phash（32x32 DCT 8x8 去 DC）、
      hamming、动态 token 过滤、build_page_fingerprint、page_similarity
      （0.375/0.375/0.25）、classify_page_match（分辨率不等封顶 low）（FR-001/002）
- [x] T006 [US1] `memory/retrieval.py`（NEW）：region_intersects_any（mask 几何）、
      find_best_page（纯函数）、match_element_template（历史 bbox 邻域外扩 + 
      match_template_array）（FR-006 前置）
- [x] T007 [US1/US3] `memory/service.py`（NEW）：PageElementMemory ——
      record_success（safe 帧裁剪模板、mask 相交拒写、锚点文本≤5、页面 upsert
      决策 7、模板替换决策 4、上限淘汰决策 8）、record_element_failure、lookup
      （只读、fail-open）（FR-004/005/006/007/013）
- [x] T008 [P] [US1] 单测 `tests/unit/test_memory_fingerprint.py`（SC-004）
- [x] T009 [P] [US1/US3] 单测 `tests/unit/test_memory_store.py`：upsert 统计、
      连续成功模板替换、上限淘汰、mask 相交拒写、失败计数清零连续（SC-004）

## Phase 3: US2/US4 runtime 接线与可观测性 (P1)

- [x] T010 [US2] `runtime/telemetry.py`：CounterKind + "element_memory_hit"
      （payload: element_memory_id / page_similarity / template_score）；
      PerformanceSummary + `memory_hits`（additive）；derive 汇总（FR-010）
- [x] T011 [US2] `runtime/agent_runtime.py`：__init__ 构造 memory（决策 10）+
      本步封禁集合；Grounding 分支 zoom 之后查记忆——high 直点旁路 Grounder（safe_
      click_point + memory_hit + skipped 审计 + counter），medium 提示入
      template_candidates；验证后成败回写（FR-004/006/007/008/010/011）
- [x] T012 [US4] reporting：`json_report.py` iteration + "memory_hit"；
      `html_report.py` 性能摘要 + 记忆命中行；`localization.py` +
      performance.memory_hit_count（FR-010）
- [x] T013 [P] [US2] 单测 `tests/unit/test_memory_retrieval.py`：邻域命中/未中、
      模板缺失降级 medium、exclude 集合生效（SC-004）

## Phase 4: e2e 与回归 (P1)

- [x] T014 [US1/US2/US3/US4] e2e `tests/e2e/test_scenario_19_page_element_memory.py`：
      run1 grounding 写入 → run2 零 grounder 直点（SC-001）；命中但验证失败 →
      失败计数+1 且回落（SC-002）；enabled:false 基线一致（SC-003）；telemetry/
      报告断言（US4）
- [x] T015 golden 快照再生成：`tests/snapshots/report_legacy_projection.json` 与
      `tests/snapshots/report_zh_cn.html` 按自带流程删除重跑（SC-005）
- [x] T016 全量回归：`uv run pytest tests/unit tests/fixtures -q`、
      `uv run pytest tests/e2e -q`、integration 离线部分（SC-005）
