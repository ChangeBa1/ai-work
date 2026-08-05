# Phase 1 Data Model: 应用感知增强插件框架

**Feature**: `024-app-perception-plugins` | **Date**: 2026-07-28

全部新增模型都是**通用结构**（几何 + 文本 + 置信度），不含任何被测应用词汇。业务词汇只出现在
`PluginProfile` 的**实例数据**（YAML 档案文件）里，不在任何 schema 的字段名或枚举值里。

---

## 1. 新增领域模型（`domain/app_perception.py`）

### 1.1 `SubWindowDetection`

一次子窗口检测的结果。

| 字段 | 类型 | 约束 / 语义 |
|---|---|---|
| `plugin_name` | `str` | 产出该检测的插件/档案名 |
| `region` | `Region` | 子窗口矩形，**原帧像素坐标**，已按 viewing-window 语义入界 |
| `confidence` | `float` | `[0,1]`；`min(命中锚点置信度) × (命中数/必需数)` |
| `method` | `Literal["ocr_anchors","template"]` | 检测手段 |
| `matched_anchors` | `list[AnchorHit]` | 每个必需锚点的命中项（文本、bbox、置信度） |
| `area_ratio` | `float` | `region` 面积 / 整帧面积，供合理性校验与审计 |

不变量：`region` 必须包含全部 `matched_anchors[*].bbox`；`area_ratio ∈ [cfg.roi_area_ratio_min, max]`；
短边 ≥ `cfg.min_roi_size_px`。任一不成立 ⇒ 检测返回 `None`（不构造该对象）。

### 1.2 `AnchorHit`

| 字段 | 类型 | 语义 |
|---|---|---|
| `anchor_text` | `str` | 档案里声明的锚点文本（归一化前的原文） |
| `matched_text` | `str` | 实际命中的 OCR 文本 |
| `bbox` | `tuple[int,int,int,int]` | 原帧坐标 |
| `confidence` | `float` | 该 OCR 项的置信度 |

### 1.3 `ActivationDecision`

| 字段 | 类型 | 语义 |
|---|---|---|
| `activated` | `bool` | 最终结论 |
| `reason_code` | `ActivationReason` | 见 §1.4，穷举枚举 |
| `declared_scope` | `str \| None` | 步骤声明的插件名（未声明为 None） |
| `declared_but_undetected` | `bool` | 声明成立但检测失败（FR-013a） |
| `scope_hint_mismatch` | `ScopeHintMismatch \| None` | 只读警示，**永不改变 `activated`** |

### 1.4 `ActivationReason`（Literal 枚举，穷举）

```
not_declared            # 缺省路径：步骤未声明（绝大多数步骤）
declared_off            # 步骤显式声明 "none"
disabled                # 全局开关关闭
plugin_not_registered   # 声明的插件名不在注册表中（正常应在加载期拦截）
plugin_not_allowed      # 该 target 的允许列表未包含它
budget_exhausted        # 本步骤激活次数已达上限
non_positional_action   # 本轮动作不产出坐标
not_detected            # 必需锚点未全部命中 / 几何退化
low_detection_confidence
roi_not_subwindow       # 面积比例超出区间（含"退化成近似全屏"）
scale_not_beneficial    # 计算出的倍率 <= 1.0
observation_failed      # observe_zoom 返回 None（fail-open）
activated               # 唯一的成功值
```

### 1.5 `ScopeHintMismatch`（只读警示）

| 字段 | 类型 | 语义 |
|---|---|---|
| `clue_texts` | `list[str]` | 本轮用于比对的线索（`target.text` ∪ `nearby_texts`） |
| `hits_inside` | `int` | 命中 OCR 项中心落在检测矩形内的数量 |
| `hits_outside` | `int` | 落在矩形外的数量 |
| `kind` | `Literal["all_outside","straddling"]` | 警示类型 |

仅当 `activated=True` 且 `hits_outside > 0` 时非空。

### 1.6 `AnchorConstraint`（通用相对位置约束）

