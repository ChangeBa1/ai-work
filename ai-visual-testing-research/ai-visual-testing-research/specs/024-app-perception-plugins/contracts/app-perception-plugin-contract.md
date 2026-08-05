# Contract: 应用感知增强扩展点

**Feature**: `024-app-perception-plugins` | **Date**: 2026-07-28

本文件定义三份契约：(A) 插件扩展点协议，(B) 声明式档案文件格式，(C) 用例声明与审计输出。
契约的稳定性承诺：**A/B/C 的字段名与语义在本 feature 内视为公开接口**，变更需要新的 spec。

---

## A. 插件扩展点协议（`perception/app_plugins/base.py`）

```python
class AppPerceptionPlugin(Protocol):
    @property
    def name(self) -> str:
        """全局唯一标识；即测试用例 `perception_scope` 的取值。"""

    def detect(self, screen: StructuredScreen) -> SubWindowDetection | None:
        """在当前帧中定位本插件描述的那个子窗口。

        约束（实现方 MUST 遵守）：
        - 纯函数：同一 `screen` 必须得到同一结果（不得依赖时间/随机/外部状态）。
        - 只读：不得修改 `screen`，不得触发抓屏、OCR 或任何 I/O。
        - 只消费 `screen` 已有的 `ocr_items` / `template_matches` / `resolution`。
        - 失败一律返回 None，不得抛出（框架仍会兜底捕获）。
        - 返回的 `region` 必须是原帧像素坐标且已入界。
        """

    def activation_vote(self, ctx: ActivationContext) -> ActivationVote:
        """可选的插件侧否决通道。默认实现返回 ABSTAIN。

        重要：`REQUIRE` **不能**把未声明的步骤变成激活——激活的唯一来源是用例声明
        （FR-011/FR-012）。插件投票只能起否决作用（VETO），REQUIRE 保留给未来扩展，
        当前框架把它等同 ABSTAIN 处理。
        """
```

`ActivationVote = Literal["require", "veto", "abstain"]`

`ActivationContext`（只读、通用）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `step_id` | `str` | — |
| `declared_scope` | `str \| None` | 步骤声明值 |
| `action_type` | `str` | 语义动作类型 |
| `target` | `dict \| None` | 语义动作的目标描述（`text` / `role` / `nearby_texts` …） |
| `detection` | `SubWindowDetection` | 已成功的检测结果 |
| `resolution` | `tuple[int,int]` | 原帧分辨率 |

**注册表契约**（`registry.py`）：

```python
class PluginRegistry:
    def register(self, plugin: AppPerceptionPlugin) -> None: ...   # 重名 -> 抛错
    def get(self, name: str) -> AppPerceptionPlugin | None: ...
    def names(self) -> list[str]: ...                              # 排序稳定
    @classmethod
    def from_profiles_dir(cls, path: Path) -> "PluginRegistry": ...  # 加载 + 校验全部档案
```

- 目录不存在 ⇒ 返回空注册表（**不是**错误：等价于"这台机器没有装任何档案"）。
- 任一档案非法 ⇒ 抛出含**文件路径 + 字段路径**的加载错误（SC-008）。
- `names()` 顺序稳定（字典序），保证多插件场景下的确定性。

---

## B. 声明式档案格式（`profiles/app_perception/<name>.yaml`）

```yaml
# 档案是本 feature 中唯一允许出现被测应用词汇的地方。
name: <plugin-name>              # 必填，[a-z0-9-]+，全局唯一，= perception_scope 的取值
description: >-                  # 可选，人类可读
  一句话说明这是哪个应用的哪个窗口。

required_anchors:                # 必填，>= 2 条；必须全部命中才算检测成功
  - "<anchor text 1>"
  - "<anchor text 2>"
title_anchor: "<window title>"   # 可选：标题栏文本，命中时参与矩形推导
template_anchor: "<template-id>" # 可选：既有模板匹配通道里的模板 id

padding_ratio:                   # 可选：相对锚点并集宽/高的四边外扩比例
  left: 0.05
  right: 0.05
  top: 0.08
  bottom: 0.05

# 形状先验只允许住在档案里（核心一律不内置形状默认值）。
# 三项全为【可选】；不写就只走核心的两条形状无关兜底。
min_required_anchor_hits: 3      # 可选，默认 = len(required_anchors)
area_ratio_range: [0.05, 0.60]   # 可选
aspect_ratio_range: [0.4, 2.5]   # 可选，宽/高比
min_size_px: 120                 # 可选

zoom:                            # 可选：覆盖固定倍率（不由窗口尺寸推导）
  scale: 2.5

# 可选：由界面定义源文件离线导出的相对几何（生成脚本产出草稿 + 人工核对）
source_geometry:
  client_size: [423, 581]        # 设计期客户区（宽, 高）
  controls:
    - name: label1
      text: "Barcode:"
      rect: [10, 6, 58, 18]      # 设计期客户区坐标
      anchors: [top, left]
    - name: btnScan
      text: "Scan"
      rect: [331, 526, 406, 549]
      anchors: [bottom, right]   # 拉伸后仍贴右下角

anchor_constraints:              # 可选：通用相对位置约束
  - subject: "<label, 仅用于审计文本>"
    relation: same_row           # same_row|same_column|right_of|left_of|above|below|between
    anchors: ["<anchor text>"]   # between 需要恰好 2 条，其余恰好 1 条
    tolerance_ratio: 0.25
    # 逐条强弱标志（用户裁决 Q3）：
    #   true  -> 强先验：违反该约束的候选被【拒绝】（从 Grounding 结果中剔除）
    #   false -> 弱提示：仅写入审计 constraint_violations，不剔除候选（默认）
    # 部署侧可用 app_perception.anchor_constraint_mode=record_only 一键降级全部约束。
    enforce: false
```

