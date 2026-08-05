# Phase 0 Research: 应用感知增强插件框架

**Feature**: `024-app-perception-plugins` | **Date**: 2026-07-28

所有结论均来自对本仓库现有代码的直接勘察，标注了文件与行号以便复核。

---

## R-1 接线点：增强应插在哪一层

**Decision**: 插在 `runtime/agent_runtime.py` 的 `if policy_result.needs_grounding:` 分支**最内层
`else:` 的开头**——即 014 zoom / 023 postmortem / 015 memory 三条捷径都没命中、确定要真的调用
Grounder 的那一支，紧邻 `GroundingRequest` 构造之前。

**Rationale**: 该分支的现状优先级链（`agent_runtime.py` 约 1450–1600 行）是：

1. `zoom_plan = self.recovery.take_zoom_request()` → `zoom_obs`（014）；
2. `if zoom_obs is None: correction = take_postmortem_correction()`（023）；
3. `if ... zoom_obs is None and postmortem_executable is None: memory.lookup(...)`（015）；
4. `else:` → 构造 `GroundingRequest` 并 `await self.grounder.ground(...)`。

把增强放在第 4 支开头，天然获得三条性质：(a) FR-020 的优先级链不需要任何显式判断；
(b) FR-021"不叠加"由结构保证——`zoom_obs` 非空时代码根本走不到这里；(c) 不影响任何不调用 Grounder
的迭代，未激活时零开销。

**Alternatives considered**:
- *在 `ObservationPipeline.observe()` 里增强*：会改变整个系统看到的 `StructuredScreen`，波及验证、
  记忆、变化检测、报告——违反"只改送 Grounder 的图像"的最小侵入原则，且无法按步骤开关。否决。
- *像 014 那样做成"旗标 + 下一迭代消费"*：会多花一个迭代（消耗 Tier-1 预算），而前置增强的全部
  价值恰恰是"不用先失败一次"。否决。

---

## R-2 观察原语：是否需要新的裁剪/放大实现

**Decision**: 完全复用 `perception/pipeline.py::ObservationPipeline.observe_zoom(roi, scale_factor,
step_id, capture_source)`，不写任何新的像素代码。

**Rationale**: 该方法（feature 014 FR-003 实现）已经覆盖全部需求：
- 通过共享 `FrameCaptureService` 做 ROI 抓屏，ROI 帧按正常采集契约进入 `TestRun.frames`；
- 驱动返回全屏时在内存裁剪同一 ROI（语义等价）；
- `cv2.resize(..., INTER_CUBIC)` 放大；
- 对放大图重新 OCR，并把 OCR bbox 还原为原帧坐标；
- 遮罩/私有持久化按既有规则落盘；
- **每一种失败路径都 `return None`**——正是本 feature 要求的 fail-open 语义。

唯一需要的改动是**增量字段**：`ZoomObservation` 追加 `ocr_items_zoom_space`（见 R-5）。

**Alternatives considered**: 另写一个 `observe_subwindow()` —— 会产生两套裁剪/遮罩/落盘语义，
是坐标错误最容易滋生的地方，且违反用户明确要求的"复用 014 语义"。否决。

---

## R-3 坐标还原：是否需要新的还原规则

**Decision**: 零改动复用。`GroundingRequest` 已有 `crop_offset` / `scale_factor` / `resolution` /
`original_resolution` 四个字段（014 FR-004 引入），`models/coordinate_space.py::restore_original_bbox`
已实现 `round(v/scale_factor) + crop_offset` 与严格拒绝（`scale<=0` / 退化 / 越界 ⇒ None，
绝不 clamp）。`resolve_pixel_bbox` 在**放大图分辨率**下先做 pixel/normalized_1000 空间解析，
顺序即 014 决策 3。

**Rationale**: 本 feature 与 014 送给 Grounder 的请求形状完全同构，差别只在 ROI 的来源和触发时机。
共用同一条还原链路是坐标正确性的唯一保障，也让 `test_coordinate_space.py` 的既有覆盖直接生效。

