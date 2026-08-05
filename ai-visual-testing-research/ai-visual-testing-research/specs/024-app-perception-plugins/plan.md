# Implementation Plan: 应用感知增强插件框架（Grounding 前置子窗口裁剪放大）

**Branch**: `024-app-perception-plugins` | **Date**: 2026-07-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/024-app-perception-plugins/spec.md`

## Summary

在 `agent_runtime` 需要 Grounding 的分支里，**在调用 Grounder 之前**插入一层可插拔的"应用感知增强"：

1. **检测**——已注册插件用**声明式档案**（数据）里的必需锚点文本在当前帧 OCR 中定位一个子窗口矩形，
   经几何合理性校验（面积比例 / 宽高比 / 最小边 / 必须含全部锚点）与置信度阈值后产出
   `SubWindowDetection`；任何异常吸收为"未检测到"。
2. **激活判定**——**默认不激活；唯一的激活来源是测试用例的显式声明**（用户 2026-07-28 裁决）。
   纯函数的确定性阶梯（FR-011，9 级、首个命中即决）：`TestStep.perception_scope` 未声明 ⇒ 立即
   零开销退出（`not_declared`，绝大多数步骤走这条）→ 显式关闭 → 全局/注册/target 允许 → 每步预算 →
   动作类型 → **运行所声明插件的检测**（检测成功只是前置条件，本身绝不构成激活理由）→ 倍率有效性 →
   观察成功 → 激活。**不做任何基于 intent 自然语言的推断，不做"看见窗口就放大"的隐式启发。**
3. **观察**——复用 feature 014 的 `ObservationPipeline.observe_zoom(roi, scale_factor)`（ROI 抓屏 /
   内存裁剪 + INTER_CUBIC 放大 + 放大图重新 OCR + 遮罩落盘，全部失败返回 None）。倍率由 ROI 尺寸
   自适应推导并被 `[min_scale, max_scale]` 与放大后总像素上限夹紧。
4. **请求构造**——用放大图与**同一坐标空间**的提示候选构造 `GroundingRequest`
   （`crop_offset` / `scale_factor` / `resolution=放大图` / `original_resolution=原帧`），坐标还原由
   014 已有的 `restore_original_bbox` 严格链路完成（越界/退化拒绝，不 clamp）。
5. **审计**——每个进入 Grounding 分支的迭代都写一条 `PerceptionEnhancementAudit`（含未激活的原因码）。

关键性质：**同一迭代内完成，不新增迭代、不新增 Grounder 调用、不消耗恢复预算、不新增 FailureType**；
每次激活的唯一新增成本是 1 次 ROI 抓屏 + 1 次放大图 OCR，每 TestStep 至多 1 次。所有失败路径 fail-open
回全帧。`app_perception.enabled=false` ⇒ 与本 feature 之前逐字节一致。

## Technical Context

**Language/Version**: Python 3.12（`vnc_agent/` 下的 uv 工程）

**Primary Dependencies**: 仅既有依赖——pydantic（档案与审计模型）、PyYAML（档案加载，测试用例加载器已在用）、
OpenCV + numpy（`observe_zoom` 内既有）、RapidOCR（既有）。**无新增依赖**。

**Storage**: 纯增量 pydantic 字段（`ActionIteration.perception_enhancement`）；放大图沿用
`observe_zoom` 既有的 artifact 落盘路径；无 schema 迁移。插件档案是仓库内的 YAML 数据文件
（`vnc_agent/profiles/app_perception/*.yaml`），运行期只读。

**Testing**: pytest + pytest-asyncio；4 个新 unit 文件、1 个新 e2e 场景（scenario 23）、
1 个跨场景契约测试扩展；legacy e2e 在 conftest 中钉 `app_perception.enabled=false`（022/023 先例）。

**Target Platform**: 不变（离线可用，Windows/Linux）

**Performance Goals**: 未激活时**零**新增开销（检测只在启用了插件的 target 上跑，且只做 OCR 项的文本
匹配 + 常数级几何运算，不做像素运算）；激活时新增 1 次 ROI 抓屏 + 1 次放大图 OCR；Grounder 调用次数
与关闭本 feature 时**完全相同**。

**Constraints**（弱配置电脑，Constitution 资源约束）：
- 放大图像素总数 MUST 有硬上限（默认 4.0 MP），倍率据此再夹紧一次——防止"小窗口 × 大倍率"
  把一次 OCR 变成十几倍全屏 OCR 的开销。
- 每 TestStep 至多 1 次激活（可配置），达上限后本步骤余下迭代零成本走全帧。
- 检测阶段 MUST NOT 触发任何额外抓屏或额外 OCR——只消费本迭代**已有**的 `StructuredScreen.ocr_items`。

**Scale/Scope**: 新增 1 个包（6 个模块）+ 1 个 domain 模块 + 2 个档案数据文件；改动既有源码 6 个文件
（全部为追加式插入）；新增 4 unit + 1 e2e + 2 fixture 数据，更新 3 个既有测试文件。

## Constitution Check

*GATE: passed（Phase 0 前）/ re-checked after Phase 1: passed。*

- **Principle I（确定性运行时控制）**: 模型在本 feature 中**不参与任何决策**——它只是收到一张不同的
  图像。检测、激活判定、倍率、坐标还原全部是确定性纯函数（同帧同档案 ⇒ 同结果）。不新增任何模型
  自主分支、不新增重试路径。
- **Principle II（Planner/Grounder/Executor/Verifier 分离）**: 本 feature 只改变**送给 Grounder 的
  观察图像与坐标系**，不改变角色边界：Planner 不知情，Grounder 仍只回答"在哪里"，
  `ActionPolicy.resolve` 与 Verifier 一行不动。
- **Principle III（键盘优先）**: 增强只作用于**已经决定要走视觉 Grounding** 的分支；键盘/回放/记忆/
  OCR 唯一命中等更高优先级路径的判定顺序完全不变（FR-020 的优先级链即既有链尾追加）。
- **Principle IV（观察-执行-验证独立闭环）**: 增强属于"观察"环节的分辨率提升，执行与独立验证完全不变，
  没有任何验证豁免。
- **Principle V（受控自进化）**: 不写入任何经验数据、不改基线、不改模型。档案是人工编写并入库的数据，
  不由运行时自动生成或修改。
- **Principle VI（业务无关核心 + 声明式场景隔离）**: 见下方专门 gate。本 feature 正是 Constitution VI
  所说"通过通用接口注册的可选场景 profile"的第一个落地实现。
- **恢复与重试门禁**: 本 feature 不属于恢复策略，不进入 `ROUTING`、不产生 `RecoveryAttempt`、
  不消耗 Tier-1/Tier-2 预算；自身的每步上限是纯粹的成本闸门，达上限只是"不增强"，不影响终结性。
- **制品与可观测性**: 每个 Grounding 迭代 100% 有审计记录；放大图沿既有 artifact 惯例落盘；
  模型调用审计的 `coordinate_transform_identity` 已含 `crop_offset`/`scale_factor`（014 建立），
  增强路径自动复用。
- **凭据与隐私**: 放大图落盘完全复用 `observe_zoom` 既有的遮罩/私有持久化语义，不新增例外。

**Domain-Agnostic Core gate (Principle VI)**:

- [x] 核心不新增任何业务字段/关键词/状态/流程分支：新增的全部词汇是通用的
      （plugin / profile / sub-window / anchor / activation / roi / scale），
      `TestStep.perception_scope` 的**值域**是插件名字符串或关闭标记，不是业务枚举。
- [x] 全部业务语义（窗口标题、控件词、锚点文本）只存在于 `vnc_agent/profiles/app_perception/*.yaml`
      档案、测试用例 YAML 与 fixture 中；删掉档案文件 ⇒ 核心行为退回全帧路径。
- [x] 通用性用**两个互不相关**的 GUI 场景验证（真实证据形态的"工具子窗口叠主画面" + 一个词汇与结构
      完全无关的合成场景），并在既有 `tests/fixtures/test_cross_scenario_coverage.py` 中登记跨场景契约测试。
- [x] 禁词扫描测试：对 `src/vnc_agent/` 扫描被测应用/窗口/业务控件词汇，零命中（新增 unit 断言）。

## Project Structure

### Documentation (this feature)

```text
specs/024-app-perception-plugins/
├── plan.md              # 本文件
├── spec.md
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── app-perception-plugin-contract.md   # 扩展点 + 档案 schema + 审计契约
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2（/speckit-tasks 产出）
```

### Source Code (repository root)

```text
vnc_agent/
├── src/vnc_agent/
│   ├── domain/
│   │   └── app_perception.py            # 新增：通用领域模型（检测/判定/审计/约束）
│   ├── perception/
│   │   ├── app_plugins/                 # 新增包：扩展点框架（全部业务无关）
│   │   │   ├── __init__.py
│   │   │   ├── base.py                  # AppPerceptionPlugin Protocol + ActivationVote
│   │   │   ├── profile.py               # PluginProfile 声明式档案 schema（pydantic）
│   │   │   ├── registry.py              # 注册表：档案目录加载 + 程序化注册
│   │   │   ├── detector.py              # DeclarativeSubWindowPlugin：锚点→矩形→合理性校验
│   │   │   ├── activation.py            # FR-011 判定阶梯（纯函数）
│   │   │   ├── geometry.py              # AnchorConstraint 关系求值 + 坐标空间投影
│   │   │   └── coordinator.py           # 每步预算 + 编排（检测→判定→observe_zoom→请求素材）
│   │   └── pipeline.py                  # 改：ZoomObservation 增量字段 ocr_items_zoom_space
│   ├── runtime/
│   │   └── agent_runtime.py             # 改：grounding 分支链尾接线 + 审计写入
│   ├── domain/run.py                    # 改：ActionIteration.perception_enhancement（增量）
│   ├── domain/testcase.py               # 改：TestStep.perception_scope（增量可选字段）
│   ├── config.py                        # 改：AppPerceptionConfig + AgentConfig.app_perception
│   └── reporting/json_report.py         # 改：增量迭代键（缺省 null）
├── config/agent.yaml                    # 改：新增 app_perception 段（含回滚注释）
├── profiles/app_perception/             # 新增数据目录（非核心代码）
│   ├── README.md
│   ├── <scenario-a>.yaml                # 真实证据形态的工具子窗口档案
│   └── <scenario-b>.yaml               # 互不相关的第二场景档案（跨场景验证用）
└── tests/
    ├── unit/test_app_perception_profile.py
    ├── unit/test_app_perception_detection.py
    ├── unit/test_app_perception_activation.py
    ├── unit/test_app_perception_declaration.py
    ├── unit/test_app_perception_geometry.py
    ├── e2e/test_scenario_23_app_perception_enhancement.py
    ├── e2e/conftest.py                  # 改：legacy 场景钉 enabled=false
    ├── fixtures/test_cross_scenario_coverage.py   # 改：登记跨场景契约
    ├── fixtures/images/                 # 新增两张离线 fixture 图（或程序化生成）
    └── fixtures/test_json_report_compatibility.py # 改：_LEGACY_ITERATION_KEYS
```

**Structure Decision**: 框架代码放在 `perception/app_plugins/`（它是观察层能力），领域模型放
`domain/app_perception.py`（与 `domain/recovery.py`、`domain/reporting_tags.py` 同构）。
**被测应用知识一律外置到 `vnc_agent/profiles/app_perception/` 数据目录**——这是 Principle VI 的
结构性保证：核心目录里没有任何一行代码知道任何具体应用。

## Phase 0 — Research（要点，详见 research.md）

- **接线点确证**: `agent_runtime.py` 的 `if policy_result.needs_grounding:` 分支已有四级优先级链
  （014 zoom_obs → 023 correction → 015 memory 直点 → grounder）。增强的正确插入位置是**最内层
  `else:` 分支的首行**——即"确定要真的调用 Grounder"之后、构造 `GroundingRequest` 之前。这天然满足
  FR-020/FR-021：zoom_obs 非空时根本走不到这里，不可能叠加。
- **观察原语可直接复用**: `observe_zoom` 已实现 ROI 抓屏（驱动不支持时内存裁剪）、INTER_CUBIC 放大、
  放大图重新 OCR、遮罩落盘，**每一种失败都返回 None**。本 feature 不需要新的像素代码。
- **坐标还原链路已就绪**: `GroundingRequest` 已有 `crop_offset` / `scale_factor` / `resolution` /
  `original_resolution`，`models/coordinate_space.restore_original_bbox` 已实现
  `round(v/scale)+offset` + 严格拒绝。本 feature **零改动**地复用。
- **ROI 入界语义已就绪**: `recovery/zoom.expand_region` 的 viewing-window 平移/收缩语义可直接用于把
  检测矩形（可能部分越界或过小）规整为合法观察窗口。
- **提示候选的坐标空间**（本 feature 必须解决的一致性问题）: 014 的 zoom 请求把 `ocr_candidates` 以
  **原帧坐标**与**放大图**一起下发（`observe_zoom` 在返回前已把 OCR bbox 还原回原帧）。这对模型是
  混合坐标系。本 feature 按 FR-017 要求同空间，做法是给 `ZoomObservation` **追加**一个
  `ocr_items_zoom_space` 字段（放大图坐标系的原始 OCR 项），024 的请求用它，**014 的调用点一行不改**
  （见 Risks：014 的一致性作为独立跟进项）。
- **模型图像降采样不冲突**: feature 018 的降采样只作用于 planner/`describe_screen` 路径；
  Grounder 的图像负载是原始文件字节（018 FR-004 明确要求 byte-identical），放大分辨率能完整送达。
- **成本量级**: 真实证据中子窗口 ≈420×615；自适应倍率把长边拉到 1600 ⇒ scale≈2.6 ⇒ 放大图约
  1.1k×1.6k ≈1.75 MP，约为全屏 OCR（1024×768=0.79 MP）的 2.2 倍像素。故必须有像素总量上限
  （默认 4.0 MP）+ 每步 1 次的双闸门。

## Phase 1 — Design

### 判定与阈值一览

| 信号 | 规则 | 配置键 | 默认 |
|---|---|---|---|
| 总开关 | 关闭即完全停用（零开销、零审计） | `app_perception.enabled` | false（首版默认关，见 Risks） |
| 插件允许列表 | 按 target 允许的插件名（未列出 ⇒ 全部允许；空列表 ⇒ 该机停用）| `app_perception.allowed_plugins[<target_id>]` | `{}` |
| 声明缺窗口 | 声明了但检测不到时的行为（未决 Q1）| `app_perception.on_declared_window_missing` | `fallback` |
| 每步上限 | 每 TestStep 激活次数 | `app_perception.max_activations_per_step` | 1 |
| 检测置信度 | 低于阈值视为未检测到 | `app_perception.min_detection_confidence` | 0.7 |
| 子窗口面积比 | 矩形/整帧面积必须落在区间内 | `app_perception.roi_area_ratio_min/max` | 0.02 / 0.70 |
| 最小边 | 矩形短边像素下限 | `app_perception.min_roi_size_px` | 96 |
| 目标长边 | 放大后长边目标像素 | `app_perception.target_long_edge_px` | 1600 |
| 倍率夹紧 | scale ∈ [min, max]，且必须 > 1.0 | `app_perception.min_scale` / `max_scale` | 1.2 / 4.0 |
| 像素上限 | 放大图总像素硬顶（再夹一次 scale） | `app_perception.max_upscaled_megapixels` | 4.0 |
| 边缘带 | 还原候选贴 ROI 边缘的记录阈值 | `app_perception.roi_edge_band_ratio` | 0.02 |
| 档案目录 | 声明式档案根目录 | `app_perception.profiles_dir` | `profiles/app_perception` |
| 约束强度 | 尊重档案逐条 `enforce`（已裁决 Q3）；`record_only` 为紧急降级 | `app_perception.anchor_constraint_mode` | `respect_profile` |

### 激活原因码（穷举，进入审计）

`not_declared`（缺省路径）· `declared_off` · `disabled` · `plugin_not_registered` ·
`plugin_not_allowed` · `budget_exhausted` · `non_positional_action` · `not_detected` ·
`low_detection_confidence` · `roi_not_subwindow` · `scale_not_beneficial` · `observation_failed` ·
`activated`

审计另有两个**独立布尔/结构字段**（不是原因码，不改变结论）：
- `declared_but_undetected: bool` —— 声明了却没检测到（FR-013a），用于报告聚合；
- `scope_hint_mismatch: {...} | null` —— 只读警示：本轮目标的文本线索命中项落在检测矩形外或跨内外，
  提示"声明可能写错了"。**永不否决、永不激活。**

### 检测算法（`detector.py`，确定性）

1. 归一化匹配（小写 + 去空白 + 容忍尾部省略号 `…`/`...`）把档案的 `required_anchors` 逐条在
   `screen.ocr_items` 中找命中；任一条零命中 ⇒ `None`。
2. 同一 anchor 多条命中时取置信度最高者（与 014 `_roi_from_anchor_texts` 同一确定性规则）。
3. 矩形推导：全部命中锚点 bbox 的并集，按档案的 `padding_ratio`（默认按并集自身宽高的比例，
   四边可分别声明）外扩；再交给 `recovery/zoom.expand_region` 的 viewing-window 语义规整入界。
4. 合理性校验（FR-008）：含全部锚点 ∧ 面积比 ∈ [min,max] ∧ 宽高比 ∈ 档案区间 ∧ 短边 ≥ 下限。
5. 置信度 = `min(命中锚点 OCR 置信度) × (命中锚点数 / 必需锚点数)`（后者恒为 1，保留字段以便未来
   支持"可选锚点"加权）；低于阈值 ⇒ 视为未检测到。
6. 全过程 try/except 吸收 ⇒ `None`（FR-010）。

> **不做**：边框像素检测 / 连通域分析 / 模板匹配作为**首选**手段。档案可选声明 `template_anchor`
> 走既有 `screen.template_matches` 通道作为补充证据，但 MVP 的主路径是纯 OCR 锚点几何——它零像素
> 开销、完全确定性、离线可复现（research.md 记录了替代方案的取舍）。

### 声明的形态（FR-013）

| 级别 | 载体 | 字段 | 作用 |
|---|---|---|---|
| 步骤级（**唯一激活开关**）| `TestStep` | `perception_scope: str \| null` | 值 = 插件/档案名 ⇒ "本步在该子窗口内操作"；`"none"` 或省略 ⇒ 不激活 |
| 用例级（可选白名单）| `TestCase` | `perception_plugins: list[str]` | 声明本用例允许的插件名；步骤取值不在其中 ⇒ **加载期**报错（抓拼写错误）|
| 部署级（配置）| `agent.yaml` | `app_perception.enabled` / `.allowed_plugins[<target_id>]` | 全局杀开关 + 按被测机器的允许列表（target 未列出 ⇒ 允许全部已注册；显式空列表 ⇒ 该机器停用）|

**多子窗口的指定**：一个档案 = 一个窗口（由其必需锚点集合唯一确定）。同机的多个工具窗口 ⇒ 多个档案；
步骤用 `perception_scope` 写明操作的是哪一个。一个步骤内 MUST NOT 同时激活多个插件。

### 激活判定（`activation.py`，纯函数）

`decide(config, declared_scope, plugin, detection, semantic_action, activations_used) → ActivationDecision`

严格按 FR-011 的 9 级顺序。关键性质：

- **第 1 级就是缺省出口**：`declared_scope` 为 None/"none" ⇒ 立刻返回 `not_declared`；
  调用方在此之前 MUST NOT 做检测——未声明路径必须是零 CPU 的（SC-002 以调用计数断言）。
- **检测不是激活理由**：检测只在"已声明"之后才运行，且只能把结论从"激活"降级为不激活，
  永远不能把未声明的步骤变成激活。
- **文本线索归属降级为只读警示**：线索集合 = `target.text` ∪ `target.nearby_texts`（不含 intent 全文）。
  命中项落在矩形外或跨内外时写入 `scope_hint_mismatch`，**不改变结论**——声明即作者责任，
  但复盘时能一眼看出"这一步的声明写错了"。

判定不做任何 I/O，可 100% 单测覆盖全部原因码。

### 编排（`coordinator.py`）

```
async def enhance(screen, step, semantic_action, *, pipeline) -> (ZoomObservation|None, PerceptionEnhancementAudit)
  0. scope = step.perception_scope；未声明/"none" → audit(not_declared|declared_off)，立即返回（零开销）
  1. enabled / 注册表 / target 允许列表 / 每步预算 / 动作类型 → 对应原因码，返回
  2. plugin = registry.get(scope)；detection = plugin.detect(screen)
     失败 → audit(not_detected|low_detection_confidence|roi_not_subwindow,
                  declared_but_undetected=True)
       · on_declared_window_missing="fallback"（默认）→ 返回 None（回退全帧）
       · on_declared_window_missing="fail" → 抛出可诊断的声明失配（由 runtime 转为本轮失败）
  3. scale = clamp_all(target_long_edge / roi_long_edge, [min,max], 像素上限)
     <=1.0 → audit(scale_not_beneficial)
  4. await pipeline.observe_zoom(roi, scale, step_id, capture_source="app_perception")
     None → audit(observation_failed)（fail-open）
  5. 计算 scope_hint_mismatch（只读警示）；activations_used[step_id] += 1
     返回 (obs, audit(activated=True, ...))
```

`reset_step(step_id)` 由 runtime 在步骤切换时调用（与既有 per-step 状态复位同处）。

### Runtime 接线（`agent_runtime.py`，插入式）

在 `needs_grounding` 分支最内层 `else:`（即真正要调 Grounder 的分支）开头：

```
enhanced, enh_audit = await self.app_perception.enhance(screen, step, sa, pipeline=self.pipeline)
iteration.perception_enhancement = enh_audit
if enhanced is not None:
    grounding_request = GroundingRequest(
        image_ref=enhanced.image_path,
        crop_offset=enhanced.crop_offset,
        scale_factor=enhanced.scale_factor,
        resolution=enhanced.resolution,            # 放大图尺寸
        original_resolution=screen.resolution,
        target=target,
        ocr_candidates=[i.model_dump() for i in enhanced.ocr_items_zoom_space],  # FR-017 同空间
        template_candidates=[...投影入 ROI 的 memory 提示，否则空...],
        ui_index_candidates=[],                    # 原帧坐标，按 FR-017 省略
    )
else:
    <既有全帧请求，一行不改>
```

`zoom_obs is not None` 时根本不进入该 `else`（zoom 分支在更外层），FR-021 由结构保证。
`grounder_identity` 的 `coordinate_transform_identity` 已包含 `scale_factor`/`crop_offset`，
增强路径自动获得区分度，无需改动。

`grounding` 返回后、`policy.resolve` 之前，若本轮增强激活且档案声明了 `anchor_constraints`，
调用 `geometry.evaluate_constraints(...)` 对**已还原到原帧坐标**的候选求值（已裁决 Q3）：
`enforce=true` 的约束违反者被**剔除**出候选列表（剔空则按既有 `target_not_found` 语义继续既有恢复链，
不新增 FailureType）；`enforce=false` 的仅写入 `constraint_violations`。
配置 `anchor_constraint_mode="record_only"` 可一键把全部约束降级为只记录（紧急止血）。

### 数据契约（详见 data-model.md / contracts/）

`ActionIteration.perception_enhancement`（`PerceptionEnhancementAudit`）:

```
enabled: bool                      declared_scope: str | null      # 步骤声明的插件名
plugin_name: str | null            reason_code: <上列 13 个之一>
roi: (x1,y1,x2,y2) | null          detection_method: "ocr_anchors" | "template" | null
detection_confidence: float | null matched_anchors: list[{text, bbox, confidence}]
activated: bool                    declared_but_undetected: bool
scope_hint_mismatch: {clue_texts, hits_inside, hits_outside} | null
scale_factor: float | null         zoom_image_ref: str | null
upscaled_resolution: (w,h) | null  constraint_violations: [{constraint, candidate_bbox, mode}]
```

`TestStep.perception_scope: str | null` —— 插件名 或 `"none"`（显式关闭）；省略 ⇒ 等同 `"none"`。
`TestCase.perception_plugins: list[str]` —— 可选白名单，加载期校验步骤取值。

### 测试策略

| 层 | 文件 | 覆盖 |
|---|---|---|
| unit | `test_app_perception_profile.py` | 档案 schema 校验：缺锚点/几何矛盾/倍率越界 ⇒ 加载期报错（SC-008）；重名注册报错 |
| unit | `test_app_perception_detection.py` | 锚点→矩形、多命中取最高置信、面积/宽高比/最小边拒绝、置信度合成、同输入同输出（确定性）、异常吸收 |
| unit | `test_app_perception_activation.py` | FR-011 全部 13 个原因码各一例；**未声明 ⇒ 零检测调用**（以 mock 调用计数断言，SC-002 的判定层保证）；`declared_but_undetected` 两种模式；`scope_hint_mismatch` 只记录不改结论 |
| unit | `test_app_perception_declaration.py` | 用例加载期校验：`perception_scope` 未注册名报错（含字段路径 + 可选值）、用例级白名单越界报错、`"none"`/省略等价 |
| unit | `test_app_perception_geometry.py` | AnchorConstraint 四类关系 + 容差；原帧↔放大图空间投影；ROI 边缘带识别；`restore_original_bbox` 组合回归 |
| unit | `test_domain_agnostic_core.py`（新增断言）| 对 `src/vnc_agent/` 做业务禁词扫描零命中（SC-005 前半） |
| e2e | `test_scenario_23_app_perception_enhancement.py` | 同一 fixture 四个场景（对应 spec 附录）：两个**声明**了范围的窗口内步骤 ⇒ 激活且点击坐标逐像素等于手算还原值（SC-001）；两个**未声明**的主画面步骤 ⇒ `not_declared` 且请求与基线逐字节相同（SC-002）；Grounder 调用计数不变（SC-004）；声明了但窗口不在画面上 ⇒ `fallback` 回退 + `declared_but_undetected` 审计 |
| fixtures | `test_cross_scenario_coverage.py`（扩展）| 两个互不相关场景档案跑同一套核心（SC-005 后半） |
| 回归 | `e2e/conftest.py` | legacy 场景钉 `app_perception.enabled=false`（022/023 先例），保证 SC-007 |

## Complexity Tracking

> Constitution Check 全部通过，无需偏离豁免。以下记录两处**有意识的复杂度**及其理由。

| 复杂度 | 为什么需要 | 被否决的更简方案 |
|---|---|---|
| 独立的插件包 + 声明式档案（而不是在 runtime 里写一个 if） | Principle VI 是硬红线：核心不得含被测应用知识。档案化是唯一能同时满足"可插拔""可审计""两场景验证"的形态 | 直接在 grounding 分支写"如果检测到某窗口就放大"——违反 VI，且第二个应用来了要改核心 |
| `ZoomObservation` 追加 `ocr_items_zoom_space` 字段 | FR-017 要求图像与提示同坐标空间；014 现状是混合空间。追加字段能让 024 正确、同时 014 逐字节不变 | 直接改 `observe_zoom` 的返回语义——会改变 014 的下发负载，触发 014 的 e2e/golden 变更且超出本 feature 范围 |

## Risks & 与既有 feature 的关系

- **R1 激活假阳性**（用户裁决后已从"最大风险"降级为**结构性消除**）：激活的唯一来源是用例的显式
  `perception_scope` 声明，系统没有任何隐式/推断激活路径，因此"不该放大却放大"只可能源于用例作者
  写错声明——而这是可审阅、可 diff、可在报告中被 `scope_hint_mismatch` 警示指出的。残余缓解：
  首版 `enabled` 默认 **false** + e2e 断言未声明步骤 0% 激活且零检测调用。
- **R1b 新增风险：声明遗漏（假阴性）**：需要增强的步骤忘了写声明 ⇒ 静默退回现状行为，没有任何提示。
  这是"显式声明模型"的固有代价，且方向是安全的（不比现状差）。缓解：报告中给出"本 run 中有 N 个
  步骤在检测范围内的画面上做了点击但未声明"的**离线**统计建议（不进运行时热路径，作为未来 evolution
  导出项），以及在档案 README 中给出标注指南。
- **R2 与 014 的关系**：互补而非重叠——014 是失败后的定向补救（ROI 来自失败候选），024 是先验前置
  （ROI 来自档案锚点）。结构上不可能叠加（FR-021 由接线位置保证）。024 激活后仍失败时，014 照常
  在后续迭代触发，且它从**原帧**重新裁剪，不继承 024 的 ROI。
- **R3 与 015 memory 的关系**：memory 高置信直接点击优先级更高（增强根本不执行）；memory 中置信提示
  是原帧坐标，增强路径下需投影入 ROI 才能下发，落在 ROI 外则丢弃并记入审计——这是一处**能力轻微
  降级**（增强激活的那一轮丢掉窗口外的 memory 提示），但由于该轮的目标本来就被判定在窗口内，影响可忽略。
- **R4 与 022/023 的关系**：023 的修正点击优先级更高（不调 Grounder）；022 的 stale-frame 守卫在执行前
  独立运行，与观察分辨率无关。均无冲突。
- **R5（跟进项，不在本 feature 范围）**：feature 014 的 zoom 请求把**原帧坐标**的 `ocr_candidates`
  与**放大图**一起下发，属于坐标空间不一致，可能降低 014 的定位质量。本 feature 不改动它（避免污染
  014 的 e2e/golden），但**建议单独开一个小 feature 修正**。
- **R6 档案维护成本**：档案里的锚点文本依赖 OCR 能稳定读出。当前部署的 OCR 是日文模型，用例注释显示
  假名会被读花——因此档案的 `required_anchors` 应优先选 ASCII/数字/汉字锚点。该约束写入档案 README 与
  quickstart，不进核心代码。