**锚点选择指南**（写入 `profiles/app_perception/README.md`，不进核心代码）：

- 优先选 **ASCII / 数字 / 汉字** 锚点。当前部署的 OCR 识别模型对部分假名不稳定
  （目标用例注释已记录"假名会被读花"），假名锚点会造成检测时灵时不灵。
- 锚点应**分布在窗口的上/中/下部**，这样并集就能覆盖整窗，`padding_ratio` 只需小幅补偿边框。
- 不要选那些**在窗口外也会出现**的文本（否则并集会被拉到窗口外，触发 `roi_not_subwindow`）。
- 不要选会随数据变化的文本（表格内容、计数器数值）；选固定标签、按钮文案、状态栏固定文字。

---

## C. 用例声明 与 审计输出

### C.1 用例声明

```yaml
# TestCase 级（可选白名单，用于加载期抓拼写错误）
perception_plugins:
  - <plugin-name-a>
  - <plugin-name-b>

steps:
  - id: <step-in-subwindow>
    # 步骤级：唯一的激活开关。值 = 插件名 ⇒ "本步骤在该子窗口内操作"
    perception_scope: <plugin-name-a>
    ...

  - id: <step-on-main-screen>
    # 省略即不激活。也可显式写 "none" 以表达作者的有意判断。
    perception_scope: none
    ...
```

**加载期校验**：
- `perception_scope` 非空且非 `"none"` 时，必须存在于注册表（若声明了用例级白名单，则必须同时属于白名单），
  否则报错，错误信息含 `steps[i].perception_scope` 字段路径与可选值列表。
- `perception_plugins` 中的名字必须全部已注册。

**语义**：省略 ≡ `"none"` ≡ 不激活 ≡ 与关闭本 feature 逐字节一致。

### C.2 Grounding 请求的增强形态（激活时）

| 字段 | 未激活（现状） | 激活 |
|---|---|---|
| `image_ref` | 全帧图（`screen.path_for_model()`） | 放大图路径 |
| `crop_offset` | `screen.crop_offset` | ROI 左上角（原帧坐标） |
| `scale_factor` | 缺省 `1.0` | 实际倍率 `> 1.0` |
| `resolution` | 全帧分辨率 | **放大图**分辨率 |
| `original_resolution` | 缺省 `None` | 原帧分辨率 |
| `ocr_candidates` | 全帧 OCR 项 | 放大图坐标系的 OCR 项（`ocr_items_zoom_space`） |
| `template_candidates` | 全帧模板 + memory 提示 | 仅能投影进 ROI 的提示；否则空 |
| `ui_index_candidates` | UI 索引候选 | 空（原帧坐标，按 FR-017 省略） |

**坐标还原**（既有链路，零改动）：先在 `resolution`（=放大图）下 `resolve_pixel_bbox`，
再 `restore_original_bbox(bbox, scale_factor=..., crop_offset=..., original_resolution=...)`
= `round(v/scale)+offset`，越界/退化 ⇒ 拒绝候选（不 clamp、不猜）。

### C.3 审计输出（`ActionIteration.perception_enhancement`）

JSON 形状（缺省 `null`；字段语义见 data-model.md §1.7）：

```json
{
  "enabled": true,
  "declared_scope": "<plugin-name>",
  "plugin_name": "<plugin-name>",
  "activated": true,
  "reason_code": "activated",
  "declared_but_undetected": false,
  "roi": [x1, y1, x2, y2],
  "detection_method": "ocr_anchors",
  "detection_confidence": 0.93,
  "matched_anchors": [{"anchor_text": "...", "matched_text": "...", "bbox": [...], "confidence": 0.95}],
  "scale_factor": 2.6,
  "upscaled_resolution": [1092, 1600],
  "zoom_image_ref": "runs/<run>/…/zoom_<n>.png",
  "scope_hint_mismatch": null,
  "constraint_violations": []
}
```

未激活时 `activated=false`、`reason_code` 为对应否决码，几何字段为 `null`，`zoom_image_ref` 为 `null`。

**不变量（可测）**：
1. 每个进入 Grounding 分支的迭代恰有一条记录（FR-024 / SC-006）。
2. `activated=true` ⟺ `reason_code == "activated"` ⟺ `zoom_image_ref != null`。
3. `reason_code == "not_declared"` ⇒ 全部几何字段为 null 且**本轮未调用任何 `detect()`**。
4. `declared_but_undetected=true` ⇒ `declared_scope != null` 且 `activated=false`。
5. `enabled=false` ⇒ 不产生任何记录（键为 `null`），Grounding 请求负载与基线逐字节相同。