| 字段 | 类型 | 语义 |
|---|---|---|
| `subject` | `str` | 被约束对象的标签（档案内自定义，仅用于审计文本） |
| `relation` | `Literal["same_row","same_column","right_of","left_of","above","below","between"]` | 通用几何关系 |
| `anchors` | `list[str]` | 参与关系的锚点文本；`between` 需要恰好 2 个，其余恰好 1 个 |
| `tolerance_ratio` | `float` | `[0,1]`，相对参考尺寸的容差（默认 0.25） |
| `enforce` | `bool` | **逐条强弱标志（用户裁决）**：`true` ⇒ 违反者**拒绝候选**（强先验）；`false`（默认）⇒ 仅记录违规。可被配置 `anchor_constraint_mode="record_only"` 统一降级 |

求值输入是**已还原到原帧坐标**的候选 bbox 与当前帧的锚点 bbox；纯几何，不含任何业务判断。

### 1.7 `PerceptionEnhancementAudit`

挂在 `ActionIteration.perception_enhancement` 上，每个进入 Grounding 分支的迭代必有一条。

| 字段 | 类型 | 语义 |
|---|---|---|
| `enabled` | `bool` | 全局开关状态（便于复盘时区分"关了"与"没声明"） |
| `declared_scope` | `str \| None` | 步骤声明值 |
| `plugin_name` | `str \| None` | 实际运行检测的插件（未声明时为 None） |
| `activated` | `bool` | — |
| `reason_code` | `ActivationReason` | — |
| `declared_but_undetected` | `bool` | — |
| `roi` | `tuple[int,int,int,int] \| None` | 检测矩形，原帧坐标 |
| `detection_method` | `str \| None` | — |
| `detection_confidence` | `float \| None` | — |
| `matched_anchors` | `list[AnchorHit]` | 默认空 |
| `scale_factor` | `float \| None` | 实际使用的倍率 |
| `upscaled_resolution` | `tuple[int,int] \| None` | 放大图尺寸 |
| `zoom_image_ref` | `str \| None` | 放大图 artifact 路径（安全遮罩版本） |
| `scope_hint_mismatch` | `ScopeHintMismatch \| None` | — |
| `constraint_violations` | `list[ConstraintViolation]` | 默认空 |
| `ocr_items_replaced` | `int` | 窗口内被精炼读数取代的全帧 OCR 项数 |
| `ocr_items_added` | `int` | 精炼后加入的 OCR 项数 |
| `grounding_reached` | `bool` | 本迭代是否真的走到 grounding；`false` 表示动作被更早解析（OCR 直接点击 / 记忆 / 回放）|
| `geometric_prediction` | `GeometricPrediction \| None` | 非空即本轮尝试过几何推算；`applied=True` 表示点击来自确定性几何而非模型 |
| `grounder_image` | `"full_frame" \| "app_perception_zoom" \| "zoom_reground" \| None` | 本轮 grounder 实际收到的图像类型。用于复盘"点歪了到底是因为它只看到全帧，还是看了放大图仍然错"|

`ConstraintViolation`: `{constraint: AnchorConstraint, candidate_bbox: tuple, mode: "record_only"|"enforced"}`。

---

## 2. 声明式档案 schema（`perception/app_plugins/profile.py`）

