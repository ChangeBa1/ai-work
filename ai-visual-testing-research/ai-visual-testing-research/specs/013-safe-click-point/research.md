# Phase 0 Research: 安全点击点计算（safe-click-point）

**Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)

Technical Context 无 NEEDS CLARIFICATION;以下为关键设计决策及备选评估。

## D1. 点选择算法:固定网格 + 全序排序 vs 解析几何求解

- **Decision**: 在安全区上取固定等距整数网格（每轴 ≤ 9 采样点，含中心与端点），按
  `(重叠深度, 到中心距离², y, x)` 全序取最小。
- **Rationale**: 解析法（对 sibling 矩形做布尔剪裁求最优点）实现复杂、边界情况多
  （多矩形并集补集）；网格法代码 ~30 行、O(81 × |siblings|) 微秒级、天然确定性、
  行为易于用测试穷举验证。网格含中心点保证"无干扰时返回中心"精确成立。
- **Alternatives considered**:
  - 矩形剪裁解析解——精确但复杂度高、易错，收益（亚像素精度）对点击无意义；
  - 随机采样/退火——违反确定性硬约束（Constitution I），直接排除；
  - 只测 4 个象限点——粒度太粗，紧贴场景下可行点可能全部漏掉。

## D2. 重叠深度度量

- **Decision**: 点 p 对包含它的 sibling s 的逃逸距离
  `esc(p,s) = min(p.x-s.x1+1, s.x2-p.x+1, p.y-s.y1+1, s.y2-p.y+1)`，
  `overlap_depth(p) = Σ esc(p, s)`（仅对包含 p 的 s 求和；不含 p 的贡献 0）。
- **Rationale**: 逃逸距离即"把点推出该矩形所需的最小位移"，是"重叠深度"的直接几何
  语义；求和使"落在 2 个 sibling 里"劣于"落在 1 个里"。整数算术、确定性。
- **Alternatives considered**: 用 IoU / 覆盖面积——是区域度量而非点度量，无法给点排序；
  用到 sibling 中心的距离——与"推出重叠区"语义不符。

## D3. 「避开 OCR 文字外溢区域」的降级（spec C-002 / FR-011）

- **Decision**: 不单独实现文字外溢区估计,由 sibling 重叠规避规则覆盖。
- **Rationale**: 外溢区估计需要字形度量（字号、基线、溢出方向），`OCRItem` 仅有
  bbox/text/confidence;凭 bbox 猜测外溢方向是不确定性的启发式，违反确定性约束且
  实现代价大。外溢文字在感知层就是"相邻的其他 OCR 命中 bbox"，作为 siblings 传入
  即获得等价规避。
- **Alternatives considered**: 按文本长度×估计字宽外扩 bbox——引入两个拍脑袋常数,
  无证据校准，收益不明,拒绝。

## D4. 返回值形态

- **Decision**: `SafeClickPoint(NamedTuple)`：`x: int`、`y: int`、
  `residual_overlap: bool`。
- **Rationale**: 调用方只需 `(pt.x, pt.y)`；`residual_overlap` 满足 FR-005 的"伴随
  元数据标注"且不改变 `ExecutableAction` 契约（无新字段，审计可后续接入）。NamedTuple
  不可变、可哈希、repr 友好，符合纯函数气质。
- **Alternatives considered**: 给 `ExecutableAction` 加字段——扩散契约、触碰
  `domain/action.py` 之外的验证/报告消费方，超出边界；返回裸 `(x, y)` + 日志——纯函数
  禁 I/O。

## D5. 配置段与透传路径

- **Decision**: `agent.yaml` 新增顶层 `click: {edge_inset_ratio: 0.15}`;
  `config.py` 新增 `ClickConfig`（校验 `0 ≤ ratio < 0.5`）挂到 `AgentConfig.click`；
  `ActionPolicy.__init__(click_edge_inset_ratio=0.15)`。
- **Rationale**: 该比例同时作用于 OCR/模板与 Grounding 两条路径，归 `grounding` 段
  语义不符;默认值三处一致（yaml/ClickConfig/ActionPolicy），`runtime/` 禁改期间行为
  无偏差（spec C-004）。
- **Alternatives considered**: 放 `planning` 段——`planning` 现有键都是"信不信/让不让"
  策略阈值，点击几何单列更清晰；放 `grounding` 段——OCR 路径也用，不合适。

## D6. clamp 语义

- **Decision**: 仅在调用方提供 `screen_resolution` 时 clamp 到 `[0,w-1]×[0,h-1]`；
  两处调用点均传 `screen.resolution`。纯函数不默认任何分辨率。
- **Rationale**: OCR bbox 偶见轻微越界（fixture 中存在），clamp 是执行安全底线；
  policy 层永远有 `screen.resolution` 可传，纯函数保持无环境假设。
