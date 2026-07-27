# Implementation Plan: 页面记忆与元素记忆（page-element-memory）

**Branch**: `015-page-element-memory` | **Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)

## Summary

新增 `memory/` 模块实现设计 §12/§13 的最小可用记忆通道：成功鼠标动作沉淀
PageMemory（页面指纹）+ ElementMemory（模板图 + 历史 bbox + 锚点文本 + 统计）；
`needs_grounding` 迭代在调用 Grounder 前查记忆，high 页面匹配 + 邻域模板匹配达标
即以 `safe_click_point` 直点并跳过 Grounder（`model_call_skipped` 审计），medium
仅作 `template_candidates` 提示；验证独立性不变，直点验证失败记失败计数并本步
封禁。全链路 fail-open；`memory.enabled: false` 逐字节等价现状。

## Technical Context

**Language/Version**: Python 3.11+（uv 管理）
**Primary Dependencies**: pydantic v2, opencv-python, numpy, SQLAlchemy 2 async + aiosqlite（全部既有，无新依赖）
**Testing**: pytest + pytest-asyncio（FakeVNC / StubPlanner / 计数 Grounder / OCR set_engine 注入，参照 scenario 18）
**Constraints（冻结面）**:
- 不改 `planning/action_policy.py` 逻辑行、`verification/`、`perception/ocr/engine.py`、
  `planning/click_point.py`、`execution/`、`models/mimo_grounder.py` 坐标链路
- 不动 008 缓存接线、009 planner-skip、014 zoom 分支既有逻辑（在其后插入记忆通道）
- `evolution/experience_collector.py` 保持 write-only（守卫测试在案）

## Constitution Check

- **I 确定性运行时控制**: 指纹/相似度/模板匹配/淘汰规则全部确定性；记忆只影响
  『Grounder 调用与否』，流程仍由状态机控制；无新增重试循环。✔
- **II 职责分离**: 记忆检索是 Grounder 的前置替代证据源（同为『目标在哪里』层），
  不触碰 Planner/Verifier 职责；直点结果仍走既有 Executor。✔
- **III 键盘优先**: 优先级不变——记忆通道只存在于已决定 needs_grounding 的分支内，
  且『已验证经验』优先于视觉 Grounding 恰是 Constitution III 的次序。✔
- **IV 独立闭环**: 记忆命中绝不豁免独立验证（FR-008）；验证失败反哺失败计数。✔
- **V 受控自进化**: 页面/元素记忆是 Constitution V 明示允许的运行时经验数据；
  不修改断言/基线/模型。✔
- **VI 业务无关**: 全部为通用像素/文本/几何结构。✔
- **凭据与隐私**: 模板/指纹只取 safe（已遮罩）帧；mask 相交拒写（FR-005）。✔

## Project Structure

### Documentation (this feature)

```text
specs/015-page-element-memory/
├── spec.md
├── plan.md
├── tasks.md
└── checklists/requirements.md
```

### Source Code (repository root: vnc_agent/)

