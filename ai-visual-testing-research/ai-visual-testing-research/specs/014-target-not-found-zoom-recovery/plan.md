# Implementation Plan: 目标未找到的局部放大重定位恢复（zoom_reground）

**Branch**: `014-target-not-found-zoom-recovery` | **Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)

## Summary

为 `target_not_found` / `grounding_low_confidence` 增加升级恢复策略 `zoom_reground`：
恢复引擎在 recapture/second_candidate 之后的升级档产出一次性 `ZoomRegroundPlan`
（ROI + 缩放因子 + 来源）；下一 ActionIteration 的 Grounding 分支消费该计划，执行
「ROI 截图/内存裁剪 → 2x 放大 → 落盘 artifact → 放大图重新 OCR → 带
`scale_factor`/`crop_offset`/`original_resolution` 的 Grounding → 严格坐标还原 →
重新走既有 ActionPolicy」。坐标还原顺序为先空间解析（放大图分辨率）后
`round(v/scale)+offset` 还原、越界/退化严格拒绝。

## Technical Context

**Language/Version**: Python 3.11+（uv 管理）
**Primary Dependencies**: pydantic v2, opencv-python, numpy, httpx, structlog
**Testing**: pytest + pytest-asyncio（offline stub 基建：FakeVNC / StubPlanner / StubGrounder / OCR set_engine 注入）
**Target Platform**: 与既有 vnc_agent 相同（Windows/Linux，VNC 黑盒被测端）
**Constraints（冻结面，来自并行 feature）**:
- 不改 `planning/action_policy.py`（经既有 resolve 接口重新调用）
- 不改 `verification/`、`perception/ocr/engine.py` 引擎选择逻辑（可调用 `run_ocr_array`）
- `runtime/agent_runtime.py` 只动 recovery 相关分支（不碰 009 planner-skip、008 缓存接线）

## Constitution Check

- **I 确定性运行时控制**: ROI 选取规则是确定性优先级序列；预算由既有 StepController /
  Tier-2 单点裁决；无新增无限重试。✔
- **II 职责分离**: 感知（放大观察）在 perception 层；策略选择在 recovery 层；动作决策
  仍由 ActionPolicy 独占。✔
- **III 键盘优先**: 不改变优先级；zoom 只影响 Grounding 输入图像。✔
- **IV 独立闭环**: zoom 后仍走完整 观察→决策→执行→独立验证 循环（旗标 + 下一迭代
  消费的接线方式即为此设计）。✔
- **V 受控自进化**: 无自进化改动。✔
- **VI 业务无关**: ROI/缩放/还原全部为通用几何；无业务词汇。✔

## Project Structure

### Documentation (this feature)

```text
specs/014-target-not-found-zoom-recovery/
├── spec.md
├── plan.md
├── tasks.md
└── checklists/requirements.md
```

### Source Code (repository root: vnc_agent/)

```text
src/vnc_agent/
├── config.py                     # + ZoomRegroundConfig；AgentConfig 从 recovery 段提取 zoom_reground
├── config/agent.yaml             # + recovery.zoom_reground 段
├── domain/recovery.py            # + "zoom_reground" 策略、ZoomRegroundPlan、RecoveryAttempt 扩展字段
├── models/coordinate_space.py    # + restore_original_bbox（严格还原：/scale + offset，拒绝不 clamp）
├── models/provider.py            # GroundingRequest + scale_factor / original_resolution
├── models/mimo_grounder.py       # ground() 顺序改为 解析→空间解析→还原；StubGrounder 同步；共享 _restore_and_cap
├── perception/pipeline.py        # + ZoomObservation + ObservationPipeline.observe_zoom()
├── recovery/zoom.py              # NEW：determine_zoom_roi / expand_region（ROI 顺序 a/b + 收缩平移）
├── recovery/strategies.py        # ROUTING 更新；StrategyContext + screen/grounding_result/target；zoom_reground no-op 执行档
├── recovery/engine.py            # zoom 计划/预算/旗标（zoom_request、take_zoom_request、每步计数）
└── runtime/agent_runtime.py      # 仅 recovery 分支：stop_recover 传上下文；Grounding 分支消费 zoom_request

tests/
├── unit/test_zoom_bbox_restore.py       # 坐标还原边界（缩放+偏移、normalized、拒绝语义）
├── unit/test_zoom_roi_determination.py  # ROI 顺序 a/b/c、外扩、收缩平移、最小尺寸
├── unit/test_zoom_recovery_budget.py    # 每步上限、预算耗尽回落、配置提取
├── e2e/test_scenario_18_zoom_reground.py# 全链路成功 + 失败终结
└── e2e/conftest.py                      # FakeVNC.capture_region 真实裁剪（保真修正）
```

