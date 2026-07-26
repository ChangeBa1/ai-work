# Quickstart: 安全点击点计算（safe-click-point）

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Data model**: [data-model.md](./data-model.md)

## 前置条件

```powershell
cd vnc_agent
uv sync
```

## 功能验证（本 feature 新增测试）

```powershell
# 纯函数：中心命中、内缩、退化、sibling 推开、最小重叠、clamp、确定性
uv run pytest tests/unit/test_click_point.py -q

# 配置：click.edge_inset_ratio 默认值 0.15 与取值校验 [0, 0.5)
uv run pytest tests/unit/test_config_click.py -q

# 策略接线：coordinates 落在安全区、target_region 保持原始 bbox、跨场景一致
uv run pytest tests/unit/test_action_policy_click_point.py -q
```

## 回归验证（既有套件必须全绿）

```powershell
uv run pytest tests/unit tests/fixtures -q
uv run pytest tests/e2e -q
```

## 手工快速验证（REPL）

```powershell
uv run python -c "
from vnc_agent.planning.click_point import safe_click_point
# 无干扰 → 中心
print(safe_click_point((100, 80, 200, 120)))
# 右侧紧贴 sibling → 点被推向左半安全区，residual_overlap=False
print(safe_click_point((100, 80, 200, 120), siblings=[(180, 80, 260, 120)]))
# sibling 覆盖整个 bbox → 最小重叠深度点，residual_overlap=True
print(safe_click_point((100, 80, 200, 120), siblings=[(90, 70, 210, 130)]))
# 贴屏边 + clamp
print(safe_click_point((790, 590, 810, 610), screen_resolution=(800, 600)))
"
```

预期：第 1 行 `(150, 100, False)`；第 2 行 x < 180 且在 `[115, 185]` 安全区内、
False;第 3 行在安全区内且 True；第 4 行坐标 ≤ (799, 599)。

## 预期观测点

- `ExecutableAction.coordinates`：唯一 OCR/模板命中与 grounding 候选路径均为安全点；
- `ExecutableAction.target_region`：仍等于命中/候选的原始 bbox（验证与审计不受影响）；
- 同一 fixture 重跑，coordinates 完全一致（回放一致性）。
