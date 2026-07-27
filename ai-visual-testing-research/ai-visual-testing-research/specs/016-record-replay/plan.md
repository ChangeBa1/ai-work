# Implementation Plan: 轨迹录制与回放（record-replay）

**Branch**: `016-record-replay` | **Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)

## Summary

新增 `replay/` 模块实现设计 §10.2/§11：探索 run 整体 passed 后由 `ReplayRecorder`
把各步骤通过迭代沉淀为版本化 `ReplayScript`（键盘=可重放 ExecutableAction 快照；
鼠标=页面指纹+模板裁剪+锚点（文本+bbox）+归一化 bbox+验证 spec）；mode:"replay"
时 `ReplayPlayer` 走独立执行路径（不进探索迭代循环）：指纹 ≥ high → 模板 → 锚点 →
同分辨率 bbox → safe_click_point 直点 → 既有独立验证；失败兜底一次 MiMo grounding
（既有 GroundingRequest 通道 + ActionPolicy.resolve 共识），成功生成 pending
ReplayPatch（ADR-005：永不自动应用），失败终结 run 并指明 ReplayStep。happy path
零 planner/零 grounder 调用（telemetry 可断言）。

## Technical Context

**Language/Version**: Python 3.11+（uv 管理）
**Primary Dependencies**: pydantic v2, opencv-python, numpy, SQLAlchemy 2 async + aiosqlite, typer（全部既有，无新依赖）
**Testing**: pytest + pytest-asyncio（FakeVNC / StubPlanner / 计数 Grounder / OCR set_engine 注入，参照 scenario 19）
**Constraints（冻结面）**:
- 不改 `memory/` 内部实现（只消费公开接口）、`planning/action_policy.py`、
  `planning/click_point.py`、`verification/` 引擎与仲裁、`perception/ocr/engine.py`、
  `models/mimo_grounder.py` 坐标链路
- 008 缓存、009 planner-skip、014 zoom、015 记忆 hot path 既有行为不可变；探索
  路径仅允许两处 fail-open 旁插（迭代通过采集草稿 / run passed 落库）

## Constitution Check

- **I 确定性运行时控制**: 定位链（模板/锚点/bbox）全确定性；回放每步预算固定
  （1 直接 + ≤1 兜底），无新增重试循环；状态机沿用既有 force 语义。✔
- **II 职责分离**: Player 不产生语义动作（来自录制的 ReplayStep）；兜底 grounding
  仍是「目标在哪里」层；验证仍由独立 Verifier 完成。✔
- **III 键盘优先**: 键盘步骤直接重放按键序列，不转视觉路径。✔
- **IV 独立闭环**: 回放每步验证照常（ReplayStep 存的 spec），绝不豁免；验证失败
  才触发兜底。✔
- **V 受控自进化（ADR-005）**: 兜底成功只生成 pending patch；脚本目标字段回放中
  只读；patch_auto_apply MVP 恒不生效（true 仅警告）。✔
- **VI 业务无关**: 指纹/模板/锚点/几何全部通用结构。✔
- **凭据与隐私**: 模板/指纹取 safe（已遮罩）帧；mask 相交步骤拒落模板并标记
  direct_fallback_only（与 015 同一遮罩规则）。✔

## Project Structure

### Documentation (this feature)

```text
specs/016-record-replay/
├── spec.md
├── plan.md
├── tasks.md
└── checklists/requirements.md
```

### Source Code (repository root: vnc_agent/)

```text
src/vnc_agent/
├── config.py                    # + ReplayConfig；AgentConfig.replay
├── config/agent.yaml            # + replay 段
├── domain/replay.py             # NEW：ReplayStep / ReplayScript / ReplayPatch /
│                                #      ReplayStepAudit / ReplayAnchor
├── domain/testcase.py           # mode: Literal["explicit","replay"]（additive）
├── domain/run.py                # ActionIteration + replay_audit（additive）
├── replay/__init__.py           # NEW
├── replay/recorder.py           # NEW：ReplayRecorder（草稿采集 + finalize 落库，
│                                #      模板裁剪/mask 拒写/锚点/归一化 bbox）
├── replay/locator.py            # NEW：纯定位函数（restore_bbox / anchor 匹配 /
│                                #      locate_target 定位链）
├── replay/player.py             # NEW：ReplayPlayer（预检 fail fast、独立回放循环、
│                                #      兜底、telemetry、报告）
├── replay/patch.py              # NEW：build_pending_patch（ADR-005 生命周期）
├── runtime/agent_runtime.py     # __init__ 构造 recorder/replay 仓库；run() 顶部
│                                #      mode=="replay" 分派 Player；通过迭代旁插
│                                #      recorder.observe；passed 后 finalize
├── runtime/exceptions.py        # + ReplayUnavailableError
├── runtime/telemetry.py         # + CounterKind replay_step_replayed /
│                                #      replay_patch_generated；PerformanceSummary
│                                #      + replay_locate_methods / replay_patch_count
├── storage/database.py          # + ReplayScriptRow / ReplayStepRow / ReplayPatchRow
├── storage/repositories.py      # + ReplayRepository
├── api/cli.py                   # run --mode 覆盖；replay scripts / replay patches
├── reporting/json_report.py     # iteration + "replay_audit"（additive）
├── reporting/html_report.py     # 性能摘要 + 回放行
└── reporting/localization.py    # + performance.replay_* 资源

tests/
├── unit/test_replay_models.py        # 序列化往返、归一化 bbox 还原/拒绝、版本
├── unit/test_replay_recorder.py      # 草稿→脚本、mask 拒模板、失败放弃、fail-open
├── unit/test_replay_locator.py       # 模板/锚点/bbox 链、锚点位移一致性、分辨率拒绝
├── unit/test_replay_patch.py         # pending 生成、auto_apply=false/true 不应用
└── e2e/test_scenario_20_record_replay.py
                                      # a 探索生成脚本；b happy path 零调用；
                                      # c 移位兜底+patch；d 兜底失败；e fail fast
```