**ROI 入界**: 复用 `recovery/zoom.py::expand_region` 的 **viewing-window** 语义（平移/收缩入界 +
最小尺寸；无合法窗口返回 None）。注释里已写明"ROI 是观察窗口，平移/收缩合法，与点击坐标的严格
不 clamp 语义无关"——本 feature 沿用同一边界，不得混淆。

---

## R-4 检测手段：OCR 锚点 vs 边框检测 vs 模板匹配

**Decision**: MVP 主路径 = **必需锚点文本集合（OCR）+ 并集外扩 + 几何合理性校验**；模板匹配作为
档案可选的补充证据通道；不做边框/连通域像素检测。

**Rationale**:
- **零额外开销**：`StructuredScreen.ocr_items` 是本迭代**已有**的观察结果，检测只做字符串归一化匹配
  和常数级几何运算，未激活时不产生任何抓屏/OCR/像素操作——这对 Constitution 的弱配置约束是决定性的。
- **确定性 + 离线可测**：同帧同档案必得同结果，可在固定 fixture 上 100% 单测。
- **不依赖绝对坐标**：矩形由锚点位置推导，窗口移动/改变大小都能跟随。
- **真实证据支持**：证据截图中该子窗口内有多个稳定的 ASCII 锚点（标题、字段标签、复选框文案、
  状态栏文案），彼此分布在窗口的上/中/下部，并集 + 小幅外扩即可覆盖整窗。

**Alternatives considered**:
- *边框/连通域像素检测*：能给出更精确的窗口边界，但需要额外像素运算、对主题/配色敏感、阈值难以
  在不同应用间通用，且失败模式难以离线复现。留作未来档案可选的 `border_refine` 扩展。
- *纯模板匹配定位标题栏*：需要为每个窗口维护模板图片资产，对分辨率/DPI 变化脆弱；作为**可选**
  补充证据保留（`screen.template_matches` 通道已存在），不作为主路径。
- *让模型自己框出窗口*：违反 Principle I（确定性）与成本原则——多一次模型调用去决定要不要省一次
  模型调用。否决。

---

## R-5 提示候选的坐标空间一致性

**Decision**: 给 `ZoomObservation` **追加** `ocr_items_zoom_space: list[OCRItem]`（放大图坐标系的
原始 OCR 项，即还原前的值），024 的增强请求用它作为 `ocr_candidates`；`template_candidates` /
`ui_index_candidates` 在增强路径上省略，除非能投影进 ROI（memory 提示走投影，投影失败则丢弃并记审计）。
**014 的调用点一行不改。**

**Rationale**: 现状（`agent_runtime.py` ~1564–1574）把 `zoom_obs.ocr_items`（已还原为**原帧坐标**）
与**放大图**一起下发给 Grounder，属于图像与提示坐标系不一致。对本 feature 这是必须解决的正确性问题
（FR-017）；但直接改 `observe_zoom` 的返回语义会改变 014 的下发负载，触发 014 的 e2e 与审计身份变化，
超出本 feature 范围。追加字段是唯一能"024 正确 + 014 逐字节不变"的做法。

**Follow-up**: 014 的同类不一致建议单独立项修正（本 feature 的 Risks R5）。

---

## R-6 与 feature 018（模型图像降采样）的相互作用

**Decision**: 无冲突，放大分辨率能完整送达 Grounder。

**Rationale**: 018 的 FR-003 只把 `HttpPlannerClient.describe_screen()` 的图像走降采样助手
（默认 `max_width=1024`），FR-004 明确要求 `MimoGrounderClient` 的图像负载**保持原始文件字节
byte-identical** 且不得改动。因此增强产生的高分辨率放大图在 Grounding 路径上不会被再次缩小。

**推论（写入 quickstart 提示）**: 如果将来把放大图也用于 `visual_question`/`describe_screen`，
会被降到 1024 宽而抵消放大收益——本 feature 明确**不**改动验证路径的图像来源。

---

