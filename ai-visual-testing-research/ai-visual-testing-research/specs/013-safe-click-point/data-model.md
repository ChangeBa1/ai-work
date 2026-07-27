# Data Model: 安全点击点计算（safe-click-point）

**Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## 实体

### SafeClickPoint（新增，`planning/click_point.py`）

| 字段 | 类型 | 语义 |
|---|---|---|
| `x` | int | 点击点横坐标（原图像素） |
| `y` | int | 点击点纵坐标（原图像素） |
| `residual_overlap` | bool | True = 返回点仍落在至少一个（相交、非退化的）sibling bbox 内，即选择的是重叠深度最小的点（FR-005） |

`typing.NamedTuple`，不可变。消费方：`ActionPolicy`（取 `x`/`y` 填
`ExecutableAction.coordinates`）、单测（断言全部三个字段）。

### 函数契约

```text
safe_click_point(
    bbox: tuple[int, int, int, int],          # (x1, y1, x2, y2)，x1≤x2、y1≤y2
    *,
    siblings: Sequence[tuple[int, int, int, int]] = (),
    screen_resolution: tuple[int, int] | None = None,   # (width, height)
    edge_inset_ratio: float = 0.15,           # 0 ≤ ratio < 0.5
) -> SafeClickPoint
```

不变量（对应 spec FR）：

1. 纯函数：无 I/O、无随机、无全局状态；同输入同输出（FR-001）。
2. 返回点 ∈ 安全区（每轴内缩后非空时）∈ bbox；退化轴取中心坐标（FR-002/003/012）。
3. 无相交 sibling 时返回中心（网格含中心，中心 overlap=0 且距离 0 最小）（FR-002）。
4. 存在零重叠网格点时 `residual_overlap=False` 且返回点不含于任何 sibling（FR-004）。
5. 无零重叠点时返回 `overlap_depth` 最小的网格点且 `residual_overlap=True`（FR-005）。
6. `screen_resolution=(w,h)` 时返回点 ∈ `[0,w-1]×[0,h-1]`；None 时不 clamp（FR-006）。

## 算法（规范性）

```text
1. cx, cy = (x1+x2)//2, (y1+y2)//2                        # 几何中心（与旧实现同式）
2. w, h = x2-x1, y2-y1
   inset_x, inset_y = round(w*ratio), round(h*ratio)
   sx1, sx2 = x1+inset_x, x2-inset_x                      # x 轴安全区
   sy1, sy2 = y1+inset_y, y2-inset_y                      # y 轴安全区
   若 sx1 > sx2：x 轴退化 → sx1 = sx2 = cx；y 轴同理      # FR-003 退化
3. active = [s for s in siblings
             if s 非退化(s.x1<s.x2 且 s.y1<s.y2) 且 s 与 bbox 相交(闭区间)]
4. xs = 每轴等距采样：linspace(sx1, sx2, 9) 取整去重升序（必含 cx? —— cx 由
   round 网格保证被包含：采样含区间中点；实现上显式并入 clamp 到安全区内的 cx）
   ys 同理；candidates = xs × ys
5. 对每个候选点 p：
   contains(p, s) := s.x1 ≤ p.x ≤ s.x2 且 s.y1 ≤ p.y ≤ s.y2
   esc(p, s)      := min(p.x-s.x1+1, s.x2-p.x+1, p.y-s.y1+1, s.y2-p.y+1)
   overlap(p)     := Σ_{s∈active, contains(p,s)} esc(p, s)
   key(p)         := (overlap(p), (p.x-cx)²+(p.y-cy)², p.y, p.x)
6. best = min(candidates, key=key)                        # 全序，确定性
7. 若 screen_resolution 提供：best 各轴 clamp 到 [0, w-1] / [0, h-1]
8. return SafeClickPoint(best.x, best.y, overlap(best) > 0)
```

注：`residual_overlap` 以 clamp 前的网格点重叠判定（clamp 只在贴屏边时移动点，属执行
安全底线，不改变"是否避开了 sibling"的语义判定；测试覆盖此点）。

## 配置模型（`config.py` 新增）

```text
class ClickConfig(BaseModel):
    edge_inset_ratio: float = Field(default=0.15, ge=0.0, lt=0.5)

class AgentConfig(BaseModel):
    ...
    click: ClickConfig = Field(default_factory=ClickConfig)
```

`config/agent.yaml`：

```yaml
click:
  edge_inset_ratio: 0.15
```

## 接线点状态变化（`planning/action_policy.py`）

| 位置 | 旧 | 新 |
|---|---|---|
| `_unique_ocr_or_template` 三处 return | `((b[0]+b[2])//2, (b[1]+b[3])//2, b)` | `safe_click_point(b, siblings=其余命中 bbox, screen_resolution=screen.resolution, edge_inset_ratio=self.click_edge_inset_ratio)` → `(pt.x, pt.y, b)` |
| `_executable_from_candidate` | `cx, cy = cand.center()` | `pt = safe_click_point(cand.bbox, siblings=[c.bbox for c in in_bounds if c is not cand], screen_resolution=resolution, ...)`；新增 `resolution` 形参由 `_from_grounding` 传入 |
| `ActionPolicy.__init__` | — | 新增 `click_edge_inset_ratio: float = 0.15` |
| `target_region` | 原始 bbox | 不变（FR-009） |

siblings 语义（spec C-007）：OCR/模板路径 = 该函数已计算的其他命中 bbox（被选中者除外，
含 OCR 与模板两个列表）；Grounding 路径 = in_bounds 中未被选中的候选 bbox。命中判定
分支、置信度分类、候选选择逻辑逐字不变（feature 012 边界）。