`PluginProfile` —— 一个档案文件 = 一个子窗口。文件位于 `profiles/app_perception/<name>.yaml`。

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `name` | `str` | ✅ | 全局唯一；`[a-z0-9-]+`；即 `perception_scope` 的取值 |
| `description` | `str` | — | 人类可读说明（档案是唯一允许写业务词汇的地方） |
| `required_anchors` | `list[str]` | ✅ | 至少 2 条；必须全部命中才算检测成功 |
| `title_anchor` | `str \| None` | — | 可选的标题锚点，命中时参与矩形推导并提升可读性 |
| `template_anchor` | `str \| None` | — | 可选：既有 `screen.template_matches` 中的模板 id |
| `min_required_anchor_hits` | `int \| None` | — | 需命中的锚点数；默认 = `len(required_anchors)`。核心**不写死** "≥2" |
| `padding_ratio` | `dict[str,float]` | — | `{left,right,top,bottom}`，相对锚点并集宽/高的外扩比例；默认全 0.05 |
| `area_ratio_range` | `tuple[float,float] \| None` | — | **可选**的逐窗口范围；未声明则只做核心兜底，**不套用任何内置形状默认** |
| `aspect_ratio_range` | `tuple[float,float] \| None` | — | 同上（形状先验只允许存在于档案） |
| `min_size_px` | `int \| None` | — | 同上 |
| `zoom` | `ZoomOverride \| None` | — | `{scale}` 覆盖固定倍率（FR-005b） |
| `anchor_constraints` | `list[AnchorConstraint]` | — | 默认空 |
| `source_geometry` | `SourceGeometry \| None` | — | 由界面定义源文件离线导出（见 §2.1） |

**加载期校验（SC-008）**：`required_anchors` 为空、`min_required_anchor_hits` 越界、
`area_ratio_range`/`aspect_ratio_range` 下界≥上界、`zoom.scale <= 1.0`、
`between` 关系的 `anchors` 不是 2 个、`name` 重复、`source_geometry` 的 `client_size` 非正 ——
全部在加载期抛出，错误信息含**档案文件路径 + 字段路径**。

### 2.1 `SourceGeometry`（源码派生的相对几何，FR-005c）

| 字段 | 类型 | 语义 |
|---|---|---|
| `client_size` | `tuple[int,int]` | 设计期客户区尺寸（宽, 高），必须为正 |
| `controls` | `list[ControlGeometry]` | 控件列表 |

`ControlGeometry`:

| 字段 | 类型 | 语义 |
|---|---|---|
| `name` | `str` | 设计期控件名（仅用于审计与档案可读性） |
| `text` | `str \| None` | 字面文本；非空者可直接充当 OCR 锚点候选 |
| `rect` | `tuple[int,int,int,int]` | 设计期矩形，**客户区坐标**（不是屏幕坐标） |
| `anchors` | `list[Literal["top","bottom","left","right"]]` | 停靠边；空列表表示两轴皆不停靠 |

**映射规则（FR-005d，纯函数，`map_control_rect`）**：设设计期客户区 `(W,H)`、实测窗口
`R=(X1,Y1,X2,Y2)`、实测尺寸 `(AW,AH)`，取统一缩放 `s = min(AW/W, AH/H)`（吸收 DPI 缩放），
残差 `dx = AW - W*s`、`dy = AH - H*s`（吸收用户拉伸）。每轴按停靠语义：

| 停靠 | X 轴映射 |
|---|---|
| `left` | `x1' = X1 + x1*s`，宽度保持 `w*s` |
| `right` | `x2' = X2 - (W-x2)*s`，宽度保持 `w*s` |
| `left`+`right` | `x1' = X1 + x1*s`，`x2' = X2 - (W-x2)*s`（随拉伸） |
| 皆无 | `x1' = X1 + x1*s + dx/2`，宽度保持 `w*s`（居中浮动） |

Y 轴同理（`top`/`bottom`）。等比缩放时 `dx=dy=0`，四种规则**退化为同一结果**（可测的一致性性质）。
映射结果退化或越出 `R` 时返回 `None`（不 clamp）。

**用途红线（FR-005e）**：映射结果只进 (a) 增强请求的提示通道、(b) `AnchorConstraint` 求值。
**MUST NOT** 成为点击坐标。

---

## 3. 既有模型的增量改动（全部 additive，默认值保持现状）

| 模型 | 新增字段 | 默认 | 说明 |
|---|---|---|---|
| `domain/run.py::ActionIteration` | `perception_enhancement: PerceptionEnhancementAudit \| None` | `None` | 非 Grounding 迭代恒为 None |
| `domain/testcase.py::TestStep` | `perception_scope: str \| None` | `None` | **唯一激活开关** |
| `domain/testcase.py::TestCase` | `perception_plugins: list[str]` | `[]` | 可选白名单；非空时校验步骤取值 |
| `perception/pipeline.py::ZoomObservation` | `ocr_items_zoom_space: list[OCRItem]` | `[]` | 放大图坐标系的 OCR 项（FR-017）；014 调用点不读它 ⇒ 014 行为不变 |
| `config.py::AgentConfig` | `app_perception: AppPerceptionConfig` | 见 §4 | 顶层新段 |

