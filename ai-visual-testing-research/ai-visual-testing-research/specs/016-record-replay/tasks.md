# Tasks: 轨迹录制与回放（record-replay）

**Input**: spec.md / plan.md（本目录）
**Prerequisites**: main 已含 feature 008~015；`uv sync --extra dev`；baseline 测试绿

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup / Foundational

- [x] T001 config：`src/vnc_agent/config.py` 新增 `ReplayConfig`（enabled=true、
      auto_generate=true、patch_auto_apply=false、template_match_threshold=0.85、
      bbox_expand_ratio=0.5、min_page_match_level="high"、
      anchor_offset_tolerance_px=8、storage_dir=None）；`AgentConfig.replay`；
      `config/agent.yaml` + replay 段（FR-011）
- [x] T002 domain：`src/vnc_agent/domain/replay.py`（NEW）——ReplayAnchor /
      ReplayStep / ReplayScript / ReplayPatch / ReplayStepAudit（FR-001）；
      `domain/testcase.py` mode 扩展 Literal["explicit","replay"] + loader 放行；
      `domain/run.py` ActionIteration + `replay_audit`（additive）
- [x] T003 storage：`storage/database.py` + ReplayScriptRow / ReplayStepRow /
      ReplayPatchRow；`storage/repositories.py` + ReplayRepository（save_script /
      get_latest_script / list_scripts / next_version / save_patch / list_patches /
      bump_step_stats）（FR-002）
- [x] T004 telemetry：`runtime/telemetry.py` + CounterKind
      "replay_step_replayed"/"replay_patch_generated"；PerformanceSummary +
      `replay_locate_methods` / `replay_patch_count`（additive）+ derive 汇总；
      `runtime/exceptions.py` + ReplayUnavailableError（FR-005/012）

## Phase 2: US1 录制 (P1)

- [x] T005 [US1] `replay/recorder.py`（NEW）：ReplayRecorder——
      observe_passed_iteration（草稿：指纹/锚点(text+bbox)/归一化 bbox/safe 帧路径）、
      finalize（缺步放弃、mask 相交拒模板 + direct_fallback_only、模板裁剪落盘、
      version=max+1、fail-open）（FR-003/004）
- [x] T006 [US1] `runtime/agent_runtime.py`：__init__ 构造 recorder（enabled &&
      auto_generate && repo）；run_action_iteration 通过后旁插 observe；run()
      all-passed 后旁插 finalize（FR-003/013）
- [x] T007 [P] [US1] 单测 `tests/unit/test_replay_recorder.py`（SC-005）

## Phase 3: US2/US3 回放与兜底 (P1)

- [x] T008 [US2] `replay/locator.py`（NEW）：restore_bbox_from_normalized（分辨率
      不一致拒绝）、match_anchor_offset（唯一文本锚点位移一致性）、locate_target
      （指纹档位 → 模板 → 锚点 → bbox 定位链，纯函数）（FR-006）
- [x] T009 [US3] `replay/patch.py`（NEW）：build_pending_patch + auto_apply 警告
      语义（FR-009）
- [x] T010 [US2/US3] `replay/player.py`（NEW）：ReplayPlayer——预检 fail fast
      （FR-005）、独立回放循环（keyboard 重放 / mouse 定位链 + safe_click_point +
      独立验证）、兜底一次（GroundingRequest + policy.resolve + patch + memory
      回写）、失败终结与 failure_reason 口径、telemetry/报告（FR-006~010/012）
- [x] T011 [US2] `runtime/agent_runtime.py` run() 顶部 mode=="replay" 分派（FR-013）
- [x] T012 [P] [US2] 单测 `tests/unit/test_replay_locator.py`、
      `tests/unit/test_replay_models.py`（SC-005）
- [x] T013 [P] [US3] 单测 `tests/unit/test_replay_patch.py`（SC-005）

## Phase 4: US4 CLI / 报告 / e2e (P1~P2)

- [x] T014 [US4] `api/cli.py`：run + `--mode` 覆盖；ReplayUnavailableError →
      EXIT_VALIDATION；`replay scripts` / `replay patches` JSON 查询（FR-011）
- [x] T015 [US4] reporting：`json_report.py` iteration + "replay_audit"；
      `html_report.py` 性能摘要回放行；`localization.py` + performance.replay_*
      资源（FR-012）
- [x] T016 [US1~US4] e2e `tests/e2e/test_scenario_20_record_replay.py`：
      a 探索生成脚本（SC-001）；b happy path 零 planner/grounder（SC-002）；
      c 移位兜底 + pending patch + 脚本不变（SC-003）；d 兜底失败 run failed +
      指明步骤（SC-003）；e enabled:false / 无脚本 fail fast（SC-004）
- [x] T017 golden 快照再生成：`tests/snapshots/report_legacy_projection.json` 与
      `tests/snapshots/report_zh_cn.html` 按自带流程删除重跑（SC-006）
- [x] T018 全量回归：`uv run pytest tests/unit tests/fixtures tests/e2e
      tests/integration -q`（SC-006）