## 关键设计

### 1. 录制（FR-003/004，决策 1）

`AgentRuntime.__init__`：`replay.enabled && auto_generate && repo` 时构造
`ReplayRecorder(repo=ReplayRepository, template_dir, config, mask_regions)`。
`run_action_iteration` 中 015 记忆回写块之后旁插：
`if self.replay_recorder is not None and vr.status=="passed": recorder.observe_passed_iteration(step, screen, sa, executable)`
——纯内存草稿（含即时计算的指纹/锚点/归一化 bbox 与 safe 帧路径）。`run()` 的
all-passed 分支后旁插 `await recorder.finalize(ctx)`：任一步缺草稿 → 放弃；否则
裁剪模板（mask 相交 → direct_fallback_only）、version=max+1 落库。全程 try/except
fail-open。

### 2. 回放执行（FR-005~008，决策 4/6）

`AgentRuntime.run()` 顶部：`if test_case.mode == "replay": return await ReplayPlayer(self).run(...)`
——探索循环体零改动。Player：预检（enabled/repo/脚本存在/步骤 id 序列一致）失败
raise `ReplayUnavailableError`（连接前）；然后 connect → 逐 ReplayStep：
observe → keyboard 步直接重放 recorded_executable；mouse 步
`locate_target(frame, screen, step, cfg)`（locator.py 纯函数链：指纹档位 →
模板 → 锚点 → 同分辨率 bbox）→ safe_click_point → execute → wait_stable →
post observe → classify_action_effect → `resolve_step_result`（ReplayStep.expected，
escalate=True）。未中/验证失败 → 兜底一次：GroundingRequest（记录 bbox 为
template_candidates 提示）→ grounder.ground（照常 model_call audit）→
`policy.resolve(sa, screen, grounding_result)` → 执行+验证 → 成功生成 pending
patch + `memory.record_success` 回写；失败 → run failed，
failure_reason=`replay step failed: replay_step_id=... step_id=... reason=...`。
每步一个/两个 ActionIteration（直接尝试 + 兜底尝试）进 StepRecord——报告/持久化
复用既有结构。

### 3. 补丁（FR-009，决策 5）

`patch.py::build_pending_patch(step, script, new_executable, reason, before_image,
after_image, evidence)` → status="pending"、old_target={template_path,bbox,
normalized_bbox,anchor_texts}、new_target={bbox,coordinates,source:"grounder"}。
存库 fail-open。`patch_auto_apply=true` 时仅 `log.warning("replay_patch_auto_apply_ignored")`。
脚本行统计更新走 `ReplayRepository.bump_step_stats`（只写 success/failure_count）。

### 4. Telemetry（FR-012）

每步终结时：`replay_step_replayed` CounterEvent（method ∈ template/anchor/bbox/
fallback_grounding/keyboard）；patch 落库时 `replay_patch_generated`。迭代
additive 字段 `replay_audit`。`derive_performance_summary` 汇总
`replay_locate_methods`（dict，无回放时空）与 `replay_patch_count`（默认 0）。
兜底 grounder / 每步 verification 照常 `model_call` 事件——`model_calls` 即
「回放 vs 探索」对比口径。golden 快照（legacy projection 含迭代新键、zh-CN HTML
含性能新行）按各自自带流程删除再生成。

### 5. CLI（FR-011）

`run` + `--mode` 选项（None=按 testcase；"replay"/"explicit" 覆盖，model_copy）。
`ReplayUnavailableError` → stderr 原因 + EXIT_VALIDATION。新 typer 子应用
`replay`：`scripts <test_case_id>` / `patches <test_case_id>` 直连 SQLite 输出
JSON（不连 VNC）。

### 6. 探索路径不变性（FR-013）

回放不触碰 `run_action_iteration` 主体；recorder 两处旁插均 `is not None` 守卫 +
内部全捕获；`replay.enabled:false` 或 `auto_generate:false` 时 recorder 为 None，
探索行为与 015 合入后逐字节一致。mode Literal 扩展与 loader 放行 "replay" 为
additive（explicit 语义不变）。