`reporting/json_report.py` 增加一个可空迭代键 `perception_enhancement`（缺省 `null`），
`tests/fixtures/test_json_report_compatibility.py::_LEGACY_ITERATION_KEYS` 同步扩充。

---

## 4. 配置模型（`config.py::AppPerceptionConfig`）

| 键 | 类型 | 默认 | 约束 |
|---|---|---|---|
| `enabled` | `bool` | `false` | 关闭 ⇒ 全链路零开销、零审计（FR-026） |
| `profiles_dir` | `str` | `profiles/app_perception` | 相对仓库根；目录不存在 ⇒ 注册表为空（非错误） |
| `allowed_plugins` | `dict[str, list[str]]` | `{}` | key = `target_id`；key 缺席 ⇒ 允许全部；空列表 ⇒ 该 target 停用 |
| `max_activations_per_step` | `int` | `1` | `ge=0`；0 = 停用 |
| `min_detection_confidence` | `float` | `0.7` | `[0,1]` |
| `roi_area_ratio_min` | `float` | `0.02` | `(0,1)`，且 `< max` |
| `roi_area_ratio_max` | `float` | `0.70` | `(0,1]` |
| `min_roi_size_px` | `int` | `96` | `ge=16` |
| `target_long_edge_px` | `int` | `1600` | `ge=256` |
| `min_scale` | `float` | `1.2` | `> 1.0`，且 `< max_scale` |
| `max_scale` | `float` | `4.0` | `le=8.0` |
| `max_upscaled_megapixels` | `float` | `4.0` | `> 0`；用于再次夹紧倍率（弱配置电脑约束） |
| `roi_edge_band_ratio` | `float` | `0.02` | `[0,0.5)` |
| `on_declared_window_missing` | `Literal["fallback","fail"]` | `fallback` | 已裁决 Q1 |
| `anchor_constraint_mode` | `Literal["respect_profile","record_only"]` | `respect_profile` | 已裁决 Q3：默认尊重档案的逐条 `enforce`；`record_only` 是紧急降级开关（全部约束只记录） |

---

## 5. 状态与生命周期

- **注册表**：进程启动时按 `profiles_dir` 一次性加载并校验全部档案；运行期只读，不热重载。
- **每步预算**：`coordinator` 持有 `dict[step_id, int]`，`reset_step()` 在步骤切换时清零。
- **一次性**：增强不跨迭代传递任何状态——每次迭代独立判定，没有 014 那样的 pending plan。
  这也意味着没有"泄漏到下一步骤"的风险。


---

## 6. `GeometricPrediction`（几何推算审计，FR-005e..j）

| 字段 | 类型 | 语义 |
|---|---|---|
| `control_name` | `str` | 步骤 `perception_target` 指名的控件 |
| `applied` | `bool` | 是否真的用它产生了点击 |
| `reject_reason` | `str \| None` | `not_enhanced` / `no_source_geometry` / `unknown_control` / `transform_rejected` / `outside_window` |
| `predicted_rect` | `tuple \| None` | 预测的屏幕矩形（原帧像素） |
| `click_point` | `tuple \| None` | 经 `safe_click_point` 得到的落点 |
| `scale_x` / `scale_y` / `offset_x` / `offset_y` | `float \| None` | 解出的每轴仿射参数 |
| `anchor_count` | `int` | 参与拟合的锚点数 |
| `max_residual_px` | `float \| None` | 最大回代残差 |
| `residuals` | `list[[name, dx, dy]]` | 逐锚点残差，用于判断是不是窗口被拉伸 |

**`TestStep.perception_target: str | None`** —— 指名控件；需与 `perception_scope` 同时声明。
