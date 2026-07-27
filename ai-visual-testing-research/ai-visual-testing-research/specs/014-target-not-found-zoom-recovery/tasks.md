# Tasks: 目标未找到的局部放大重定位恢复（zoom_reground）

**Input**: spec.md / plan.md（本目录）
**Prerequisites**: main 已含 feature 008~011；uv sync --extra dev；baseline 测试绿

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup / Foundational

- [x] T001 config：`src/vnc_agent/config.py` 新增 `ZoomRegroundConfig`
      （max_per_step=1/scale_factor=2.0/roi_expand_factor=2.0/min_roi_size_px=64，
      带校验）；`AgentConfig` 增 `zoom_reground` 字段并用 before-validator 从
      `recovery` 段原始 dict 中提取 `zoom_reground` 键（FR-007）
- [x] T002 config：`config/agent.yaml` recovery 段新增 `zoom_reground` 条目
- [x] T003 domain：`src/vnc_agent/domain/recovery.py` — `RecoveryStrategy` 增
      `"zoom_reground"`；新增 `ZoomRegroundPlan`；`RecoveryAttempt` 增
      `roi` / `scale_factor` / `roi_source` 可选字段（FR-008）

## Phase 2: US1 坐标还原 + 放大观察 + Grounding 链路 (P1)

- [x] T004 [US1] `src/vnc_agent/models/coordinate_space.py` 新增
      `restore_original_bbox(bbox, *, scale_factor, crop_offset,
      original_resolution)`：`round(v/scale)+offset`，退化/越界/scale<=0 → None
      （严格拒绝，不 clamp）（FR-004）
- [x] T005 [US1] `src/vnc_agent/models/provider.py` — `GroundingRequest` 增
      `scale_factor: float = 1.0`、`original_resolution: tuple[int,int] | None`
- [x] T006 [US1] `src/vnc_agent/models/mimo_grounder.py` — ground() 流程改为
      解析 → merge ui_index → `_resolve_coordinate_spaces`（分辨率=送模型图像尺寸）
      → `_restore_and_cap`（还原+拒绝+cap+model_name，审计含 restored_bbox）；
      `StubGrounder` 走同一 `_restore_and_cap` 共享路径（FR-004/US1-2）
- [x] T007 [US1] `src/vnc_agent/perception/pipeline.py` — 新增 `ZoomObservation` 与
      `ObservationPipeline.observe_zoom()`（ROI 捕获/内存裁剪、放大、OCR 还原、
      遮罩、artifact 落盘、fail-open None）（FR-003/008）
- [x] T008 [P] [US1] 单测 `tests/unit/test_zoom_bbox_restore.py`：缩放+偏移组合、
      normalized_1000@放大图分辨率、越界拒绝、退化拒绝、恒等、grounder 级端到端还原
      （SC-002）

## Phase 3: US1+US2 恢复引擎与 runtime 接线 (P1)

- [x] T009 [US1] `src/vnc_agent/recovery/zoom.py`（NEW）：`expand_region` +
      `determine_zoom_roi`（顺序 a/b/c，锚点邻域=2×外扩因子，收缩平移+最小尺寸）
      （FR-002）
- [x] T010 [US1] `src/vnc_agent/recovery/strategies.py`：ROUTING 更新两个
      FailureType；`StrategyContext` 增 screen/grounding_result/target；`_run` 增
      zoom_reground no-op 档（FR-001）
- [x] T011 [US1/US2] `src/vnc_agent/recovery/engine.py`：`_plan_zoom`（每步上限 +
      ROI 计算）、计划不可得时以下一策略替代、执行成功后设 `zoom_request` /
      计数 / attempt 扩展字段、`take_zoom_request()`、`reset_iteration()` 清理
      （FR-001/006/008）
- [x] T012 [US1/US2] `src/vnc_agent/runtime/agent_runtime.py`（仅 recovery 分支）：
      stop_recover 传 StrategyContext 上下文；Grounding 分支消费 zoom_request →
      observe_zoom → 放大版 GroundingRequest（含 original_resolution、空
      ui_index_candidates）；审计 coordinate_transform_identity 增 scale 字段
      （FR-003/005/008）
- [x] T013 [P] [US1] 单测 `tests/unit/test_zoom_roi_determination.py`：顺序 a/b/c、
      外扩倍数、边缘收缩平移、最小尺寸、多锚点取最高置信（FR-002）
- [x] T014 [P] [US2] 单测 `tests/unit/test_zoom_recovery_budget.py`：每步上限、
      预算耗尽回落 re_ground 且无新 zoom_request、`allows_action_path_change=false`
      拒绝、config 提取（FR-006/007/009）

## Phase 4: e2e (P1) + Polish

- [x] T015 [US1/US2] `tests/e2e/conftest.py`：FakeVNC.capture_region 真实裁剪
- [x] T016 [US1] e2e `tests/e2e/test_scenario_18_zoom_reground.py`：全屏失败 →
      recapture 失败 → zoom_reground 成功定位点击（坐标逐像素断言 + attempts 断言 +
      artifact 存在）（SC-001/004）
- [x] T017 [US2] 同文件：zoom 也失败 → 按既有路径 failed 终结、zoom 次数 ≤ 上限
      （SC-003）
- [x] T018 Polish：HTML golden 快照按自带流程再生成；
      `uv run pytest tests/unit tests/fixtures -q` 与 `tests/e2e -q` 全绿（SC-005）

## Dependencies & Execution Order

- T001~T003 → T004~T007 → T009~T012 → T015~T017 → T018
- [P] 标记的测试任务可与后续实现并行编写