```text
src/vnc_agent/
├── config.py                    # + MemoryConfig；AgentConfig.memory
├── config/agent.yaml            # + memory 段
├── domain/memory.py             # NEW：PageFingerprint / PageMemory / ElementMemory /
│                                #      MemoryLookupResult / MemoryHitAudit
├── domain/run.py                # ActionIteration + memory_hit（additive）
├── memory/__init__.py           # NEW
├── memory/fingerprint.py        # NEW：compute_phash / build_page_fingerprint /
│                                #      page_similarity / classify_page_match（纯函数）
├── memory/retrieval.py          # NEW：match_element_template / find_best_page（纯函数）
├── memory/service.py            # NEW：PageElementMemory（lookup / record_success /
│                                #      record_element_failure，全部 fail-open）
├── storage/database.py          # + PageMemoryRow / ElementMemoryRow
├── storage/repositories.py      # + MemoryRepository（既有 repository 模式）
├── runtime/agent_runtime.py     # Grounding 分支：zoom 之后、Grounder 之前查记忆；
│                                # 直点旁路 + medium 提示；验证后成败回写；本步封禁集合
├── runtime/telemetry.py         # + CounterKind "element_memory_hit"；
│                                # PerformanceSummary.memory_hits（additive）+ 汇总
├── reporting/json_report.py     # iteration + "memory_hit"（additive）
├── reporting/html_report.py     # 性能摘要 + 记忆命中行
└── reporting/localization.py    # + performance.memory_hit_count 资源

tests/
├── unit/test_memory_fingerprint.py   # pHash 确定性/噪声、相似度权重、三档、分辨率封顶、动态 token
├── unit/test_memory_store.py         # upsert 统计、模板替换策略、上限淘汰、mask 拒写、失败计数
├── unit/test_memory_retrieval.py     # 邻域模板匹配命中/未中、模板缺失降级、config 校验
└── e2e/test_scenario_19_page_element_memory.py
                                      # run1 写入 → run2 零 grounder 直点；命中但验证失败；
                                      # enabled:false 基线一致
```

## 关键设计

### 1. 指纹与相似度（FR-001/002）

pHash：BGR→灰度→`cv2.resize(32,32, INTER_AREA)`→`cv2.dct`→左上 8x8 去 DC 项均值
二值化→64bit hex。文本分量：归一化 token 集合 Jaccard（两侧皆空=1.0，单侧空=0.0，
动态 token 过滤见 spec 决策 2）；布局分量：token 中心点 8x8 网格占用集合 Jaccard
（同空集约定）。总分 = 0.375·pHash + 0.375·文本 + 0.25·布局；
`classify_page_match` 在分辨率不等时封顶 "low"。

### 2. 命中直点接线（FR-006/011，仿 014）

`run_action_iteration` 的 `needs_grounding` 分支内、`take_zoom_request()` 之后：
`zoom_obs is None` 且动作为 click/double_click/right_click 时
`await self.memory.lookup(screen, target_hint, exclude=本步封禁集合)`；
level=="high" 且 matched_bbox 非空 → runtime 构造
`ExecutableAction(method="mouse", coordinates=safe_click_point(matched_bbox, …),
target_region=matched_bbox)`，记 `iteration.memory_hit` + telemetry，整个
『Grounder 调用 + policy 二次 resolve』块被旁路（原代码块降级为 else 分支，行内
逻辑不变）；level=="medium"（或 high 但模板未达标）→ 把历史 bbox 以
`{"template_id": "element_memory:<label>", "bbox": …, "confidence": page_similarity}`
追加进 `grounding_request.template_candidates`。

### 3. 成败回写（FR-004/008）

`vr` 产出后：`memory_hit` 且 vr≠passed → `record_element_failure` + 本步封禁；
vr==passed 且 executable 为 mouse+target_region → `record_success(screen(动作前帧),
target_hint, region, ocr_items)`。两者均 try/except + log（fail-open）。封禁集合在
`run()` 每步 `recovery.reset_iteration()` 处同步清空。

### 4. Telemetry（FR-010，仿 009 planner-skip）

直点时：`element_memory_hit` CounterEvent、`model_call_skipped`
CounterEvent（model_role=grounder, reason=element_memory_hit）、outcome="skipped"
ModelCallAudit（request_identity 用 grounder_identity，失败回退 content_hash）。
`derive_performance_summary` 统计 `memory_hits`（setdefault "element_memory"→0）。
golden 快照（legacy JSON projection / zh-CN HTML）按各自自带流程删除再生成。

### 5. `enabled:false` 等价性（FR-009/SC-003）

`AgentRuntime.__init__` 仅在 `memory.enabled and repo is not None` 时构造服务，
否则 `self.memory=None`；所有接线点以 `self.memory is not None` 守卫——禁用时不新增
任何 I/O、事件或分支副作用。`PerformanceSummary.memory_hits` 为 derive 层默认值，
与运行路径无关（报告 schema 恒定，行为差异为零）。