## R-7 成本量级与闸门

**Decision**: 双闸门——每步至多 1 次激活（可配置）+ 放大图总像素硬上限（默认 4.0 MP，用于再次夹紧倍率）。

**Rationale**（基于真实证据的定量估算）:

| 项 | 值 |
|---|---|
| 全屏帧 | 1024×768 = 0.79 MP |
| 子窗口 ROI | ≈420×615 = 0.26 MP |
| 目标长边 1600 ⇒ scale | ≈2.6 |
| 放大图 | ≈1092×1600 ≈ 1.75 MP（≈2.2× 全屏 OCR 的像素量） |

一次激活 = 1 次 ROI 抓屏（比全屏抓屏更便宜）+ 1 次约 2.2× 全屏量的 OCR + **0 次**额外模型调用。
若无像素上限，一个 200×150 的小窗口在 `max_scale=4` 下只有 0.48 MP（安全），但一个 800×600 的窗口
在同样倍率下会到 7.7 MP —— 故需要像素硬顶把倍率再夹一次。

**Alternatives considered**: 按 014 的固定 2.0 倍率 —— 对很小的窗口放大不足、对很大的窗口浪费；
自适应 + 双夹紧在两端都可控。

---

## R-8 激活来源：显式声明（用户 2026-07-28 裁决，已定案）

**Decision**: **默认不激活。唯一的激活来源是 `TestStep.perception_scope` 的显式声明。**
系统不做基于 `step.intent` 的自然语言推断，也不把"画面上检测到了某窗口"当作激活理由——
检测只是声明成立后的**前置条件**。

**Rationale**（用户裁决 + 本次勘察支持该裁决的证据）:
- **假阳性被结构性消除**。前置增强的失败模式（把 Grounder 视野裁到窗口内而目标在窗口外）会导致
  不可撤销的误点击；把激活权交给用例作者，等于把这个风险从"运行期启发式"移到"可评审、可 diff、
  可回归"的用例文本里。
- **缺省天然安全**。未声明 ⇒ 与关闭本 feature 逐字节一致，因此"画面上有子窗口但本步不操作它"的
  场景不需要任何排除逻辑——目标用例里 13 个步骤有 11 个属于这一类（见 spec 附录），
  让它们零成本保持现状远比让它们逐一"被推断排除"可靠。
- **意图文本确实不可靠**（本次勘察的直接证据）：目标用例的 `return-to-pos-click-blank` 与
  `start-cash-for-remainder` 两步，intent 里都**同时**出现了子窗口与主画面的对象名（前者写
  "不要点 ScannerSimulator 窗口内任何位置"，后者写"不要点击或操作模拟器窗口"）。任何基于
  intent 关键词的推断都会在这里踩雷——否定式表述里的窗口名与肯定式表述里的窗口名，
  在词袋层面无法区分。
- **`target.nearby_texts` 也不足以独立支撑激活**：它是 Planner 每轮生成的，措辞会随重试变化
  （用例里甚至明确要求"重试时换措辞"），把激活挂在它上面等于让激活行为随模型输出漂移，
  违反 Principle I 的确定性要求。

**降级保留**: 文本线索归属仍然计算，但只作为**只读警示** `scope_hint_mismatch` 写入审计
（线索命中项落在检测矩形外或跨内外），永不改变激活结论。它的价值是复盘时一眼看出"这一步的声明
写错了"，而不是替作者做决定。

**Alternatives considered（均已被裁决否决）**:
- *显式声明优先 + 无声明时保守推断*：存量用例零改动即可受益，但保留了一条隐式激活路径，
  与"默认不激活"的安全模型相冲突。否决。
- *以检测置信度为主驱动*：直接踩中假阳性方向。否决。

---

## R-11 "声明了但画面上找不到该窗口"：回退还是失败

**Decision**: 配置项 `on_declared_window_missing: fallback | fail`，**默认 `fallback`**（回退全帧 +
强制 `declared_but_undetected` 审计）。

