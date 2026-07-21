# Contract: Grounding 坐标空间协议

**Feature**: [../spec.md](../spec.md) | **Data Model**: [../data-model.md](../data-model.md)

对应 FR-012~017。本契约定义 Grounder 响应中 `coordinate_space` 字段的取值约定、
`models/coordinate_space.py::resolve_pixel_bbox()` 的换算/拒绝规则，以及
`models/mimo_grounder.py::MimoGrounderClient.ground()` 的行为变更。

## 1. Grounder 响应 wire 格式增量

在 001 已确立的 Grounding JSON 响应格式基础上，每个候选新增一个字段：

```json
{
  "found": true,
  "candidates": [
    {
      "bbox": [251, 402, 405, 459],
      "coordinate_space": "normalized_1000",
      "confidence": 0.95,
      "label": "レジ袋",
      "reason": "..."
    }
  ]
}
```

`coordinate_space` 的合法取值 MUST 是 `"pixel"` 或 `"normalized_1000"` 之一；模型
未输出该字段时，`GroundingCandidate.coordinate_space` 解析为 `None`（历史/未升级
响应的兼容路径，见 §3）。系统提示词（`_GROUNDING_SYSTEM_PROMPT`）MUST 明确要求模型
为每个候选提供该字段，并说明：`"pixel"` 表示 bbox 数值直接是图片内的原始像素坐标；
`"normalized_1000"` 表示 bbox 的四个数值各自独立按 X 轴 0–1000 相对宽度、Y 轴 0–1000
相对高度归一化。

## 2. `models.coordinate_space.resolve_pixel_bbox`

```python
def resolve_pixel_bbox(
    raw_bbox: tuple[int, int, int, int],
    declared_space: Literal["pixel", "normalized_1000"] | None,
    resolution: tuple[int, int],
    *,
    siblings: Sequence[GroundingCandidate] = (),
) -> tuple[int, int, int, int] | None: ...
```

**契约保证**：

- 纯函数，MUST NOT 发起任何网络请求或 VNC 操作。
- `declared_space == "normalized_1000"` 时，MUST 校验 `raw_bbox` 四个分量均落在
  闭区间 `[0, 1000]`（0 与 1000 本身合法，不视为越界）；校验通过后 MUST 按
  `x' = x * resolution[0] / 1000`、`y' = y * resolution[1] / 1000` 独立换算两个轴，
  四舍五入取整。
- `declared_space == "pixel"` 时 MUST NOT 做任何数值变换，只校验四角落在
  `[0, resolution[0]) × [0, resolution[1])` 内。
- 任一方向校验失败（越界）MUST 返回 `None`（拒绝该候选），MUST NOT 返回一个
  裁剪/夹紧（clamp）后的"修正"坐标——越界即拒绝，不得静默修正后仍然使用。
- `declared_space is None` 时，MUST 分别按 `"pixel"`、`"normalized_1000"` 两种
  假设试算，仅当**恰好一种**假设同时满足"换算/校验后落在分辨率范围内"与"和
  `siblings` 中已声明坐标空间的候选不矛盾（如同一响应内另一候选已声明
  `coordinate_space` 时，数值量级应与之匹配）"，才返回该假设下的换算结果；两种假设
  都满足、都不满足、或 `siblings` 证据本身冲突时，MUST 返回 `None`。
- 本函数 MUST 是代码库中**唯一**调用点为 `models/mimo_grounder.py::
  MimoGrounderClient.ground()`（生产路径）与 `models/mimo_grounder.py::StubGrounder`
  （离线测试路径）；其它任何模块 MUST NOT 独立实现坐标空间换算逻辑。

## 3. `MimoGrounderClient.ground()` 行为变更

```python
async def ground(self, request: GroundingRequest) -> GroundingResult: ...
```

**契约保证（对 001 既有契约的增量约束）**：

- 解析响应、应用 `crop_offset` 平移（既有 `_apply_crop_and_cap()`）之后，MUST 对
  **每个**候选独立调用 §2 `resolve_pixel_bbox()`；返回 `None` 的候选 MUST 从最终
  `GroundingResult.candidates` 中剔除，MUST NOT 以任何猜测坐标的方式保留。
- 若全部候选均被剔除，`GroundingResult.found` MUST 为 `False`、`candidates` MUST
  为空列表（与 001 `found_consistency` 校验器已有的不变量一致，不需要新增校验）。
- 返回的 `GroundingCandidate.bbox` MUST 是 §2 换算后的原始像素坐标；
  `GroundingCandidate.coordinate_space`/`raw_bbox` MUST 分别保留该候选**声明**的
  坐标空间与**换算前**的原始数值，供报告审计（FR-026/036），MUST NOT 被换算结果
  覆盖或丢弃。
- 下游消费方（`planning/action_policy.py::ActionPolicy`、`execution/router.py::
  ExecutionRouter`）MUST 将 `GroundingCandidate.bbox` 视为已经是可信原始像素坐标，
  MUST NOT 再次判断或转换其坐标空间。

## 4. `ActionPolicy` 的执行前 OCR 合理性核对（增量约束）

`planning/action_policy.py::ActionPolicy._from_grounding()`/
`_executable_from_candidate()` 在候选已通过 §2 换算之后，新增：

- 当 `SemanticAction.target.text` 非空且 `StructuredScreen.ocr_items` 中存在与之
  唯一匹配的锚点时，候选中心点与该锚点中心的欧氏距离超过
  `config.agent.planning.ocr_sanity_check_ratio × min(width, height)`（默认比例
  `0.10`）MUST 视为与已有 OCR 证据矛盾，MUST 拒绝该候选（返回 `PolicyResult(
  outcome="stop_recover", failure_type=FailureType.TARGET_NOT_FOUND, ...)` 或等效的
  既有失败分类），MUST NOT 仍然执行点击。
- 不存在唯一匹配的 OCR 锚点时，本项核对 MUST NOT 触发（不产生额外拒绝），MUST NOT
  因为"没有 OCR 证据"就默认拒绝候选——本条只在**有明确矛盾证据**时生效。

## 5. 契约总结：三条不可违反的不变量

1. **单一换算点**：`resolve_pixel_bbox()` 只在 `mimo_grounder.py` 内被调用一次；
   `GroundingCandidate.bbox` 一旦离开 `models/` 边界，永远是最终原始像素坐标
   （FR-014）。
2. **越界/矛盾即拒绝，不猜测**：任何未通过 §2/§4 校验的候选 MUST 被剔除或阻止执行，
   MUST NOT 被裁剪、夹紧或忽略校验后仍然使用（FR-013/016）。
3. **声明与推断分离**：`coordinate_space` 显式声明时 MUST 直接采信（不做双重验证
   猜测）；仅缺失声明（历史响应）时才进入 §2 的双解释推断分支，且推断标准与显式声明
   路径一致严格（FR-015）。