## 关键设计

### 1. 坐标还原（FR-004，红线）

`MimoGrounderClient.ground()` / `StubGrounder.ground()` 统一为：

```text
parse → _merge_ui_index_candidates → _resolve_coordinate_spaces(分辨率=送模型图像尺寸)
      → _restore_and_cap: bbox' = round(bbox/scale_factor) + crop_offset
        （original_resolution 提供时越界即拒绝；退化即拒绝；cap top_k；model_name）
```

既有全屏调用（scale=1、offset=(0,0)、resolution=全屏、original_resolution=None）
逐候选行为不变。`resolve_pixel_bbox` 不改动。新增 `restore_original_bbox` 独立单测。

### 2. ROI 确定（FR-002）

`recovery/zoom.py::determine_zoom_roi`：
1. 上次 grounding 候选（含被在界过滤前的原始结果）取 max confidence bbox →
   `expand_region(bbox, roi_expand_factor)`；
2. `target.nearby_texts` 命中 OCR（normalized 双向 contains）取 max confidence →
   `expand_region(bbox, roi_expand_factor * 2)`；
3. 否则 None（放弃升级）。
`expand_region`：中心外扩 → 最小尺寸下限 → 平移收缩进屏幕 → 仍非法则 None。
（ROI 是观察窗口，平移/收缩合法；点击坐标的严格拒绝语义不受影响。）

### 3. 恢复引擎接线（FR-001/006）

- ROUTING: `target_not_found: [recapture, zoom_reground, re_ground]`；
  `grounding_low_confidence: [second_candidate, zoom_reground, re_ground]`。
- `handle()` 选中 zoom_reground 时先 `_plan_zoom(ctx)`（检查每步上限 + 计算 ROI）；
  计划不可得 → 以序列中下一策略替代执行（预算耗尽后不再升级、既有测试语义兼容）。
- 执行成功 → `zoom_request=plan`、每步计数 +1、`need_reground=True`、
  RecoveryAttempt 填 roi/scale_factor/roi_source。
- `reset_iteration()`（步骤开始）清零计划与计数；`take_zoom_request()` 一次性消费。
- 全局预算：沿用既有 `consume_global_retry_budget()` 通用路径；
  `allows_action_path_change=false` 时 zoom_reground 与 re_ground 一样被拒。

### 4. 放大观察（FR-003/008）

`ObservationPipeline.observe_zoom(roi, scale_factor, step_id)`：
`capture_service.capture(roi=..., capture_source="recovery")` →（驱动返回全屏时内存
裁剪同一 ROI）→ cv2.resize(INTER_CUBIC) → `run_ocr_array`（bbox `/scale + offset`
还原原图坐标；ocr_enabled=False 时跳过）→ 遮罩处理（局部遮罩平移+缩放；安全版始终
落盘，模型版遵循 private_persistence_allowed）→ `artifact_store.save_bytes(run_id,
"zoom/…png")` → ZoomObservation。任何失败返回 None（fail-open 回全屏 Grounding）。

### 5. runtime 接线（仅 recovery 分支）

- `stop_recover` 分支：`StrategyContext(driver, screen, grounding_result=原始
  grounding（优先，含未过滤候选）, target=sa.target)`。
- Grounding 分支开头：`plan = recovery.take_zoom_request()` → 有则 `observe_zoom`；
  成功则 GroundingRequest 采用放大图（image_ref/crop_offset/scale_factor/
  resolution=放大图尺寸/original_resolution=screen.resolution/ocr_candidates=放大 OCR、
  ui_index_candidates=[]），失败则回退原全屏请求。审计 coordinate_transform_identity
  增加 scale_factor / original_resolution。

## Complexity Tracking

- HTML golden 快照（tests/snapshots/report_zh_cn.html）因 RecoveryAttempt 新字段按
  其自带流程重新生成（spec 决策 6）。
- `_blocked_iteration_verdict` 内的 TARGET_NOT_FOUND 恢复调用不传 grounding 上下文 →
  zoom 自动跳过（回落下一策略），行为与 spec Edge Case 一致，不另行接线。
- 网格扫描（ROI 顺序 c 的替代方案）明确出局（spec 决策 2）。