**Rationale**:
1. **架构层面**：判定步骤成败的唯一依据必须是操作后独立采集的证据（Constitution IV + 验证独立性
   门禁）。让感知层的一个提示直接判失败，等于在 Verifier 之外新增失败裁决者；同时与 FR-022
   "不新增 FailureType / 不新增失败路径"冲突。
2. **有真实反例**：目标用例的 `select-scanner-simulator` 步骤，其目的**就是**把子窗口切到前台——
   步骤开始时窗口只是任务视图里的小缩略图，档案锚点（小字标签）在那个尺度上 OCR 读不出来。
   `fail` 模式会恰好在最需要帮助的步骤上把用例打死。
3. **时序**：步骤内多次迭代是正常的（等待窗口渲染、上一步动作生效延迟）；首轮检测不到不代表步骤错。
4. **诊断性无损**：`fallback` 下每轮强制写审计，报告可聚合成"步骤 X 声明了范围 Y，N 次迭代 0 次检测到"
   ——信息量比一次硬失败更大。

**`fail` 的保留理由**：当团队把"子窗口存在"视为步骤的前置不变量、希望尽早失败而不是让 Grounder
在全帧上瞎猜时，可在部署配置里打开。实现代价仅为一个枚举分支。

**Alternatives considered**: 只做 `fallback` 不留开关 —— 剥夺了严格团队的选择，且加一个枚举分支的
成本极低。否决。

---

## R-9 插件的交付形态：代码类 vs 声明式档案

**Decision**: 主形态 = **声明式 YAML 档案**（数据），由核心的通用 `DeclarativeSubWindowPlugin` 消费；
保留程序化注册的代码插件通道供特殊场景，但本 feature 不交付任何代码插件实现。

**Rationale**: Constitution VI 明确允许"通过通用接口注册的可选场景 profile"，并禁止业务语义进入核心。
档案化把"这个窗口长什么样"完全变成数据：核心目录禁词扫描可以硬性零命中（SC-005），新增被测应用
零代码改动（US3），删除档案即自动退回全帧路径。仓库已有同构先例——`TestCase.action_tags` /
`RunPrecondition` 都是"核心只定义通用容器、具体 key 由用例声明"。

**Alternatives considered**: 入口点式（entry_points）动态发现第三方包 —— MVP 阶段引入分发复杂度、
且与"单进程模块化单体 + 内部注册表"的架构约束（Constitution 工程约束）不符。否决。

---

## R-10 配置位置与开关默认值

**Decision**: 顶层新增 `app_perception:` 段 → `AgentConfig.app_perception`；`enabled` **首版默认 false**。

**Rationale**:
- 顶层段而非 `perception.*` 嵌套：`PerceptionConfig` 已承载 OCR/模板/视觉/缓存/022 阈值等多组无关键，
  再塞入十余个键会变得难以阅读；`recovery.zoom_reground` 那样的"嵌在别的段里再抽取"是为兼容既有
  `recovery` 字典结构的权宜，本 feature 没有这个约束。
- 默认 false：本 feature 的假阳性代价是不可撤销的误点击（Risks R1）。默认关闭 ⇒ 老部署零风险升级，
  开启是部署侧的显式决策；也让 SC-007（既有测试套件全绿）天然成立，不需要在每个 legacy 测试里打桩。
  （e2e conftest 仍显式钉 false，防止将来默认翻转时静默影响 legacy 场景 —— 022/023 的既有做法。）

**Alternatives considered**: 默认 true + 靠"无允许插件"来实际停用 —— 两个开关语义重叠，
回滚语句变成"删配置"，不如一个布尔清晰。否决。

**命名**: 按 target 的列表叫 `allowed_plugins`（允许列表）而非 `enabled_plugins`（启用列表）——
用户裁决后"启用"的语义已经归属于用例的 `perception_scope` 声明，配置侧只负责"这台机器上允许用哪些"。
target 未在映射中出现 ⇒ 允许全部已注册插件；显式空列表 ⇒ 该 target 完全停用。
