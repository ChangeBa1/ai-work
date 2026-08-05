# Quickstart / 验证指南: 应用感知增强插件框架

**Feature**: `024-app-perception-plugins` | **Date**: 2026-07-28

本文件是**验证与运行指南**，不含实现代码。实现步骤见 `tasks.md`。

---

## 0. 前置条件

- 仓库根：`ai-visual-testing-research/`，Python 工程在 `vnc_agent/`（uv 管理，Python 3.12）。
- 无新增依赖：全部能力基于既有的 pydantic / PyYAML / OpenCV / RapidOCR。
- 参考契约：[`contracts/app-perception-plugin-contract.md`](./contracts/app-perception-plugin-contract.md)；
  数据结构见 [`data-model.md`](./data-model.md)。

---

## 1. 离线验证（不需要 VNC，CI 可跑）

```bash
cd vnc_agent

# 1.1 扩展点与档案：schema 校验、注册表、重名/非法档案报错
uv run pytest tests/unit/test_app_perception_profile.py -q

# 1.2 检测：锚点 -> 矩形 -> 合理性校验 -> 置信度；确定性与异常吸收
uv run pytest tests/unit/test_app_perception_detection.py -q

# 1.3 激活判定：13 个原因码全覆盖；未声明 => 零 detect() 调用
uv run pytest tests/unit/test_app_perception_activation.py -q

# 1.4 用例声明：加载期校验（未注册名/白名单越界/none 等价省略）
uv run pytest tests/unit/test_app_perception_declaration.py -q

# 1.5 几何：AnchorConstraint 关系、坐标空间投影、ROI 边缘带
uv run pytest tests/unit/test_app_perception_geometry.py -q

# 1.6 坐标还原回归（既有覆盖 + 本 feature 的组合用例）
uv run pytest tests/unit/test_coordinate_space.py -q
```

**期望**：全部通过。1.3 中"未声明 ⇒ 零 detect() 调用"是 SC-002 的判定层保证，用 mock 调用计数断言。

---

## 2. 端到端场景验证（离线 e2e，脚本化 Grounder + FakeVNC）

```bash
uv run pytest tests/e2e/test_scenario_23_app_perception_enhancement.py -q
```

该场景在**同一张 fixture 截图**上跑四组步骤（素材来自 spec 附录对目标用例的标注）：

| 组 | 步骤形态 | 声明 | 期望 |
|---|---|---|---|
| 1 | 点击子窗口内的小按钮 | `perception_scope: <plugin>` | `activated=true`；点击坐标**逐像素**等于手算的 `round(bbox/scale)+crop_offset`（SC-001） |
| 2 | 点击子窗口内的输入框 | `perception_scope: <plugin>` | 同上；`scale_factor` 落在配置区间内 |
| 3 | 点击**主画面**空白处 | 省略 | `activated=false`、`reason_code="not_declared"`、`detect()` 调用数为 0、Grounding 请求与基线**逐字节相同**（SC-002） |
| 4 | 声明了但画面上没有该窗口 | `perception_scope: <plugin>` | `fallback` 模式：回退全帧 + `declared_but_undetected=true`（FR-013a） |

同时断言：
- 本 run 的 **Grounder 调用总次数**与关闭本 feature 时相同（SC-004）；
- 每个 Grounding 迭代都有一条审计记录（SC-006）；
- 激活迭代的放大图产物文件存在于 run 的 artifact 目录。

---

## 3. 跨场景（Constitution VI）验证

```bash
uv run pytest tests/fixtures/test_cross_scenario_coverage.py -q
uv run pytest tests/unit/test_domain_agnostic_core.py -q
```

- 前者：两个**互不相关**的 GUI 场景档案（窗口结构、锚点词汇完全无关）跑同一套核心，
  各自正确检测/激活/还原坐标，且互不干扰。
- 后者：对 `src/vnc_agent/` 做业务禁词扫描，**零命中**（SC-005）。

> 若禁词扫描命中，说明有业务语义漏进了核心——这是本 feature 的**不合格条件**，必须把该词
> 移回 `profiles/app_perception/*.yaml` 档案或测试 fixture。

---

## 4. 回滚验证（SC-007 / FR-026）

```bash
# 全量套件（app_perception.enabled 默认 false）
uv run pytest -q
```

**期望**：既有全部 unit / fixtures / e2e 保持通过，产物集合与基线一致。

手工确认回滚语句：在 `config/agent.yaml` 中

```yaml
app_perception:
  enabled: false      # 一行回滚：全链路零开销、零审计，行为与本 feature 之前逐字节一致
```

---

## 5. 在真实环境上启用（部署侧操作指南）

1. **写档案**：在 `vnc_agent/profiles/app_perception/` 下新建 `<name>.yaml`，按
   [契约 §B](./contracts/app-perception-plugin-contract.md) 填写。锚点选择务必遵守 README 指南
   （优先 ASCII/数字/汉字；分布在窗口上/中/下部；避开会变化的文本）。
2. **开开关**：

   ```yaml
   app_perception:
     enabled: true
     allowed_plugins:
       <target_id>: ["<name>"]      # 省略该 target ⇒ 允许全部已注册档案
   ```

3. **标注用例**：只给**确实要在该子窗口内点击**的步骤加一行

   ```yaml
   perception_scope: <name>
   ```

   其余步骤**什么都不用写**——默认不激活即是安全缺省。
   参考 spec 附录：目标用例 13 个步骤中只有 2 个需要声明。

4. **验证一次真实 run**，然后在 HTML/JSON 报告里检查每个相关迭代的
   `perception_enhancement` 块：`activated`、`roi`、`detection_confidence`、`scale_factor`。

---

## 6. 排障对照表

| 现象 | 看什么 | 常见原因 |
|---|---|---|
| 步骤没有被增强 | `reason_code` | `not_declared`（忘了写声明，最常见）/ `disabled`（没开开关）/ `plugin_not_allowed`（target 允许列表没包含） |
| 声明了却总是回退 | `declared_but_undetected` + `matched_anchors` | 锚点在当前画面 OCR 不出来（字号太小 / 假名被读花 / 窗口被遮挡）；或窗口此刻本就不该可见 |
| 检测到但不激活 | `reason_code` | `roi_not_subwindow`（矩形被锚点拉太大，检查 `padding_ratio` 与锚点选择）/ `scale_not_beneficial`（窗口本来就很大） |
| 激活了但仍点错 | `scope_hint_mismatch` + `constraint_violations` | 声明写在了错误的步骤上（目标其实在窗口外）；或档案矩形切掉了目标（检查 `padding_ratio`） |
| 报告里没有该块 | 全局开关 | `enabled=false` ⇒ 按设计不产生任何记录 |

---

## 7. 已知边界（不在本 feature 范围）

- **不改动 feature 014** 的 zoom 请求提示坐标空间（该处 `ocr_candidates` 为原帧坐标而图像为放大图，
  属于独立跟进项，见 plan.md Risks R5）。
- **不把放大图用于 `visual_question` / `describe_screen`**：那条路径受 feature 018 降采样
  （默认 `max_width=1024`）约束，会抵消放大收益。本 feature 只作用于 Grounding。
- **不做窗口边框像素检测 / 网格扫描**：MVP 只用 OCR 锚点几何（research.md R-4）。
